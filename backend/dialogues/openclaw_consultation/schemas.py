"""Strict, versioned schemas for External Self-Consultation v1.

A requesting agent may ask an ISOLATED fresh model session a bounded question
and receive advice. The advice is candidate material, never authority. Every
record here is hash-bound and fails closed on anything unexpected.

Three versioned artifacts:
  openclaw_external_consultation_request_v1   what was asked, and under what limits
  openclaw_external_consultation_result_v1    the strict per-mode structured advice
  openclaw_external_consultation_receipt_v1   tamper-evident binding of the two

No secrets, no keys, no hidden reasoning, no tool access, no nested calls.
Deterministic and offline; the only side effect a caller may add is one
provider request, performed by the service, never here.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

# ── versions ─────────────────────────────────────────────────────────────────

REQUEST_VERSION = "openclaw_external_consultation_request_v1"
RESULT_VERSION = "openclaw_external_consultation_result_v1"
RECEIPT_VERSION = "openclaw_external_consultation_receipt_v1"

# ── bounded limits (v1 non-negotiable ceilings) ──────────────────────────────

MAX_QUESTION_CHARS = 8000
MAX_DRAFT_CHARS = 16000
MAX_CANDIDATE_CHARS = 16000
MAX_PURPOSE_CHARS = 500
MAX_EVIDENCE_REFERENCES = 16
MAX_EVIDENCE_REF_CHARS = 256
MAX_TOKENS_CEILING = 4096
MAX_TIMEOUT_SECONDS = 300.0
CONSULTATION_DEPTH = 1

MODES = ("critic", "independent_solver", "judge")
RELATIONS = ("same_model_new_session", "peer_model")

# ── enums for strict payload validation ──────────────────────────────────────

_SEVERITIES = ("critical", "major", "minor")
_VERDICTS = ("candidate_a", "candidate_b", "tie", "insufficient_evidence")

# ── shared validation primitives ─────────────────────────────────────────────

_AGENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
#: request_id is turned into a filesystem name, so it must be a strict,
#: path-separator-free identifier (no "/", "\\", ":", and never "." or "..").
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{6,}",
        re.IGNORECASE,
    ),
)
#: phrases an advisory model must not use to fake authority/tool use.
_AUTHORITY_PATTERNS = (
    re.compile(r"\bI (?:have )?(?:executed|ran|called|invoked)\b", re.IGNORECASE),
    re.compile(r"\btool[_-]?call\b", re.IGNORECASE),
    re.compile(r"\bI approve\b", re.IGNORECASE),
    re.compile(r"\bI have (?:updated|written|saved|committed)\b", re.IGNORECASE),
)


class ConsultationError(ValueError):
    """Any consultation validation/policy/parse failure (fails closed)."""


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ConsultationError("consultation data must be finite JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(value: Any, *, field: str, maximum: int,
               allow_authority: bool = True) -> str:
    if not isinstance(value, str):
        raise ConsultationError(f"{field} must be a string")
    text = value.strip()
    if not text:
        raise ConsultationError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ConsultationError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ConsultationError(f"{field} contains control characters")
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        raise ConsultationError(f"{field} contains secret-shaped data")
    if not allow_authority and any(
            pattern.search(text) for pattern in _AUTHORITY_PATTERNS):
        raise ConsultationError(f"{field} contains an authority/tool-use claim")
    return text


def clean_agent(value: Any, *, field: str = "requesting_agent_id") -> str:
    text = clean_text(value, field=field, maximum=128)
    if not _AGENT_RE.fullmatch(text):
        raise ConsultationError(f"{field} contains unsupported characters")
    return text


def clean_id(value: Any, *, field: str) -> str:
    text = clean_text(value, field=field, maximum=256)
    if not _SAFE_RE.fullmatch(text):
        raise ConsultationError(f"{field} contains unsupported characters")
    return text


def clean_request_id(value: Any, *, field: str = "request_id") -> str:
    """A request_id becomes a filesystem name, so it must be a strict,
    path-separator-free identifier. Rejects "/", "\\", ":", any traversal
    sequence, and the bare "." / ".." ids. Never trust it as a filename even
    after this - the store additionally hashes it and contains the path."""
    text = clean_text(value, field=field, maximum=128)
    if text in (".", ".."):
        raise ConsultationError(f"{field} may not be '.' or '..'")
    if not _REQUEST_ID_RE.fullmatch(text):
        raise ConsultationError(
            f"{field} must be a filename-safe id (ASCII letters, digits, dot, "
            "underscore, hyphen; no path separators or drive/stream markers)")
    return text


def clean_hex64(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HEX64_RE.fullmatch(text):
        raise ConsultationError(f"{field} must be lowercase SHA-256")
    return text


def iso_utc(value: str) -> _dt.datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime so ordering is
    correct across mixed Z/offset notations. Any parser failure (impossible
    month/day/hour, bad offset, overflow) is re-raised as ConsultationError so
    callers that catch ConsultationError still fail closed."""
    try:
        parsed = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OverflowError, TypeError) as exc:
        raise ConsultationError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def clean_iso(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not _ISO_RE.fullmatch(text):
        raise ConsultationError(f"{field} must be an ISO-8601 timestamp")
    # Format is necessary but not sufficient: reject semantically-impossible
    # dates (month 13, day 30 in Feb, hour 25, bad offset) as ConsultationError.
    try:
        iso_utc(text)
    except ConsultationError as exc:
        raise ConsultationError(
            f"{field} is not a valid timestamp: {text!r}") from exc
    return text


def finite_number(value: Any, *, field: str, minimum: float,
                  maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConsultationError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ConsultationError(
            f"{field} must be finite and within [{minimum}, {maximum}]")
    return number


def positive_int(value: Any, *, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConsultationError(f"{field} must be a positive integer")
    if value > maximum:
        raise ConsultationError(f"{field} exceeds {maximum}")
    return value


def _string_tuple(values: Any, *, field: str, maximum_items: int,
                  item_max: int, allow_authority: bool = True) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ConsultationError(f"{field} must be a sequence")
    if len(values) > maximum_items:
        raise ConsultationError(f"{field} exceeds {maximum_items} entries")
    return tuple(clean_text(item, field=f"{field} item", maximum=item_max,
                            allow_authority=allow_authority)
                 for item in values)


def _permutation_pair(values: Any, *, field: str) -> Tuple[int, int]:
    """A judge candidate order: exactly two entries that are a permutation of
    [0, 1]. Strict integer typing (no bool, no float, no str)."""
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ConsultationError(f"{field} must be a sequence")
    items = list(values)
    if len(items) != 2:
        raise ConsultationError(f"{field} must have exactly two entries")
    for item in items:
        if type(item) is not int:
            raise ConsultationError(f"{field} entries must be integers")
    if sorted(items) != [0, 1]:
        raise ConsultationError(f"{field} must be a permutation of [0, 1]")
    return (items[0], items[1])


# ── request ──────────────────────────────────────────────────────────────────

_REQUEST_FIELDS = {
    "schema_version", "request_id", "requesting_agent_id", "mode",
    "consulted_provider", "consulted_model", "consultation_relation",
    "question", "question_sha256", "draft", "candidates", "candidate_order",
    "public_evidence_references", "purpose", "max_tokens", "timeout_seconds",
    "created_at", "expires_at", "consultation_depth", "tools_allowed",
    "request_digest",
}


@dataclass(frozen=True)
class ExternalConsultationRequest:
    request_id: str
    requesting_agent_id: str
    mode: str
    consulted_provider: str
    consulted_model: str
    consultation_relation: str
    question: str
    purpose: str
    max_tokens: int
    timeout_seconds: float
    created_at: str
    expires_at: str
    draft: Optional[str] = None
    candidates: Tuple[str, ...] = ()
    candidate_order: Tuple[int, ...] = ()
    public_evidence_references: Tuple[str, ...] = ()
    consultation_depth: int = CONSULTATION_DEPTH
    tools_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id",
                           clean_request_id(self.request_id, field="request_id"))
        object.__setattr__(self, "requesting_agent_id",
                           clean_agent(self.requesting_agent_id))
        mode = str(self.mode)
        if mode not in MODES:
            raise ConsultationError(f"unknown consultation mode {mode!r}")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "consulted_provider",
                           clean_id(self.consulted_provider,
                                    field="consulted_provider"))
        object.__setattr__(self, "consulted_model",
                           clean_id(self.consulted_model,
                                    field="consulted_model"))
        relation = str(self.consultation_relation)
        if relation not in RELATIONS:
            raise ConsultationError(f"unknown consultation relation {relation!r}")
        object.__setattr__(self, "consultation_relation", relation)
        object.__setattr__(self, "question",
                           clean_text(self.question, field="question",
                                      maximum=MAX_QUESTION_CHARS))
        object.__setattr__(self, "purpose",
                           clean_text(self.purpose, field="purpose",
                                      maximum=MAX_PURPOSE_CHARS))

        # depth and tools are hard invariants, not preferences. Strict typing:
        # bool/float/str/Decimal that merely equal 1 are rejected.
        if type(self.consultation_depth) is not int or \
                self.consultation_depth != CONSULTATION_DEPTH:
            raise ConsultationError(
                "consultation_depth must be exactly the integer 1 in v1")
        if self.tools_allowed is not False:
            raise ConsultationError("tools_allowed must be false in v1")

        object.__setattr__(self, "max_tokens",
                           positive_int(self.max_tokens, field="max_tokens",
                                        maximum=MAX_TOKENS_CEILING))
        object.__setattr__(self, "timeout_seconds",
                           finite_number(self.timeout_seconds,
                                         field="timeout_seconds",
                                         minimum=0.1, maximum=MAX_TIMEOUT_SECONDS))
        object.__setattr__(self, "created_at",
                           clean_iso(self.created_at, field="created_at"))
        object.__setattr__(self, "expires_at",
                           clean_iso(self.expires_at, field="expires_at"))
        if iso_utc(self.expires_at) <= iso_utc(self.created_at):
            raise ConsultationError("expires_at must be after created_at")

        object.__setattr__(self, "public_evidence_references",
                           _string_tuple(self.public_evidence_references,
                                         field="public_evidence_references",
                                         maximum_items=MAX_EVIDENCE_REFERENCES,
                                         item_max=MAX_EVIDENCE_REF_CHARS))

        # mode-specific draft/candidates invariants.
        draft = self.draft
        candidates = tuple(self.candidates or ())
        if self.mode == "critic":
            if draft is None:
                raise ConsultationError("critic mode requires a draft")
            if candidates:
                raise ConsultationError("critic mode forbids candidates")
        elif self.mode == "independent_solver":
            if draft is not None:
                raise ConsultationError("independent_solver forbids a draft")
            if candidates:
                raise ConsultationError("independent_solver forbids candidates")
        else:  # judge
            if draft is not None:
                raise ConsultationError("judge mode forbids a draft")
            if len(candidates) != 2:
                raise ConsultationError(
                    "judge mode requires exactly two candidates")
        if draft is not None:
            draft = clean_text(draft, field="draft", maximum=MAX_DRAFT_CHARS)
        object.__setattr__(self, "draft", draft)
        object.__setattr__(self, "candidates", tuple(
            clean_text(item, field="candidate", maximum=MAX_CANDIDATE_CHARS)
            for item in candidates))

        # candidate_order: bound into the request (and thus the digest) so the
        # judge prompt is fully determined by the canonical request. Only judge
        # may carry it; it defaults to [0, 1] when omitted so it is always
        # concrete. critic/independent_solver must not carry it.
        order = tuple(self.candidate_order or ())
        if self.mode == "judge":
            if not order:
                order = (0, 1)
            order = _permutation_pair(order, field="candidate_order")
        elif order:
            raise ConsultationError(
                f"{self.mode} mode forbids candidate_order")
        object.__setattr__(self, "candidate_order", order)

    @property
    def question_sha256(self) -> str:
        return sha256_text(self.question)

    def _unsigned(self) -> Dict[str, Any]:
        return {
            "schema_version": REQUEST_VERSION,
            "request_id": self.request_id,
            "requesting_agent_id": self.requesting_agent_id,
            "mode": self.mode,
            "consulted_provider": self.consulted_provider,
            "consulted_model": self.consulted_model,
            "consultation_relation": self.consultation_relation,
            "question": self.question,
            "question_sha256": self.question_sha256,
            "draft": self.draft,
            "candidates": list(self.candidates),
            "candidate_order": list(self.candidate_order),
            "public_evidence_references": list(self.public_evidence_references),
            "purpose": self.purpose,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "consultation_depth": self.consultation_depth,
            "tools_allowed": self.tools_allowed,
        }

    @property
    def request_digest(self) -> str:
        return digest(self._unsigned())

    def to_record(self) -> Dict[str, Any]:
        record = self._unsigned()
        record["request_digest"] = self.request_digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]
                    ) -> "ExternalConsultationRequest":
        if not isinstance(record, Mapping) or set(record) != _REQUEST_FIELDS:
            raise ConsultationError(
                "consultation request contains missing or unknown fields")
        if record.get("schema_version") != REQUEST_VERSION:
            raise ConsultationError("unknown consultation request schema version")
        request = cls(
            request_id=record["request_id"],
            requesting_agent_id=record["requesting_agent_id"],
            mode=record["mode"],
            consulted_provider=record["consulted_provider"],
            consulted_model=record["consulted_model"],
            consultation_relation=record["consultation_relation"],
            question=record["question"],
            purpose=record["purpose"],
            max_tokens=record["max_tokens"],
            timeout_seconds=record["timeout_seconds"],
            created_at=record["created_at"],
            expires_at=record["expires_at"],
            draft=record["draft"],
            candidates=tuple(record["candidates"] or ()),
            candidate_order=tuple(record["candidate_order"] or ()),
            public_evidence_references=tuple(
                record["public_evidence_references"] or ()),
            consultation_depth=record["consultation_depth"],
            tools_allowed=record["tools_allowed"],
        )
        if record["question_sha256"] != request.question_sha256:
            raise ConsultationError("consultation question hash mismatch")
        if record["request_digest"] != request.request_digest:
            raise ConsultationError("consultation request digest mismatch")
        return request


