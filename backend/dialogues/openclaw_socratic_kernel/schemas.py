"""Strict, versioned schemas for the Micro-Socratic Kernel v1.

A Micro-Socratic Kernel is a small, bounded self-check an agent runs on its own
draft BEFORE finalizing an answer. It identifies the central claim, the required
assumptions, the strongest challenge, what still needs verification, and a single
bounded recommendation. It is advice to the caller, never authority.

Central invariant:

    Every agent may question itself.
    No agent may certify itself.

Three versioned artifacts:
  openclaw_micro_socratic_request_v1   what to audit, and under what limits
  openclaw_micro_socratic_check_v1     the strict per-mode structured findings
  openclaw_micro_socratic_receipt_v1   tamper-evident binding of the two

No secrets, no keys, no hidden chain-of-thought, no tool access, no consultation,
no nested self-questioning. Exactly one provider call happens per request, in the
service - never here. Every record is hash-bound and fails closed.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

# ── versions ─────────────────────────────────────────────────────────────────

REQUEST_VERSION = "openclaw_micro_socratic_request_v1"
CHECK_VERSION = "openclaw_micro_socratic_check_v1"
RECEIPT_VERSION = "openclaw_micro_socratic_receipt_v1"

# ── bounded budgets (v1 non-negotiable ceilings) ─────────────────────────────

MAX_TASK_CHARS = 8000
MAX_DRAFT_CHARS = 16000
MAX_PURPOSE_CHARS = 500
MAX_TOKENS_CEILING = 4096
MAX_TIMEOUT_SECONDS = 300.0

MAX_INNER_ROUNDS = 1            # exactly one structured pass, ever
MAX_ASSUMPTIONS = 5
MAX_CHALLENGES = 3
MAX_MISSING_EVIDENCE = 5
MAX_VERIFICATION_REQUESTS = 3
MAX_UNCERTAINTIES = 5
MAX_REVISION_GUIDANCE = 3      # guidance for the single recommended revision

MODES = ("light", "standard", "high_risk")
DECISIONS = ("accept", "revise", "verify_with_tool",
             "consult_external_model", "insufficient_information")
#: decisions light mode may reach (it carries no verification_requests field).
_LIGHT_DECISIONS = ("accept", "revise", "insufficient_information")

VERIFICATION_KINDS = ("calculator", "web", "time_date", "calendar_read",
                      "external_consultation", "code_test", "source_check",
                      "user_clarification")
#: kinds that count as a deterministic/tool verification for decision coherence.
_TOOL_KINDS = ("calculator", "web", "time_date", "calendar_read",
               "code_test", "source_check")
PRIORITIES = ("required", "recommended", "optional")

# ── shared validation primitives ─────────────────────────────────────────────

_AGENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
#: request_id becomes a filesystem name → strict, path-separator-free identifier.
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
#: phrases a bounded auditor must not use to fake authority, tool use,
#: consultation, or (the kernel's cardinal sin) SELF-CERTIFICATION.
_AUTHORITY_PATTERNS = (
    re.compile(r"\bI (?:have )?(?:executed|ran|called|invoked)\b", re.IGNORECASE),
    re.compile(r"\btool[_-]?call\b", re.IGNORECASE),
    re.compile(r"\bI (?:have )?consulted\b", re.IGNORECASE),
    re.compile(r"\bI approve\b", re.IGNORECASE),
    re.compile(r"\bI have (?:updated|written|saved|committed)\b", re.IGNORECASE),
    re.compile(r"\bcertif(?:y|ied|ies|ication)\b", re.IGNORECASE),
    re.compile(r"\bself[- ]?approv", re.IGNORECASE),
    re.compile(r"\b(?:grant|granted) (?:it|the agent|myself)? ?authority\b",
               re.IGNORECASE),
    re.compile(r"\byou are approved\b", re.IGNORECASE),
    re.compile(r"\bfinal authority\b", re.IGNORECASE),
)


class MicroSocraticError(ValueError):
    """Any kernel validation/policy/parse failure (fails closed)."""


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise MicroSocraticError("kernel data must be finite JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(value: Any, *, field: str, maximum: int,
               allow_authority: bool = True) -> str:
    if not isinstance(value, str):
        raise MicroSocraticError(f"{field} must be a string")
    text = value.strip()
    if not text:
        raise MicroSocraticError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise MicroSocraticError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise MicroSocraticError(f"{field} contains control characters")
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        raise MicroSocraticError(f"{field} contains secret-shaped data")
    if not allow_authority and any(
            pattern.search(text) for pattern in _AUTHORITY_PATTERNS):
        raise MicroSocraticError(
            f"{field} contains an authority/tool/self-certification claim")
    return text


def clean_agent(value: Any, *, field: str = "agent_id") -> str:
    text = clean_text(value, field=field, maximum=128)
    if not _AGENT_RE.fullmatch(text):
        raise MicroSocraticError(f"{field} contains unsupported characters")
    return text


def clean_id(value: Any, *, field: str) -> str:
    text = clean_text(value, field=field, maximum=256)
    if not _SAFE_RE.fullmatch(text):
        raise MicroSocraticError(f"{field} contains unsupported characters")
    return text


def clean_request_id(value: Any, *, field: str = "request_id") -> str:
    """A request_id becomes a filesystem name, so it must be a strict,
    path-separator-free identifier. Rejects "/", "\\", ":", traversal, and the
    bare "." / ".." ids. Never trusted as a filename even after this - the store
    additionally hashes it and contains the path."""
    text = clean_text(value, field=field, maximum=128)
    if text in (".", ".."):
        raise MicroSocraticError(f"{field} may not be '.' or '..'")
    if not _REQUEST_ID_RE.fullmatch(text):
        raise MicroSocraticError(
            f"{field} must be a filename-safe id (ASCII letters, digits, dot, "
            "underscore, hyphen; no path separators or drive/stream markers)")
    return text


def clean_hex64(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HEX64_RE.fullmatch(text):
        raise MicroSocraticError(f"{field} must be lowercase SHA-256")
    return text


def iso_utc(value: str) -> _dt.datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime. Any parser
    failure (impossible month/day/hour, bad offset, overflow) is re-raised as
    MicroSocraticError so callers that catch it still fail closed."""
    try:
        parsed = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OverflowError, TypeError) as exc:
        raise MicroSocraticError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def clean_iso(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not _ISO_RE.fullmatch(text):
        raise MicroSocraticError(f"{field} must be an ISO-8601 timestamp")
    try:
        iso_utc(text)
    except MicroSocraticError as exc:
        raise MicroSocraticError(
            f"{field} is not a valid timestamp: {text!r}") from exc
    return text


def finite_number(value: Any, *, field: str, minimum: float,
                  maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MicroSocraticError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise MicroSocraticError(
            f"{field} must be finite and within [{minimum}, {maximum}]")
    return number


def positive_int(value: Any, *, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise MicroSocraticError(f"{field} must be a positive integer")
    if value > maximum:
        raise MicroSocraticError(f"{field} exceeds {maximum}")
    return value


def _string_list(values: Any, *, field: str, maximum_items: int,
                 item_max: int, allow_authority: bool = False) -> list:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise MicroSocraticError(f"{field} must be a sequence")
    if len(values) > maximum_items:
        raise MicroSocraticError(f"{field} exceeds {maximum_items} entries")
    return [clean_text(item, field=f"{field} item", maximum=item_max,
                       allow_authority=allow_authority)
            for item in values]


# ── request ──────────────────────────────────────────────────────────────────

_REQUEST_FIELDS = {
    "schema_version", "request_id", "agent_id", "mode", "provider", "model",
    "task", "task_sha256", "draft", "draft_sha256", "purpose", "max_tokens",
    "timeout_seconds", "created_at", "expires_at", "max_inner_rounds",
    "tools_allowed", "consultation_allowed", "request_digest",
}


@dataclass(frozen=True)
class MicroSocraticRequest:
    request_id: str
    agent_id: str
    mode: str
    provider: str
    model: str
    task: str
    draft: str
    purpose: str
    max_tokens: int
    timeout_seconds: float
    created_at: str
    expires_at: str
    max_inner_rounds: int = MAX_INNER_ROUNDS
    tools_allowed: bool = False
    consultation_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id",
                           clean_request_id(self.request_id, field="request_id"))
        object.__setattr__(self, "agent_id", clean_agent(self.agent_id))
        mode = str(self.mode)
        if mode not in MODES:
            raise MicroSocraticError(f"unknown kernel mode {mode!r}")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "provider",
                           clean_id(self.provider, field="provider"))
        object.__setattr__(self, "model", clean_id(self.model, field="model"))
        object.__setattr__(self, "task",
                           clean_text(self.task, field="task",
                                      maximum=MAX_TASK_CHARS))
        object.__setattr__(self, "draft",
                           clean_text(self.draft, field="draft",
                                      maximum=MAX_DRAFT_CHARS))
        object.__setattr__(self, "purpose",
                           clean_text(self.purpose, field="purpose",
                                      maximum=MAX_PURPOSE_CHARS))

        # Hard invariants — strict typing (bool/float/str that equal 1 refused).
        if type(self.max_inner_rounds) is not int or \
                self.max_inner_rounds != MAX_INNER_ROUNDS:
            raise MicroSocraticError(
                "max_inner_rounds must be exactly the integer 1 in v1")
        if self.tools_allowed is not False:
            raise MicroSocraticError("tools_allowed must be false in v1")
        if self.consultation_allowed is not False:
            raise MicroSocraticError("consultation_allowed must be false in v1")

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
            raise MicroSocraticError("expires_at must be after created_at")

    @property
    def task_sha256(self) -> str:
        return sha256_text(self.task)

    @property
    def draft_sha256(self) -> str:
        return sha256_text(self.draft)

    def _unsigned(self) -> Dict[str, Any]:
        return {
            "schema_version": REQUEST_VERSION,
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "task": self.task,
            "task_sha256": self.task_sha256,
            "draft": self.draft,
            "draft_sha256": self.draft_sha256,
            "purpose": self.purpose,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "max_inner_rounds": self.max_inner_rounds,
            "tools_allowed": self.tools_allowed,
            "consultation_allowed": self.consultation_allowed,
        }

    @property
    def request_digest(self) -> str:
        return digest(self._unsigned())

    def to_record(self) -> Dict[str, Any]:
        record = self._unsigned()
        record["request_digest"] = self.request_digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "MicroSocraticRequest":
        if not isinstance(record, Mapping) or set(record) != _REQUEST_FIELDS:
            raise MicroSocraticError(
                "kernel request contains missing or unknown fields")
        if record.get("schema_version") != REQUEST_VERSION:
            raise MicroSocraticError("unknown kernel request schema version")
        request = cls(
            request_id=record["request_id"],
            agent_id=record["agent_id"],
            mode=record["mode"],
            provider=record["provider"],
            model=record["model"],
            task=record["task"],
            draft=record["draft"],
            purpose=record["purpose"],
            max_tokens=record["max_tokens"],
            timeout_seconds=record["timeout_seconds"],
            created_at=record["created_at"],
            expires_at=record["expires_at"],
            max_inner_rounds=record["max_inner_rounds"],
            tools_allowed=record["tools_allowed"],
            consultation_allowed=record["consultation_allowed"],
        )
        if record["task_sha256"] != request.task_sha256:
            raise MicroSocraticError("kernel task hash mismatch")
        if record["draft_sha256"] != request.draft_sha256:
            raise MicroSocraticError("kernel draft hash mismatch")
        if record["request_digest"] != request.request_digest:
            raise MicroSocraticError("kernel request digest mismatch")
        return request


# ── check (result) ───────────────────────────────────────────────────────────

_CHECK_FIELDS = {
    "schema_version", "request_id", "request_digest", "agent_id", "mode",
    "provider", "model", "provider_status", "structured_payload",
    "isolated_check", "tools_executed", "consultation_executed", "inner_rounds",
    "response_digest",
}


@dataclass(frozen=True)
class MicroSocraticCheck:
    request_id: str
    request_digest: str
    agent_id: str
    mode: str
    provider: str
    model: str
    provider_status: str
    structured_payload: Dict[str, Any]
    isolated_check: bool = True
    tools_executed: bool = False
    consultation_executed: bool = False
    inner_rounds: int = MAX_INNER_ROUNDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id",
                           clean_request_id(self.request_id, field="request_id"))
        object.__setattr__(self, "request_digest",
                           clean_hex64(self.request_digest,
                                       field="request_digest"))
        object.__setattr__(self, "agent_id", clean_agent(self.agent_id))
        if self.mode not in MODES:
            raise MicroSocraticError(f"unknown kernel mode {self.mode!r}")
        object.__setattr__(self, "provider",
                           clean_id(self.provider, field="provider"))
        object.__setattr__(self, "model", clean_id(self.model, field="model"))
        object.__setattr__(self, "provider_status",
                           clean_text(self.provider_status,
                                      field="provider_status", maximum=32))
        if self.provider_status != "ok":
            raise MicroSocraticError(
                "a check may only be built from an OK provider status")
        if self.isolated_check is not True:
            raise MicroSocraticError("isolated_check must be true")
        if self.tools_executed is not False:
            raise MicroSocraticError("tools_executed must be false")
        if self.consultation_executed is not False:
            raise MicroSocraticError("consultation_executed must be false")
        if type(self.inner_rounds) is not int or \
                self.inner_rounds != MAX_INNER_ROUNDS:
            raise MicroSocraticError("inner_rounds must be exactly the integer 1")
        payload = validate_check_payload(self.mode, self.structured_payload)
        object.__setattr__(self, "structured_payload", payload)

    @property
    def decision(self) -> str:
        return self.structured_payload["decision"]

    def _unsigned(self) -> Dict[str, Any]:
        return {
            "schema_version": CHECK_VERSION,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "agent_id": self.agent_id,
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "provider_status": self.provider_status,
            "structured_payload": self.structured_payload,
            "isolated_check": self.isolated_check,
            "tools_executed": self.tools_executed,
            "consultation_executed": self.consultation_executed,
            "inner_rounds": self.inner_rounds,
        }

    @property
    def response_digest(self) -> str:
        return digest(self._unsigned())

    def to_record(self) -> Dict[str, Any]:
        record = self._unsigned()
        record["response_digest"] = self.response_digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "MicroSocraticCheck":
        if not isinstance(record, Mapping) or set(record) != _CHECK_FIELDS:
            raise MicroSocraticError(
                "kernel check contains missing or unknown fields")
        if record.get("schema_version") != CHECK_VERSION:
            raise MicroSocraticError("unknown kernel check schema version")
        check = cls(
            request_id=record["request_id"],
            request_digest=record["request_digest"],
            agent_id=record["agent_id"],
            mode=record["mode"],
            provider=record["provider"],
            model=record["model"],
            provider_status=record["provider_status"],
            structured_payload=dict(record["structured_payload"]),
            isolated_check=record["isolated_check"],
            tools_executed=record["tools_executed"],
            consultation_executed=record["consultation_executed"],
            inner_rounds=record["inner_rounds"],
        )
        if record["response_digest"] != check.response_digest:
            raise MicroSocraticError("kernel check digest mismatch")
        return check


