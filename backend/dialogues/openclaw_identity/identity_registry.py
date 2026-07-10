"""
OpenClaw Agent Identity — persistent, auditable identity profiles.

One human-readable JSON file is stored per agent. Persistence grants no runtime
authority, but earned history and approved self-revisions are protected:

- version_history and revision_history remain exact append-only prefixes;
- every stored transition and revision is revalidated on every load;
- version/stage transitions remain canonical and non-self-approved;
- known failures, stable lessons, and soul principles cannot change without a
  matching approved revision entry;
- untrusted JSON is schema/type checked and secret-shaped data is refused;
- writes are atomic and serialized by a per-agent exclusive lock.

Evidence-derived descriptive fields may be recomputed between saves. Pure
stdlib, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .identity_profile import AgentIdentityProfile, from_record

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)
_VERSION_ENTRY_REQUIRED = {
    "from_version", "to_version", "gate_id", "gate_description",
    "approved_by", "approved_on", "evidence", "reasons",
}
_VERSION_ENTRY_ALLOWED = _VERSION_ENTRY_REQUIRED | {"approval_reference"}
_STAGE_ENTRY_REQUIRED = {
    "from_status", "to_status", "approved_by", "approved_on",
}
_STAGE_ENTRY_ALLOWED = _STAGE_ENTRY_REQUIRED | {"evidence_reference"}


def _history_prefix(old: Sequence[Dict], new: Sequence[Dict]) -> bool:
    return len(new) >= len(old) and tuple(new[:len(old)]) == tuple(old)


def _find_secret(value: Any, path: str = "identity") -> Optional[str]:
    if isinstance(value, dict):
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
                return (
                    f"{path} contains token-shaped data matching "
                    f"{pattern.pattern!r}")
    return None


def _validate_approver(entry: Mapping[str, Any], agent_id: str) -> None:
    approver = str(entry.get("approved_by", "")).strip()
    if not approver:
        raise ValueError("identity-history transition requires a named approver")
    if approver == agent_id:
        raise ValueError("an agent cannot approve its own identity transition")


def _validate_version_entry_shape(entry: Mapping[str, Any]) -> None:
    if not isinstance(entry, Mapping):
        raise ValueError("version-history entry must be a mapping")
    fields = set(entry)
    if not _VERSION_ENTRY_REQUIRED.issubset(fields) or \
            not fields.issubset(_VERSION_ENTRY_ALLOWED):
        raise ValueError(
            "version-history entry contains missing or unknown fields")
    if not isinstance(entry.get("evidence"), Mapping):
        raise ValueError("version-history evidence must be a mapping")
    reasons = entry.get("reasons")
    if isinstance(reasons, (str, bytes)) or not isinstance(reasons, (list, tuple)):
        raise ValueError("version-history reasons must be a sequence")
    if not all(isinstance(reason, str) and reason.strip() for reason in reasons):
        raise ValueError("version-history reasons must contain non-empty text")
    if not isinstance(entry.get("approved_on"), str):
        raise ValueError("version-history approved_on must be text")
    if "approval_reference" in entry and not isinstance(
            entry["approval_reference"], str):
        raise ValueError("version-history approval_reference must be text")


def _validate_stage_entry_shape(entry: Mapping[str, Any]) -> None:
    if not isinstance(entry, Mapping):
        raise ValueError("stage-history entry must be a mapping")
    fields = set(entry)
    if not _STAGE_ENTRY_REQUIRED.issubset(fields) or \
            not fields.issubset(_STAGE_ENTRY_ALLOWED):
        raise ValueError("stage-history entry contains missing or unknown fields")
    if not isinstance(entry.get("approved_on"), str):
        raise ValueError("stage-history approved_on must be text")
    if "evidence_reference" in entry and not isinstance(
            entry["evidence_reference"], str):
        raise ValueError("stage-history evidence_reference must be text")


def _validate_version_transition(
    entry: Mapping[str, Any],
    current_version: str,
    agent_id: str,
) -> str:
    from .promotion_policy import VERSION_GATES, evaluate_gate

    _validate_version_entry_shape(entry)
    from_version = str(entry["from_version"])
    to_version = str(entry["to_version"])
    gate_id = str(entry["gate_id"])
    if from_version != current_version:
        raise ValueError(
            "version-history chain does not start at the stored version")

    gate = next(
        (candidate for candidate in VERSION_GATES
         if candidate.gate_id == gate_id),
        None,
    )
    if gate is None:
        raise ValueError(f"unknown canonical identity gate {gate_id!r}")
    if gate.from_version != from_version or gate.to_version != to_version:
        raise ValueError(
            "version-history transition does not match its canonical gate")
    if str(entry["gate_description"]) != gate.description:
        raise ValueError("version-history gate description is not canonical")
    result = evaluate_gate(gate, dict(entry["evidence"]))
    if not result.passed:
        raise ValueError("version-history evidence does not pass its gate")
    if dict(result.evidence_used) != dict(entry["evidence"]):
        raise ValueError("version-history stored evidence is not canonical")
    if list(result.reasons) != list(entry["reasons"]):
        raise ValueError("version-history stored reasons are not canonical")
    _validate_approver(entry, agent_id)
    return to_version


def _validate_stage_transition(
    entry: Mapping[str, Any],
    current_status: str,
    agent_id: str,
) -> str:
    from .promotion_policy import STAGE_NAMES

    _validate_stage_entry_shape(entry)
    from_status = str(entry["from_status"])
    to_status = str(entry["to_status"])
    if from_status != current_status:
        raise ValueError(
            "stage-history chain does not start at the stored status")
    if from_status not in STAGE_NAMES or to_status not in STAGE_NAMES:
        raise ValueError("stage transition references an unknown ladder status")
    if STAGE_NAMES.index(to_status) != STAGE_NAMES.index(from_status) + 1:
        raise ValueError("stage transition must advance exactly one ladder rung")
    _validate_approver(entry, agent_id)
    return to_status


def _reverse_version_transition(
    entry: Mapping[str, Any],
    current_version: str,
    agent_id: str,
) -> str:
    from .promotion_policy import VERSION_GATES, evaluate_gate

    _validate_version_entry_shape(entry)
    from_version = str(entry["from_version"])
    to_version = str(entry["to_version"])
    gate_id = str(entry["gate_id"])
    if to_version != current_version:
        raise ValueError(
            "stored version-history does not terminate at identity_version")
    gate = next(
        (candidate for candidate in VERSION_GATES
         if candidate.gate_id == gate_id),
        None,
    )
    if gate is None or gate.from_version != from_version or \
            gate.to_version != to_version:
        raise ValueError(
            "stored version-history transition is not a canonical gate")
    if str(entry["gate_description"]) != gate.description:
        raise ValueError("stored version-history gate description is not canonical")
    result = evaluate_gate(gate, dict(entry["evidence"]))
    if not result.passed or dict(result.evidence_used) != dict(entry["evidence"]):
        raise ValueError("stored version-history evidence is not canonical")
    if list(result.reasons) != list(entry["reasons"]):
        raise ValueError("stored version-history reasons are not canonical")
    _validate_approver(entry, agent_id)
    return from_version


def _reverse_stage_transition(
    entry: Mapping[str, Any],
    current_status: str,
    agent_id: str,
) -> str:
    from .promotion_policy import STAGE_NAMES

    _validate_stage_entry_shape(entry)
    from_status = str(entry["from_status"])
    to_status = str(entry["to_status"])
    if to_status != current_status:
        raise ValueError(
            "stored stage-history does not terminate at promotion_status")
    if from_status not in STAGE_NAMES or to_status not in STAGE_NAMES:
        raise ValueError("stored stage-history references an unknown status")
    if STAGE_NAMES.index(to_status) != STAGE_NAMES.index(from_status) + 1:
        raise ValueError("stored stage transition is not one ladder rung")
    _validate_approver(entry, agent_id)
    return from_status


def _validate_appended_history(
    existing: AgentIdentityProfile,
    profile: AgentIdentityProfile,
) -> None:
    """Refuse history rewrite, non-canonical jumps, and unrecorded state changes."""
    old_history = tuple(existing.version_history)
    new_history = tuple(profile.version_history)
    if not _history_prefix(old_history, new_history):
        raise ValueError(
            "identity version_history is append-only; existing entries cannot "
            "be removed or rewritten")

    current_version = existing.identity_version
    current_status = existing.promotion_status
    for entry in new_history[len(old_history):]:
        has_version = "from_version" in entry or "to_version" in entry
        has_status = "from_status" in entry or "to_status" in entry
        if has_version == has_status:
            raise ValueError(
                "each appended identity-history entry must describe exactly one "
                "version or stage transition")
        if has_version:
            current_version = _validate_version_transition(
                entry, current_version, profile.agent_id)
        else:
            current_status = _validate_stage_transition(
                entry, current_status, profile.agent_id)

    if current_version != profile.identity_version:
        raise ValueError(
            "identity_version changed without a matching append-only transition")
    if current_status != profile.promotion_status:
        raise ValueError(
            "promotion_status changed without a matching append-only transition")


def _reverse_revision_state(
    failures: Tuple[str, ...],
    lessons: Tuple[str, ...],
    principles: Tuple[str, ...],
    entry: Mapping[str, Any],
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    target = str(entry.get("target", ""))
    action = str(entry.get("action", ""))
    value = str(entry.get("value", ""))
    failure_list = list(failures)
    lesson_list = list(lessons)
    principle_list = list(principles)

    if target == "identity" and action == "add_known_failure":
        if value not in failure_list:
            raise ValueError("stored add_known_failure effect is absent")
        failure_list.remove(value)
    elif target == "identity" and action == "resolve_known_failure":
        if value in failure_list:
            raise ValueError("stored resolved failure is still present")
        failure_list.append(value)
    elif target == "memory" and action == "link_stable_lesson":
        if value not in lesson_list:
            raise ValueError("stored linked lesson effect is absent")
        lesson_list.remove(value)
    elif target == "memory" and action == "unlink_stable_lesson":
        if value in lesson_list:
            raise ValueError("stored unlinked lesson is still present")
        lesson_list.append(value)
    elif target == "soul" and action == "add_principle":
        if value not in principle_list:
            raise ValueError("stored Soul principle effect is absent")
        principle_list.remove(value)
    elif target == "soul" and action == "retire_principle":
        if value in principle_list:
            raise ValueError("stored retired Soul principle is still present")
        principle_list.append(value)
    else:
        raise ValueError("stored self-revision action is unsupported")
    return tuple(failure_list), tuple(lesson_list), tuple(principle_list)


def _validate_complete_profile_history(profile: AgentIdentityProfile) -> None:
    """Prove all stored history can reconstruct the current governed state."""
    from .promotion_policy import next_gate_for
    from .self_revision import replay_revision_entry

    expected_gate = next_gate_for(profile.identity_version)
    expected_gate_id = expected_gate.gate_id if expected_gate else None
    if profile.next_gate != expected_gate_id:
        raise ValueError("identity next_gate does not match identity_version")

    current_version = profile.identity_version
    current_status = profile.promotion_status
    for entry in reversed(profile.version_history):
        if not isinstance(entry, Mapping):
            raise ValueError("identity version_history entries must be mappings")
        has_version = "from_version" in entry or "to_version" in entry
        has_status = "from_status" in entry or "to_status" in entry
        if has_version == has_status:
            raise ValueError(
                "each stored identity-history entry must describe exactly one "
                "version or stage transition")
        if has_version:
            current_version = _reverse_version_transition(
                entry, current_version, profile.agent_id)
        else:
            current_status = _reverse_stage_transition(
                entry, current_status, profile.agent_id)

    failures = tuple(profile.known_failures)
    lessons = tuple(profile.stable_lessons)
    principles = tuple(profile.soul_principles)
    seen_proposals = set()
    for entry in reversed(profile.revision_history):
        if not isinstance(entry, Mapping):
            raise ValueError("identity revision_history entries must be mappings")
        proposal_id = str(entry.get("proposal_id", ""))
        if not proposal_id or proposal_id in seen_proposals:
            raise ValueError("stored self-revision proposal IDs must be unique")
        current_state = (failures, lessons, principles)
        prior_state = _reverse_revision_state(
            failures, lessons, principles, entry)
        replayed = replay_revision_entry(
            *prior_state,
            entry,
            agent_id=profile.agent_id,
        )
        if replayed != current_state:
            raise ValueError(
                "stored self-revision history does not reconstruct current state")
        failures, lessons, principles = prior_state
        seen_proposals.add(proposal_id)


def _validate_appended_revisions(
    existing: AgentIdentityProfile,
    profile: AgentIdentityProfile,
) -> None:
    """Replay appended self-revisions and bind them to the resulting profile."""
    old_history = tuple(existing.revision_history)
    new_history = tuple(profile.revision_history)
    if not _history_prefix(old_history, new_history):
        raise ValueError(
            "identity revision_history is append-only; existing entries cannot "
            "be removed or rewritten")

    failures = tuple(existing.known_failures)
    lessons = tuple(existing.stable_lessons)
    principles = tuple(existing.soul_principles)
    seen_proposals = {
        str(entry.get("proposal_id", "")) for entry in old_history
    }
    from .self_revision import replay_revision_entry

    for entry in new_history[len(old_history):]:
        proposal_id = str(entry.get("proposal_id", ""))
        if proposal_id in seen_proposals:
            raise ValueError("self-revision proposal_id cannot be replayed")
        failures, lessons, principles = replay_revision_entry(
            failures,
            lessons,
            principles,
            entry,
            agent_id=profile.agent_id,
        )
        seen_proposals.add(proposal_id)

    if failures != tuple(profile.known_failures):
        raise ValueError(
            "known_failures changed without matching approved self-revisions")
    if lessons != tuple(profile.stable_lessons):
        raise ValueError(
            "stable_lessons changed without matching approved self-revisions")
    if principles != tuple(profile.soul_principles):
        raise ValueError(
            "soul_principles changed without matching approved self-revisions")


class IdentityRegistry:
    """One atomic, monotonic JSON profile per filesystem-safe agent id."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path_for(self, agent_id: str) -> Path:
        if not _AGENT_ID_RE.fullmatch(agent_id or ""):
            raise ValueError(
                f"agent_id {agent_id!r} is not filesystem-safe "
                "(1-128 letters, digits, dot, underscore, hyphen)")
        return self.directory / f"{agent_id}.json"

    @contextmanager
    def _locked(self, path: Path):
        self.directory.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as exc:
            raise ValueError(
                f"identity profile {path} is locked by another update") from exc
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

    def _read_path(self, path: Path) -> Optional[AgentIdentityProfile]:
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            violation = _find_secret(record)
            if violation:
                raise ValueError(
                    f"identity profile contains secret-shaped data at {violation}")
            profile = from_record(record)
            _validate_complete_profile_history(profile)
            return profile
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"identity profile {path} is unreadable or corrupt") from exc

    def save_profile(self, profile: AgentIdentityProfile) -> Path:
        """Atomically save a strict profile without permitting history rollback."""
        path = self._path_for(profile.agent_id)
        record = profile.to_record()
        validated = from_record(record)
        if validated != profile:
            raise ValueError("identity profile is not canonical or type-safe")
        violation = _find_secret(record)
        if violation:
            raise ValueError(
                f"identity profile refused because secret-shaped data was found at "
                f"{violation}")

        with self._locked(path):
            existing = self._read_path(path)
            if existing is not None:
                # Tamper detection outranks content validation: a rewritten
                # stored history entry must be reported as an append-only
                # violation, not as whatever semantic rule the forged
                # content happens to break.
                _validate_appended_history(existing, profile)
                _validate_appended_revisions(existing, profile)
            elif profile.version_history or profile.revision_history:
                raise ValueError(
                    "a new identity profile must be saved before version or "
                    "self-revision history is appended; bootstrap fields may be "
                    "curated, history may not")
            _validate_complete_profile_history(profile)

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
                    dir=self.directory,
                    prefix=f".{profile.agent_id}.",
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

    def load_profile(self, agent_id: str) -> Optional[AgentIdentityProfile]:
        """Load one strict profile; None means it has never been saved."""
        return self._read_path(self._path_for(agent_id))

    def all_profiles(self) -> List[AgentIdentityProfile]:
        """Load every profile in deterministic order; corruption is never hidden."""
        if not self.directory.exists():
            return []
        profiles: List[AgentIdentityProfile] = []
        for path in sorted(self.directory.glob("*.json")):
            profile = self._read_path(path)
            if profile is not None:
                if path.name != f"{profile.agent_id}.json":
                    raise ValueError(
                        f"identity profile filename does not match agent_id: {path}")
                profiles.append(profile)
        return profiles
