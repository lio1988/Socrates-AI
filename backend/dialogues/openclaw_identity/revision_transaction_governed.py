"""Transaction coordinator with causal-isolation and Memory-binding preflight.

A lifecycle registry may refuse an unrelated second probationary application.
That refusal, and every personal Memory evidence binding failure, must happen
before the transaction journal or Identity file changes—not after
``identity_saved``.
"""

from __future__ import annotations

from typing import Any, Mapping

from .identity_profile import AgentIdentityProfile, from_record
from .memory_evidence_binding import (
    memory_binding_reasons,
    stable_lesson_fingerprint_map,
)
from .revision_reversal import is_canonical_reversal
from .revision_transaction_recovery import (
    SelfRevisionTransactionCoordinator as _RecoveryCoordinator,
)
from .self_review import profile_fingerprint
from .self_revision import proposal_from_record


def _applied_event(record: Mapping[str, Any]) -> Mapping[str, Any]:
    events = [
        event for event in record.get("events", [])
        if event.get("event_type") == "applied"
    ]
    if len(events) != 1:
        raise ValueError(
            "probationary lifecycle requires exactly one applied event")
    return events[0]


class SelfRevisionTransactionCoordinator(_RecoveryCoordinator):
    """Recoverable coordinator that refuses inadmissible changes pre-write."""

    def _preflight_application(
        self,
        agent_id: str,
        proposal_id: str,
        previous_profile: AgentIdentityProfile,
    ) -> None:
        candidate = self.lifecycle_registry.load(agent_id, proposal_id)
        if candidate is None:
            raise ValueError("self-revision proposal does not exist")
        active = [
            record for record in self.lifecycle_registry.all_records(agent_id)
            if record["status"] == "probationary"
            and record["proposal_id"] != proposal_id
        ]
        if len(active) > 1:
            raise ValueError(
                "agent has multiple probationary revisions; transaction refused")
        if not active:
            return

        original = active[0]
        original_proposal = proposal_from_record(
            original["proposal"], expected_agent_id=agent_id)
        candidate_proposal = proposal_from_record(
            candidate["proposal"], expected_agent_id=agent_id)
        if not is_canonical_reversal(original_proposal, candidate_proposal):
            raise ValueError(
                "agent already has a probationary revision; transaction may "
                "apply only its exact canonical inverse")
        current = profile_fingerprint(previous_profile)
        if _applied_event(original)["profile_fingerprint"] != current:
            raise ValueError(
                "inverse transaction baseline does not match active probation")
        if candidate["profile_fingerprint"] != current:
            raise ValueError(
                "inverse proposal is not bound to current governed identity")

    def _preflight_memory_binding(
        self,
        agent_id: str,
        proposal_id: str,
        previous_profile: AgentIdentityProfile,
        *,
        evidence_manifest,
        stable_lesson_fingerprints=None,
    ) -> None:
        lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
        if lifecycle is None:
            raise ValueError("self-revision lifecycle is missing")
        proposal = proposal_from_record(
            lifecycle["proposal"], expected_agent_id=agent_id)
        fingerprints = stable_lesson_fingerprint_map(
            stable_lesson_fingerprints)
        reasons = memory_binding_reasons(
            proposal,
            current_profile=previous_profile,
            evidence_manifest=evidence_manifest,
            stable_lesson_fingerprints=fingerprints,
        )
        if reasons:
            raise ValueError(reasons[0])

    def apply_approved(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        evidence_manifest,
        stable_lesson_ids=(),
        stable_lesson_fingerprints=None,
        applied_by: str,
        application_reference: str,
        applied_on: str = "",
    ):
        previous = self.identity_registry.load_profile(agent_id)
        if previous is None:
            raise ValueError("identity profile does not exist")
        self._preflight_memory_binding(
            agent_id,
            proposal_id,
            previous,
            evidence_manifest=evidence_manifest,
            stable_lesson_fingerprints=stable_lesson_fingerprints,
        )
        self._preflight_application(agent_id, proposal_id, previous)
        return super().apply_approved(
            agent_id,
            proposal_id,
            evidence_manifest=evidence_manifest,
            stable_lesson_ids=stable_lesson_ids,
            applied_by=applied_by,
            application_reference=application_reference,
            applied_on=applied_on,
        )

    def _continue_locked(self, path, record):
        state = record.get("state")
        if state is None:
            from .revision_transaction import _validate_record
            state = _validate_record(record)
        if state == "prepared":
            payload = record["payload"]
            previous = from_record(payload["previous_profile"])
            self._preflight_application(
                record["agent_id"], record["proposal_id"], previous)
        return super()._continue_locked(path, record)


__all__ = ["SelfRevisionTransactionCoordinator"]
