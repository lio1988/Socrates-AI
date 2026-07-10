"""Bounded governed public lifecycle for agent self-revision proposals.

This layer extends causal isolation with admission control:

- at most eight active proposals per agent;
- no two active proposals may request the same target/action/value change;
- terminal history remains unlimited and append-only;
- canonical inverse proposals remain possible because their action differs from
  the original proposal.

The limit prevents proposal flooding from turning human review and audit into a
denial-of-service surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from .revision_registry_isolated import (
    REGISTRY_SCHEMA_VERSION,
    SelfRevisionRegistry as _IsolatedRegistry,
)
from .self_revision import SelfRevisionProposal, proposal_from_record

MAX_ACTIVE_PROPOSALS_PER_AGENT = 8
_ACTIVE_STATUSES = frozenset({
    "submitted",
    "evaluated_passed",
    "evaluated_failed",
    "approved",
    "probationary",
})


def _semantic_key(record: Mapping[str, Any]) -> Tuple[str, str, str]:
    proposal = proposal_from_record(
        record["proposal"], expected_agent_id=record["agent_id"])
    return proposal.target, proposal.action, proposal.value


class SelfRevisionRegistry(_IsolatedRegistry):
    """Causally isolated lifecycle with bounded active admission."""

    def _active_records(self, agent_id: str) -> List[Dict[str, Any]]:
        return [
            record for record in self.all_records(agent_id)
            if record["status"] in _ACTIVE_STATUSES
        ]

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        snapshot,
        submitted_on: str = "",
    ):
        active = self._active_records(proposal.agent_id)
        if len(active) >= MAX_ACTIVE_PROPOSALS_PER_AGENT:
            raise ValueError(
                "agent reached the active self-revision proposal limit of "
                f"{MAX_ACTIVE_PROPOSALS_PER_AGENT}")
        candidate_key = (proposal.target, proposal.action, proposal.value)
        duplicate = next(
            (record for record in active
             if _semantic_key(record) == candidate_key),
            None,
        )
        if duplicate is not None:
            raise ValueError(
                "an active self-revision already requests the same "
                "target/action/value change")
        return super().submit(
            proposal,
            snapshot=snapshot,
            submitted_on=submitted_on,
        )

    def all_records(self, agent_id: str = "") -> List[Dict[str, Any]]:
        records = super().all_records(agent_id)
        active_by_agent: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            if record["status"] in _ACTIVE_STATUSES:
                active_by_agent.setdefault(record["agent_id"], []).append(record)
        for agent, active in active_by_agent.items():
            if len(active) > MAX_ACTIVE_PROPOSALS_PER_AGENT:
                raise ValueError(
                    f"agent {agent!r} exceeds the active proposal limit")
            keys = [_semantic_key(record) for record in active]
            if len(set(keys)) != len(keys):
                raise ValueError(
                    f"agent {agent!r} has duplicate active semantic revisions")
        return records


__all__ = [
    "MAX_ACTIVE_PROPOSALS_PER_AGENT",
    "REGISTRY_SCHEMA_VERSION",
    "SelfRevisionRegistry",
]
