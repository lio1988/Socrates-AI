"""Recoverable transaction coordinator for approved self-revision application.

Identity persistence and lifecycle persistence are separate atomic files. A
process failure between them could otherwise leave one side updated and the
other side still `approved`. This module adds a write-ahead journal:

    prepared -> identity_saved -> lifecycle_recorded -> committed

The journal stores the exact proposal, cited evidence, stable lesson catalogue,
application metadata, and previous/updated governed fingerprints. Its events are
append-only and hash-chained. Recovery inspects both registries and completes the
only transition consistent with the journal; ambiguous or conflicting state
fails closed.

This is recoverable atomicity across local files, not a distributed transaction
or cryptographic authentication layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .identity_profile import AgentIdentityProfile, from_record
from .identity_registry import IdentityRegistry
from .revision_registry import SelfRevisionRegistry
from .self_review import observational_profile_fingerprint, profile_fingerprint
from .self_revision import (
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    evaluate_self_revision,
    proposal_from_record,
)

TRANSACTION_SCHEMA_VERSION = "openclaw_self_revision_transaction_v1"

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)
_RECORD_FIELDS = {
    "schema_version", "agent_id", "proposal_id", "payload", "events",
}
_BASE_EVENT_FIELDS = {
    "event_index", "event_type", "actor", "on", "prev_event_hash", "event_hash",
}
_EVENT_FIELDS = {
    "prepared": _BASE_EVENT_FIELDS | {"payload_digest"},
    "identity_saved": _BASE_EVENT_FIELDS | {
        "governed_profile_fingerprint", "observational_profile_fingerprint",
    },
    "lifecycle_recorded": _BASE_EVENT_FIELDS | {
        "lifecycle_event_hash", "governed_profile_fingerprint",
    },
    "committed": _BASE_EVENT_FIELDS | {"commit_digest"},
}
_STATE_BY_EVENT = {
    "prepared": "prepared",
    "identity_saved": "identity_saved",
    "lifecycle_recorded": "lifecycle_recorded",
    "committed": "committed",
}
_MAX_EVENTS = 4


def _clean_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError(f"{field} contains control characters")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"{field} contains secret-shaped data matching {pattern.pattern!r}")
    return text


def _clean_optional_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    return _clean_text(text, field=field, maximum=maximum) if text else ""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("transaction data must be canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _find_secret(value: Any, path: str = "transaction") -> Optional[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            violation = _find_secret(child, f"{path}.{key}")
            if violation:
                return violation
        return None
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violation = _find_secret(child, f"{path}[{index}]")
            if violation:
                return violation
        return None
    if isinstance(value, str):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                return f"{path} contains secret-shaped data"
    return None


def _clean_stable_ids(values: Iterable[Any]) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("stable_lesson_ids must be a sequence, not text")
    stable = []
    seen = set()
    for value in values:
        lesson_id = _clean_text(
            value, field="stable lesson id", maximum=128)
        if not lesson_id.startswith("LESSON-"):
            raise ValueError("stable lesson ids must use LESSON-* format")
        if lesson_id not in seen:
            stable.append(lesson_id)
            seen.add(lesson_id)
    if len(stable) > 256:
        raise ValueError("stable_lesson_ids exceeds 256 entries")
    return tuple(stable)


def _cited_manifest(
    proposal: SelfRevisionProposal,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    if not isinstance(evidence_manifest, Mapping):
        raise ValueError("evidence_manifest must be a mapping")
    cited: Dict[str, Dict[str, Any]] = {}
    for reference in proposal.evidence_references:
        record = evidence_manifest.get(reference)
        if not isinstance(record, Mapping):
            raise ValueError(
                f"transaction is missing cited evidence {reference!r}")
        cited[reference] = dict(record)
    return cited


def _build_event(
    events: List[Dict[str, Any]],
    *,
    event_type: str,
    actor: str,
    on: str = "",
    **fields: Any,
) -> Dict[str, Any]:
    event_type = _clean_text(event_type, field="event_type", maximum=64)
    event: Dict[str, Any] = {
        "event_index": len(events),
        "event_type": event_type,
        "actor": _clean_text(actor, field="event actor", maximum=128),
        "on": _clean_optional_text(on, field="event date", maximum=64),
        "prev_event_hash": events[-1]["event_hash"] if events else "",
    }
    event.update(fields)
    expected = _EVENT_FIELDS.get(event_type)
    actual = set(event) | {"event_hash"}
    if expected is None or actual != expected:
        raise ValueError(f"transaction event {event_type!r} has invalid fields")
    event["event_hash"] = _digest(event)
    return event


def _validate_event_chain(events: Any) -> str:
    if not isinstance(events, list) or not events:
        raise ValueError("transaction requires a non-empty event list")
    if len(events) > _MAX_EVENTS:
        raise ValueError("transaction contains too many events")
    expected_order = [
        "prepared", "identity_saved", "lifecycle_recorded", "committed"]
    previous = ""
    for index, raw in enumerate(events):
        if not isinstance(raw, Mapping):
            raise ValueError("transaction events must be mappings")
        event = dict(raw)
        event_type = str(event.get("event_type", ""))
        if event_type != expected_order[index]:
            raise ValueError("transaction events are out of order")
        expected_fields = _EVENT_FIELDS[event_type]
        if set(event) != expected_fields:
            raise ValueError("transaction event contains invalid fields")
        if event.get("event_index") != index:
            raise ValueError("transaction event indexes are not contiguous")
        if str(event.get("prev_event_hash", "")) != previous:
            raise ValueError("transaction event hash chain is broken")
        supplied = str(event.pop("event_hash", ""))
        if not _HEX64_RE.fullmatch(supplied) or _digest(event) != supplied:
            raise ValueError("transaction event content does not match its hash")
        previous = supplied
    return _STATE_BY_EVENT[events[-1]["event_type"]]


def _decision_event(lifecycle: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = [
        event for event in lifecycle.get("events", [])
        if event.get("event_type") == "decision"
    ]
    if len(matches) != 1 or matches[0].get("decision") != "approved":
        raise ValueError("transaction requires exactly one approved decision")
    return matches[0]


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    agent_id: str,
    proposal_id: str,
) -> Tuple[SelfRevisionProposal, AgentIdentityProfile, AgentIdentityProfile]:
    required = {
        "proposal", "evidence_manifest", "stable_lesson_ids",
        "previous_profile", "updated_profile", "previous_governed_fingerprint",
        "updated_governed_fingerprint", "application_actor",
        "application_reference", "application_on",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise ValueError("transaction payload contains missing or unknown fields")
    proposal = proposal_from_record(
        payload["proposal"], expected_agent_id=agent_id)
    if proposal.proposal_id != proposal_id:
        raise ValueError("transaction proposal_id does not match payload")
    if not isinstance(payload["evidence_manifest"], Mapping):
        raise ValueError("transaction evidence_manifest must be a mapping")
    stable_ids = _clean_stable_ids(payload["stable_lesson_ids"])
    previous = from_record(payload["previous_profile"])
    updated = from_record(payload["updated_profile"])
    if previous.agent_id != agent_id or updated.agent_id != agent_id:
        raise ValueError("transaction profiles belong to another agent")
    if profile_fingerprint(previous) != payload["previous_governed_fingerprint"]:
        raise ValueError("transaction previous governed fingerprint is invalid")
    if profile_fingerprint(updated) != payload["updated_governed_fingerprint"]:
        raise ValueError("transaction updated governed fingerprint is invalid")
    _clean_text(
        payload["application_actor"], field="application_actor", maximum=128)
    _clean_text(
        payload["application_reference"],
        field="application_reference",
        maximum=512,
    )
    _clean_optional_text(
        payload["application_on"], field="application_on", maximum=64)

    evaluation = evaluate_self_revision(
        proposal,
        evidence_manifest=payload["evidence_manifest"],
        stable_lesson_ids=stable_ids,
    )
    if not evaluation.passed:
        raise ValueError("transaction evidence no longer passes")
    return proposal, previous, updated


def _validate_record(record: Mapping[str, Any]) -> str:
    if not isinstance(record, Mapping) or set(record) != _RECORD_FIELDS:
        raise ValueError("transaction record contains invalid fields")
    if record.get("schema_version") != TRANSACTION_SCHEMA_VERSION:
        raise ValueError("unknown self-revision transaction schema")
    agent_id = _clean_text(record["agent_id"], field="agent_id", maximum=128)
    proposal_id = _clean_text(
        record["proposal_id"], field="proposal_id", maximum=128)
    if not _SAFE_ID_RE.fullmatch(agent_id) or not _SAFE_ID_RE.fullmatch(proposal_id):
        raise ValueError("transaction ids must be filesystem-safe")
    proposal, _, _ = _validate_payload(
        record["payload"], agent_id=agent_id, proposal_id=proposal_id)
    state = _validate_event_chain(record["events"])
    if record["events"][0]["payload_digest"] != _digest(record["payload"]):
        raise ValueError("prepared event does not bind current transaction payload")
    if proposal.agent_id != agent_id:
        raise ValueError("transaction proposal belongs to another agent")
    violation = _find_secret(record)
    if violation:
        raise ValueError(f"transaction contains secret-shaped data at {violation}")
    return state


class SelfRevisionTransactionCoordinator:
    """Apply and recover approved revisions across identity/lifecycle registries."""

    def __init__(
        self,
        identity_registry: IdentityRegistry,
        lifecycle_registry: SelfRevisionRegistry,
        journal_directory: Path | str,
    ) -> None:
        self.identity_registry = identity_registry
        self.lifecycle_registry = lifecycle_registry
        self.journal_directory = Path(journal_directory)

    def _path_for(self, agent_id: str, proposal_id: str) -> Path:
        if not _SAFE_ID_RE.fullmatch(agent_id or "") or \
                not _SAFE_ID_RE.fullmatch(proposal_id or ""):
            raise ValueError("transaction ids must be filesystem-safe")
        return self.journal_directory / agent_id / f"{proposal_id}.json"

    @contextmanager
    def _locked(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        try:
            descriptor = os.open(
                lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ValueError(
                f"self-revision transaction {path} is already locked") from exc
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            descriptor = -1
            yield
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def _atomic_write(self, path: Path, record: Mapping[str, Any]) -> Path:
        _validate_record(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
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

    def _load_path(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            record["state"] = _validate_record(record)
            return record
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"self-revision transaction {path} is unreadable or corrupt") from exc

    def load(self, agent_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self._load_path(self._path_for(agent_id, proposal_id))

    def all_transactions(self, agent_id: str = "") -> List[Dict[str, Any]]:
        if not self.journal_directory.exists():
            return []
        if agent_id:
            if not _SAFE_ID_RE.fullmatch(agent_id):
                raise ValueError("agent_id is not filesystem-safe")
            paths = sorted((self.journal_directory / agent_id).glob("*.json"))
        else:
            paths = sorted(self.journal_directory.glob("*/*.json"))
        return [record for path in paths if (record := self._load_path(path))]

    def _append_event(
        self,
        path: Path,
        record: Dict[str, Any],
        *,
        event_type: str,
        actor: str,
        on: str = "",
        **fields: Any,
    ) -> Path:
        record.pop("state", None)
        events = list(record["events"])
        events.append(_build_event(
            events,
            event_type=event_type,
            actor=actor,
            on=on,
            **fields,
        ))
        record["events"] = events
        return self._atomic_write(path, record)

    def _expected_updated_profile(
        self,
        previous: AgentIdentityProfile,
        lifecycle: Mapping[str, Any],
        proposal: SelfRevisionProposal,
        evidence_manifest: Mapping[str, Mapping[str, Any]],
        stable_ids: Tuple[str, ...],
    ) -> AgentIdentityProfile:
        decision = _decision_event(lifecycle)
        evaluation = evaluate_self_revision(
            proposal,
            evidence_manifest=evidence_manifest,
            stable_lesson_ids=stable_ids,
        )
        if not evaluation.passed:
            raise ValueError("approved transaction evidence does not pass")
        return approve_and_apply_self_revision(
            previous,
            proposal,
            evaluation,
            evidence_manifest=evidence_manifest,
            stable_lesson_ids=stable_ids,
            approved_by=decision["actor"],
            approval_reference=decision["decision_reference"],
            approved_on=decision["on"],
        )

    def apply_approved(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        evidence_manifest: Mapping[str, Mapping[str, Any]],
        stable_lesson_ids: Iterable[str] = (),
        applied_by: str,
        application_reference: str,
        applied_on: str = "",
    ) -> AgentIdentityProfile:
        """Journal, apply, and commit one already-approved lifecycle proposal."""
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            if path.exists():
                raise ValueError(
                    "self-revision transaction already exists; call recover")
            previous = self.identity_registry.load_profile(agent_id)
            if previous is None:
                raise ValueError("identity profile does not exist")
            lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
            if lifecycle is None or lifecycle["status"] != "approved":
                raise ValueError("self-revision lifecycle is not approved")
            proposal = proposal_from_record(
                lifecycle["proposal"], expected_agent_id=agent_id)
            stable_ids = _clean_stable_ids(stable_lesson_ids)
            cited = _cited_manifest(proposal, evidence_manifest)
            updated = self._expected_updated_profile(
                previous, lifecycle, proposal, cited, stable_ids)
            actor = _clean_text(applied_by, field="applied_by", maximum=128)
            if actor == agent_id:
                raise ValueError("an agent cannot apply its own self-revision")
            application_ref = _clean_text(
                application_reference,
                field="application_reference",
                maximum=512,
            )
            application_date = _clean_optional_text(
                applied_on, field="applied_on", maximum=64)
            payload = {
                "proposal": proposal.to_record(),
                "evidence_manifest": cited,
                "stable_lesson_ids": list(stable_ids),
                "previous_profile": previous.to_record(),
                "updated_profile": updated.to_record(),
                "previous_governed_fingerprint": profile_fingerprint(previous),
                "updated_governed_fingerprint": profile_fingerprint(updated),
                "application_actor": actor,
                "application_reference": application_ref,
                "application_on": application_date,
            }
            events: List[Dict[str, Any]] = []
            events.append(_build_event(
                events,
                event_type="prepared",
                actor=actor,
                on=application_date,
                payload_digest=_digest(payload),
            ))
            record: Dict[str, Any] = {
                "schema_version": TRANSACTION_SCHEMA_VERSION,
                "agent_id": agent_id,
                "proposal_id": proposal_id,
                "payload": payload,
                "events": events,
            }
            self._atomic_write(path, record)
            return self._continue_locked(path, record)

    def _continue_locked(
        self,
        path: Path,
        record: Dict[str, Any],
    ) -> AgentIdentityProfile:
        """Complete a prepared transaction while the transaction lock is held."""
        # _load_path decorates records with a derived "state" for readers;
        # validation must see the exact on-disk schema (the recover path is
        # the one that arrives here with a decorated record).
        record = dict(record)
        record.pop("state", None)
        state = _validate_record(record)
        payload = record["payload"]
        agent_id = record["agent_id"]
        proposal_id = record["proposal_id"]
        proposal, journal_previous, journal_updated = _validate_payload(
            payload, agent_id=agent_id, proposal_id=proposal_id)
        stable_ids = _clean_stable_ids(payload["stable_lesson_ids"])
        evidence_manifest = payload["evidence_manifest"]
        actor = payload["application_actor"]
        application_reference = payload["application_reference"]
        application_on = payload["application_on"]

        lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
        if lifecycle is None:
            raise ValueError("transaction lifecycle record is missing")
        current = self.identity_registry.load_profile(agent_id)
        if current is None:
            raise ValueError("transaction identity profile is missing")
        current_governed = profile_fingerprint(current)
        previous_governed = payload["previous_governed_fingerprint"]
        updated_governed = payload["updated_governed_fingerprint"]

        if current_governed == previous_governed:
            updated = self._expected_updated_profile(
                current, lifecycle, proposal, evidence_manifest, stable_ids)
            if profile_fingerprint(updated) != updated_governed:
                raise ValueError(
                    "recomputed transaction update does not match journal")
        elif current_governed == updated_governed:
            updated = current
        else:
            raise ValueError(
                "identity state conflicts with both transaction endpoints")

        if state == "prepared":
            if lifecycle["status"] != "approved":
                raise ValueError(
                    "prepared transaction requires approved lifecycle state")
            if current_governed == previous_governed:
                self.identity_registry.save_profile(updated)
            self._append_event(
                path,
                record,
                event_type="identity_saved",
                actor=actor,
                on=application_on,
                governed_profile_fingerprint=profile_fingerprint(updated),
                observational_profile_fingerprint=(
                    observational_profile_fingerprint(updated)),
            )
            record = self._load_path(path)
            if record is None:
                raise ValueError("transaction journal disappeared")
            state = record["state"]

        if state == "identity_saved":
            lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
            if lifecycle is None:
                raise ValueError("transaction lifecycle record disappeared")
            current = self.identity_registry.load_profile(agent_id)
            if current is None or profile_fingerprint(current) != updated_governed:
                raise ValueError(
                    "identity_saved transaction does not match identity registry")
            if lifecycle["status"] == "approved":
                previous_for_application = journal_previous
                if profile_fingerprint(previous_for_application) != previous_governed:
                    raise ValueError("journal previous profile is invalid")
                # Preserve any refreshed observation metrics captured before the
                # identity write by rebuilding the previous state from current.
                previous_for_application = dataclasses_replace_governed(
                    current,
                    journal_previous,
                )
                self.lifecycle_registry.record_application(
                    agent_id,
                    proposal_id,
                    previous_profile=previous_for_application,
                    updated_profile=current,
                    evidence_manifest=evidence_manifest,
                    stable_lesson_ids=stable_ids,
                    applied_by=actor,
                    application_reference=application_reference,
                    applied_on=application_on,
                )
                lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
            if lifecycle is None or lifecycle["status"] != "probationary":
                raise ValueError(
                    "identity_saved transaction could not record lifecycle application")
            lifecycle_hash = lifecycle["events"][-1]["event_hash"]
            self._append_event(
                path,
                record,
                event_type="lifecycle_recorded",
                actor=actor,
                on=application_on,
                lifecycle_event_hash=lifecycle_hash,
                governed_profile_fingerprint=updated_governed,
            )
            record = self._load_path(path)
            if record is None:
                raise ValueError("transaction journal disappeared")
            state = record["state"]

        if state == "lifecycle_recorded":
            lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
            current = self.identity_registry.load_profile(agent_id)
            if lifecycle is None or lifecycle["status"] != "probationary":
                raise ValueError("lifecycle_recorded transaction lost probation state")
            if current is None or profile_fingerprint(current) != updated_governed:
                raise ValueError("lifecycle_recorded transaction lost identity state")
            expected_hash = lifecycle["events"][-1]["event_hash"]
            if record["events"][-1]["lifecycle_event_hash"] != expected_hash:
                raise ValueError("transaction lifecycle event hash has changed")
            self._append_event(
                path,
                record,
                event_type="committed",
                actor=actor,
                on=application_on,
                commit_digest=_digest({
                    "agent_id": agent_id,
                    "proposal_id": proposal_id,
                    "updated_governed_fingerprint": updated_governed,
                    "lifecycle_event_hash": expected_hash,
                }),
            )

        committed = self._load_path(path)
        if committed is None or committed["state"] != "committed":
            raise ValueError("self-revision transaction did not commit")
        final_profile = self.identity_registry.load_profile(agent_id)
        if final_profile is None or profile_fingerprint(final_profile) != \
                updated_governed:
            raise ValueError("committed transaction final identity is inconsistent")
        return final_profile

    def recover(self, agent_id: str, proposal_id: str) -> AgentIdentityProfile:
        """Complete a non-committed journal or verify an already committed one."""
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision transaction does not exist")
            if record["state"] == "committed":
                payload = record["payload"]
                current = self.identity_registry.load_profile(agent_id)
                if current is None or profile_fingerprint(current) != \
                        payload["updated_governed_fingerprint"]:
                    raise ValueError(
                        "committed transaction no longer matches identity state")
                lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
                if lifecycle is None or lifecycle["status"] != "probationary":
                    raise ValueError(
                        "committed transaction no longer matches lifecycle state")
                if lifecycle["events"][-1]["event_hash"] != \
                        record["events"][-2]["lifecycle_event_hash"]:
                    raise ValueError(
                        "committed transaction lifecycle hash no longer matches")
                return current
            return self._continue_locked(path, record)


def dataclasses_replace_governed(
    updated: AgentIdentityProfile,
    previous: AgentIdentityProfile,
) -> AgentIdentityProfile:
    """Project previous governed state onto updated observational measurements."""
    import dataclasses

    return dataclasses.replace(
        updated,
        identity_version=previous.identity_version,
        promotion_status=previous.promotion_status,
        known_failures=previous.known_failures,
        stable_lessons=previous.stable_lessons,
        soul_principles=previous.soul_principles,
        next_gate=previous.next_gate,
        version_history=previous.version_history,
        revision_history=previous.revision_history,
    )
