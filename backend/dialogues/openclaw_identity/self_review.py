"""Bounded self-review snapshots for governed agent self-improvement.

A full identity profile is a system artifact and is never injected into ordinary
reasoning contexts. During an explicit self-review task, however, an agent needs
a safe, bounded view of its own public performance record and the verified
evidence it may cite. This module creates that view.

The snapshot is descriptive, not authority. It excludes other agents, hidden
scorecards, raw dialogue content, secrets, and every write capability. It can be
used only to author a ``SelfRevisionProposal`` which still requires independent
evidence validation and named non-self approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

from .identity_profile import AgentIdentityProfile
from .self_revision import REVISION_TARGET_ACTIONS, SelfRevisionProposal

SNAPSHOT_VERSION = "openclaw_self_review_v4"
MAX_REVIEW_EVIDENCE = 64
MAX_PENDING_PROPOSALS = 32
MAX_KNOWN_FAILURES = 32
MAX_STABLE_LESSONS = 64
MAX_SOUL_PRINCIPLES = 32
MAX_INSTRUCTION_BYTES = 65536

_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)

SELF_REVIEW_BOUNDARIES: Tuple[str, ...] = (
    "This snapshot is descriptive and grants no runtime authority.",
    "Use only the evidence references included in this snapshot.",
    "Every visible evidence item has a named non-self verifier.",
    "The agent may propose one revision but cannot approve or activate it.",
    "Do not infer facts about other agents or hidden evaluation records.",
    "A proposal must state risk and may be rejected without changing identity.",
)


def _safe_text(value: Any, *, field: str, maximum: int = 1000) -> str:
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


def _require_bounded_count(
    values: Sequence[Any],
    *,
    field: str,
    maximum: int,
) -> None:
    if len(values) > maximum:
        raise ValueError(
            f"{field} contains {len(values)} entries; maximum is {maximum}")


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("self-review state must be canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def observational_profile_fingerprint(profile: AgentIdentityProfile) -> str:
    """Digest every profile field, including refreshable performance metrics."""
    return _canonical_digest(profile.to_record())


def profile_fingerprint(profile: AgentIdentityProfile) -> str:
    """Digest the governed Identity/Memory/Soul state.

    This is the canonical fingerprint used by revision lifecycle transitions.
    Role rates, counts, and session totals are evidence observations that may
    refresh without changing the agent's governed identity commitments.
    """
    return _canonical_digest({
        "agent_id": profile.agent_id,
        "identity_version": profile.identity_version,
        "promotion_status": profile.promotion_status,
        "known_failures": list(profile.known_failures),
        "stable_lessons": list(profile.stable_lessons),
        "soul_principles": list(profile.soul_principles),
        "next_gate": profile.next_gate,
        "version_history": [dict(entry) for entry in profile.version_history],
        "revision_history": [dict(entry) for entry in profile.revision_history],
    })


def governed_profile_fingerprint(profile: AgentIdentityProfile) -> str:
    """Explicit alias for the canonical governed ``profile_fingerprint``."""
    return profile_fingerprint(profile)


@dataclass(frozen=True)
class SelfReviewEvidence:
    """One verified, agent-owned evidence claim safe to expose for self-review."""

    reference: str
    source: str
    supports: Tuple[str, ...]
    value: str
    verified_by: str
    verification_reference: str

    def to_record(self) -> Dict[str, Any]:
        return {
            "reference": self.reference,
            "source": self.source,
            "supports": list(self.supports),
            "value": self.value,
            "verified_by": self.verified_by,
            "verification_reference": self.verification_reference,
        }


@dataclass(frozen=True)
class SelfReviewSnapshot:
    """Versioned, bounded input for an explicit agent self-review task."""

    agent_id: str
    profile_fingerprint: str
    governed_profile_fingerprint: str
    observational_profile_fingerprint: str
    identity_version: str
    promotion_status: str
    role_strengths: Dict[str, Dict[str, Any]]
    known_failures: Tuple[str, ...]
    stable_lessons: Tuple[str, ...]
    soul_principles: Tuple[str, ...]
    verified_evidence: Tuple[SelfReviewEvidence, ...]
    pending_proposal_ids: Tuple[str, ...]
    boundaries: Tuple[str, ...] = SELF_REVIEW_BOUNDARIES
    snapshot_version: str = SNAPSHOT_VERSION

    def to_record(self) -> Dict[str, Any]:
        return {
            "snapshot_version": self.snapshot_version,
            "agent_id": self.agent_id,
            "profile_fingerprint": self.profile_fingerprint,
            "governed_profile_fingerprint": self.governed_profile_fingerprint,
            "observational_profile_fingerprint": (
                self.observational_profile_fingerprint),
            "identity_version": self.identity_version,
            "promotion_status": self.promotion_status,
            "role_strengths": {
                name: dict(value)
                for name, value in sorted(self.role_strengths.items())
            },
            "known_failures": list(self.known_failures),
            "stable_lessons": list(self.stable_lessons),
            "soul_principles": list(self.soul_principles),
            "verified_evidence": [
                evidence.to_record() for evidence in self.verified_evidence
            ],
            "pending_proposal_ids": list(self.pending_proposal_ids),
            "boundaries": list(self.boundaries),
        }

    @property
    def snapshot_fingerprint(self) -> str:
        return _canonical_digest(self.to_record())


def _public_strengths(profile: AgentIdentityProfile) -> Dict[str, Dict[str, Any]]:
    strengths: Dict[str, Dict[str, Any]] = {}
    for name in sorted(profile.section_opportunities):
        opportunities = int(profile.section_opportunities.get(name, 0))
        if opportunities <= 0:
            continue
        strengths[name] = {
            "win_rate": float(profile.role_strengths.get(name, 0.0)),
            "wins": int(profile.section_wins.get(name, 0)),
            "opportunities": opportunities,
        }
    return strengths


def _eligible_evidence(
    agent_id: str,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
) -> Tuple[SelfReviewEvidence, ...]:
    if not isinstance(evidence_manifest, Mapping):
        raise ValueError("evidence_manifest must be a mapping")

    allowed_supports = {
        f"{target}:{action}"
        for target, actions in REVISION_TARGET_ACTIONS.items()
        for action in actions
    }
    evidence_rows = []
    for raw_reference in sorted(evidence_manifest, key=str):
        record = evidence_manifest[raw_reference]
        if not isinstance(record, Mapping):
            raise ValueError(
                f"evidence record {raw_reference!r} must be a mapping")
        if record.get("verified") is not True:
            continue
        if str(record.get("agent_id", "")).strip() != agent_id:
            continue

        reference = _safe_text(
            raw_reference, field="evidence reference", maximum=256)
        source = _safe_text(
            record.get("source", ""), field="evidence source", maximum=512)
        verified_by = _safe_text(
            record.get("verified_by", ""),
            field="evidence verified_by",
            maximum=128,
        )
        if verified_by == agent_id:
            raise ValueError(
                f"verified evidence {reference!r} was self-verified by the agent")
        verification_reference = _safe_text(
            record.get("verification_reference", ""),
            field="evidence verification_reference",
            maximum=512,
        )
        raw_supports = record.get("supports") or ()
        if isinstance(raw_supports, (str, bytes)):
            raise ValueError(
                f"evidence supports for {reference!r} must be a sequence")
        supports = tuple(sorted({
            _safe_text(value, field="evidence support", maximum=128)
            for value in raw_supports
            if str(value or "").strip() in allowed_supports
        }))
        if not supports:
            raise ValueError(
                f"verified evidence {reference!r} has no supported revision action")
        value = _safe_text(
            record.get("value", ""), field="evidence value", maximum=500)
        evidence_rows.append(SelfReviewEvidence(
            reference=reference,
            source=source,
            supports=supports,
            value=value,
            verified_by=verified_by,
            verification_reference=verification_reference,
        ))
        if len(evidence_rows) > MAX_REVIEW_EVIDENCE:
            raise ValueError(
                "self-review evidence exceeds the bounded snapshot limit of "
                f"{MAX_REVIEW_EVIDENCE}")
    return tuple(evidence_rows)


def build_self_review_snapshot(
    profile: AgentIdentityProfile,
    *,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    pending_proposals: Sequence[SelfRevisionProposal] = (),
) -> SelfReviewSnapshot:
    """Create a safe snapshot containing only this agent's reviewable evidence."""
    _require_bounded_count(
        profile.known_failures,
        field="known_failures",
        maximum=MAX_KNOWN_FAILURES,
    )
    _require_bounded_count(
        profile.stable_lessons,
        field="stable_lessons",
        maximum=MAX_STABLE_LESSONS,
    )
    _require_bounded_count(
        profile.soul_principles,
        field="soul_principles",
        maximum=MAX_SOUL_PRINCIPLES,
    )
    if isinstance(pending_proposals, (str, bytes)):
        raise ValueError("pending_proposals must be a sequence, not text")

    pending_ids = []
    seen = set()
    for proposal in pending_proposals:
        if not isinstance(proposal, SelfRevisionProposal):
            raise ValueError("pending_proposals must contain SelfRevisionProposal values")
        if proposal.agent_id != profile.agent_id:
            raise ValueError("pending proposal belongs to another agent")
        if proposal.proposal_id not in seen:
            pending_ids.append(proposal.proposal_id)
            seen.add(proposal.proposal_id)
        if len(pending_ids) > MAX_PENDING_PROPOSALS:
            raise ValueError(
                "pending self-revision proposals exceed the bounded snapshot "
                f"limit of {MAX_PENDING_PROPOSALS}")

    governed = profile_fingerprint(profile)
    return SelfReviewSnapshot(
        agent_id=_safe_text(profile.agent_id, field="agent_id", maximum=128),
        profile_fingerprint=governed,
        governed_profile_fingerprint=governed,
        observational_profile_fingerprint=(
            observational_profile_fingerprint(profile)),
        identity_version=_safe_text(
            profile.identity_version, field="identity_version", maximum=64),
        promotion_status=_safe_text(
            profile.promotion_status, field="promotion_status", maximum=128),
        role_strengths=_public_strengths(profile),
        known_failures=tuple(
            _safe_text(value, field="known failure", maximum=500)
            for value in profile.known_failures
        ),
        stable_lessons=tuple(
            _safe_text(value, field="stable lesson", maximum=128)
            for value in profile.stable_lessons
        ),
        soul_principles=tuple(
            _safe_text(value, field="soul principle", maximum=500)
            for value in profile.soul_principles
        ),
        verified_evidence=_eligible_evidence(
            profile.agent_id, evidence_manifest),
        pending_proposal_ids=tuple(pending_ids),
    )