# ── per-mode payload validation (never trust provider JSON) ──────────────────

_MODE_FIELDS: Dict[str, set] = {
    "light": {"claim_summary", "strongest_challenges", "decision",
              "revision_guidance"},
    "standard": {"claim_summary", "assumptions", "strongest_challenges",
                 "verification_requests", "decision", "revision_guidance"},
    "high_risk": {"claim_summary", "assumptions", "strongest_challenges",
                  "missing_evidence", "verification_requests", "uncertainties",
                  "decision", "revision_guidance"},
}


def _verification_request(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, Mapping) or set(entry) != {
            "kind", "reason", "priority"}:
        raise MicroSocraticError(
            "verification_request has missing or unknown fields")
    kind = str(entry["kind"])
    if kind not in VERIFICATION_KINDS:
        raise MicroSocraticError(f"unknown verification kind {kind!r}")
    priority = str(entry["priority"])
    if priority not in PRIORITIES:
        raise MicroSocraticError(f"unknown verification priority {priority!r}")
    return {
        "kind": kind,
        "reason": clean_text(entry["reason"], field="verification reason",
                             maximum=500, allow_authority=False),
        "priority": priority,
    }


def _verification_list(values: Any) -> list:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise MicroSocraticError("verification_requests must be a sequence")
    if len(values) > MAX_VERIFICATION_REQUESTS:
        raise MicroSocraticError(
            f"verification_requests exceed {MAX_VERIFICATION_REQUESTS} entries")
    return [_verification_request(item) for item in values]


