"""Strict builders from instrument reports to trusted self-revision evidence.

The generic OpenClaw failure detector observes session-level protocol facts and
the existing Lesson A/B harness measures a whole council treatment. Neither is,
by itself, sufficient to assign a weakness or lesson effect to one agent.

This module therefore accepts only explicit, versioned reports that include the
missing causal attribution:

- repeated failure observations attributed to one agent;
- matched before/after evidence resolving one attributed weakness;
- single-agent lesson A/B evidence;
- explicit constitutional review for Soul principles.

Malformed, council-wide, un-attributed, undersampled, harmful, self-verified, or
secret-shaped reports fail closed. Builders create evidence records only; they
never approve or apply a revision.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from .revision_evidence import RevisionEvidenceRecord

IDENTITY_FAILURE_REPORT_VERSION = "openclaw_identity_failure_attribution_v1"
IDENTITY_RESOLUTION_REPORT_VERSION = "openclaw_identity_resolution_v1"
AGENT_LESSON_AB_REPORT_VERSION = "openclaw_agent_lesson_ab_v1"
SOUL_ATTESTATION_VERSION = "openclaw_soul_attestation_v1"

_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)

_IDENTITY_FAILURE_FIELDS = {
    "schema_version", "reference", "agent_id", "pattern_key", "weakness",
    "observations", "source", "verified_by", "verification_reference",
    "observed_on",
}
_IDENTITY_RESOLUTION_FIELDS = {
    "schema_version", "reference", "agent_id", "pattern_key", "weakness",
    "before_session_ids", "after_session_ids", "before_failures",
    "after_failures", "matched_window", "source", "verified_by",
    "verification_reference", "observed_on",
}
_AGENT_LESSON_AB_FIELDS = {
    "schema_version", "reference", "target_agent_id", "lesson_id",
    "treatment_scope", "tested", "min_tested", "verdict", "helped",
    "mean_score_delta", "harm_rate", "max_harm_rate",
    "ratification_regressions", "unresolved_regressions",
    "catastrophic_regressions", "configuration_mismatches", "source",
    "verified_by", "verification_reference", "observed_on",
}
_SOUL_ATTESTATION_FIELDS = {
    "schema_version", "reference", "agent_id", "action", "principle",
    "constitutional_review", "risk_reviewed", "evidence_references",
    "rationale", "reviewed_by", "review_reference", "observed_on",
}


def _clean_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError(f"{field} contains control characters")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"{field} contains secret-shaped data matching {pattern.pattern!r}")
    return text


def _strict_report(
    report: Mapping[str, Any],
    *,
    fields: set[str],
    version: str,
) -> Dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValueError("instrument report must be a mapping")
    actual = set(report)
    if actual != fields:
        raise ValueError(
            "instrument report contains missing or unknown fields: "
            f"{sorted(actual ^ fields)}")
    if report.get("schema_version") != version:
        raise ValueError(
            f"instrument report must use schema_version {version!r}")
    return dict(report)


def _sequence(
    values: Iterable[Any],
    *,
    field: str,
    minimum: int = 1,
    maximum: int = 128,
    text_maximum: int = 256,
) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a sequence, not text")
    cleaned = tuple(
        _clean_text(value, field=field, maximum=text_maximum)
        for value in values
    )
    if len(cleaned) < minimum:
        raise ValueError(f"{field} requires at least {minimum} entries")
    if len(cleaned) > maximum:
        raise ValueError(f"{field} exceeds {maximum} entries")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field} must not contain duplicate entries")
    return cleaned


def _integer(value: Any, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not boolean")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed != value or parsed < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return parsed


def _number(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric, not boolean")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _base_record(
    report: Mapping[str, Any],
    *,
    agent_field: str,
    support: str,
    value: str,
    outcomes: Sequence[str] = (),
    source_suffix: str = "",
) -> RevisionEvidenceRecord:
    source = _clean_text(report["source"], field="source", maximum=512)
    if source_suffix:
        source = f"{source}#{source_suffix}"
    return RevisionEvidenceRecord(
        reference=_clean_text(
            report["reference"], field="reference", maximum=256),
        agent_id=_clean_text(
            report[agent_field], field=agent_field, maximum=128),
        source=source,
        supports=(support,),
        value=value,
        verified_by=_clean_text(
            report["verified_by"], field="verified_by", maximum=128),
        verification_reference=_clean_text(
            report["verification_reference"],
            field="verification_reference",
            maximum=512,
        ),
        observed_on=str(report.get("observed_on", "") or "").strip(),
        outcomes=tuple(outcomes),
    )


def build_identity_failure_evidence(
    report: Mapping[str, Any],
    *,
    min_occurrences: int = 2,
) -> RevisionEvidenceRecord:
    """Build `add_known_failure` evidence from repeated agent attribution.

    Each observation must explicitly name the same agent, carry a distinct
    session ID and source trace, and set ``attribution_verified`` to true. Raw
    session-level failure observations without agent attribution are refused.
    """
    data = _strict_report(
        report,
        fields=_IDENTITY_FAILURE_FIELDS,
        version=IDENTITY_FAILURE_REPORT_VERSION,
    )
    if min_occurrences < 2:
        raise ValueError("identity failure evidence requires min_occurrences >= 2")
    agent_id = _clean_text(data["agent_id"], field="agent_id", maximum=128)
    pattern_key = _clean_text(
        data["pattern_key"], field="pattern_key", maximum=128)
    weakness = _clean_text(data["weakness"], field="weakness", maximum=500)
    observations = data["observations"]
    if isinstance(observations, (str, bytes)) or not isinstance(
            observations, (list, tuple)):
        raise ValueError("observations must be a sequence")
    if len(observations) < min_occurrences:
        raise ValueError(
            f"identity failure evidence requires {min_occurrences} observations")

    sessions = []
    sources = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise ValueError("each identity failure observation must be a mapping")
        required = {
            "session_id", "attributed_agent_id", "pattern_key",
            "attribution_verified", "source_trace",
        }
        if set(observation) != required:
            raise ValueError(
                "identity failure observation contains missing or unknown fields")
        if observation.get("attribution_verified") is not True:
            raise ValueError("identity failure attribution is not verified")
        if str(observation.get("attributed_agent_id", "")).strip() != agent_id:
            raise ValueError("identity failure observation belongs to another agent")
        if str(observation.get("pattern_key", "")).strip() != pattern_key:
            raise ValueError("identity failure observations mix different patterns")
        sessions.append(_clean_text(
            observation["session_id"], field="session_id", maximum=128))
        sources.append(_clean_text(
            observation["source_trace"], field="source_trace", maximum=512))
    if len(set(sessions)) != len(sessions):
        raise ValueError("identity failure observations must use distinct sessions")
    if len(set(sources)) != len(sources):
        raise ValueError("identity failure observations must use distinct traces")

    attribution_digest = _digest({
        "agent_id": agent_id,
        "pattern_key": pattern_key,
        "sessions": sorted(sessions),
        "sources": sorted(sources),
    })
    return _base_record(
        data,
        agent_field="agent_id",
        support="identity:add_known_failure",
        value=weakness,
        source_suffix=f"attribution-{attribution_digest[:16]}",
    )


def build_identity_resolution_evidence(
    report: Mapping[str, Any],
    *,
    min_window: int = 2,
) -> RevisionEvidenceRecord:
    """Build `resolve_known_failure` evidence from matched before/after windows."""
    data = _strict_report(
        report,
        fields=_IDENTITY_RESOLUTION_FIELDS,
        version=IDENTITY_RESOLUTION_REPORT_VERSION,
    )
    if min_window < 2:
        raise ValueError("identity resolution evidence requires min_window >= 2")
    if data.get("matched_window") is not True:
        raise ValueError("identity resolution requires a matched comparison window")
    before_ids = _sequence(
        data["before_session_ids"], field="before_session_ids", minimum=min_window)
    after_ids = _sequence(
        data["after_session_ids"], field="after_session_ids", minimum=min_window)
    if len(before_ids) != len(after_ids):
        raise ValueError("identity resolution windows must have equal size")
    if set(before_ids) & set(after_ids):
        raise ValueError("before and after identity windows must not overlap")
    before_failures = _integer(
        data["before_failures"], field="before_failures", minimum=1)
    after_failures = _integer(
        data["after_failures"], field="after_failures", minimum=0)
    if before_failures < min_window:
        raise ValueError("identity resolution needs repeated failures before change")
    if after_failures != 0:
        raise ValueError("identity resolution requires zero failures after change")

    weakness = _clean_text(data["weakness"], field="weakness", maximum=500)
    comparison_digest = _digest({
        "agent_id": data["agent_id"],
        "pattern_key": data["pattern_key"],
        "before": before_ids,
        "after": after_ids,
        "before_failures": before_failures,
        "after_failures": after_failures,
    })
    return _base_record(
        data,
        agent_field="agent_id",
        support="identity:resolve_known_failure",
        value=weakness,
        source_suffix=f"matched-{comparison_digest[:16]}",
    )


def build_agent_lesson_ab_evidence(
    report: Mapping[str, Any],
    *,
    action: str,
) -> RevisionEvidenceRecord:
    """Build Memory evidence only from a single-agent, matched Lesson A/B report.

    A normal council-wide ``lesson_ab_v2`` report is deliberately rejected. It
    cannot establish that one particular agent benefited from a lesson.
    """
    data = _strict_report(
        report,
        fields=_AGENT_LESSON_AB_FIELDS,
        version=AGENT_LESSON_AB_REPORT_VERSION,
    )
    if action not in {"link_stable_lesson", "unlink_stable_lesson"}:
        raise ValueError("lesson evidence action must link or unlink a stable lesson")
    if data.get("treatment_scope") != "single_agent":
        raise ValueError("lesson evidence must use treatment_scope='single_agent'")
    lesson_id = _clean_text(data["lesson_id"], field="lesson_id", maximum=128)
    if not lesson_id.startswith("LESSON-"):
        raise ValueError("lesson evidence value must be a LESSON-* id")

    tested = _integer(data["tested"], field="tested", minimum=0)
    min_tested = _integer(data["min_tested"], field="min_tested", minimum=1)
    if tested < min_tested:
        raise ValueError("lesson evidence has insufficient tested comparisons")
    mean_delta = _number(data["mean_score_delta"], field="mean_score_delta")
    harm_rate = _number(data["harm_rate"], field="harm_rate")
    max_harm_rate = _number(data["max_harm_rate"], field="max_harm_rate")
    if not 0.0 <= harm_rate <= 1.0 or not 0.0 <= max_harm_rate <= 1.0:
        raise ValueError("lesson harm rates must be between 0 and 1")

    regressions = sum(_integer(
        data[field], field=field, minimum=0)
        for field in (
            "ratification_regressions", "unresolved_regressions",
            "catastrophic_regressions", "configuration_mismatches",
        )
    )
    verdict = _clean_text(data["verdict"], field="verdict", maximum=32)
    helped = data.get("helped")
    if not isinstance(helped, bool):
        raise ValueError("lesson evidence helped must be boolean")

    if action == "link_stable_lesson":
        if verdict != "helped" or helped is not True:
            raise ValueError("link evidence requires verdict='helped' and helped=true")
        if mean_delta <= 0:
            raise ValueError("link evidence requires positive mean_score_delta")
        if regressions != 0 or harm_rate > max_harm_rate:
            raise ValueError("link evidence contains harm or configuration regressions")
        outcomes: Tuple[str, ...] = ("confirmed",)
    else:
        harmed = (
            verdict == "harmed"
            and helped is False
            and (mean_delta < 0 or regressions > 0 or harm_rate > max_harm_rate)
        )
        if not harmed:
            raise ValueError("unlink evidence requires a concrete harmed verdict")
        outcomes = ("reverted",)

    report_digest = _digest({
        key: data[key]
        for key in sorted(data)
        if key not in {"verified_by", "verification_reference", "observed_on"}
    })
    return _base_record(
        data,
        agent_field="target_agent_id",
        support=f"memory:{action}",
        value=lesson_id,
        outcomes=outcomes,
        source_suffix=f"agent-ab-{report_digest[:16]}",
    )


def build_soul_attestation_evidence(
    report: Mapping[str, Any],
) -> RevisionEvidenceRecord:
    """Build Soul evidence only from explicit non-self constitutional review.

    Soul principles are normative commitments, not facts inferable from traces.
    This builder therefore refuses automatic or unreviewed principle generation.
    """
    data = _strict_report(
        report,
        fields=_SOUL_ATTESTATION_FIELDS,
        version=SOUL_ATTESTATION_VERSION,
    )
    if data.get("constitutional_review") is not True:
        raise ValueError("Soul evidence requires explicit constitutional review")
    if data.get("risk_reviewed") is not True:
        raise ValueError("Soul evidence requires explicit risk review")
    action = _clean_text(data["action"], field="action", maximum=32)
    if action not in {"add_principle", "retire_principle"}:
        raise ValueError("Soul action must add or retire a principle")
    principle = _clean_text(data["principle"], field="principle", maximum=500)
    evidence_references = _sequence(
        data["evidence_references"],
        field="Soul evidence reference",
        minimum=1,
        maximum=32,
        text_maximum=256,
    )
    rationale = _clean_text(data["rationale"], field="rationale", maximum=2000)
    review_reference = _clean_text(
        data["review_reference"], field="review_reference", maximum=512)
    attestation_digest = _digest({
        "agent_id": data["agent_id"],
        "action": action,
        "principle": principle,
        "evidence_references": evidence_references,
        "rationale": rationale,
        "review_reference": review_reference,
    })
    shaped = {
        "reference": data["reference"],
        "agent_id": data["agent_id"],
        "source": f"SoulConstitutionalReview/{review_reference}",
        "verified_by": data["reviewed_by"],
        "verification_reference": review_reference,
        "observed_on": data["observed_on"],
    }
    return _base_record(
        shaped,
        agent_field="agent_id",
        support=f"soul:{action}",
        value=principle,
        source_suffix=f"attestation-{attestation_digest[:16]}",
    )
