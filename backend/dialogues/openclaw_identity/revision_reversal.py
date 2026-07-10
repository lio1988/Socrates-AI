"""Governed rollback helpers for applied self-revisions.

Rollback never deletes or rewrites identity history. It creates a NEW inverse
``SelfRevisionProposal`` authored by the same agent, citing new evidence, and the
normal independent validation/non-self approval path applies again.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Tuple

from .identity_profile import AgentIdentityProfile
from .self_revision import SelfRevisionProposal

INVERSE_REVISION_ACTIONS: Mapping[Tuple[str, str], str] = {
    ("identity", "add_known_failure"): "resolve_known_failure",
    ("identity", "resolve_known_failure"): "add_known_failure",
    ("memory", "link_stable_lesson"): "unlink_stable_lesson",
    ("memory", "unlink_stable_lesson"): "link_stable_lesson",
    ("soul", "add_principle"): "retire_principle",
    ("soul", "retire_principle"): "add_principle",
}


def _entry_for(
    profile: AgentIdentityProfile,
    proposal_id: str,
) -> Mapping[str, object]:
    matches = [
        entry for entry in profile.revision_history
        if str(entry.get("proposal_id", "")) == proposal_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "rollback requires exactly one applied revision with that proposal_id")
    entry = matches[0]
    if entry.get("entry_type") != "self_revision":
        raise ValueError("rollback target is not a self-revision entry")
    return entry


def _effect_is_current(
    profile: AgentIdentityProfile,
    *,
    target: str,
    action: str,
    value: str,
) -> bool:
    if target == "identity":
        present = value in profile.known_failures
        return present if action == "add_known_failure" else not present
    if target == "memory":
        present = value in profile.stable_lessons
        return present if action == "link_stable_lesson" else not present
    if target == "soul":
        present = value in profile.soul_principles
        return present if action == "add_principle" else not present
    return False


def build_reversal_proposal(
    profile: AgentIdentityProfile,
    original_proposal_id: str,
    *,
    proposal_id: str,
    evidence_references: Iterable[str],
    reason: str,
    risk: str,
) -> SelfRevisionProposal:
    """Build a new inverse proposal without mutating or erasing old history."""
    if proposal_id == original_proposal_id:
        raise ValueError("rollback must use a new proposal_id")
    if any(str(entry.get("proposal_id", "")) == proposal_id
           for entry in profile.revision_history):
        raise ValueError("rollback proposal_id has already been applied")

    entry = _entry_for(profile, original_proposal_id)
    target = str(entry.get("target", ""))
    action = str(entry.get("action", ""))
    value = str(entry.get("value", ""))
    inverse = INVERSE_REVISION_ACTIONS.get((target, action))
    if inverse is None:
        raise ValueError("applied revision has no canonical inverse action")
    if not _effect_is_current(
        profile, target=target, action=action, value=value):
        raise ValueError(
            "original revision effect is no longer current; rollback would be stale")

    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=profile.agent_id,
        proposed_by=profile.agent_id,
        target=target,
        action=inverse,
        value=value,
        reason=reason,
        evidence_references=tuple(evidence_references),
        risk=risk,
    )


def is_canonical_reversal(
    original: SelfRevisionProposal,
    candidate: SelfRevisionProposal,
) -> bool:
    """Return whether ``candidate`` exactly reverses ``original``."""
    return (
        candidate.agent_id == original.agent_id
        and candidate.target == original.target
        and candidate.value == original.value
        and candidate.action == INVERSE_REVISION_ACTIONS.get(
            (original.target, original.action))
        and candidate.proposal_id != original.proposal_id
    )