def _coherence(mode: str, payload: Dict[str, Any]) -> None:
    """Decision must be consistent with the structured content, so a caller
    cannot cherry-pick an incoherent 'accept' that also demands revision, or a
    'verify_with_tool' with nothing to verify. (Kernel improvement.)"""
    decision = payload["decision"]
    guidance = payload.get("revision_guidance", [])
    vrs = payload.get("verification_requests", [])

    if decision == "accept" and guidance:
        raise MicroSocraticError(
            "decision 'accept' must not carry revision_guidance")
    if decision == "accept" and any(vr["priority"] == "required" for vr in vrs):
        # 'accept' means no unresolved blocking verification requirement - it is
        # NOT governance approval or self-certification. A 'required' verification
        # is blocking by definition, so a caller must not be able to cherry-pick
        # the 'accept' and silently drop it. (vrs items are already validated,
        # so "priority" is guaranteed present.)
        raise MicroSocraticError(
            "decision 'accept' must not carry a required verification_request")
    if decision == "revise" and not guidance:
        raise MicroSocraticError(
            "decision 'revise' requires non-empty revision_guidance")
    if decision == "verify_with_tool":
        if not any(vr["kind"] in _TOOL_KINDS for vr in vrs):
            raise MicroSocraticError(
                "decision 'verify_with_tool' requires a tool verification_request")
    if decision == "consult_external_model":
        if not any(vr["kind"] == "external_consultation" for vr in vrs):
            raise MicroSocraticError(
                "decision 'consult_external_model' requires an "
                "external_consultation verification_request")
    if decision == "insufficient_information" and mode != "light":
        if not (vrs or payload.get("missing_evidence")
                or payload.get("uncertainties")):
            raise MicroSocraticError(
                "decision 'insufficient_information' requires a "
                "verification_request, missing_evidence, or uncertainty")