# ── result ───────────────────────────────────────────────────────────────────

_RESULT_FIELDS = {
    "schema_version", "request_id", "request_digest", "mode", "provider",
    "model", "provider_status", "isolated_session", "tools_disabled",
    "delegation_disabled", "structured_payload", "response_digest",
}


@dataclass(frozen=True)
class ConsultationResult:
    request_id: str
    request_digest: str
    mode: str
    provider: str
    model: str
    provider_status: str
    structured_payload: Dict[str, Any]
    isolated_session: bool = True
    tools_disabled: bool = True
    delegation_disabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id",
                           clean_request_id(self.request_id, field="request_id"))
        object.__setattr__(self, "request_digest",
                           clean_hex64(self.request_digest,
                                       field="request_digest"))
        if self.mode not in MODES:
            raise ConsultationError(f"unknown consultation mode {self.mode!r}")
        object.__setattr__(self, "provider",
                           clean_id(self.provider, field="provider"))
        object.__setattr__(self, "model", clean_id(self.model, field="model"))
        object.__setattr__(self, "provider_status",
                           clean_text(self.provider_status,
                                      field="provider_status", maximum=32))
        if self.provider_status != "ok":
            raise ConsultationError(
                "a result may only be built from an OK provider status")
        for flag, name in ((self.isolated_session, "isolated_session"),
                           (self.tools_disabled, "tools_disabled"),
                           (self.delegation_disabled, "delegation_disabled")):
            if flag is not True:
                raise ConsultationError(f"{name} must be true")
        payload = validate_payload(self.mode, self.structured_payload)
        object.__setattr__(self, "structured_payload", payload)

    def _unsigned(self) -> Dict[str, Any]:
        return {
            "schema_version": RESULT_VERSION,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "provider_status": self.provider_status,
            "isolated_session": self.isolated_session,
            "tools_disabled": self.tools_disabled,
            "delegation_disabled": self.delegation_disabled,
            "structured_payload": self.structured_payload,
        }

    @property
    def response_digest(self) -> str:
        return digest(self._unsigned())

    def to_record(self) -> Dict[str, Any]:
        record = self._unsigned()
        record["response_digest"] = self.response_digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ConsultationResult":
        if not isinstance(record, Mapping) or set(record) != _RESULT_FIELDS:
            raise ConsultationError(
                "consultation result contains missing or unknown fields")
        if record.get("schema_version") != RESULT_VERSION:
            raise ConsultationError("unknown consultation result schema version")
        result = cls(
            request_id=record["request_id"],
            request_digest=record["request_digest"],
            mode=record["mode"],
            provider=record["provider"],
            model=record["model"],
            provider_status=record["provider_status"],
            structured_payload=dict(record["structured_payload"]),
            isolated_session=record["isolated_session"],
            tools_disabled=record["tools_disabled"],
            delegation_disabled=record["delegation_disabled"],
        )
        if record["response_digest"] != result.response_digest:
            raise ConsultationError("consultation result digest mismatch")
        return result


