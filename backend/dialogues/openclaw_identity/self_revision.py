"""
OpenClaw Agent Identity — governed self-revision proposals.

Agents may propose changes to their own descriptive memory/identity/soul record,
but they cannot activate those changes, approve themselves, or reach the CED
runtime through this module.

Lifecycle:

    agent proposal -> deterministic validation -> evidence check
    -> named non-self approval -> append-only profile revision

The proposal is untrusted input. The apply path recomputes validation against a
trusted evidence manifest and the stable lesson catalogue; a caller-supplied
``passed=True`` is never sufficient.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from .identity_profile import AgentIdentityProfile

REVISION_TARGET_ACTIONS: Mapping[str, Tuple[str, ...]] = {
    "identity": ("add_known_failure", "resolve_known_failure"),
    "memory": ("link_stable_lesson", "unlink_stable_lesson"),
    "soul": ("add_principle", "retire_principle"),
}

_PROPOSAL_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
_LESSON_ID_RE = re.compile(r"^LESSON-[A-Za-z0-9._-]+$")
_MAX_VALUE_LENGTH = 500
_MAX_REASON_LENGTH = 2000
_MAX_RISK_LENGTH = 2000


def _clean_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError(f"{field} contains control characters")
    return text


def _clean_references(values: Iterable[Any]) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("evidence_references must be a sequence, not text")
    refs = []
    seen = set()
    for value in values:
        reference = _clean_text(
            value, field="evidence reference", maximum=256)
        if reference not in seen:
            refs.append(reference)
            seen.add(reference)
    if not refs:
        raise ValueError("self-revision proposal requires evidence references")
    return tuple(refs)


def _support_key(target: str, action: str) -> str:
    return f"{target}:{action}"


@dataclass(frozen=True)
class SelfRevisionProposal:
    """Untrusted, reviewable proposal authored by an agent about itself."""

    proposal_id: str
    agent_id: str
    proposed_by: str
    target: str
    action: str
    value: str
    reason: str
    evidence_references: Tuple[str, ...]
    risk: str
    status: str = "proposed"

    def __post_init__(self) -> None:
        proposal_id = _clean_text(
            self.proposal_id, field="proposal_id", maximum=96)
        if not _PROPOSAL_ID_RE.fullmatch(proposal_id):
            raise ValueError("proposal_id must be filesystem-safe")
        agent_id = _clean_text(self.agent_id, field="agent_id", maximum=128)
        proposed_by = _clean_text(
            self.proposed_by, field="proposed_by", maximum=128)
        if proposed_by != agent_id:
            raise ValueError(
                "a self-revision proposal must be authored by the same agent")
        target = _clean_text(self.target, field="target", maximum=32)
        action = _clean_text(self.action, field="action", maximum=64)
        if target not in REVISION_TARGET_ACTIONS:
            raise ValueError(f"unknown self-revision target {target!r}")
        if action not in REVISION_TARGET_ACTIONS[target]:
            raise ValueError(
                f"action {action!r} is not valid for target {target!r}")
        value = _clean_text(
            self.value, field="value", maximum=_MAX_VALUE_LENGTH)
        if target == "memory" and not _LESSON_ID_RE.fullmatch(value):
            raise ValueError(
                "memory self-revisions must reference a LESSON-* id")
        reason = _clean_text(
            self.reason, field="reason", maximum=_MAX_REASON_LENGTH)
        risk = _clean_text(self.risk, field="risk", maximum=_MAX_RISK_LENGTH)
        refs = _clean_references(self.evidence_references)
        if self.status != "proposed":
            raise ValueError("agent self-revisions enter only as status='proposed'")

        object.__setattr__(self, "proposal_id", proposal_id)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "proposed_by", proposed_by)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "risk", risk)
        object.__setattr__(self, "evidence_references", refs)

    def to_record(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "proposed_by": self.proposed_by,
            "target": self.target,
            "action": self.action,
            "value": self.value,
            "reason": self.reason,
            "evidence_references": list(self.evidence_references),
            "risk": self.risk,
            "status": self.status,
        }


@dataclass(frozen=True)
class RevisionEvaluation:
    """A recommendation, never an activation."""

    proposal_id: str
    passed: bool
    reasons: Tuple[str, ...]
    evidence_used: Tuple[str, ...]


def proposal_from_record(
    record: Mapping[str, Any],
    *,
    expected_agent_id: str = "",
) -> SelfRevisionProposal:
    """Parse an untrusted agent-emitted mapping into the strict proposal schema."""
    allowed = {
        "proposal_id", "agent_id", "proposed_by", "target", "action", "value",
        "reason", "evidence_references", "risk", "status",
    }
    extras = set(record) - allowed
    if extras:
        raise ValueError(
            f"self-revision proposal contains unknown fields: {sorted(extras)}")
    raw_references = record.get("evidence_references") or ()
    if isinstance(raw_references, (str, bytes)):
        raise ValueError("evidence_references must be a sequence, not text")
    proposal = SelfRevisionProposal(
        proposal_id=record.get("proposal_id", ""),
        agent_id=record.get("agent_id", ""),
        proposed_by=record.get("proposed_by", ""),
        target=record.get("target", ""),
        action=record.get("action", ""),
        value=record.get("value", ""),
        reason=record.get("reason", ""),
        evidence_references=tuple(raw_references),
        risk=record.get("risk", ""),
        status=record.get("status", "proposed"),
    )
    if expected_agent_id and proposal.agent_id != expected_agent_id:
        raise ValueError(
            "self-revision proposal agent_id does not match the reviewed seat")
    return proposal


def evaluate_self_revision(
    proposal: SelfRevisionProposal,
    *,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    stable_lesson_ids: Iterable[str] = (),
) -> RevisionEvaluation:
    """Verify evidence ownership, provenance, and action-specific relevance."""
    support_key = _support_key(proposal.target, proposal.action)
    reasons = []
    matched = []

    for reference in proposal.evidence_references:
        evidence = evidence_manifest.get(reference)
        if not isinstance(evidence, Mapping):
            reasons.append(f"missing evidence reference: {reference}")
            continue
        if evidence.get("verified") is not True:
            reasons.append(f"evidence is not verified: {reference}")
            continue
        if str(evidence.get("agent_id", "")).strip() != proposal.agent_id:
            reasons.append(f"evidence belongs to another agent: {reference}")
            continue
        source = str(evidence.get("source", "")).strip()
        if not source:
            reasons.append(f"evidence has no auditable source: {reference}")
            continue
        supports = evidence.get("supports") or ()
        if isinstance(supports, (str, bytes)):
            reasons.append(f"evidence supports field is invalid: {reference}")
            continue
        if support_key not in {str(item).strip() for item in supports}:
            reasons.append(
                f"evidence does not support {support_key}: {reference}")
            continue
        matched.append(reference)

    stable = {
        str(lesson_id).strip()
        for lesson_id in stable_lesson_ids
        if str(lesson_id).strip()
    }
    if (proposal.target == "memory"
            and proposal.action == "link_stable_lesson"
            and proposal.value not in stable):
        reasons.append(
            f"lesson {proposal.value!r} is not in the stable/verified catalogue")

    passed = not reasons and len(matched) == len(proposal.evidence_references)
    if passed:
        reasons.append(
            f"{len(matched)} action-specific evidence record(s) verified")
    return RevisionEvaluation(
        proposal_id=proposal.proposal_id,
        passed=passed,
        reasons=tuple(reasons),
        evidence_used=tuple(matched),
    )


def _apply_action(
    known_failures: Sequence[str],
    stable_lessons: Sequence[str],
    soul_principles: Sequence[str],
    *,
    target: str,
    action: str,
    value: str,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    failures = list(known_failures)
    lessons = list(stable_lessons)
    principles = list(soul_principles)

    if target == "identity" and action == "add_known_failure":
        if value in failures:
            raise ValueError("known failure is already recorded")
        failures.append(value)
    elif target == "identity" and action == "resolve_known_failure":
        if value not in failures:
            raise ValueError("cannot resolve a known failure that is not recorded")
        failures.remove(value)
    elif target == "memory" and action == "link_stable_lesson":
        if value in lessons:
            raise ValueError("stable lesson is already linked")
        lessons.append(value)
    elif target == "memory" and action == "unlink_stable_lesson":
        if value not in lessons:
            raise ValueError("cannot unlink a stable lesson that is not linked")
        lessons.remove(value)
    elif target == "soul" and action == "add_principle":
        if value in principles:
            raise ValueError("soul principle is already recorded")
        principles.append(value)
    elif target == "soul" and action == "retire_principle":
        if value not in principles:
            raise ValueError("cannot retire a soul principle that is not recorded")
        principles.remove(value)
    else:
        raise ValueError(
            f"unsupported self-revision operation {target!r}/{action!r}")

    return tuple(failures), tuple(lessons), tuple(principles)


def approve_and_apply_self_revision(
    profile: AgentIdentityProfile,
    proposal: SelfRevisionProposal,
    evaluation: RevisionEvaluation,
    *,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    approved_by: str,
    approval_reference: str,
    stable_lesson_ids: Iterable[str] = (),
    approved_on: str = "",
) -> AgentIdentityProfile:
    """Return a new profile after independent validation and non-self approval."""
    if proposal.agent_id != profile.agent_id:
        raise ValueError("proposal agent_id does not match the identity profile")
    if any(entry.get("proposal_id") == proposal.proposal_id
           for entry in profile.revision_history):
        raise ValueError("self-revision proposal_id has already been applied")
    if evaluation.proposal_id != proposal.proposal_id:
        raise ValueError("revision evaluation does not match the proposal")
    if not evaluation.passed:
        raise ValueError("self-revision requires a passing evaluation")

    verified = evaluate_self_revision(
        proposal,
        evidence_manifest=evidence_manifest,
        stable_lesson_ids=stable_lesson_ids,
    )
    if not verified.passed:
        raise ValueError(
            "self-revision evidence does not pass independent re-evaluation: "
            f"{verified.reasons[0]}")

    approver = _clean_text(approved_by, field="approved_by", maximum=128)
    if approver == profile.agent_id:
        raise ValueError("an agent can never approve its own self-revision")
    approval_ref = _clean_text(
        approval_reference, field="approval_reference", maximum=512)

    failures, lessons, principles = _apply_action(
        profile.known_failures,
        profile.stable_lessons,
        profile.soul_principles,
        target=proposal.target,
        action=proposal.action,
        value=proposal.value,
    )
    entry = {
        "entry_type": "self_revision",
        "proposal_id": proposal.proposal_id,
        "target": proposal.target,
        "action": proposal.action,
        "value": proposal.value,
        "proposed_by": proposal.proposed_by,
        "reason": proposal.reason,
        "risk": proposal.risk,
        "evidence_support": _support_key(proposal.target, proposal.action),
        "evidence_references": list(verified.evidence_used),
        "approved_by": approver,
        "approved_on": approved_on,
        "approval_reference": approval_ref,
    }
    return dataclasses.replace(
        profile,
        known_failures=failures,
        stable_lessons=lessons,
        soul_principles=principles,
        revision_history=profile.revision_history + (entry,),
    )


def replay_revision_entry(
    known_failures: Sequence[str],
    stable_lessons: Sequence[str],
    soul_principles: Sequence[str],
    entry: Mapping[str, Any],
    *,
    agent_id: str,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    """Validate and replay one stored revision entry for registry integrity."""
    if entry.get("entry_type") != "self_revision":
        raise ValueError("revision history entry must be type 'self_revision'")
    required = {
        "proposal_id", "target", "action", "value", "proposed_by", "reason",
        "risk", "evidence_support", "evidence_references", "approved_by",
        "approval_reference",
    }
    if not required.issubset(entry):
        missing = sorted(required - set(entry))
        raise ValueError(
            f"revision history entry is missing fields: {missing}")
    raw_references = entry["evidence_references"]
    if isinstance(raw_references, (str, bytes)):
        raise ValueError("evidence_references must be a sequence, not text")

    proposal = SelfRevisionProposal(
        proposal_id=entry["proposal_id"],
        agent_id=agent_id,
        proposed_by=entry["proposed_by"],
        target=entry["target"],
        action=entry["action"],
        value=entry["value"],
        reason=entry["reason"],
        evidence_references=tuple(raw_references or ()),
        risk=entry["risk"],
    )
    expected_support = _support_key(proposal.target, proposal.action)
    if str(entry["evidence_support"]).strip() != expected_support:
        raise ValueError("revision evidence_support does not match its action")
    approver = _clean_text(entry["approved_by"], field="approved_by", maximum=128)
    if approver == agent_id:
        raise ValueError("an agent cannot approve its own self-revision")
    _clean_text(
        entry["approval_reference"],
        field="approval_reference",
        maximum=512,
    )
    return _apply_action(
        known_failures,
        stable_lessons,
        soul_principles,
        target=proposal.target,
        action=proposal.action,
        value=proposal.value,
    )
