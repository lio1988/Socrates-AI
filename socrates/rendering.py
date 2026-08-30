"""Fail-closed rendering for the ordinary Socrates interface.

The canonical CED response intentionally retains an assembled candidate even
when ratification or the governing release prevents publication.  This module
keeps that candidate available to the local artifact layer, while making the
public rendering decision from the H7 governing fields and their audit copy.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Optional

from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    sanitize_public_assistant_output_v1,
)


RELEASE_SUPPORTED = "release_supported"
RELEASE_UNRESOLVED = "release_unresolved"
BLOCKED = "blocked"

UNRESOLVED_NOTICE = (
    "WARNING: GOVERNING RELEASE UNRESOLVED. The answer below is ratified "
    "council output, but its governing evidence status remains unresolved."
)
BLOCKED_NOTICE = (
    "GOVERNING RELEASE BLOCKED. The council candidate was withheld."
)
UNAVAILABLE_NOTICE = (
    "GOVERNING RELEASE UNAVAILABLE. The council candidate was withheld."
)
INCONSISTENT_NOTICE = (
    "GOVERNING RELEASE INCONSISTENT. The council candidate was withheld."
)

_RECOGNIZED_RELEASES = frozenset(
    {RELEASE_SUPPORTED, RELEASE_UNRESOLVED, BLOCKED}
)
_ALLOWED_GOVERNING_STATUS = {
    RELEASE_SUPPORTED: frozenset({"supported"}),
    RELEASE_UNRESOLVED: frozenset(
        {"unsupported", "unresolved", "external_evidence_required"}
    ),
    BLOCKED: frozenset(
        {
            "unsupported",
            "unresolved",
            "falsified",
            "external_evidence_required",
        }
    ),
}

# The shared public sanitizer handles OpenRouter keys and bearer-shaped values.
# Normal mode additionally removes the *whole remainder of a sensitive line*.
# Token-at-a-time replacement is unsafe for Basic auth, multi-cookie headers,
# quoted passphrases, connection strings, and pasted ``.env`` records.
_NORMAL_SENSITIVE_ASSIGNMENT_LINE = re.compile(
    r"(?im)(?P<prefix>\b(?:"
    r"authorization|cookie|set-cookie|session[_-]?cookie|password|secret|"
    r"token|access[_-]?token|refresh[_-]?token|api[_-]?key|"
    r"cf_clearance|__cf_bm|cf_chl_[a-z0-9_]*|"
    r"(?:[A-Z][A-Z0-9_]*_)?(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|COOKIE|"
    r"AUTHORIZATION|ACCESS[_-]?KEY|CREDENTIAL|PRIVATE[_-]?KEY|"
    r"CONNECTION[_-]?STRING|DATABASE[_-]?URL|REDIS[_-]?URL|DSN)"
    r"(?:_[A-Z0-9_]+)*"
    r")\b[\"']?\s*(?:[:=]|\bis\b)\s*)[\"']?[^\r\n]*"
)
_NORMAL_HIGH_CONFIDENCE_SECRET_SUBSTITUTIONS = (
    (
        re.compile(
            r"(?<![A-Z0-9])(?:AKIA|ASIA|AIDA|AROA|AIPA|ANPA|ANVA)"
            r"[A-Z0-9]{16}(?![A-Z0-9])"
        ),
        "[REDACTED]",
    ),
    (
        re.compile(r"(?<![0-9A-Za-z_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"),
        "[REDACTED]",
    ),
    (
        re.compile(
            r"(?<![0-9A-Za-z_])(?:gh[pousr]_[0-9A-Za-z]{36,255}|"
            r"github_pat_[0-9A-Za-z_]{22,255})(?![0-9A-Za-z_])"
        ),
        "[REDACTED]",
    ),
    (
        re.compile(
            r"(?<![0-9A-Za-z-])xox[baprs]-[0-9A-Za-z-]{10,}"
            r"(?![0-9A-Za-z-])"
        ),
        "[REDACTED]",
    ),
    (
        re.compile(
            r"(?is)-----BEGIN[ \t]+(?:[A-Z0-9]+[ \t]+)*PRIVATE[ \t]+KEY-----"
            r".*?-----END[ \t]+(?:[A-Z0-9]+[ \t]+)*PRIVATE[ \t]+KEY-----"
        ),
        "[REDACTED PRIVATE KEY]",
    ),
    (
        re.compile(
            r"(?i)(?P<scheme>\b(?:postgres(?:ql)?|mysql|mariadb|"
            r"mongodb(?:\+srv)?|redis|rediss|amqp|amqps|smtp|smtps|ftp|https?)"
            r"://)[^/\s:@]+:[^/\s@]+@"
        ),
        r"\g<scheme>[REDACTED]@",
    ),
)

# Strip complete terminal-control sequences before applying the credential
# filters.  Removing the introducer alone would make the bytes inert, but
# removing the whole sequence also prevents escape payloads from becoming
# misleading visible text.  The second pattern catches malformed/incomplete
# sequences and every other C0/C1 control except intended tab/newline/return.
_NORMAL_TERMINAL_ESCAPE_SEQUENCE = re.compile(
    r"(?:"
    r"(?:\x1b\]|\x9d).*?(?:\x07|\x9c|\x1b\\)"
    r"|(?:\x1b[P^_X]|\x90|\x98|\x9e|\x9f).*?(?:\x9c|\x1b\\)"
    r"|(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]"
    r"|\x1b[@-_]"
    r")",
    re.DOTALL,
)
_NORMAL_DISALLOWED_TERMINAL_CONTROLS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

RenderOutcome = Literal[
    "release_supported",
    "release_unresolved",
    "blocked",
    "unavailable",
    "inconsistent",
]


@dataclass(frozen=True)
class NormalRenderResult:
    """Small immutable result consumed by the CLI and artifact projector."""

    outcome: RenderOutcome
    release_decision: Optional[str]
    governing_epistemic_status: Optional[str]
    public_answer: str
    notice: str
    candidate_authorized: bool
    candidate: str = field(repr=False)


def sanitize_normal_text(text: str) -> str:
    """Sanitize provider-visible text without accepting non-text diagnostics."""

    if not isinstance(text, str):
        raise TypeError("Normal visible text must be a string")
    sanitized = _NORMAL_TERMINAL_ESCAPE_SEQUENCE.sub("", text)
    sanitized = _NORMAL_DISALLOWED_TERMINAL_CONTROLS.sub("", sanitized)
    sanitized = _NORMAL_SENSITIVE_ASSIGNMENT_LINE.sub(
        r"\g<prefix>[REDACTED]", sanitized
    )
    for pattern, replacement in _NORMAL_HIGH_CONFIDENCE_SECRET_SUBSTITUTIONS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitize_public_assistant_output_v1(sanitized)


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return sanitize_normal_text(value)


def _candidate(final: object, sanitized_answer: str) -> str:
    synthesis = getattr(final, "synthesis", None)
    full_text = getattr(synthesis, "full_text", None)
    if callable(full_text):
        try:
            assembled = _text(full_text())
        except Exception:
            # A malformed FinalResponse-like test double must not leak its
            # exception or prevent the safe fallback from being preserved.
            assembled = ""
        if assembled:
            return assembled
    return sanitized_answer


def _withheld(
    *,
    outcome: RenderOutcome,
    notice: str,
    candidate: str,
    release_decision: Optional[str],
    governing_status: Optional[str],
) -> NormalRenderResult:
    return NormalRenderResult(
        outcome=outcome,
        release_decision=release_decision,
        governing_epistemic_status=governing_status,
        public_answer="",
        notice=notice,
        candidate_authorized=False,
        candidate=candidate,
    )


def render_normal_response(final: object) -> NormalRenderResult:
    """Render a FinalResponse-like object through the governing release only.

    Publication fails closed unless the successful governing audit repeats the
    exact decision and epistemic status carried on the response.  A supported
    or unresolved decision additionally requires canonical ratification and a
    non-empty ``final.answer``.  The legacy ``epistemic_status`` is never read.
    """

    sanitized_answer = _text(getattr(final, "answer", ""))
    candidate = _candidate(final, sanitized_answer)

    field_decision = getattr(final, "release_decision", None)
    field_status = getattr(final, "governing_epistemic_status", None)
    safe_decision = field_decision if isinstance(field_decision, str) else None
    safe_status = field_status if isinstance(field_status, str) else None

    audit_summary = getattr(final, "audit_summary", None)
    governing = (
        audit_summary.get("governing_release")
        if isinstance(audit_summary, Mapping)
        else None
    )
    if not isinstance(governing, Mapping) or governing.get("available") is not True:
        return _withheld(
            outcome="unavailable",
            notice=UNAVAILABLE_NOTICE,
            candidate=candidate,
            release_decision=safe_decision,
            governing_status=safe_status,
        )

    audit_decision = governing.get("release_decision")
    audit_status = governing.get("governing_epistemic_status")
    governing_consistent = (
        isinstance(field_decision, str)
        and field_decision in _RECOGNIZED_RELEASES
        and audit_decision == field_decision
        and isinstance(field_status, str)
        and field_status in _ALLOWED_GOVERNING_STATUS[field_decision]
        and audit_status == field_status
    )
    if not governing_consistent:
        return _withheld(
            outcome="inconsistent",
            notice=INCONSISTENT_NOTICE,
            candidate=candidate,
            release_decision=safe_decision,
            governing_status=safe_status,
        )

    if field_decision == BLOCKED:
        return _withheld(
            outcome="blocked",
            notice=BLOCKED_NOTICE,
            candidate=candidate,
            release_decision=field_decision,
            governing_status=field_status,
        )

    ratified_answer = getattr(final, "ratified", None) is True and bool(
        sanitized_answer.strip()
    )
    if not ratified_answer:
        return _withheld(
            outcome="inconsistent",
            notice=INCONSISTENT_NOTICE,
            candidate=candidate,
            release_decision=field_decision,
            governing_status=field_status,
        )

    if field_decision == RELEASE_UNRESOLVED:
        return NormalRenderResult(
            outcome="release_unresolved",
            release_decision=field_decision,
            governing_epistemic_status=field_status,
            public_answer=sanitized_answer,
            notice=UNRESOLVED_NOTICE,
            candidate_authorized=True,
            candidate=candidate,
        )

    return NormalRenderResult(
        outcome="release_supported",
        release_decision=field_decision,
        governing_epistemic_status=field_status,
        public_answer=sanitized_answer,
        notice="",
        candidate_authorized=True,
        candidate=candidate,
    )


__all__ = [
    "BLOCKED_NOTICE",
    "INCONSISTENT_NOTICE",
    "NormalRenderResult",
    "UNAVAILABLE_NOTICE",
    "UNRESOLVED_NOTICE",
    "render_normal_response",
    "sanitize_normal_text",
]
