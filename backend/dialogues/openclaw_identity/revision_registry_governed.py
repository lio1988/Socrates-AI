"""Bounded governed public lifecycle for agent self-revision proposals.

This layer extends causal isolation with admission control and current-state
Memory evidence binding:

- at most eight active proposals per agent;
- no two active proposals may request the same target/action/value change;
- personal Memory proposals require bound single-agent Lesson A/B evidence;
- evaluation and decision recheck current governed Identity and lesson revision;
- terminal history remains unlimited and append-only;
- canonical inverse proposals remain possible because their action differs from
  the original proposal.

The limit prevents proposal flooding from turning human review and audit into a
denial-of-service surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from .memory_evidence_binding import (
    lesson_fingerprint_map,
    memory_binding_reasons,
    parse_memory_ab_binding,
)
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

    def _proposal_for(self, agent_id: str, proposal_id: str):
        record = self.load(agent_id, proposal_id)
        if record is None:
            raise ValueError("self-revision proposal does not exist")
        return proposal_from_record(
            record["proposal"], expected_agent_id=agent_id)

    def _preflight_memory_binding(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        current_profile,
        evidence_manifest,
        lesson_fingerprints=None,
    ) -> None:
        proposal = self._proposal_for(agent_id, proposal_id)
        reasons = memory_binding_reasons(
            proposal,
            current_profile=current_profile,
            evidence_manifest=evidence_manifest,
            lesson_fingerprints=lesson_fingerprints,
        )
        if reasons:
            raise ValueError(reasons[0])

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        snapshot,
        submitted_on: str = "",
    ):
        # Identity collision outranks admission control: resubmitting an
        # existing proposal_id must fail as an ID conflict (the base
        # registry's own refusal), never as a semantic duplicate of itself.
        existing_ids = {
            record["proposal_id"]
            for record in self.all_records(proposal.agent_id)
        }
        if proposal.proposal_id in existing_ids:
            raise ValueError(
                "self-revision proposal_id already exists in registry")
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

        if proposal.target == "memory":
            by_reference = {
                evidence.reference: evidence
                for evidence in snapshot.verified_evidence
            }
            for reference in proposal.evidence_references:
                evidence = by_reference.get(reference)
                if evidence is None:
                    continue  # base submit reports absence from snapshot
                binding = parse_memory_ab_binding(evidence.source)
                if binding is None:
                    raise ValueError(
                        "Memory proposal evidence is not bound single-agent "
                        "Lesson A/B evidence")
                _lesson, identity, _experiment = binding
                if identity != snapshot.profile_fingerprint:
                    raise ValueError(
                        "Memory proposal evidence is stale for the bound "
                        "self-review Identity")

        return super().submit(
            proposal,
            snapshot=snapshot,
            submitted_on=submitted_on,
        )

    def record_evaluation(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        current_profile,
        evidence_manifest,
        stable_lesson_ids=(),
        lesson_fingerprints=None,
        evaluated_by: str = "evidence-harness",
        evaluated_on: str = "",
    ):
        fingerprints = lesson_fingerprint_map(lesson_fingerprints)
        self._preflight_memory_binding(
            agent_id,
            proposal_id,
            current_profile=current_profile,
            evidence_manifest=evidence_manifest,
            lesson_fingerprints=fingerprints,
        )
        return super().record_evaluation(
            agent_id,
            proposal_id,
            current_profile=current_profile,
            evidence_manifest=evidence_manifest,
            stable_lesson_ids=stable_lesson_ids,
            evaluated_by=evaluated_by,
            evaluated_on=evaluated_on,
        )

    def record_decision(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        current_profile,
        evidence_manifest,
        stable_lesson_ids=(),
        lesson_fingerprints=None,
        decision: str,
        decided_by: str,
        decision_reference: str,
        decided_on: str = "",
    ):
        fingerprints = lesson_fingerprint_map(lesson_fingerprints)
        self._preflight_memory_binding(
            agent_id,
            proposal_id,
            current_profile=current_profile,
            evidence_manifest=evidence_manifest,
            lesson_fingerprints=fingerprints,
        )
        return super().record_decision(
            agent_id,
            proposal_id,
            current_profile=current_profile,
            evidence_manifest=evidence_manifest,
            stable_lesson_ids=stable_lesson_ids,
            decision=decision,
            decided_by=decided_by,
            decision_reference=decision_reference,
            decided_on=decided_on,
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
