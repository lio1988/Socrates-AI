"""Strict public self-revision lifecycle registry.

The base registry already binds proposal, snapshot, evidence, decision, and
application. This wrapper closes the final rollback gap: an original revision
may be marked ``reverted`` only after its canonical inverse proposal has itself
been applied and confirmed against the current identity profile.

This module is exported as the package-level ``SelfRevisionRegistry``. The base
implementation remains isolated for compatibility and low-level migration tests.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .identity_profile import AgentIdentityProfile
from .revision_registry import (
    SelfRevisionRegistry as _BaseSelfRevisionRegistry,
    _SAFE_ID_RE,
    _build_event,
    _clean_text,
    _digest,
    _validate_non_self,
    _validate_outcome_evidence,
)
from .revision_reversal import is_canonical_reversal
from .self_review import SNAPSHOT_VERSION, SelfReviewSnapshot, profile_fingerprint
from .self_revision import SelfRevisionProposal, proposal_from_record


def _single_applied_event(record: Mapping[str, Any]) -> Mapping[str, Any]:
    events = [
        event for event in record.get("events", ())
        if event.get("event_type") == "applied"
    ]
    if len(events) != 1:
        raise ValueError(
            "applied lifecycle requires exactly one application event")
    return events[0]


def _bind_applied_record_to_profile(
    record: Mapping[str, Any],
    profile: AgentIdentityProfile,
) -> Mapping[str, Any]:
    """Require the profile history entry committed by the lifecycle event."""
    event = _single_applied_event(record)
    index = event.get("revision_index")
    if not isinstance(index, int) or index < 0 or index >= len(
            profile.revision_history):
        raise ValueError(
            "applied lifecycle revision index is absent from current identity history")
    entry = profile.revision_history[index]
    if str(entry.get("proposal_id", "")) != str(record.get("proposal_id", "")):
        raise ValueError(
            "applied lifecycle points to a different identity revision entry")
    if _digest(entry) != event.get("revision_entry_digest"):
        raise ValueError(
            "identity revision entry no longer matches lifecycle application digest")
    return event


class SelfRevisionRegistry(_BaseSelfRevisionRegistry):
    """Governed registry with rollback completion and profile reconciliation."""

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        snapshot: SelfReviewSnapshot,
        submitted_on: str = "",
    ):
        if snapshot.snapshot_version != SNAPSHOT_VERSION:
            raise ValueError(
                "self-revision snapshot version is not the current governed version")
        return super().submit(
            proposal,
            snapshot=snapshot,
            submitted_on=submitted_on,
        )

    def all_records(self, agent_id: str = ""):
        records = super().all_records(agent_id)
        index = {
            (record["agent_id"], record["proposal_id"]): record
            for record in records
        }
        for record in records:
            if record.get("status") != "reverted":
                continue
            linked_id = record["events"][-1]["linked_proposal_id"]
            linked = index.get((record["agent_id"], linked_id))
            if linked is None:
                raise ValueError(
                    "reverted lifecycle points to a missing reversal proposal")
            if linked.get("status") != "confirmed":
                raise ValueError(
                    "reverted lifecycle requires a confirmed reversal proposal")
            _single_applied_event(linked)
        return records

    def record_outcome(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        current_profile: AgentIdentityProfile,
        outcome: str,
        evidence_manifest: Mapping[str, Mapping[str, Any]],
        recorded_by: str,
        evidence_reference: str,
        linked_proposal_id: str = "",
        recorded_on: str = "",
    ):
        """Finalize probation only when the profile proves the claimed outcome.

        ``confirmed`` requires the current profile to equal the original applied
        state. ``reverted`` requires a canonical inverse lifecycle that is already
        confirmed and whose applied profile is exactly the current profile.
        """
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision proposal does not exist")
            if record["status"] != "probationary":
                raise ValueError(
                    "outcome requires a probationary applied revision")
            if current_profile.agent_id != agent_id:
                raise ValueError("current profile belongs to another agent")

            proposal = proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
            original_applied = _bind_applied_record_to_profile(
                record, current_profile)
            outcome = _clean_text(outcome, field="outcome", maximum=32)
            if outcome not in {"confirmed", "reverted"}:
                raise ValueError("outcome must be confirmed or reverted")

            actor = _clean_text(
                recorded_by, field="recorded_by", maximum=128)
            _validate_non_self(actor, agent_id, action="confirm or revert")
            evidence_ref = _clean_text(
                evidence_reference, field="evidence_reference", maximum=512)
            outcome_digest, evidence_verifier = _validate_outcome_evidence(
                proposal,
                outcome=outcome,
                reference=evidence_ref,
                evidence_manifest=evidence_manifest,
            )
            if actor == evidence_verifier:
                raise ValueError(
                    "outcome evidence verification and final outcome review must "
                    "be performed by different actors")

            linked = str(linked_proposal_id or "").strip()
            if outcome == "confirmed":
                if linked:
                    raise ValueError(
                        "confirmed outcome must not link a reversal proposal")
                if profile_fingerprint(current_profile) != \
                        original_applied["profile_fingerprint"]:
                    raise ValueError(
                        "post-change identity state changed before confirmation")
            else:
                if not _SAFE_ID_RE.fullmatch(linked) or linked == proposal_id:
                    raise ValueError(
                        "reverted outcome requires a new linked reversal proposal id")
                linked_record = self._load_path(
                    self._path_for(agent_id, linked))
                if linked_record is None:
                    raise ValueError("linked reversal proposal does not exist")
                candidate = proposal_from_record(
                    linked_record["proposal"], expected_agent_id=agent_id)
                if not is_canonical_reversal(proposal, candidate):
                    raise ValueError(
                        "linked proposal is not a canonical reversal")
                if linked_record.get("status") != "confirmed":
                    raise ValueError(
                        "linked reversal proposal must be applied and confirmed "
                        "before the original can be marked reverted")
                linked_applied = _bind_applied_record_to_profile(
                    linked_record, current_profile)
                if profile_fingerprint(current_profile) != \
                        linked_applied["profile_fingerprint"]:
                    raise ValueError(
                        "current identity profile does not equal the confirmed "
                        "reversal result")

            event = _build_event(
                record["events"],
                event_type="outcome",
                actor=actor,
                on=recorded_on,
                outcome=outcome,
                evidence_reference=evidence_ref,
                outcome_evidence_digest=outcome_digest,
                linked_proposal_id=linked,
            )
            record.pop("status", None)
            record["events"].append(event)
            return self._atomic_write(path, record)
