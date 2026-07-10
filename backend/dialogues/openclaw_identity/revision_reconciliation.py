"""Read-only reconciliation between identity history and lifecycle records.

Each registry is internally append-only, but governance also requires them to
agree with each other. This module detects drift such as:

- an identity revision with no lifecycle application;
- a lifecycle marked applied while the identity history lacks its entry;
- a mismatched revision index or digest;
- a pre-application proposal already present in the profile;
- a reverted original whose applied canonical inverse is absent.

Nothing is mutated. Operators may fail closed with
``assert_revision_state_consistent`` before producing Soul Cards or status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from .identity_profile import AgentIdentityProfile
from .revision_registry import _digest
from .revision_reversal import is_canonical_reversal
from .self_revision import proposal_from_record

_PRE_APPLY_STATUSES = frozenset({
    "submitted",
    "evaluated_passed",
    "evaluated_failed",
    "approved",
    "rejected",
})
_APPLIED_STATUSES = frozenset({"probationary", "confirmed", "reverted"})


@dataclass(frozen=True)
class RevisionConsistencyReport:
    agent_id: str
    consistent: bool
    issues: Tuple[str, ...]
    profile_revision_count: int
    lifecycle_record_count: int

    def to_record(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "consistent": self.consistent,
            "issues": list(self.issues),
            "profile_revision_count": self.profile_revision_count,
            "lifecycle_record_count": self.lifecycle_record_count,
        }


def _single_applied_event(record: Mapping[str, Any]):
    events = [
        event for event in record.get("events", ())
        if event.get("event_type") == "applied"
    ]
    return events[0] if len(events) == 1 else None


def reconcile_revision_state(
    profile: AgentIdentityProfile,
    lifecycle_records: Iterable[Mapping[str, Any]],
) -> RevisionConsistencyReport:
    """Compare one agent profile with its complete validated lifecycle set."""
    records = tuple(lifecycle_records)
    issues = []
    lifecycle_by_id = {}
    for record in records:
        if not isinstance(record, Mapping):
            issues.append("lifecycle record is not a mapping")
            continue
        agent_id = str(record.get("agent_id", ""))
        proposal_id = str(record.get("proposal_id", ""))
        if agent_id != profile.agent_id:
            issues.append(
                f"lifecycle {proposal_id or '<unknown>'} belongs to another agent")
            continue
        if not proposal_id:
            issues.append("lifecycle record has no proposal_id")
            continue
        if proposal_id in lifecycle_by_id:
            issues.append(f"duplicate lifecycle proposal_id {proposal_id}")
            continue
        lifecycle_by_id[proposal_id] = record

    profile_by_id = {}
    for index, entry in enumerate(profile.revision_history):
        proposal_id = str(entry.get("proposal_id", ""))
        if not proposal_id:
            issues.append(f"identity revision index {index} has no proposal_id")
            continue
        if proposal_id in profile_by_id:
            issues.append(f"duplicate identity revision proposal_id {proposal_id}")
            continue
        profile_by_id[proposal_id] = (index, entry)

    for proposal_id, (index, entry) in profile_by_id.items():
        lifecycle = lifecycle_by_id.get(proposal_id)
        if lifecycle is None:
            issues.append(
                f"identity revision {proposal_id} has no lifecycle record")
            continue
        status = str(lifecycle.get("status", ""))
        if status not in _APPLIED_STATUSES:
            issues.append(
                f"identity revision {proposal_id} exists while lifecycle is {status}")
            continue
        applied = _single_applied_event(lifecycle)
        if applied is None:
            issues.append(
                f"applied lifecycle {proposal_id} lacks exactly one application event")
            continue
        if applied.get("revision_index") != index:
            issues.append(
                f"lifecycle {proposal_id} revision_index does not match identity history")
        if applied.get("revision_entry_digest") != _digest(entry):
            issues.append(
                f"lifecycle {proposal_id} digest does not match identity history")

    for proposal_id, lifecycle in lifecycle_by_id.items():
        status = str(lifecycle.get("status", ""))
        in_profile = proposal_id in profile_by_id
        if status in _PRE_APPLY_STATUSES and in_profile:
            issues.append(
                f"pre-application lifecycle {proposal_id} already appears in identity")
        elif status in _APPLIED_STATUSES and not in_profile:
            issues.append(
                f"applied lifecycle {proposal_id} is absent from identity history")
        elif status not in _PRE_APPLY_STATUSES | _APPLIED_STATUSES:
            issues.append(
                f"lifecycle {proposal_id} has unknown status {status!r}")

        if status != "reverted":
            continue
        events = lifecycle.get("events") or ()
        if not events:
            issues.append(f"reverted lifecycle {proposal_id} has no events")
            continue
        linked_id = str(events[-1].get("linked_proposal_id", ""))
        linked = lifecycle_by_id.get(linked_id)
        if linked is None:
            issues.append(
                f"reverted lifecycle {proposal_id} has no linked reversal record")
            continue
        if linked.get("status") not in {"probationary", "confirmed"}:
            issues.append(
                f"reverted lifecycle {proposal_id} links an unapplied reversal")
        linked_applied = _single_applied_event(linked)
        if linked_applied is None:
            issues.append(
                f"reverted lifecycle {proposal_id} links a reversal without one "
                "application event")
        try:
            original = proposal_from_record(
                lifecycle.get("proposal") or {},
                expected_agent_id=profile.agent_id,
            )
            candidate = proposal_from_record(
                linked.get("proposal") or {},
                expected_agent_id=profile.agent_id,
            )
        except ValueError:
            issues.append(
                f"reverted lifecycle {proposal_id} has an invalid proposal pair")
            continue
        if not is_canonical_reversal(original, candidate):
            issues.append(
                f"reverted lifecycle {proposal_id} links a non-canonical reversal")
        if linked_id not in profile_by_id:
            issues.append(
                f"applied reversal {linked_id} is absent from identity history")

    unique_issues = tuple(dict.fromkeys(issues))
    return RevisionConsistencyReport(
        agent_id=profile.agent_id,
        consistent=not unique_issues,
        issues=unique_issues,
        profile_revision_count=len(profile.revision_history),
        lifecycle_record_count=len(records),
    )


def assert_revision_state_consistent(
    profile: AgentIdentityProfile,
    lifecycle_records: Sequence[Mapping[str, Any]],
) -> None:
    report = reconcile_revision_state(profile, lifecycle_records)
    if not report.consistent:
        raise ValueError(
            "identity/lifecycle revision state is inconsistent: " +
            report.issues[0])