def build_self_revision_instruction(snapshot: SelfReviewSnapshot) -> str:
    """Render the exact, bounded task that may be given to the reviewed agent."""
    allowed_references = [
        evidence.reference for evidence in snapshot.verified_evidence
    ]
    schema = {
        "proposal_id": "filesystem-safe unique id",
        "agent_id": snapshot.agent_id,
        "proposed_by": snapshot.agent_id,
        "target": "identity | memory | soul",
        "action": "one allowed action for the target",
        "value": "the exact evidence-supported value",
        "reason": "why the change is warranted",
        "evidence_references": allowed_references,
        "risk": "how this self-change could be wrong or harmful",
        "status": "proposed",
    }
    instruction = "\n".join([
        "SELF-REVIEW TASK (proposal only; no authority)",
        "Return exactly one JSON object and nothing else.",
        "You may propose at most one change to your own descriptive identity.",
        "Cite only evidence references listed in the snapshot.",
        "Do not request promotion, permissions, role changes, or prompt execution.",
        "A proposal can be rejected and never activates without external approval.",
        "",
        "Required output schema:",
        json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2),
        "",
        "Self-review snapshot:",
        json.dumps(
            snapshot.to_record(), ensure_ascii=False, sort_keys=True, indent=2),
    ])
    size = len(instruction.encode("utf-8"))
    if size > MAX_INSTRUCTION_BYTES:
        raise ValueError(
            f"self-review instruction is {size} bytes; maximum is "
            f"{MAX_INSTRUCTION_BYTES}")
    return instruction


