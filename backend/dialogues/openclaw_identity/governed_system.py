"""One safe integration surface for governed agent self-revision.

The lower-level modules remain independently testable, but production/operator
code should not hand-wire them. This facade always composes:

- strict IdentityRegistry;
- immutable RevisionEvidenceRegistry;
- bounded, deduplicated, causally isolated lifecycle registry;
- terminal-aware recoverable application transaction coordinator.

Every mutating method reloads current state and trusted evidence. Callers provide
named actors and references, not precomputed `passed=True` decisions or profiles.
No provider calls and no CED authority path exist here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple

from .identity_profile import AgentIdentityProfile
from .identity_registry import IdentityRegistry
from .revision_evidence import RevisionEvidenceRecord, RevisionEvidenceRegistry
from .revision_registry_governed import SelfRevisionRegistry
from .revision_transaction_recovery import SelfRevisionTransactionCoordinator
from .self_review import SelfReviewSnapshot, build_self_review_snapshot
from .self_revision import RevisionEvaluation, SelfRevisionProposal, proposal_from_record

_ACTIVE_STATUSES = frozenset({
    "submitted",
    "evaluated_passed",
    "evaluated_failed",
    "approved",
    "probationary",
})


@dataclass(frozen=True)
class GovernedSelfRevisionSystem:
    """Bound registries and operations for one local governance installation."""

    identity_registry: IdentityRegistry
    evidence_registry: RevisionEvidenceRegistry
    lifecycle_registry: SelfRevisionRegistry
    transaction_coordinator: SelfRevisionTransactionCoordinator

    @classmethod
    def from_root(cls, root: Path | str) -> "GovernedSelfRevisionSystem":
        root_path = Path(root)
        identity = IdentityRegistry(root_path / "identity")
        evidence = RevisionEvidenceRegistry(root_path / "evidence")
        lifecycle = SelfRevisionRegistry(root_path / "lifecycle")
        transactions = SelfRevisionTransactionCoordinator(
            identity,
            lifecycle,
            root_path / "transactions",
        )
        return cls(identity, evidence, lifecycle, transactions)

    def profile(self, agent_id: str) -> AgentIdentityProfile:
        profile = self.identity_registry.load_profile(agent_id)
        if profile is None:
            raise ValueError(f"identity profile {agent_id!r} does not exist")
        return profile

    def trusted_manifest(self, agent_id: str):
        return self.evidence_registry.manifest(agent_id)

    def active_proposals(self, agent_id: str) -> Tuple[SelfRevisionProposal, ...]:
        return tuple(
            proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
            for record in self.lifecycle_registry.all_records(agent_id)
            if record["status"] in _ACTIVE_STATUSES
        )

    def snapshot(self, agent_id: str) -> SelfReviewSnapshot:
        """Build a fresh snapshot from current identity, evidence, and queue."""
        return build_self_review_snapshot(
            self.profile(agent_id),
            evidence_manifest=self.trusted_manifest(agent_id),
            pending_proposals=self.active_proposals(agent_id),
        )

    def register_evidence(self, evidence: RevisionEvidenceRecord):
        return self.evidence_registry.register(evidence)

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        submitted_on: str = "",
    ):
        """Submit against a newly built bounded snapshot, never caller state."""
        snapshot = self.snapshot(proposal.agent_id)
        return self.lifecycle_registry.submit(
            proposal,
            snapshot=snapshot,
            submitted_on=submitted_on,
        )

    def evaluate(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        evaluated_by: str,
        stable_lesson_ids: Iterable[str] = (),
        evaluated_on: str = "",
    ) -> RevisionEvaluation:
        return self.lifecycle_registry.record_evaluation(
            agent_id,
            proposal_id,
            current_profile=self.profile(agent_id),
            evidence_manifest=self.trusted_manifest(agent_id),
            stable_lesson_ids=stable_lesson_ids,
            evaluated_by=evaluated_by,
            evaluated_on=evaluated_on,
        )

    def decide(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        decision: str,
        decided_by: str,
        decision_reference: str,
        stable_lesson_ids: Iterable[str] = (),
        decided_on: str = "",
    ):
        return self.lifecycle_registry.record_decision(
            agent_id,
            proposal_id,
            current_profile=self.profile(agent_id),
            evidence_manifest=self.trusted_manifest(agent_id),
            stable_lesson_ids=stable_lesson_ids,
            decision=decision,
            decided_by=decided_by,
            decision_reference=decision_reference,
            decided_on=decided_on,
        )

    def apply_approved(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        applied_by: str,
        application_reference: str,
        stable_lesson_ids: Iterable[str] = (),
        applied_on: str = "",
    ) -> AgentIdentityProfile:
        """Apply only through the write-ahead transaction coordinator."""
        return self.transaction_coordinator.apply_approved(
            agent_id,
            proposal_id,
            evidence_manifest=self.trusted_manifest(agent_id),
            stable_lesson_ids=stable_lesson_ids,
            applied_by=applied_by,
            application_reference=application_reference,
            applied_on=applied_on,
        )

    def recover(
        self,
        agent_id: str,
        proposal_id: str,
    ) -> AgentIdentityProfile:
        return self.transaction_coordinator.recover(agent_id, proposal_id)

    def record_outcome(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        outcome: str,
        recorded_by: str,
        evidence_reference: str,
        linked_proposal_id: str = "",
        recorded_on: str = "",
    ):
        return self.lifecycle_registry.record_outcome(
            agent_id,
            proposal_id,
            current_profile=self.profile(agent_id),
            outcome=outcome,
            evidence_manifest=self.trusted_manifest(agent_id),
            recorded_by=recorded_by,
            evidence_reference=evidence_reference,
            linked_proposal_id=linked_proposal_id,
            recorded_on=recorded_on,
        )

    def incomplete_transactions(self):
        return tuple(
            record
            for record in self.transaction_coordinator.all_transactions()
            if record["state"] != "committed"
        )


__all__ = ["GovernedSelfRevisionSystem"]
