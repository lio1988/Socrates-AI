"""Persistent lifecycle registry for governed agent self-revision.

The identity profile stores approved descriptive effects. This registry stores
the complete proposal lifecycle around those effects:

    submitted -> evaluated -> approved/rejected -> applied -> confirmed/reverted

Security properties:

- submission is bound to one exact bounded self-review snapshot;
- proposal and snapshot metadata are committed into the first event hash;
- evaluation is recomputed from trusted evidence, never caller-supplied;
- decisions are bound to the same evidence digest and unchanged profile state;
- application is recomputed and must exactly equal the supplied new profile;
- post-change outcomes require trusted, action- and outcome-specific evidence;
- events are append-only, hash-chained, atomically written, and non-self governed;
- a per-proposal exclusive lock prevents concurrent lost updates.

The hash chain detects local record rewriting but is not cryptographic actor
authentication. External signatures or a remote transparency log remain future
hardening.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .identity_profile import AgentIdentityProfile
from .revision_reversal import is_canonical_reversal
from .self_review import SelfReviewSnapshot, profile_fingerprint
from .self_revision import (
    RevisionEvaluation,
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    evaluate_self_revision,
    proposal_from_record,
)

REGISTRY_SCHEMA_VERSION = "openclaw_self_revision_registry_v3"

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
_TERMINAL_STATUSES = frozenset({"rejected", "confirmed", "reverted"})
_MAX_EVENTS = 5
_MAX_REASONS = 32
_MAX_EVIDENCE_REFERENCES = 64

_BASE_EVENT_FIELDS = {
    "event_index", "event_type", "actor", "on", "prev_event_hash", "event_hash",
}
_EVENT_FIELDS = {
    "submitted": _BASE_EVENT_FIELDS | {
        "proposal_digest", "snapshot_fingerprint", "profile_fingerprint",
        "snapshot_evidence_digest",
    },
    "evaluated": _BASE_EVENT_FIELDS | {
        "passed", "reasons", "evidence_used", "evidence_digest",
    },
    "decision": _BASE_EVENT_FIELDS | {"decision", "decision_reference"},
    "applied": _BASE_EVENT_FIELDS | {
        "profile_fingerprint", "revision_index", "revision_entry_digest",
        "application_reference",
    },
    "outcome": _BASE_EVENT_FIELDS | {
        "outcome", "evidence_reference", "outcome_evidence_digest",
        "linked_proposal_id",
    },
}
_RECORD_FIELDS = {
    "schema_version", "agent_id", "proposal_id", "snapshot_version",
    "snapshot_fingerprint", "profile_fingerprint",
    "snapshot_evidence_references", "proposal", "events",
}


def _clean_text(value: Any, *, field: str, maximum: int = 1000) -> str:
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


def _clean_sequence(
    values: Iterable[Any],
    *,
    field: str,
    maximum_entries: int,
    maximum_text: int,
) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a sequence, not text")
    cleaned = tuple(
        _clean_text(value, field=field, maximum=maximum_text)
        for value in values
    )
    if len(cleaned) > maximum_entries:
        raise ValueError(
            f"{field} contains {len(cleaned)} entries; maximum is "
            f"{maximum_entries}")
    return cleaned


def _stable_tuple(values: Iterable[str]) -> Tuple[str, ...]:
    return _clean_sequence(
        values,
        field="stable_lesson_ids",
        maximum_entries=256,
        maximum_text=128,
    )


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("revision lifecycle data must be canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _event_hash(event_without_hash: Mapping[str, Any]) -> str:
    return _digest(event_without_hash)


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
    event_type = _clean_text(event_type, field="event_type", maximum=64)
    event: Dict[str, Any] = {
        "event_index": len(events),
        "event_type": event_type,
        "actor": _clean_text(actor, field="event actor", maximum=128),
        "on": _clean_optional_text(on, field="event date", maximum=64),
        "prev_event_hash": (
            str(events[-1].get("event_hash", "")) if events else ""
        ),
    }
    event.update(fields)
    expected = _EVENT_FIELDS.get(event_type)
    actual = set(event) | {"event_hash"}
    if expected is None:
        raise ValueError(f"unknown lifecycle event type {event_type!r}")
    if actual != expected:
        raise ValueError(
            f"lifecycle event {event_type!r} has invalid fields: "
            f"{sorted(actual ^ expected)}")
    event["event_hash"] = _event_hash(event)
    return event


def _validate_non_self(actor: str, agent_id: str, *, action: str) -> None:
    if actor == agent_id:
        raise ValueError(f"an agent cannot {action} its own self-revision")


def _evaluation_digest(
    proposal: SelfRevisionProposal,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    stable_lesson_ids: Tuple[str, ...],
) -> str:
    if not isinstance(evidence_manifest, Mapping):
        raise ValueError("evidence_manifest must be a mapping")
    cited = {}
    for reference in proposal.evidence_references:
        record = evidence_manifest.get(reference)
        if record is None:
            cited[reference] = None
        elif not isinstance(record, Mapping):
            raise ValueError(
                f"evidence record {reference!r} must be a mapping")
        else:
            cited[reference] = dict(record)
    return _digest({
        "proposal_id": proposal.proposal_id,
        "cited_evidence": cited,
        "stable_lesson_ids": sorted(set(stable_lesson_ids)),
    })


def _outcome_evidence_digest(
    proposal: SelfRevisionProposal,
    outcome: str,
    reference: str,
    evidence: Mapping[str, Any],
) -> str:
    return _digest({
        "proposal_id": proposal.proposal_id,
        "outcome": outcome,
        "reference": reference,
        "evidence": dict(evidence),
    })


def _validate_hash_chain(events: Sequence[Mapping[str, Any]]) -> None:
    if len(events) > _MAX_EVENTS:
        raise ValueError(
            f"revision lifecycle exceeds maximum {_MAX_EVENTS} events")
    previous = ""
    for index, raw_event in enumerate(events):
        if not isinstance(raw_event, Mapping):
            raise ValueError("revision registry events must be mappings")
        event = dict(raw_event)
        event_type = str(event.get("event_type", ""))
        expected_fields = _EVENT_FIELDS.get(event_type)
        if expected_fields is None or set(event) != expected_fields:
            raise ValueError(
                f"revision lifecycle event {event_type!r} has invalid fields")
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
    evaluator = ""
    for index, event in enumerate(events[1:], start=1):
        event_type = str(event.get("event_type", ""))
        actor = _clean_text(
            event.get("actor", ""), field="event actor", maximum=128)
        _validate_non_self(actor, proposal.agent_id, action="govern")

        if status in _TERMINAL_STATUSES:
            raise ValueError("terminal self-revision records cannot receive more events")

        if event_type == "evaluated":
            if status != "submitted":
                raise ValueError("self-revision can be evaluated exactly once after submit")
            if not isinstance(event.get("passed"), bool):
                raise ValueError("evaluation event requires boolean passed")
            reasons = _clean_sequence(
                event.get("reasons") or (),
                field="evaluation reason",
                maximum_entries=_MAX_REASONS,
                maximum_text=1000,
            )
            evidence_used = _clean_sequence(
                event.get("evidence_used") or (),
                field="evaluation evidence reference",
                maximum_entries=_MAX_EVIDENCE_REFERENCES,
                maximum_text=256,
            )
            if not reasons:
                raise ValueError("evaluation event requires reasons")
            if event["passed"] and tuple(evidence_used) != proposal.evidence_references:
                raise ValueError(
                    "passing evaluation must use every proposal evidence reference")
            if not _HEX64_RE.fullmatch(str(event.get("evidence_digest", ""))):
                raise ValueError("evaluation event requires evidence_digest")
            evaluator = actor
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
            if actor == evaluator:
                raise ValueError(
                    "evaluation and approval must be performed by different actors")
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
            for field in ("profile_fingerprint", "revision_entry_digest"):
                if not _HEX64_RE.fullmatch(str(event.get(field, ""))):
                    raise ValueError(f"applied event requires {field}")
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
            if not _HEX64_RE.fullmatch(
                    str(event.get("outcome_evidence_digest", ""))):
                raise ValueError("outcome event requires outcome_evidence_digest")
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
    if set(record) != _RECORD_FIELDS:
        raise ValueError("revision registry record contains invalid fields")
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
    for field in ("snapshot_fingerprint", "profile_fingerprint"):
        if not _HEX64_RE.fullmatch(str(record.get(field, ""))):
            raise ValueError(f"registry record requires a valid {field}")
    _clean_text(
        record.get("snapshot_version", ""),
        field="snapshot_version",
        maximum=64,
    )
    snapshot_references = _clean_sequence(
        record.get("snapshot_evidence_references") or (),
        field="snapshot evidence reference",
        maximum_entries=_MAX_EVIDENCE_REFERENCES,
        maximum_text=256,
    )
    if not set(proposal.evidence_references).issubset(snapshot_references):
        raise ValueError(
            "proposal cites evidence absent from its bound self-review snapshot")
    events = record.get("events")
    if not isinstance(events, list):
        raise ValueError("revision registry events must be a list")
    _validate_event_sequence(events, proposal=proposal)

    submitted = events[0]
    expected_bindings = {
        "proposal_digest": _digest(proposal.to_record()),
        "snapshot_fingerprint": str(record["snapshot_fingerprint"]),
        "profile_fingerprint": str(record["profile_fingerprint"]),
        "snapshot_evidence_digest": _digest(list(snapshot_references)),
    }
    for field, expected in expected_bindings.items():
        if submitted.get(field) != expected:
            raise ValueError(
                f"submitted event does not bind current {field}")
    return proposal, _record_status(events)


def _decision_event(record: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = [
        event for event in record["events"]
        if event.get("event_type") == "decision"
    ]
    if len(matches) != 1:
        raise ValueError("approved lifecycle requires exactly one decision event")
    return matches[0]


def _evaluation_event(record: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = [
        event for event in record["events"]
        if event.get("event_type") == "evaluated"
    ]
    if len(matches) != 1:
        raise ValueError("lifecycle requires exactly one evaluation event")
    return matches[0]


def _validate_outcome_evidence(
    proposal: SelfRevisionProposal,
    *,
    outcome: str,
    reference: str,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
) -> Tuple[str, str]:
    if not isinstance(evidence_manifest, Mapping):
        raise ValueError("evidence_manifest must be a mapping")
    evidence = evidence_manifest.get(reference)
    if not isinstance(evidence, Mapping):
        raise ValueError("outcome evidence reference is missing")
    if evidence.get("verified") is not True:
        raise ValueError("outcome evidence is not verified")
    if str(evidence.get("agent_id", "")).strip() != proposal.agent_id:
        raise ValueError("outcome evidence belongs to another agent")
    _clean_text(evidence.get("source", ""), field="outcome source", maximum=512)
    verifier = _clean_text(
        evidence.get("verified_by", ""),
        field="outcome evidence verifier",
        maximum=128,
    )
    _validate_non_self(verifier, proposal.agent_id, action="verify")
    if str(evidence.get("value", "")).strip() != proposal.value:
        raise ValueError("outcome evidence value does not match proposal value")
    raw_supports = evidence.get("supports") or ()
    supports = _clean_sequence(
        raw_supports,
        field="outcome action support",
        maximum_entries=16,
        maximum_text=128,
    )
    support_key = f"{proposal.target}:{proposal.action}"
    if support_key not in supports:
        raise ValueError(
            f"outcome evidence does not support {support_key}")
    raw_outcomes = evidence.get("outcomes") or ()
    outcomes = _clean_sequence(
        raw_outcomes,
        field="outcome support",
        maximum_entries=2,
        maximum_text=32,
    )
    if outcome not in outcomes:
        raise ValueError(
            f"outcome evidence does not support {outcome!r}")
    return (
        _outcome_evidence_digest(proposal, outcome, reference, evidence),
        verifier,
    )


class SelfRevisionRegistry:
    """Atomic per-proposal storage with a governed append-only lifecycle."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path_for(self, agent_id: str, proposal_id: str) -> Path:
        if not _SAFE_ID_RE.fullmatch(agent_id or ""):
            raise ValueError("agent_id is not filesystem-safe")
        if not _SAFE_ID_RE.fullmatch(proposal_id or ""):
            raise ValueError("proposal_id is not filesystem-safe")
        return self.directory / agent_id / f"{proposal_id}.json"

    @contextmanager
    def _locked(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as exc:
            raise ValueError(
                f"self-revision record {path} is locked by another update") from exc
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

    def _load_path(self, path: Path) -> Optional[Dict[str, Any]]:
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

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        snapshot: SelfReviewSnapshot,
        submitted_on: str = "",
    ) -> Path:
        """Persist a proposal bound to the exact snapshot that permitted it."""
        if snapshot.agent_id != proposal.agent_id:
            raise ValueError("proposal and self-review snapshot belong to different agents")
        if proposal.proposal_id in snapshot.pending_proposal_ids:
            raise ValueError("proposal_id is already pending in the bound snapshot")
        by_reference = {
            evidence.reference: evidence
            for evidence in snapshot.verified_evidence
        }
        support = f"{proposal.target}:{proposal.action}"
        for reference in proposal.evidence_references:
            evidence = by_reference.get(reference)
            if evidence is None:
                raise ValueError(
                    "proposal cites evidence absent from its bound self-review snapshot")
            if support not in evidence.supports or evidence.value != proposal.value:
                raise ValueError(
                    "proposal evidence does not match target/action/value in snapshot")

        path = self._path_for(proposal.agent_id, proposal.proposal_id)
        with self._locked(path):
            if path.exists():
                raise ValueError("self-revision proposal_id already exists in registry")
            snapshot_references = [
                evidence.reference for evidence in snapshot.verified_evidence
            ]
            events: List[Dict[str, Any]] = []
            events.append(_build_event(
                events,
                event_type="submitted",
                actor=proposal.agent_id,
                on=submitted_on,
                proposal_digest=_digest(proposal.to_record()),
                snapshot_fingerprint=snapshot.snapshot_fingerprint,
                profile_fingerprint=snapshot.profile_fingerprint,
                snapshot_evidence_digest=_digest(snapshot_references),
            ))
            record = {
                "schema_version": REGISTRY_SCHEMA_VERSION,
                "agent_id": proposal.agent_id,
                "proposal_id": proposal.proposal_id,
                "snapshot_version": snapshot.snapshot_version,
                "snapshot_fingerprint": snapshot.snapshot_fingerprint,
                "profile_fingerprint": snapshot.profile_fingerprint,
                "snapshot_evidence_references": snapshot_references,
                "proposal": proposal.to_record(),
                "events": events,
            }
            return self._atomic_write(path, record)

    def load(self, agent_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self._load_path(self._path_for(agent_id, proposal_id))

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
            record = self._load_path(path)
            if record is not None:
                records.append(record)

        index = {
            (record["agent_id"], record["proposal_id"]): record
            for record in records
        }
        for record in records:
            if record["status"] != "reverted":
                continue
            outcome_event = record["events"][-1]
            linked_id = outcome_event["linked_proposal_id"]
            linked = index.get((record["agent_id"], linked_id))
            if linked is None:
                raise ValueError(
                    "reverted lifecycle points to a missing reversal proposal")
            original = proposal_from_record(
                record["proposal"], expected_agent_id=record["agent_id"])
            candidate = proposal_from_record(
                linked["proposal"], expected_agent_id=record["agent_id"])
            if not is_canonical_reversal(original, candidate):
                raise ValueError(
                    "reverted lifecycle points to a non-canonical reversal proposal")
        return records

    def record_evaluation(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        current_profile: AgentIdentityProfile,
        evidence_manifest: Mapping[str, Mapping[str, Any]],
        stable_lesson_ids: Iterable[str] = (),
        evaluated_by: str = "evidence-harness",
        evaluated_on: str = "",
    ) -> RevisionEvaluation:
        """Recompute trusted evidence and append the resulting evaluation."""
        stable_ids = _stable_tuple(stable_lesson_ids)
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision proposal does not exist")
            if record["status"] != "submitted":
                raise ValueError("self-revision can be evaluated only once after submit")
            if current_profile.agent_id != agent_id:
                raise ValueError("current profile belongs to another agent")
            if profile_fingerprint(current_profile) != record["profile_fingerprint"]:
                raise ValueError(
                    "self-revision snapshot is stale because identity state changed")
            proposal = proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
            evaluation = evaluate_self_revision(
                proposal,
                evidence_manifest=evidence_manifest,
                stable_lesson_ids=stable_ids,
            )
            actor = _clean_text(
                evaluated_by, field="evaluated_by", maximum=128)
            _validate_non_self(actor, agent_id, action="evaluate")
            event = _build_event(
                record["events"],
                event_type="evaluated",
                actor=actor,
                on=evaluated_on,
                passed=evaluation.passed,
                reasons=list(evaluation.reasons),
                evidence_used=list(evaluation.evidence_used),
                evidence_digest=_evaluation_digest(
                    proposal, evidence_manifest, stable_ids),
            )
            record.pop("status", None)
            record["events"].append(event)
            self._atomic_write(path, record)
            return evaluation

    def record_decision(
        self,
        agent_id: str,
        proposal_id: str,
        *,
        current_profile: AgentIdentityProfile,
        evidence_manifest: Mapping[str, Mapping[str, Any]],
        stable_lesson_ids: Iterable[str] = (),
        decision: str,
        decided_by: str,
        decision_reference: str,
        decided_on: str = "",
    ) -> Path:
        """Record a segregated non-self decision against unchanged evidence/state."""
        stable_ids = _stable_tuple(stable_lesson_ids)
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision proposal does not exist")
            if record["status"] not in {"evaluated_passed", "evaluated_failed"}:
                raise ValueError("decision requires a completed evaluation")
            if current_profile.agent_id != agent_id:
                raise ValueError("current profile belongs to another agent")
            if profile_fingerprint(current_profile) != record["profile_fingerprint"]:
                raise ValueError(
                    "self-revision snapshot is stale because identity state changed")
            proposal = proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
            evaluation_event = _evaluation_event(record)
            fresh = evaluate_self_revision(
                proposal,
                evidence_manifest=evidence_manifest,
                stable_lesson_ids=stable_ids,
            )
            digest = _evaluation_digest(
                proposal, evidence_manifest, stable_ids)
            if digest != evaluation_event["evidence_digest"]:
                raise ValueError("evidence changed after lifecycle evaluation")
            if fresh.passed != evaluation_event["passed"] or \
                    tuple(fresh.evidence_used) != tuple(
                        evaluation_event["evidence_used"]):
                raise ValueError("stored evaluation does not match recomputed evidence")

            decision = _clean_text(decision, field="decision", maximum=32)
            if decision not in {"approved", "rejected"}:
                raise ValueError("decision must be approved or rejected")
            if decision == "approved" and not fresh.passed:
                raise ValueError("a failing evaluation cannot be approved")
            actor = _clean_text(decided_by, field="decided_by", maximum=128)
            _validate_non_self(actor, agent_id, action="approve or reject")
            if actor == evaluation_event["actor"]:
                raise ValueError(
                    "evaluation and approval must be performed by different actors")
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
            record.pop("status", None)
            record["events"].append(event)
            return self._atomic_write(path, record)

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
    ) -> Path:
        """Recompute the approved change and require exact resulting profile state."""
        stable_ids = _stable_tuple(stable_lesson_ids)
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision proposal does not exist")
            if record["status"] != "approved":
                raise ValueError("profile application requires an approved proposal")
            if previous_profile.agent_id != agent_id or \
                    updated_profile.agent_id != agent_id:
                raise ValueError("application profiles belong to another agent")
            if profile_fingerprint(previous_profile) != record["profile_fingerprint"]:
                raise ValueError(
                    "application baseline does not match bound self-review profile")

            proposal = proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
            evaluation_event = _evaluation_event(record)
            decision_event = _decision_event(record)
            fresh = evaluate_self_revision(
                proposal,
                evidence_manifest=evidence_manifest,
                stable_lesson_ids=stable_ids,
            )
            digest = _evaluation_digest(
                proposal, evidence_manifest, stable_ids)
            if not fresh.passed or digest != evaluation_event["evidence_digest"]:
                raise ValueError("application evidence no longer matches approval")
            if decision_event["decision"] != "approved":
                raise ValueError("application requires an approved decision")

            expected = approve_and_apply_self_revision(
                previous_profile,
                proposal,
                fresh,
                evidence_manifest=evidence_manifest,
                stable_lesson_ids=stable_ids,
                approved_by=decision_event["actor"],
                approval_reference=decision_event["decision_reference"],
                approved_on=decision_event["on"],
            )
            if expected.to_record() != updated_profile.to_record():
                raise ValueError(
                    "updated profile does not exactly match the approved revision")
            revision_index = len(updated_profile.revision_history) - 1
            entry = updated_profile.revision_history[revision_index]

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
                profile_fingerprint=profile_fingerprint(updated_profile),
                revision_index=revision_index,
                revision_entry_digest=_digest(entry),
                application_reference=reference,
            )
            record.pop("status", None)
            record["events"].append(event)
            return self._atomic_write(path, record)

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
    ) -> Path:
        """Record confirmed/reverted only from trusted outcome-specific evidence."""
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision proposal does not exist")
            if record["status"] != "probationary":
                raise ValueError("outcome requires a probationary applied revision")
            if current_profile.agent_id != agent_id:
                raise ValueError("current profile belongs to another agent")
            applied_event = record["events"][-1]
            if profile_fingerprint(current_profile) != \
                    applied_event["profile_fingerprint"]:
                raise ValueError(
                    "post-change identity state changed before outcome review")

            proposal = proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
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
            if outcome == "reverted":
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
                    raise ValueError("linked proposal is not a canonical reversal")
                if linked_record["profile_fingerprint"] != \
                        profile_fingerprint(current_profile):
                    raise ValueError(
                        "linked reversal proposal is not bound to current identity state")
            elif linked:
                raise ValueError("confirmed outcome must not link a reversal proposal")

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
