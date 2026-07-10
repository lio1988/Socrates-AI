"""Persistent lifecycle registry for agent-authored self-revision proposals.

The identity profile stores only approved descriptive effects. This registry
stores the complete proposal lifecycle around those effects:

    submitted -> evaluated -> approved/rejected -> applied -> confirmed/reverted

Each proposal is immutable, events are append-only and hash-chained, writes are
atomic, and every decision actor must be named and non-self. The hash chain is an
audit-integrity aid, not cryptographic authentication; external signatures or a
remote transparency log remain future work.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .identity_profile import AgentIdentityProfile
from .self_review import profile_fingerprint
from .self_revision import RevisionEvaluation, SelfRevisionProposal, proposal_from_record

REGISTRY_SCHEMA_VERSION = "openclaw_self_revision_registry_v1"

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATUSES = frozenset({"rejected", "confirmed", "reverted"})


def _clean_text(value: Any, *, field: str, maximum: int = 1000) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError(f"{field} contains control characters")
    return text


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _event_hash(event_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(event_without_hash).encode("utf-8")
    ).hexdigest()


def _record_status(events: Sequence[Mapping[str, Any]]) -> str:
    if not events:
        raise ValueError("revision registry record requires events")
    event_type = str(events[-1].get("event_type", ""))
    if event_type == "submitted":
        return "submitted"
    if event_type == "evaluated":
        return "evaluated_passed" if events[-1].get("passed") is True \
            else "evaluated_failed"
    if event_type == "decision":
        return str(events[-1].get("decision", ""))
    if event_type == "applied":
        return "probationary"
    if event_type == "outcome":
        return str(events[-1].get("outcome", ""))
    raise ValueError(f"unknown revision registry event type {event_type!r}")


def _build_event(
    events: Sequence[Mapping[str, Any]],
    *,
    event_type: str,
    actor: str,
    on: str = "",
    **fields: Any,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "event_index": len(events),
        "event_type": _clean_text(event_type, field="event_type", maximum=64),
        "actor": _clean_text(actor, field="event actor", maximum=128),
        "on": str(on or "").strip(),
        "prev_event_hash": (
            str(events[-1].get("event_hash", "")) if events else ""
        ),
    }
    event.update(fields)
    event["event_hash"] = _event_hash(event)
    return event


def _validate_non_self(actor: str, agent_id: str, *, action: str) -> None:
    if actor == agent_id:
        raise ValueError(f"an agent cannot {action} its own self-revision")


def _validate_hash_chain(events: Sequence[Mapping[str, Any]]) -> None:
    previous = ""
    for index, raw_event in enumerate(events):
        if not isinstance(raw_event, Mapping):
            raise ValueError("revision registry events must be mappings")
        event = dict(raw_event)
        if event.get("event_index") != index:
            raise ValueError("revision registry event indexes are not contiguous")
        if str(event.get("prev_event_hash", "")) != previous:
            raise ValueError("revision registry event hash chain is broken")
        supplied = str(event.pop("event_hash", ""))
        if not _HEX64_RE.fullmatch(supplied):
            raise ValueError("revision registry event hash is invalid")
        if _event_hash(event) != supplied:
            raise ValueError("revision registry event content does not match its hash")
        previous = supplied


def _validate_event_sequence(
    events: Sequence[Mapping[str, Any]],
    *,
    proposal: SelfRevisionProposal,
) -> None:
    _validate_hash_chain(events)
    if not events or events[0].get("event_type") != "submitted":
        raise ValueError("revision registry must start with a submitted event")
    if str(events[0].get("actor", "")) != proposal.agent_id:
        raise ValueError("submitted event must be authored by the reviewed agent")

    status = "submitted"
    for index, event in enumerate(events[1:], start=1):
        event_type = str(event.get("event_type", ""))
        actor = _clean_text(event.get("actor", ""), field="event actor", maximum=128)
        _validate_non_self(actor, proposal.agent_id, action="govern")

        if status in _TERMINAL_STATUSES:
            raise ValueError("terminal self-revision records cannot receive more events")

        if event_type == "evaluated":
            if status != "submitted":
                raise ValueError("self-revision can be evaluated exactly once after submit")
            if not isinstance(event.get("passed"), bool):
                raise ValueError("evaluation event requires boolean passed")
            reasons = event.get("reasons")
            evidence_used = event.get("evidence_used")
            if not isinstance(reasons, list) or not reasons:
                raise ValueError("evaluation event requires reasons")
            if not isinstance(evidence_used, list):
                raise ValueError("evaluation event requires evidence_used list")
            status = "evaluated_passed" if event["passed"] else "evaluated_failed"
            continue

        if event_type == "decision":
            if status not in {"evaluated_passed", "evaluated_failed"}:
                raise ValueError("decision requires a completed evaluation")
            decision = str(event.get("decision", ""))
            if decision not in {"approved", "rejected"}:
                raise ValueError("decision must be approved or rejected")
            if decision == "approved" and status != "evaluated_passed":
                raise ValueError("a failing evaluation cannot be approved")
            _clean_text(
                event.get("decision_reference", ""),
                field="decision_reference",
                maximum=512,
            )
            status = decision
            continue

        if event_type == "applied":
            if status != "approved":
                raise ValueError("profile application requires prior approval")
            fingerprint = str(event.get("profile_fingerprint", ""))
            if not _HEX64_RE.fullmatch(fingerprint):
                raise ValueError("applied event requires a profile fingerprint")
            revision_index = event.get("revision_index")
            if not isinstance(revision_index, int) or revision_index < 0:
                raise ValueError("applied event requires a non-negative revision_index")
            _clean_text(
                event.get("application_reference", ""),
                field="application_reference",
                maximum=512,
            )
            status = "probationary"
            continue

        if event_type == "outcome":
            if status != "probationary":
                raise ValueError("outcome requires a previously applied revision")
            outcome = str(event.get("outcome", ""))
            if outcome not in {"confirmed", "reverted"}:
                raise ValueError("outcome must be confirmed or reverted")
            _clean_text(
                event.get("evidence_reference", ""),
                field="outcome evidence_reference",
                maximum=512,
            )
            linked = str(event.get("linked_proposal_id", "")).strip()
            if outcome == "reverted":
                if not _SAFE_ID_RE.fullmatch(linked):
                    raise ValueError(
                        "reverted outcome requires a linked reversal proposal id")
                if linked == proposal.proposal_id:
                    raise ValueError("a reversal must use a new proposal id")
            elif linked:
                raise ValueError("confirmed outcome must not link a reversal proposal")
            status = outcome
            continue

        raise ValueError(
            f"unexpected event {event_type!r} at revision lifecycle index {index}")


def _validate_record(record: Mapping[str, Any]) -> Tuple[SelfRevisionProposal, str]:
    if not isinstance(record, Mapping):
        raise ValueError("revision registry record must be a mapping")
    if record.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError("unknown revision registry schema version")
    agent_id = _clean_text(record.get("agent_id", ""), field="agent_id", maximum=128)
    proposal_id = _clean_text(
        record.get("proposal_id", ""), field="proposal_id", maximum=128)
    if not _SAFE_ID_RE.fullmatch(agent_id) or not _SAFE_ID_RE.fullmatch(proposal_id):
        raise ValueError("revision registry ids must be filesystem-safe")
    proposal = proposal_from_record(
        record.get("proposal") or {}, expected_agent_id=agent_id)
    if proposal.proposal_id != proposal_id:
        raise ValueError("registry proposal_id does not match proposal payload")
    snapshot_fingerprint = str(record.get("snapshot_fingerprint", ""))
    if not _HEX64_RE.fullmatch(snapshot_fingerprint):
        raise ValueError("registry record requires a valid snapshot fingerprint")
    events = record.get("events")
    if not isinstance(events, list):
        raise ValueError("revision registry events must be a list")
    _validate_event_sequence(events, proposal=proposal)
    return proposal, _record_status(events)


class SelfRevisionRegistry:
    """Atomic per-proposal storage with an append-only lifecycle event chain."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path_for(self, agent_id: str, proposal_id: str) -> Path:
        if not _SAFE_ID_RE.fullmatch(agent_id or ""):
            raise ValueError("agent_id is not filesystem-safe")
        if not _SAFE_ID_RE.fullmatch(proposal_id or ""):
            raise ValueError("proposal_id is not filesystem-safe")
        return self.directory / agent_id / f"{proposal_id}.json"

    def _atomic_write(self, path: Path, record: Mapping[str, Any]) -> Path:
        _validate_record(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temp_path = Path(temporary.name)
            os.replace(temp_path, path)
            temp_path = None
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        return path

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        snapshot_fingerprint: str,
        submitted_on: str = "",
    ) -> Path:
        """Persist a new immutable proposal bound to one exact self-review snapshot."""
        if not _HEX64_RE.fullmatch(str(snapshot_fingerprint or "")):
            raise ValueError("submit requires a valid snapshot fingerprint")
        path = self._path_for(proposal.agent_id, proposal.proposal_id)
        if path.exists():
            raise ValueError("self-revision proposal_id already exists in registry")
        events: List[Dict[str, Any]] = []
        events.append(_build_event(
            events,
            event_type="submitted",
            actor=proposal.agent_id,
            on=submitted_on,
        ))
        record = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "agent_id": proposal.agent_id,
            "proposal_id": proposal.proposal_id,
            "snapshot_fingerprint": snapshot_fingerprint,
            "proposal": proposal.to_record(),
            "events": events,
        }
        return self._atomic_write(path, record)

    def load(self, agent_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(agent_id, proposal_id)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            _, status = _validate_record(record)
            record["status"] = status
            return record
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"self-revision registry record {path} is unreadable or corrupt"
            ) from exc

    def all_records(self, agent_id: str = "") -> List[Dict[str, Any]]:
        if not self.directory.exists():
            return []
        if agent_id:
            if not _SAFE_ID_RE.fullmatch(agent_id):
                raise ValueError("agent_id is not filesystem-safe")
            paths = sorted((self.directory / agent_id).glob("*.json"))
        else:
            paths = sorted(self.directory.glob("*/*.json"))
        records = []
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                _, status = _validate_record(record)
                record["status"] = status
                records.append(record)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"self-revision registry record {path} is unreadable or corrupt"
                ) from exc
        return records

    def _append(
        self,
        agent_id: str,
        proposal_id: str,
        event: Mapping[str, Any],
    ) -> Path:
        path = self._path_for(agent_id, proposal_id)
        record = self.load(agent_id, proposal_id)
        if record is None:
            raise ValueError("self-revision proposal does not exist")
        record.pop("status", None)
        events = list(record["events"])
        events.append(dict(event))
        record["events"] = events
        return self._atomic_write(path, record)

    def record_evaluation(
        self,
        agent_id: str,
        proposal_id: str,
        evaluation: RevisionEvaluation,
        *,
        evaluated_by: str = "system",
        evaluated_on: str = "",
    ) -> Path:
        record = self.load(agent_id, proposal_id)
        if record is None:
            raise ValueError("self-revision proposal does not exist")
        if record["status"] != "submitted":
            raise ValueError("self-revision can be evaluated only once after submit")
        if evaluation.proposal_id != proposal_id:
            raise ValueError("evaluation does not match proposal_id")
        actor = _clean_text(evaluated_by, field="evaluated_by", maximum=128)
        _validate_non_self(actor, agent_id, action="evaluate")
        event = _build_event(
            record["events"],
            event_type="evaluated",
            actor=actor,
            on=evaluated_on,
            passed=bool(evaluation.passed),
            reasons=list(evaluation.reasons),
            evidence_used=list(evaluation.evidence_used),
        )
        return self._append(agent_id, proposal_id, event)

    def record_decision(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        decision: str,
        decided_by: str,
        decision_reference: str,
        decided_on: str = "",
    ) -> Path:
        record = self.load(agent_id, proposal_id)
        if record is None:
            raise ValueError("self-revision proposal does not exist")
        if record["status"] not in {"evaluated_passed", "evaluated_failed"}:
            raise ValueError("decision requires a completed evaluation")
        decision = _clean_text(decision, field="decision", maximum=32)
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        if decision == "approved" and record["status"] != "evaluated_passed":
            raise ValueError("a failing evaluation cannot be approved")
        actor = _clean_text(decided_by, field="decided_by", maximum=128)
        _validate_non_self(actor, agent_id, action="approve or reject")
        reference = _clean_text(
            decision_reference, field="decision_reference", maximum=512)
        event = _build_event(
            record["events"],
            event_type="decision",
            actor=actor,
            on=decided_on,
            decision=decision,
            decision_reference=reference,
        )
        return self._append(agent_id, proposal_id, event)

    def record_application(
        self,
        agent_id: str,
        proposal_id: str,
        profile: AgentIdentityProfile,
        *,
        applied_by: str,
        application_reference: str,
        applied_on: str = "",
    ) -> Path:
        record = self.load(agent_id, proposal_id)
        if record is None:
            raise ValueError("self-revision proposal does not exist")
        if record["status"] != "approved":
            raise ValueError("profile application requires an approved proposal")
        if profile.agent_id != agent_id:
            raise ValueError("applied profile belongs to another agent")
        matching_indexes = [
            index for index, entry in enumerate(profile.revision_history)
            if entry.get("proposal_id") == proposal_id
        ]
        if len(matching_indexes) != 1:
            raise ValueError(
                "applied profile must contain exactly one matching revision entry")
        actor = _clean_text(applied_by, field="applied_by", maximum=128)
        _validate_non_self(actor, agent_id, action="apply")
        reference = _clean_text(
            application_reference,
            field="application_reference",
            maximum=512,
        )
        event = _build_event(
            record["events"],
            event_type="applied",
            actor=actor,
            on=applied_on,
            profile_fingerprint=profile_fingerprint(profile),
            revision_index=matching_indexes[0],
            application_reference=reference,
        )
        return self._append(agent_id, proposal_id, event)

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
    ) -> Path:
        record = self.load(agent_id, proposal_id)
        if record is None:
            raise ValueError("self-revision proposal does not exist")
        if record["status"] != "probationary":
            raise ValueError("outcome requires a probationary applied revision")
        outcome = _clean_text(outcome, field="outcome", maximum=32)
        if outcome not in {"confirmed", "reverted"}:
            raise ValueError("outcome must be confirmed or reverted")
        actor = _clean_text(recorded_by, field="recorded_by", maximum=128)
        _validate_non_self(actor, agent_id, action="confirm or revert")
        evidence_ref = _clean_text(
            evidence_reference, field="evidence_reference", maximum=512)
        linked = str(linked_proposal_id or "").strip()
        if outcome == "reverted":
            if not _SAFE_ID_RE.fullmatch(linked):
                raise ValueError(
                    "reverted outcome requires a linked reversal proposal id")
            if linked == proposal_id:
                raise ValueError("a reversal must use a new proposal id")
        elif linked:
            raise ValueError("confirmed outcome must not link a reversal proposal")
        event = _build_event(
            record["events"],
            event_type="outcome",
            actor=actor,
            on=recorded_on,
            outcome=outcome,
            evidence_reference=evidence_ref,
            linked_proposal_id=linked,
        )
        return self._append(agent_id, proposal_id, event)
