"""Current-state binding for governed Memory self-revision evidence.

Personal Memory changes are permitted only from the bound single-agent Lesson
A/B bridge. The immutable evidence source carries a machine-readable marker:

    #memory-ab-v1:<lesson_sha256>:<identity_sha256>:<experiment_sha256>

The generic evidence record remains backward-compatible, while the canonical
governed lifecycle calls this module on every evaluation, decision, and
application. Evidence produced for another lesson revision, another governed
Identity state, or an unbound/whole-council experiment fails closed.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .identity_profile import AgentIdentityProfile
from .self_review import profile_fingerprint
from .self_revision import (
    RevisionEvaluation,
    SelfRevisionProposal,
    evaluate_self_revision,
)

MEMORY_AB_BINDING_VERSION = "memory-ab-v1"
_MEMORY_AB_MARKER_RE = re.compile(
    r"#memory-ab-v1:([0-9a-f]{64}):([0-9a-f]{64}):([0-9a-f]{64})"
)
_AGENT_AB_MARKER = "#agent-ab-"
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def memory_ab_binding_marker(
    *,
    lesson_fingerprint: str,
    identity_fingerprint: str,
    experiment_fingerprint: str,
) -> str:
    """Return the canonical source marker committed by the G4 bridge."""
    values = (
        lesson_fingerprint,
        identity_fingerprint,
        experiment_fingerprint,
    )
    if any(not _HEX64_RE.fullmatch(str(value or "")) for value in values):
        raise ValueError("Memory A/B bindings must be lowercase SHA-256 digests")
    return (
        f"#{MEMORY_AB_BINDING_VERSION}:{lesson_fingerprint}:"
        f"{identity_fingerprint}:{experiment_fingerprint}"
        f"#bindings-{experiment_fingerprint[:16]}"
    )


def parse_memory_ab_binding(source: Any):
    """Return ``(lesson, identity, experiment)`` or ``None``."""
    match = _MEMORY_AB_MARKER_RE.search(str(source or ""))
    return match.groups() if match else None


def _clean_fingerprint_map(values: Mapping[str, str] | None) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError("lesson_fingerprints must be a mapping")
    cleaned: dict[str, str] = {}
    for raw_lesson_id, raw_fingerprint in values.items():
        lesson_id = str(raw_lesson_id or "").strip()
        fingerprint = str(raw_fingerprint or "").strip()
        if not lesson_id.startswith("LESSON-"):
            raise ValueError("lesson_fingerprints keys must use LESSON-* format")
        if not _HEX64_RE.fullmatch(fingerprint):
            raise ValueError(
                "lesson_fingerprints values must be lowercase SHA-256")
        if lesson_id in cleaned and cleaned[lesson_id] != fingerprint:
            raise ValueError("lesson fingerprint mapping is conflicting")
        cleaned[lesson_id] = fingerprint
    if len(cleaned) > 256:
        raise ValueError("lesson_fingerprints exceeds 256 entries")
    return cleaned


def lesson_fingerprint_map(
    values: Mapping[str, str] | None,
) -> dict[str, str]:
    """Public strict normalizer used by lifecycle and transaction layers."""
    return _clean_fingerprint_map(values)


def memory_binding_reasons(
    proposal: SelfRevisionProposal,
    *,
    current_profile: AgentIdentityProfile,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    lesson_fingerprints: Mapping[str, str] | None,
) -> tuple[str, ...]:
    """Return fail-closed reasons for personal Memory evidence bindings."""
    if proposal.target != "memory":
        return ()
    if current_profile.agent_id != proposal.agent_id:
        raise ValueError("current profile belongs to another agent")
    fingerprints = _clean_fingerprint_map(lesson_fingerprints)
    current_lesson = fingerprints.get(proposal.value)
    reasons = []
    current_identity = profile_fingerprint(current_profile)

    for reference in proposal.evidence_references:
        evidence = evidence_manifest.get(reference)
        if not isinstance(evidence, Mapping):
            continue  # generic evaluation reports the missing record
        source = str(evidence.get("source", ""))
        if _AGENT_AB_MARKER not in source:
            reasons.append(
                f"Memory evidence is not a single-agent Lesson A/B record: "
                f"{reference}")
            continue
        binding = parse_memory_ab_binding(source)
        if binding is None:
            reasons.append(
                f"Memory evidence is not bound to governed state: {reference}")
            continue
        lesson_fingerprint, identity_fingerprint, _experiment = binding
        if identity_fingerprint != current_identity:
            reasons.append(
                f"Memory evidence was produced for a stale governed Identity: "
                f"{reference}")
        if current_lesson is None:
            reasons.append(
                f"current lesson fingerprint is missing for {proposal.value!r}")
        elif lesson_fingerprint != current_lesson:
            reasons.append(
                f"Memory evidence was produced for a stale lesson revision: "
                f"{reference}")
    return tuple(dict.fromkeys(reasons))


def evaluate_governed_self_revision(
    proposal: SelfRevisionProposal,
    *,
    current_profile: AgentIdentityProfile,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    stable_lesson_ids=(),
    lesson_fingerprints: Mapping[str, str] | None = None,
) -> RevisionEvaluation:
    """Run generic validation plus current-state Memory binding checks."""
    base = evaluate_self_revision(
        proposal,
        evidence_manifest=evidence_manifest,
        stable_lesson_ids=stable_lesson_ids,
    )
    binding_reasons = memory_binding_reasons(
        proposal,
        current_profile=current_profile,
        evidence_manifest=evidence_manifest,
        lesson_fingerprints=lesson_fingerprints,
    )
    if not binding_reasons:
        return base
    reasons = tuple(
        reason for reason in base.reasons
        if not reason.endswith("action-specific evidence record(s) verified")
    ) + binding_reasons
    return RevisionEvaluation(
        proposal_id=base.proposal_id,
        passed=False,
        reasons=reasons,
        evidence_used=base.evidence_used,
    )


__all__ = [
    "MEMORY_AB_BINDING_VERSION",
    "evaluate_governed_self_revision",
    "lesson_fingerprint_map",
    "memory_ab_binding_marker",
    "memory_binding_reasons",
    "parse_memory_ab_binding",
]