def render_self_review_summary(snapshot: SelfReviewSnapshot) -> str:
    """Human-readable summary; the instruction above is the machine task form."""
    lines = [
        "SELF-REVIEW SNAPSHOT (descriptive, proposal-only)",
        "=" * 49,
        f"Agent: {snapshot.agent_id}",
        f"Identity: {snapshot.identity_version} / {snapshot.promotion_status}",
        f"Governed fingerprint: {snapshot.profile_fingerprint}",
        f"Observational fingerprint: {snapshot.observational_profile_fingerprint}",
        f"Snapshot fingerprint: {snapshot.snapshot_fingerprint}",
        f"Verified evidence records: {len(snapshot.verified_evidence)}",
        f"Pending proposals: {len(snapshot.pending_proposal_ids)}",
        "Known failures:",
    ]
    lines.extend(f"  - {value}" for value in snapshot.known_failures)
    if not snapshot.known_failures:
        lines.append("  - none recorded")
    lines.append("Approved soul principles:")
    lines.extend(f"  - {value}" for value in snapshot.soul_principles)
    if not snapshot.soul_principles:
        lines.append("  - none recorded")
    lines.append("Evidence provenance:")
    for evidence in snapshot.verified_evidence:
        lines.append(
            f"  - {evidence.reference}: {evidence.verified_by} "
            f"({evidence.verification_reference})")
    if not snapshot.verified_evidence:
        lines.append("  - none available")
    lines.append("Boundaries:")
    lines.extend(f"  - {value}" for value in snapshot.boundaries)
    return "\n".join(lines)