# ── per-mode payload validation (never trust provider JSON) ──────────────────

def _issue(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, Mapping) or set(entry) != {
            "severity", "category", "description", "affected_claim",
            "suggested_check"}:
        raise ConsultationError("critic issue has missing or unknown fields")
    severity = str(entry["severity"])
    if severity not in _SEVERITIES:
        raise ConsultationError(f"unknown issue severity {severity!r}")
    return {
        "severity": severity,
        "category": clean_text(entry["category"], field="issue category",
                               maximum=64, allow_authority=False),
        "description": clean_text(entry["description"], field="issue description",
                                  maximum=1000, allow_authority=False),
        "affected_claim": clean_text(entry["affected_claim"],
                                     field="issue affected_claim", maximum=1000,
                                     allow_authority=False),
        "suggested_check": clean_text(entry["suggested_check"],
                                      field="issue suggested_check", maximum=500,
                                      allow_authority=False),
    }


def _bounded_list(values: Any, *, field: str, maximum_items: int = 12,
                  item_max: int = 1000) -> list:
    # Payload free-text lists are advice; they may never carry an authority or
    # tool-use claim, so authority-checking is always on here.
    return list(_string_tuple(values, field=field, maximum_items=maximum_items,
                              item_max=item_max, allow_authority=False))