def validate_check_payload(mode: str, payload: Any) -> Dict[str, Any]:
    """Strict, exact per-mode validation of the auditor's findings. Fails closed.
    No hidden chain-of-thought / monologue fields are accepted - the field set is
    exact, so any 'reasoning'/'scratchpad'/'thoughts' key is refused."""
    if mode not in MODES:
        raise MicroSocraticError(f"unknown kernel mode {mode!r}")
    if not isinstance(payload, Mapping):
        raise MicroSocraticError("structured_payload must be an object")
    if set(payload) != _MODE_FIELDS[mode]:
        raise MicroSocraticError(f"{mode} payload has missing or unknown fields")

    decision = str(payload["decision"])
    allowed = _LIGHT_DECISIONS if mode == "light" else DECISIONS
    if decision not in allowed:
        raise MicroSocraticError(
            f"decision {decision!r} not permitted in {mode} mode")

    clean: Dict[str, Any] = {
        "claim_summary": clean_text(payload["claim_summary"],
                                    field="claim_summary", maximum=1000,
                                    allow_authority=False),
        "strongest_challenges": _string_list(
            payload["strongest_challenges"], field="strongest_challenges",
            maximum_items=MAX_CHALLENGES, item_max=1000),
        "decision": decision,
        "revision_guidance": _string_list(
            payload["revision_guidance"], field="revision_guidance",
            maximum_items=MAX_REVISION_GUIDANCE, item_max=1000),
    }
    if mode in ("standard", "high_risk"):
        clean["assumptions"] = _string_list(
            payload["assumptions"], field="assumptions",
            maximum_items=MAX_ASSUMPTIONS, item_max=1000)
        clean["verification_requests"] = _verification_list(
            payload["verification_requests"])
    if mode == "high_risk":
        clean["missing_evidence"] = _string_list(
            payload["missing_evidence"], field="missing_evidence",
            maximum_items=MAX_MISSING_EVIDENCE, item_max=1000)
        clean["uncertainties"] = _string_list(
            payload["uncertainties"], field="uncertainties",
            maximum_items=MAX_UNCERTAINTIES, item_max=1000)

    _coherence(mode, clean)
    return clean


__all__ = [
    "REQUEST_VERSION", "CHECK_VERSION", "RECEIPT_VERSION",
    "MODES", "DECISIONS", "VERIFICATION_KINDS", "PRIORITIES",
    "MAX_INNER_ROUNDS", "MAX_TASK_CHARS", "MAX_DRAFT_CHARS",
    "MAX_TOKENS_CEILING", "MAX_TIMEOUT_SECONDS",
    "MicroSocraticError", "MicroSocraticRequest", "MicroSocraticCheck",
    "canonical_json", "digest", "sha256_text", "validate_check_payload",
    "clean_iso", "iso_utc", "clean_request_id",
]
