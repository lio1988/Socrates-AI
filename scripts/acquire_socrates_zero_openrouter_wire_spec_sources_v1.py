"""One-shot bounded acquisition of frozen OpenRouter wire-spec sources v1.

This script is intentionally inert on import.  When explicitly invoked, it
consumes only the six-source plan frozen in ``openrouter_wire_spec_source_v1``.
It performs direct, unauthenticated HTTPS GETs with the Python standard library,
retains deterministic exact source slices plus canonical extracts, and publishes
one write-once retrieval log.  It has no provider, model, credential,
environment, adapter, parser, tool, or CED integration.

The extractor records absent required anchors instead of substituting nearby
content.  Ambiguous headings, malformed source structure, unresolved OpenAPI
references, unexpected media, redirects outside the frozen origin, and all
resource-bound breaches fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import ssl
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional, Sequence, Tuple
from urllib.parse import unquote, urljoin, urlsplit

if __package__ in (None, ""):
    _repository_root = Path(__file__).resolve().parents[1]
    if str(_repository_root) not in sys.path:
        sys.path.insert(0, str(_repository_root))

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1,
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
    OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1,
    OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1,
    OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1,
    OpenRouterWireExtractFormatV1,
    OpenRouterWireRedirectHopV1,
    OpenRouterWireRedirectOutcomeV1,
    OpenRouterWireRetainedSourceSnapshotV1,
    OpenRouterWireRetrievalErrorCodeV1,
    OpenRouterWireRetrievalEventV1,
    OpenRouterWireRetrievalLogV1,
    OpenRouterWireRetrievalStatusV1,
    OpenRouterWireSourcePlanRecordV1,
    build_openrouter_wire_retained_source_snapshot_v1,
    canonicalize_openrouter_wire_extract_v1,
    render_openrouter_wire_source_plan_v1,
    sha256_bytes_v1,
)


_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CONTENT_TYPE_PATTERN = re.compile(
    r"^[a-z0-9!#$&^_.+\-]+/[a-z0-9!#$&^_.+\-]+$"
)
_ATX_HEADING_PATTERN = re.compile(
    r"^(?P<marks>#{1,6})[ \t]+(?P<title>.*?)[ \t]*#*[ \t]*(?:\r?\n|\r|$)"
)
_HTML_MAIN_START_PATTERN = re.compile(r"<main(?:\s[^>]*)?>", re.IGNORECASE)
_HTML_MAIN_END_PATTERN = re.compile(r"</main\s*>", re.IGNORECASE)
_HTML_HEADING_PATTERN = re.compile(
    r"<h(?P<level>[1-6])(?:\s[^>]*)?>.*?</h(?P=level)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_YAML_MAPPING_KEY_PATTERN = re.compile(
    r"^(?P<indent> *)(?P<key>\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*'|[^:#][^:]*?):[ \t]*(?:#.*)?(?:\r?\n|\r|$)"
)
_YAML_REF_PATTERN = re.compile(
    r"^[ \t]*\$ref[ \t]*:[ \t]*(?:\"([^\"]+)\"|'([^']+)'|(\#[^ \t\r\n]+|[^ \t#\r\n]+))",
    re.MULTILINE,
)
_ERROR_CODE_SANITIZER = re.compile(r"[^A-Z0-9_]+")


class _AcquisitionFailure(Exception):
    def __init__(
        self,
        status: OpenRouterWireRetrievalStatusV1,
        error_code: str | OpenRouterWireRetrievalErrorCodeV1,
        *,
        redirect_chain: Tuple[OpenRouterWireRedirectHopV1, ...] = (),
        http_status: Optional[int] = None,
        final_resolved_locator: Optional[str] = None,
        raw_content_type_header: Optional[str] = None,
        media_type: Optional[str] = None,
        response_content_bytes: Optional[int] = None,
        response_bytes_received: int = 0,
    ) -> None:
        canonical_error = _canonical_error_enum(status, error_code)
        super().__init__(canonical_error.value)
        self.status = status
        self.error_code = canonical_error
        self.redirect_chain = redirect_chain
        self.http_status = http_status
        self.final_resolved_locator = final_resolved_locator
        self.raw_content_type_header = raw_content_type_header
        self.media_type = media_type
        self.response_content_bytes = response_content_bytes
        self.response_bytes_received = response_bytes_received


@dataclass(frozen=True)
class _ExtractionResult:
    raw_source_ranges: Tuple[Tuple[int, int], ...]
    relevant_anchors: Tuple[str, ...]


@dataclass(frozen=True)
class _FetchedDocument:
    final_locator: str
    redirect_chain: Tuple[OpenRouterWireRedirectHopV1, ...]
    status: int
    raw_content_type_header: str
    media_type: str
    response_body: bytes


@dataclass(frozen=True)
class _RetainedBundle:
    snapshot: OpenRouterWireRetainedSourceSnapshotV1
    raw_path: Path
    raw_bytes: bytes
    canonical_path: Path
    canonical_bytes: bytes
    snapshot_path: Path
    snapshot_bytes: bytes

    @property
    def retained_byte_length(self) -> int:
        return len(self.raw_bytes) + len(self.canonical_bytes) + len(
            self.snapshot_bytes
        )


@dataclass
class _ResourceBudget:
    response_bytes: int
    retained_bytes: int
    aggregate_deadline: float


@dataclass(frozen=True)
class _YamlEntry:
    key: str
    start: int
    end: int
    indent: int


class _VisibleTextParser(HTMLParser):
    _SKIPPED_TAGS = frozenset(
        {"script", "style", "noscript", "nav", "navigation", "analytics"}
    )
    _BREAK_TAGS = frozenset(
        {
            "address",
            "article",
            "aside",
            "blockquote",
            "br",
            "dd",
            "div",
            "dl",
            "dt",
            "figcaption",
            "figure",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "hr",
            "li",
            "main",
            "ol",
            "p",
            "pre",
            "section",
            "table",
            "td",
            "th",
            "tr",
            "ul",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, Optional[str]]]
    ) -> None:
        del attrs
        lowered = tag.lower()
        if lowered in self._SKIPPED_TAGS:
            self._skip_depth += 1
        elif self._skip_depth == 0 and lowered in self._BREAK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self._SKIPPED_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
        elif self._skip_depth == 0 and lowered in self._BREAK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def _canonical_error_code(value: str) -> str:
    normalized = _ERROR_CODE_SANITIZER.sub("_", value.upper()).strip("_")
    return normalized[:160] or "UNSPECIFIED_ACQUISITION_FAILURE"


def _canonical_error_enum(
    status: OpenRouterWireRetrievalStatusV1,
    value: str | OpenRouterWireRetrievalErrorCodeV1,
) -> OpenRouterWireRetrievalErrorCodeV1:
    if isinstance(value, OpenRouterWireRetrievalErrorCodeV1):
        return value
    token = _canonical_error_code(value)
    if status is OpenRouterWireRetrievalStatusV1.FETCH_FAILED:
        if "TIMEOUT" in token or "DEADLINE" in token:
            return OpenRouterWireRetrievalErrorCodeV1.TIMEOUT
        if "SSL" in token or "TLS" in token:
            return OpenRouterWireRetrievalErrorCodeV1.TLS_ERROR
        return OpenRouterWireRetrievalErrorCodeV1.NETWORK_ERROR
    if status is OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED:
        return OpenRouterWireRetrievalErrorCodeV1.REDIRECT_POLICY_REJECTED
    if status is OpenRouterWireRetrievalStatusV1.STATUS_REJECTED:
        return OpenRouterWireRetrievalErrorCodeV1.HTTP_STATUS_REJECTED
    if status is OpenRouterWireRetrievalStatusV1.MEDIA_TYPE_REJECTED:
        return OpenRouterWireRetrievalErrorCodeV1.MEDIA_TYPE_REJECTED
    if status is OpenRouterWireRetrievalStatusV1.SIZE_REJECTED:
        if "TOTAL" in token or "AGGREGATE" in token:
            return OpenRouterWireRetrievalErrorCodeV1.TOTAL_SIZE_REJECTED
        return OpenRouterWireRetrievalErrorCodeV1.SOURCE_SIZE_REJECTED
    if "UTF8" in token or "UTF_8" in token or "NUL" in token:
        return OpenRouterWireRetrievalErrorCodeV1.STRICT_UTF8_REJECTED
    if "CANONICAL" in token:
        return OpenRouterWireRetrievalErrorCodeV1.CANONICALIZATION_FAILED
    return OpenRouterWireRetrievalErrorCodeV1.REQUIRED_EXTRACTION_FAILED


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _render_contract(value: object) -> bytes:
    model_dump = getattr(value, "model_dump")
    return (canonical_json(model_dump(mode="json")) + "\n").encode("utf-8")


def _within_root(repository_root: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ContractValidationError("output path is not a safe repository-relative path")
    destination = repository_root.joinpath(*relative.parts)
    resolved_root = repository_root.resolve(strict=True)
    resolved_parent = destination.parent.resolve(strict=False)
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise ContractValidationError("output path escapes the repository root")
    current = resolved_root
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ContractValidationError("output path traverses a symbolic link")
    return destination


def _write_once(destination: Path, payload: bytes) -> None:
    if type(payload) is not bytes or not payload:
        raise ContractValidationError("write-once payload must be non-empty bytes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        handle.write(payload)
        handle.flush()


def _normalize_base_content_type(value: Optional[str]) -> str:
    if value is None or "," in value:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.MEDIA_TYPE_REJECTED,
            "MISSING_OR_AMBIGUOUS_CONTENT_TYPE",
        )
    base = value.split(";", 1)[0].strip().lower()
    if not _CONTENT_TYPE_PATTERN.fullmatch(base):
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.MEDIA_TYPE_REJECTED,
            "INVALID_CONTENT_TYPE",
        )
    return base


def _validate_same_origin_redirect(origin: str, current: str, location: str) -> str:
    candidate = urljoin(current, location)
    origin_parts = urlsplit(origin)
    candidate_parts = urlsplit(candidate)
    if (
        candidate_parts.scheme != "https"
        or candidate_parts.hostname != origin_parts.hostname
        or candidate_parts.port not in (None, 443)
        or candidate_parts.username is not None
        or candidate_parts.password is not None
        or candidate_parts.query
        or candidate_parts.fragment
        or not candidate_parts.path.startswith("/")
    ):
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED,
            "REDIRECT_NOT_SAME_ORIGIN_CANONICAL_HTTPS",
        )
    return candidate


def _ssl_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    return context


def _bounded_response_body(
    response: http.client.HTTPResponse,
    *,
    budget: _ResourceBudget,
    source_bytes_before_response: int,
    source_deadline: float,
) -> bytes:
    policy = FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1
    declared_length = response.getheader("Content-Length")
    if declared_length is not None:
        try:
            parsed_length = int(declared_length, 10)
        except ValueError as exc:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                "INVALID_CONTENT_LENGTH",
            ) from exc
        if parsed_length < 0:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                "NEGATIVE_CONTENT_LENGTH",
            )
        if source_bytes_before_response + parsed_length > policy.maximum_response_bytes_per_source:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                "DECLARED_SOURCE_RESPONSE_SIZE_LIMIT_EXCEEDED",
            )
        if budget.response_bytes + parsed_length > policy.maximum_total_response_bytes:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                "DECLARED_TOTAL_RESPONSE_SIZE_LIMIT_EXCEEDED",
            )
    chunks: list[bytes] = []
    observed = 0
    while True:
        now = time.monotonic()
        if now > source_deadline or now > budget.aggregate_deadline:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                "RETRIEVAL_TIME_LIMIT_EXCEEDED",
            )
        source_remaining = (
            policy.maximum_response_bytes_per_source
            - source_bytes_before_response
            - observed
        )
        total_remaining = policy.maximum_total_response_bytes - budget.response_bytes
        read_size = min(65_536, max(1, min(source_remaining, total_remaining) + 1))
        chunk = response.read(read_size)
        if not chunk:
            break
        observed += len(chunk)
        budget.response_bytes += len(chunk)
        chunks.append(chunk)
        if source_bytes_before_response + observed > policy.maximum_response_bytes_per_source:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                "OBSERVED_SOURCE_RESPONSE_SIZE_LIMIT_EXCEEDED",
                response_bytes_received=observed,
            )
        if budget.response_bytes > policy.maximum_total_response_bytes:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                "OBSERVED_TOTAL_RESPONSE_SIZE_LIMIT_EXCEEDED",
                response_bytes_received=observed,
            )
    return b"".join(chunks)


def _fetch_one(
    record: OpenRouterWireSourcePlanRecordV1,
    budget: _ResourceBudget,
) -> _FetchedDocument:
    policy = FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1
    source_deadline = min(
        time.monotonic() + policy.retrieval_timeout_seconds,
        budget.aggregate_deadline,
    )
    origin = record.canonical_public_locator
    current = origin
    redirect_chain: list[OpenRouterWireRedirectHopV1] = []
    source_response_bytes = 0
    while True:
        if time.monotonic() >= source_deadline:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                "SOURCE_DEADLINE_EXPIRED_BEFORE_REQUEST",
            )
        parsed = urlsplit(current)
        remaining = max(0.001, source_deadline - time.monotonic())
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            port=443,
            timeout=remaining,
            context=_ssl_context(),
        )
        response: Optional[http.client.HTTPResponse] = None
        try:
            accept = ", ".join(record.expected_media_types)
            connection.request(
                "GET",
                parsed.path or "/",
                headers={
                    "Accept": accept,
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                    "User-Agent": "SocratesZero-WireSpecEvidence/1",
                },
            )
            response = connection.getresponse()
            content_encoding = response.getheader("Content-Encoding")
            if content_encoding is not None and content_encoding.strip().lower() not in (
                "",
                "identity",
            ):
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                    "CONTENT_ENCODING_NOT_IDENTITY",
                )
            if response.status in _REDIRECT_STATUSES:
                location = response.getheader("Location")
                if location is None:
                    raise _AcquisitionFailure(
                        OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED,
                        "REDIRECT_LOCATION_MISSING",
                    )
                candidate = urljoin(current, location)
                hop = OpenRouterWireRedirectHopV1(
                    ordinal=len(redirect_chain) + 1,
                    source_locator=current,
                    http_status=response.status,
                    target_locator=candidate,
                )
                if (
                    len(redirect_chain) >= policy.maximum_redirects_per_source
                    or hop.outcome is OpenRouterWireRedirectOutcomeV1.REJECTED_BY_POLICY
                ):
                    # The frozen contract can represent one policy-rejected hop.  A
                    # second otherwise-valid hop is conservatively classified as a
                    # fetch failure rather than fabricating a rejected redirect.
                    if len(redirect_chain) >= policy.maximum_redirects_per_source:
                        raise _AcquisitionFailure(
                            OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                            "REDIRECT_LIMIT_EXCEEDED",
                        )
                    rejected_chain = tuple(redirect_chain + [hop])
                    raise _AcquisitionFailure(
                        OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED,
                        OpenRouterWireRetrievalErrorCodeV1.REDIRECT_POLICY_REJECTED,
                        redirect_chain=rejected_chain,
                        http_status=response.status,
                        final_resolved_locator=current,
                    )
                redirect_chain.append(hop)
                current = candidate
                continue
            if response.status != 200:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.STATUS_REJECTED,
                    OpenRouterWireRetrievalErrorCodeV1.HTTP_STATUS_REJECTED,
                    redirect_chain=tuple(redirect_chain),
                    http_status=response.status,
                    final_resolved_locator=current,
                )
            raw_content_type_header = response.getheader("Content-Type")
            try:
                media_type = _normalize_base_content_type(raw_content_type_header)
            except _AcquisitionFailure as exc:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.MEDIA_TYPE_REJECTED,
                    OpenRouterWireRetrievalErrorCodeV1.MEDIA_TYPE_REJECTED,
                    redirect_chain=tuple(redirect_chain),
                    http_status=response.status,
                    final_resolved_locator=current,
                ) from exc
            if media_type not in record.expected_media_types:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.MEDIA_TYPE_REJECTED,
                    OpenRouterWireRetrievalErrorCodeV1.MEDIA_TYPE_REJECTED,
                    redirect_chain=tuple(redirect_chain),
                    http_status=response.status,
                    final_resolved_locator=current,
                    raw_content_type_header=raw_content_type_header,
                    media_type=media_type,
                )
            try:
                body = _bounded_response_body(
                    response,
                    budget=budget,
                    source_bytes_before_response=source_response_bytes,
                    source_deadline=source_deadline,
                )
            except _AcquisitionFailure as exc:
                if exc.status is OpenRouterWireRetrievalStatusV1.SIZE_REJECTED:
                    raise _AcquisitionFailure(
                        exc.status,
                        exc.error_code,
                        redirect_chain=tuple(redirect_chain),
                        http_status=response.status,
                        final_resolved_locator=current,
                        raw_content_type_header=raw_content_type_header,
                        media_type=media_type,
                        response_bytes_received=exc.response_bytes_received,
                    ) from exc
                raise
            source_response_bytes += len(body)
            return _FetchedDocument(
                final_locator=current,
                redirect_chain=tuple(redirect_chain),
                status=response.status,
                raw_content_type_header=raw_content_type_header,
                media_type=media_type,
                response_body=body,
            )
        except _AcquisitionFailure:
            raise
        except TimeoutError as exc:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                OpenRouterWireRetrievalErrorCodeV1.TIMEOUT,
            ) from exc
        except ssl.SSLError as exc:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                OpenRouterWireRetrievalErrorCodeV1.TLS_ERROR,
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                OpenRouterWireRetrievalErrorCodeV1.NETWORK_ERROR,
            ) from exc
        finally:
            if response is not None:
                response.close()
            connection.close()


def _strict_utf8(raw: bytes, source_kind: str) -> str:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            f"{source_kind}_NOT_STRICT_UTF8",
        ) from exc
    if "\x00" in text:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            f"{source_kind}_CONTAINS_NUL",
        )
    return text



def _char_range_to_byte_range(text: str, start: int, end: int) -> tuple[int, int]:
    if not (0 <= start < end <= len(text)):
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "SOURCE_CHARACTER_RANGE_INVALID",
        )
    return (
        len(text[:start].encode("utf-8")),
        len(text[:end].encode("utf-8")),
    )


def _merge_source_ranges(
    ranges: Iterable[tuple[int, int]],
) -> Tuple[Tuple[int, int], ...]:
    ordered = sorted(set(ranges))
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if start < 0 or end <= start:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "SOURCE_BYTE_RANGE_INVALID",
            )
        if merged and start <= merged[-1][1]:
            prior_start, prior_end = merged[-1]
            merged[-1] = (prior_start, max(prior_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)

def _normalize_visible_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _html_visible_text(value: str) -> str:
    parser = _VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
    except Exception as exc:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "HTML_VISIBLE_TEXT_PARSE_FAILED",
        ) from exc
    return parser.text()


def _section_end(
    headings: Sequence[tuple[int, int, int, str]],
    index: int,
    document_end: int,
) -> int:
    start_level = headings[index][2]
    for later in headings[index + 1 :]:
        if later[2] <= start_level:
            return later[0]
    return document_end


def _extract_markdown(
    body: bytes,
    record: OpenRouterWireSourcePlanRecordV1,
) -> _ExtractionResult:
    text = _strict_utf8(body, "MARKDOWN")
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, int, int, str]] = []
    cursor = 0
    for line in lines:
        match = _ATX_HEADING_PATTERN.match(line)
        if match is not None:
            headings.append(
                (
                    cursor,
                    cursor + len(line),
                    len(match.group("marks")),
                    _normalize_visible_text(match.group("title")),
                )
            )
        cursor += len(line)
    if not headings:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "MARKDOWN_ATX_HEADINGS_NOT_FOUND",
        )
    selected: list[tuple[int, int]] = []
    present: list[str] = []
    for anchor in record.required_anchors:
        matches = [
            index
            for index, heading in enumerate(headings)
            if heading[3] == unicodedata.normalize("NFC", anchor)
        ]
        if len(matches) > 1:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "MARKDOWN_ANCHOR_AMBIGUOUS",
            )
        if len(matches) == 1:
            index = matches[0]
            selected.append(
                (headings[index][0], _section_end(headings, index, len(text)))
            )
            present.append(anchor)
    if not selected:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "MARKDOWN_REQUIRED_ANCHORS_NOT_FOUND",
        )
    slice_start = min(item[0] for item in selected)
    slice_end = max(item[1] for item in selected)
    raw_range = _char_range_to_byte_range(text, slice_start, slice_end)
    canonicalize_openrouter_wire_extract_v1(
        body[raw_range[0] : raw_range[1]],
        OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
    )
    return _ExtractionResult((raw_range,), tuple(present))


def _extract_html(
    body: bytes,
    record: OpenRouterWireSourcePlanRecordV1,
) -> _ExtractionResult:
    text = _strict_utf8(body, "HTML")
    main_starts = list(_HTML_MAIN_START_PATTERN.finditer(text))
    if len(main_starts) != 1:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "HTML_MAIN_NOT_EXACTLY_ONE",
        )
    main_end = _HTML_MAIN_END_PATTERN.search(text, main_starts[0].end())
    if main_end is None:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "HTML_MAIN_END_NOT_FOUND",
        )
    if _HTML_MAIN_END_PATTERN.search(text, main_end.end()) is not None:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "HTML_MAIN_END_AMBIGUOUS",
        )
    main_start_offset = main_starts[0].start()
    main_text = text[main_start_offset : main_end.end()]
    headings: list[tuple[int, int, int, str]] = []
    for match in _HTML_HEADING_PATTERN.finditer(main_text):
        title = _normalize_visible_text(_html_visible_text(match.group(0)))
        headings.append(
            (match.start(), match.end(), int(match.group("level")), title)
        )
    if not headings:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "HTML_HEADINGS_NOT_FOUND_IN_MAIN",
        )
    sections = [
        (
            heading[0],
            _section_end(headings, index, len(main_text)),
            heading[3],
        )
        for index, heading in enumerate(headings)
    ]
    selected: list[tuple[int, int]] = []
    present: list[str] = []
    for anchor in record.required_anchors:
        normalized_anchor = unicodedata.normalize("NFC", anchor)
        exact_heading_matches = [
            section for section in sections if section[2] == normalized_anchor
        ]
        if len(exact_heading_matches) > 1:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "HTML_HEADING_ANCHOR_AMBIGUOUS",
            )
        if len(exact_heading_matches) == 1:
            section = exact_heading_matches[0]
            selected.append((section[0], section[1]))
            present.append(anchor)
            continue
        containing_sections = []
        for section in sections:
            visible = _normalize_visible_text(
                _html_visible_text(main_text[section[0] : section[1]])
            )
            if normalized_anchor in visible:
                containing_sections.append(section)
        if len(containing_sections) > 1:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "HTML_INLINE_ANCHOR_AMBIGUOUS",
            )
        if len(containing_sections) == 1:
            section = containing_sections[0]
            selected.append((section[0], section[1]))
            present.append(anchor)
    if not selected:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "HTML_REQUIRED_ANCHORS_NOT_FOUND",
        )
    slice_start = main_start_offset + min(item[0] for item in selected)
    slice_end = main_start_offset + max(item[1] for item in selected)
    raw_range = _char_range_to_byte_range(text, slice_start, slice_end)
    canonicalize_openrouter_wire_extract_v1(
        body[raw_range[0] : raw_range[1]],
        OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS,
    )
    return _ExtractionResult((raw_range,), tuple(present))


def _yaml_key(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith('"'):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "OPENAPI_QUOTED_KEY_INVALID",
            ) from exc
        if type(parsed) is not str:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "OPENAPI_QUOTED_KEY_NOT_STRING",
            )
        return parsed
    if stripped.startswith("'"):
        return stripped[1:-1].replace("''", "'")
    return stripped


def _line_offsets(text: str) -> tuple[list[str], list[int]]:
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    return lines, offsets


def _yaml_direct_entries(
    lines: Sequence[str],
    offsets: Sequence[int],
    *,
    container_start_line: int,
    container_end_line: int,
    parent_indent: int,
) -> tuple[_YamlEntry, ...]:
    candidates: list[tuple[int, int, str]] = []
    for index in range(container_start_line, container_end_line):
        line = lines[index]
        if "\t" in line[: len(line) - len(line.lstrip(" \t"))]:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "OPENAPI_TAB_INDENTATION_REJECTED",
            )
        match = _YAML_MAPPING_KEY_PATTERN.match(line)
        if match is None:
            continue
        indent = len(match.group("indent"))
        if indent > parent_indent:
            candidates.append((index, indent, _yaml_key(match.group("key"))))
    if not candidates:
        return ()
    direct_indent = min(item[1] for item in candidates)
    direct = [item for item in candidates if item[1] == direct_indent]
    entries: list[_YamlEntry] = []
    for position, (line_index, indent, key) in enumerate(direct):
        end_line = (
            direct[position + 1][0] if position + 1 < len(direct) else container_end_line
        )
        start = offsets[line_index]
        if end_line < len(offsets):
            end = offsets[end_line]
        else:
            end = sum(len(line) for line in lines)
        entries.append(_YamlEntry(key=key, start=start, end=end, indent=indent))
    return tuple(entries)


def _yaml_find_entry(
    entries: Sequence[_YamlEntry], key: str, *, error_prefix: str
) -> Optional[_YamlEntry]:
    matches = [entry for entry in entries if entry.key == key]
    if len(matches) > 1:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            f"{error_prefix}_AMBIGUOUS",
        )
    return matches[0] if matches else None


def _offset_to_line(offsets: Sequence[int], offset: int) -> int:
    low = 0
    high = len(offsets)
    while low + 1 < high:
        middle = (low + high) // 2
        if offsets[middle] <= offset:
            low = middle
        else:
            high = middle
    return low


def _yaml_children(
    text: str,
    lines: Sequence[str],
    offsets: Sequence[int],
    entry: _YamlEntry,
) -> tuple[_YamlEntry, ...]:
    del text
    start_line = _offset_to_line(offsets, entry.start) + 1
    end_line = _offset_to_line(offsets, entry.end)
    if entry.end > offsets[end_line]:
        end_line += 1
    return _yaml_direct_entries(
        lines,
        offsets,
        container_start_line=start_line,
        container_end_line=min(end_line, len(lines)),
        parent_indent=entry.indent,
    )


def _decode_json_pointer_token(value: str) -> str:
    return unquote(value).replace("~1", "/").replace("~0", "~")


def _yaml_internal_refs(block: str) -> tuple[str, ...]:
    refs: list[str] = []
    for match in _YAML_REF_PATTERN.finditer(block):
        value = next(item for item in match.groups() if item is not None)
        if not value.startswith("#/components/"):
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "OPENAPI_NON_COMPONENT_REFERENCE_REJECTED",
            )
        parts = value[2:].split("/")
        if len(parts) != 3 or parts[0] != "components":
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "OPENAPI_COMPONENT_REFERENCE_SHAPE_INVALID",
            )
        canonical = "#/components/{}/{}".format(
            _decode_json_pointer_token(parts[1]),
            _decode_json_pointer_token(parts[2]),
        )
        if canonical not in refs:
            refs.append(canonical)
    return tuple(refs)


def _extract_openapi_yaml(
    body: bytes,
    record: OpenRouterWireSourcePlanRecordV1,
) -> _ExtractionResult:
    text = _strict_utf8(body, "OPENAPI")
    lines, offsets = _line_offsets(text)
    root_entries = _yaml_direct_entries(
        lines,
        offsets,
        container_start_line=0,
        container_end_line=len(lines),
        parent_indent=-1,
    )
    components = _yaml_find_entry(
        root_entries, "components", error_prefix="OPENAPI_COMPONENTS"
    )
    paths = _yaml_find_entry(root_entries, "paths", error_prefix="OPENAPI_PATHS")
    if components is None or paths is None:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "OPENAPI_COMPONENTS_OR_PATHS_NOT_FOUND",
        )
    component_categories = _yaml_children(text, lines, offsets, components)
    schemas = _yaml_find_entry(
        component_categories, "schemas", error_prefix="OPENAPI_SCHEMAS"
    )
    schema_entries = (
        _yaml_children(text, lines, offsets, schemas) if schemas is not None else ()
    )
    path_entries = _yaml_children(text, lines, offsets, paths)
    selected: dict[str, _YamlEntry] = {}
    present: list[str] = []
    for anchor in record.required_anchors:
        if anchor.startswith("/"):
            entry = _yaml_find_entry(
                path_entries, anchor, error_prefix="OPENAPI_CHAT_PATH"
            )
            pointer = f"#/paths/{anchor.replace('~', '~0').replace('/', '~1')}"
        else:
            entry = _yaml_find_entry(
                schema_entries, anchor, error_prefix="OPENAPI_REQUIRED_SCHEMA"
            )
            pointer = f"#/components/schemas/{anchor}"
        if entry is not None:
            selected[pointer] = entry
            present.append(anchor)
    if not selected:
        raise _AcquisitionFailure(
            OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
            "OPENAPI_REQUIRED_ANCHORS_NOT_FOUND",
        )

    category_cache: dict[str, tuple[_YamlEntry, ...]] = {"schemas": schema_entries}

    def resolve_reference(pointer: str) -> _YamlEntry:
        parts = pointer[2:].split("/")
        category = parts[1]
        name = parts[2]
        entries = category_cache.get(category)
        if entries is None:
            category_entry = _yaml_find_entry(
                component_categories,
                category,
                error_prefix="OPENAPI_REFERENCED_COMPONENT_CATEGORY",
            )
            if category_entry is None:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                    "OPENAPI_REFERENCED_COMPONENT_CATEGORY_MISSING",
                )
            entries = _yaml_children(text, lines, offsets, category_entry)
            category_cache[category] = entries
        entry = _yaml_find_entry(
            entries, name, error_prefix="OPENAPI_REFERENCED_COMPONENT"
        )
        if entry is None:
            raise _AcquisitionFailure(
                OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                "OPENAPI_REFERENCED_COMPONENT_MISSING",
            )
        return entry

    pending = sorted(
        {
            ref
            for entry in selected.values()
            for ref in _yaml_internal_refs(text[entry.start : entry.end])
        }
    )
    while pending:
        pointer = pending.pop(0)
        if pointer in selected:
            continue
        entry = resolve_reference(pointer)
        selected[pointer] = entry
        for discovered in _yaml_internal_refs(text[entry.start : entry.end]):
            if discovered not in selected and discovered not in pending:
                pending.append(discovered)
        pending.sort()

    raw_ranges = _merge_source_ranges(
        _char_range_to_byte_range(text, entry.start, entry.end)
        for entry in selected.values()
    )
    for start, end in raw_ranges:
        canonicalize_openrouter_wire_extract_v1(
            body[start:end],
            OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS,
        )
    return _ExtractionResult(raw_ranges, tuple(present))


def _extract_document(
    body: bytes,
    record: OpenRouterWireSourcePlanRecordV1,
) -> _ExtractionResult:
    if record.extract_format is OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS:
        return _extract_openapi_yaml(body, record)
    if record.extract_format is OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS:
        return _extract_markdown(body, record)
    if record.extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        return _extract_html(body, record)
    if record.extract_format is OpenRouterWireExtractFormatV1.JSON:
        canonicalize_openrouter_wire_extract_v1(
            body, OpenRouterWireExtractFormatV1.JSON
        )
        return _ExtractionResult(((0, len(body)),), record.required_anchors)
    raise _AcquisitionFailure(
        OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
        "EXTRACT_FORMAT_NOT_IMPLEMENTED",
    )


def _suffixes(record: OpenRouterWireSourcePlanRecordV1) -> tuple[str, str]:
    if record.extract_format is OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS:
        return ".yaml", ".yaml"
    if record.extract_format is OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS:
        return ".md", ".md"
    if record.extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        return ".html", ".txt"
    return ".json", ".json"


def _build_retained_bundle(
    repository_root: Path,
    record: OpenRouterWireSourcePlanRecordV1,
    fetched: _FetchedDocument,
    extraction: _ExtractionResult,
    retrieved_utc: str,
) -> _RetainedBundle:
    snapshot, retained_raw, canonical_extract = (
        build_openrouter_wire_retained_source_snapshot_v1(
            plan_record=record,
            retrieved_utc=retrieved_utc,
            final_resolved_locator=fetched.final_locator,
            redirect_chain=fetched.redirect_chain,
            raw_content_type_header=fetched.raw_content_type_header,
            response_content=fetched.response_body,
            raw_source_ranges=extraction.raw_source_ranges,
        )
    )
    snapshot_bytes = _render_contract(snapshot)
    snapshot_relative = str(
        PurePosixPath(OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1)
        / record.source_key
        / "snapshot.json"
    )
    return _RetainedBundle(
        snapshot=snapshot,
        raw_path=_within_root(repository_root, snapshot.retained_raw_evidence_path),
        raw_bytes=retained_raw,
        canonical_path=_within_root(
            repository_root, snapshot.retained_canonical_extract_path
        ),
        canonical_bytes=canonical_extract,
        snapshot_path=_within_root(repository_root, snapshot_relative),
        snapshot_bytes=snapshot_bytes,
    )


def _failure_event(
    *,
    sequence: int,
    record: OpenRouterWireSourcePlanRecordV1,
    started_utc: str,
    failure: _AcquisitionFailure,
) -> OpenRouterWireRetrievalEventV1:
    return OpenRouterWireRetrievalEventV1(
        sequence=sequence,
        plan_record_id=record.plan_record_id or "",
        source_key=record.source_key,
        started_utc=started_utc,
        completed_utc=_utc_now(),
        status=failure.status,
        redirect_chain=failure.redirect_chain,
        http_status=failure.http_status,
        final_resolved_locator=failure.final_resolved_locator,
        raw_content_type_header=failure.raw_content_type_header,
        media_type=failure.media_type,
        response_content_bytes=failure.response_content_bytes,
        response_bytes_received=failure.response_bytes_received,
        error_code=failure.error_code,
    )


def _preflight(repository_root: Path) -> None:
    expected_plan = render_openrouter_wire_source_plan_v1()
    plan_path = _within_root(repository_root, OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1)
    if not plan_path.is_file() or plan_path.read_bytes() != expected_plan:
        raise ContractValidationError(
            "persisted source plan is absent or differs from the frozen contract"
        )
    log_path = _within_root(
        repository_root, OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1
    )
    if log_path.exists():
        raise ContractValidationError("write-once retrieval log already exists")
    source_root = _within_root(
        repository_root,
        str(PurePosixPath(OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1) / ".root"),
    ).parent
    if source_root.exists() and any(source_root.iterdir()):
        raise ContractValidationError("retained source directory is not empty")


def acquire_openrouter_wire_spec_sources_v1(
    repository_root: Path,
) -> OpenRouterWireRetrievalLogV1:
    """Run the frozen six-source acquisition exactly once and publish its log."""

    root = repository_root.resolve(strict=True)
    _preflight(root)
    policy = FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1
    budget = _ResourceBudget(
        response_bytes=0,
        retained_bytes=0,
        aggregate_deadline=(
            time.monotonic()
            + policy.retrieval_timeout_seconds
            * policy.maximum_official_document_fetches
        ),
    )
    events: list[OpenRouterWireRetrievalEventV1] = []
    bundles: list[_RetainedBundle] = []

    for sequence, record in enumerate(
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records, start=1
    ):
        started_utc = _utc_now()
        fetched: Optional[_FetchedDocument] = None
        try:
            if time.monotonic() >= budget.aggregate_deadline:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                    OpenRouterWireRetrievalErrorCodeV1.TIMEOUT,
                )
            fetched = _fetch_one(record, budget)
            try:
                extraction = _extract_document(fetched.response_body, record)
            except _AcquisitionFailure as exc:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                    exc.error_code,
                    redirect_chain=fetched.redirect_chain,
                    http_status=fetched.status,
                    final_resolved_locator=fetched.final_locator,
                    raw_content_type_header=fetched.raw_content_type_header,
                    media_type=fetched.media_type,
                    response_content_bytes=len(fetched.response_body),
                    response_bytes_received=len(fetched.response_body),
                ) from exc
            try:
                bundle = _build_retained_bundle(
                    root, record, fetched, extraction, _utc_now()
                )
            except (ContractValidationError, UnicodeError, ValueError) as exc:
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                    OpenRouterWireRetrievalErrorCodeV1.CANONICALIZATION_FAILED,
                    redirect_chain=fetched.redirect_chain,
                    http_status=fetched.status,
                    final_resolved_locator=fetched.final_locator,
                    raw_content_type_header=fetched.raw_content_type_header,
                    media_type=fetched.media_type,
                    response_content_bytes=len(fetched.response_body),
                    response_bytes_received=len(fetched.response_body),
                ) from exc
            if (
                budget.retained_bytes + bundle.retained_byte_length
                > policy.total_retained_evidence_byte_cap
            ):
                raise _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.SIZE_REJECTED,
                    OpenRouterWireRetrievalErrorCodeV1.TOTAL_SIZE_REJECTED,
                    redirect_chain=fetched.redirect_chain,
                    http_status=fetched.status,
                    final_resolved_locator=fetched.final_locator,
                    raw_content_type_header=fetched.raw_content_type_header,
                    media_type=fetched.media_type,
                    response_bytes_received=len(fetched.response_body),
                )
            budget.retained_bytes += bundle.retained_byte_length
            bundles.append(bundle)
            events.append(
                OpenRouterWireRetrievalEventV1(
                    sequence=sequence,
                    plan_record_id=record.plan_record_id or "",
                    source_key=record.source_key,
                    started_utc=started_utc,
                    completed_utc=_utc_now(),
                    status=OpenRouterWireRetrievalStatusV1.RETAINED,
                    redirect_chain=fetched.redirect_chain,
                    http_status=fetched.status,
                    final_resolved_locator=fetched.final_locator,
                    raw_content_type_header=fetched.raw_content_type_header,
                    media_type=fetched.media_type,
                    response_content_bytes=len(fetched.response_body),
                    retained_snapshot_id=bundle.snapshot.snapshot_id,
                    response_bytes_received=len(fetched.response_body),
                )
            )
        except _AcquisitionFailure as failure:
            events.append(
                _failure_event(
                    sequence=sequence,
                    record=record,
                    started_utc=started_utc,
                    failure=failure,
                )
            )
        except (ContractValidationError, UnicodeError, ValueError) as exc:
            if fetched is None:
                failure = _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.FETCH_FAILED,
                    OpenRouterWireRetrievalErrorCodeV1.NETWORK_ERROR,
                )
            else:
                failure = _AcquisitionFailure(
                    OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED,
                    OpenRouterWireRetrievalErrorCodeV1.CANONICALIZATION_FAILED,
                    redirect_chain=fetched.redirect_chain,
                    http_status=fetched.status,
                    final_resolved_locator=fetched.final_locator,
                    raw_content_type_header=fetched.raw_content_type_header,
                    media_type=fetched.media_type,
                    response_content_bytes=len(fetched.response_body),
                    response_bytes_received=len(fetched.response_body),
                )
            events.append(
                _failure_event(
                    sequence=sequence,
                    record=record,
                    started_utc=started_utc,
                    failure=failure,
                )
            )

    snapshots = tuple(bundle.snapshot for bundle in bundles)
    retrieval_log = OpenRouterWireRetrievalLogV1(
        events=tuple(events),
        snapshots=snapshots,
        official_public_document_fetches=len(events),
        official_public_page_inspections=0,
        redirects=sum(len(event.redirect_chain) for event in events),
        failed_documentation_fetches=sum(
            event.status is not OpenRouterWireRetrievalStatusV1.RETAINED
            for event in events
        ),
        official_public_response_bytes_received=sum(
            event.response_bytes_received for event in events
        ),
        retained_raw_source_bytes=sum(
            snapshot.raw_source_byte_length for snapshot in snapshots
        ),
        retained_canonical_extract_bytes=sum(
            snapshot.canonical_extract_byte_length for snapshot in snapshots
        ),
        total_retained_evidence_bytes=sum(
            snapshot.raw_source_byte_length
            + snapshot.canonical_extract_byte_length
            for snapshot in snapshots
        ),
    )
    log_bytes = _render_contract(retrieval_log)
    if budget.retained_bytes + len(log_bytes) > policy.total_retained_evidence_byte_cap:
        raise ContractValidationError(
            "retrieval log would exceed the retained evidence byte cap"
        )

    all_destinations = [
        destination
        for bundle in bundles
        for destination in (
            bundle.raw_path,
            bundle.canonical_path,
            bundle.snapshot_path,
        )
    ]
    log_path = _within_root(root, OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1)
    all_destinations.append(log_path)
    if len(all_destinations) != len(set(all_destinations)):
        raise ContractValidationError("publication destinations are duplicated")
    if any(destination.exists() for destination in all_destinations):
        raise ContractValidationError("write-once publication destination already exists")

    for bundle in bundles:
        _write_once(bundle.raw_path, bundle.raw_bytes)
        _write_once(bundle.canonical_path, bundle.canonical_bytes)
        _write_once(bundle.snapshot_path, bundle.snapshot_bytes)
    _write_once(log_path, log_bytes)
    return retrieval_log


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire the frozen OpenRouter wire-spec source plan exactly once."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing the frozen persisted source plan.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        retrieval_log = acquire_openrouter_wire_spec_sources_v1(args.root)
    except (ContractValidationError, OSError) as exc:
        sys.stderr.write(f"acquisition not published: {type(exc).__name__}\n")
        return 2
    summary = {
        "failed_documentation_fetches": retrieval_log.failed_documentation_fetches,
        "official_public_document_fetches": (
            retrieval_log.official_public_document_fetches
        ),
        "redirects": retrieval_log.redirects,
        "retained_sources": sum(
            event.status is OpenRouterWireRetrievalStatusV1.RETAINED
            for event in retrieval_log.events
        ),
        "retrieval_log_id": retrieval_log.retrieval_log_id,
        "retrieval_log_path": OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1,
        "sources_with_missing_required_anchors": [
            snapshot.source_key
            for snapshot in retrieval_log.snapshots
            if snapshot.missing_required_anchors
        ],
    }
    sys.stdout.write(canonical_json(summary) + "\n")
    return 1 if retrieval_log.failed_documentation_fetches else 0


if __name__ == "__main__":
    raise SystemExit(main())