def validate_payload(mode: str, payload: Any) -> Dict[str, Any]:
    """Strict, exact per-mode validation of the advisory JSON. Fails closed."""
    if not isinstance(payload, Mapping):
        raise ConsultationError("structured_payload must be an object")

    if mode == "critic":
        if set(payload) != {"issues", "strengths", "missing_assumptions",
                            "recommended_checks"}:
            raise ConsultationError("critic payload has missing or unknown fields")
        issues = payload["issues"]
        if isinstance(issues, (str, bytes)) or not isinstance(issues, Sequence):
            raise ConsultationError("critic issues must be a sequence")
        if len(issues) > 12:
            raise ConsultationError("critic issues exceed 12 entries")
        return {
            "issues": [_issue(entry) for entry in issues],
            "strengths": _bounded_list(payload["strengths"], field="strengths"),
            "missing_assumptions": _bounded_list(
                payload["missing_assumptions"], field="missing_assumptions"),
            "recommended_checks": _bounded_list(
                payload["recommended_checks"], field="recommended_checks"),
        }

    if mode == "independent_solver":
        if set(payload) != {"independent_answer", "assumptions", "uncertainties",
                            "recommended_verifications"}:
            raise ConsultationError(
                "independent_solver payload has missing or unknown fields")
        return {
            "independent_answer": clean_text(
                payload["independent_answer"], field="independent_answer",
                maximum=8000, allow_authority=False),
            "assumptions": _bounded_list(payload["assumptions"],
                                         field="assumptions"),
            "uncertainties": _bounded_list(payload["uncertainties"],
                                           field="uncertainties"),
            "recommended_verifications": _bounded_list(
                payload["recommended_verifications"],
                field="recommended_verifications"),
        }

    # judge
    if set(payload) != {"verdict", "criterion_scores", "rationale",
                        "critical_difference"}:
        raise ConsultationError("judge payload has missing or unknown fields")
    verdict = str(payload["verdict"])
    if verdict not in _VERDICTS:
        raise ConsultationError(f"unknown judge verdict {verdict!r}")
    scores = payload["criterion_scores"]
    if not isinstance(scores, Mapping) or not scores or len(scores) > 12:
        raise ConsultationError("judge criterion_scores must be 1-12 entries")
    clean_scores = {}
    for key, value in scores.items():
        criterion = clean_text(key, field="criterion", maximum=64,
                               allow_authority=False)
        clean_scores[criterion] = finite_number(
            value, field=f"criterion_scores[{criterion}]",
            minimum=0.0, maximum=10.0)
    return {
        "verdict": verdict,
        "criterion_scores": clean_scores,
        "rationale": clean_text(payload["rationale"], field="rationale",
                                maximum=4000, allow_authority=False),
        "critical_difference": clean_text(
            payload["critical_difference"], field="critical_difference",
            maximum=2000, allow_authority=False),
    }


__all__ = [
    "REQUEST_VERSION", "RESULT_VERSION", "RECEIPT_VERSION",
    "MODES", "RELATIONS", "CONSULTATION_DEPTH",
    "MAX_QUESTION_CHARS", "MAX_DRAFT_CHARS", "MAX_CANDIDATE_CHARS",
    "MAX_EVIDENCE_REFERENCES", "MAX_TOKENS_CEILING", "MAX_TIMEOUT_SECONDS",
    "ConsultationError", "ExternalConsultationRequest", "ConsultationResult",
    "canonical_json", "digest", "sha256_text", "validate_payload",
    "clean_iso", "iso_utc", "clean_request_id",
]
