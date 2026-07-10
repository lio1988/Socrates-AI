"""Causally isolated public self-revision lifecycle registry.

Ordinary governed changes are applied one at a time per agent. This preserves a
clean causal interpretation for post-change evidence: a probation result refers
to one changed governed variable, not an uncontrolled bundle of simultaneous
Soul/Memory/Identity edits.

The only permitted overlap is a canonical inverse proposal applied while its
original revision is probationary. This creates a temporary two-record reversal
pair. The later inverse must be independently confirmed before the original may
be marked ``reverted``. Thus rollback means an applied and verified inverse, not
merely rollback intent.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Tuple

from .identity_profile import AgentIdentityProfile
from .revision_registry import (
    _SAFE_ID_RE,
    _build_event,
    _clean_text,
    _validate_non_self,
    _validate_outcome_evidence,
)
from .revision_registry_bound import (
    REGISTRY_SCHEMA_VERSION,
    SelfRevisionRegistry as _BoundRegistry,
)
from .revision_reversal import is_canonical_reversal
from .self_review import profile_fingerprint
from .self_revision import proposal_from_record


def _applied_event(record: Mapping[str, Any]) -> Mapping[str, Any]:
    events = [
        event for event in record.get("events", [])
        if event.get("event_type") == "applied"
    ]
    if len(events) != 1:
        raise ValueError(
            "applied self-revision lifecycle requires exactly one applied event")
    return events[0]


def _proposal(record: Mapping[str, Any]):
    return proposal_from_record(
        record["proposal"], expected_agent_id=record["agent_id"])


def _canonical_pair(
    original: Mapping[str, Any],
    inverse: Mapping[str, Any],
) -> bool:
    return is_canonical_reversal(_proposal(original), _proposal(inverse))


def _application_order(record: Mapping[str, Any]) -> int:
    index = _applied_event(record).get("revision_index")
    if not isinstance(index, int) or index < 0:
        raise ValueError("applied lifecycle has an invalid revision index")
    return index


class SelfRevisionRegistry(_BoundRegistry):
    """Lifecycle registry with one-change-at-a-time causal isolation."""

    def _probationary_records(
        self,
        agent_id: str,
        *,
        exclude_proposal_id: str = "",
    ) -> List[Dict[str, Any]]:
        return [
            record for record in self.all_records(agent_id)
            if record["status"] == "probationary"
            and record["proposal_id"] != exclude_proposal_id
        ]

    def pending_reversal_pairs(
        self,
        agent_id: str = "",
    ) -> Tuple[Tuple[str, str], ...]:
        """Return original/inverse pairs while both revisions are probationary."""
        records = self.all_records(agent_id)
        by_agent: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            if record["status"] == "probationary":
                by_agent.setdefault(record["agent_id"], []).append(record)
        pairs = []
        for records_for_agent in by_agent.values():
            if len(records_for_agent) != 2:
                continue
            first, second = records_for_agent
            if _canonical_pair(first, second):
                original, inverse = first, second
            elif _canonical_pair(second, first):
                original, inverse = second, first
            else:
                continue
            if _application_order(original) > _application_order(inverse):
                original, inverse = inverse, original
            pairs.append((original["proposal_id"], inverse["proposal_id"]))
        return tuple(sorted(pairs))

    def ready_reversion_pairs(
        self,
        agent_id: str = "",
    ) -> Tuple[Tuple[str, str], ...]:
        """Return probationary originals whose later inverse is confirmed."""
        records = self.all_records(agent_id)
        pairs = []
        for original in records:
            if original["status"] != "probationary":
                continue
            for inverse in records:
                if inverse["agent_id"] != original["agent_id"]:
                    continue
                if inverse["status"] != "confirmed":
                    continue
                if not _canonical_pair(original, inverse):
                    continue
                if _application_order(original) < _application_order(inverse):
                    pairs.append(
                        (original["proposal_id"], inverse["proposal_id"]))
        return tuple(sorted(set(pairs)))

    def record_application(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        previous_profile: AgentIdentityProfile,
        updated_profile: AgentIdentityProfile,
        evidence_manifest: Mapping[str, Mapping[str, Any]],
        stable_lesson_ids: Iterable[str] = (),
        applied_by: str,
        application_reference: str,
        applied_on: str = "",
    ):
        """Apply one isolated change or one exact inverse of the active change."""
        active = self._probationary_records(
            agent_id, exclude_proposal_id=proposal_id)
        if len(active) > 1:
            raise ValueError(
                "agent has multiple probationary revisions; resolve recovery or "
                "reversal state before applying another change")
        if active:
            candidate = self.load(agent_id, proposal_id)
            if candidate is None:
                raise ValueError("self-revision proposal does not exist")
            original = active[0]
            if not _canonical_pair(original, candidate):
                raise ValueError(
                    "agent already has a probationary revision; only its exact "
                    "canonical inverse may be applied concurrently")
            original_applied = _applied_event(original)
            if original_applied["profile_fingerprint"] != \
                    profile_fingerprint(previous_profile):
                raise ValueError(
                    "inverse application baseline does not equal the original "
                    "probationary governed state")
            if candidate["profile_fingerprint"] != \
                    profile_fingerprint(previous_profile):
                raise ValueError(
                    "inverse proposal is not bound to the current governed state")

        return super().record_application(
            agent_id,
            proposal_id,
            previous_profile=previous_profile,
            updated_profile=updated_profile,
            evidence_manifest=evidence_manifest,
            stable_lesson_ids=stable_lesson_ids,
            applied_by=applied_by,
            application_reference=application_reference,
            applied_on=applied_on,
        )

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
        """Record confirmation or a rollback completed by a confirmed inverse."""
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision proposal does not exist")
            if record["status"] != "probationary":
                raise ValueError("outcome requires a probationary applied revision")
            if current_profile.agent_id != agent_id:
                raise ValueError("current profile belongs to another agent")

            proposal = _proposal(record)
            outcome = _clean_text(outcome, field="outcome", maximum=32)
            if outcome not in {"confirmed", "reverted"}:
                raise ValueError("outcome must be confirmed or reverted")
            actor = _clean_text(recorded_by, field="recorded_by", maximum=128)
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
            current_fingerprint = profile_fingerprint(current_profile)
            current_applied = _applied_event(record)
            if outcome == "confirmed":
                if linked:
                    raise ValueError(
                        "confirmed outcome must not link a reversal proposal")
                if current_fingerprint != current_applied["profile_fingerprint"]:
                    raise ValueError(
                        "governed identity changed before confirmation review")
                for candidate in self._probationary_records(
                        agent_id, exclude_proposal_id=proposal_id):
                    if not (_canonical_pair(record, candidate)
                            or _canonical_pair(candidate, record)):
                        continue
                    if _application_order(candidate) > \
                            _application_order(record):
                        raise ValueError(
                            "cannot confirm a revision after its later inverse "
                            "was applied")
            else:
                if not _SAFE_ID_RE.fullmatch(linked) or linked == proposal_id:
                    raise ValueError(
                        "reverted outcome requires a new linked reversal proposal id")
                inverse = self._load_path(self._path_for(agent_id, linked))
                if inverse is None:
                    raise ValueError("linked reversal proposal does not exist")
                if inverse["status"] != "confirmed":
                    raise ValueError(
                        "linked reversal must be applied and confirmed before "
                        "the original is reverted")
                if not _canonical_pair(record, inverse):
                    raise ValueError(
                        "linked proposal is not a canonical reversal")
                if _application_order(inverse) <= _application_order(record):
                    raise ValueError(
                        "linked reversal was not applied after the original")
                if inverse["profile_fingerprint"] != \
                        current_applied["profile_fingerprint"]:
                    raise ValueError(
                        "inverse proposal was not authored from the original "
                        "probationary state")
                inverse_applied = _applied_event(inverse)
                if current_fingerprint != inverse_applied["profile_fingerprint"]:
                    raise ValueError(
                        "current governed profile does not contain the confirmed "
                        "inverse revision")

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

    def all_records(self, agent_id: str = "") -> List[Dict[str, Any]]:
        records = super().all_records(agent_id)
        by_agent: Dict[str, List[Dict[str, Any]]] = {}
        index = {
            (record["agent_id"], record["proposal_id"]): record
            for record in records
        }
        for record in records:
            if record["status"] == "probationary":
                by_agent.setdefault(record["agent_id"], []).append(record)
            if record["status"] == "reverted":
                linked_id = record["events"][-1]["linked_proposal_id"]
                linked = index.get((record["agent_id"], linked_id))
                if linked is None or not _canonical_pair(record, linked):
                    raise ValueError(
                        "reverted lifecycle does not reference a canonical inverse")
                if linked["status"] != "confirmed":
                    raise ValueError(
                        "reverted lifecycle requires a confirmed inverse")
                _applied_event(linked)

        for records_for_agent in by_agent.values():
            if len(records_for_agent) > 2:
                raise ValueError(
                    "agent has more than two probationary revisions")
            if len(records_for_agent) == 2:
                first, second = records_for_agent
                if not (_canonical_pair(first, second)
                        or _canonical_pair(second, first)):
                    raise ValueError(
                        "concurrent probationary revisions are not a canonical "
                        "original/inverse pair")
        return records


__all__ = ["REGISTRY_SCHEMA_VERSION", "SelfRevisionRegistry"]
