"""
OpenClaw Agent Identity — persistent, auditable identity profiles.

One human-readable JSON file is stored per agent. Persistence grants no runtime
authority, but earned history and approved self-revisions are protected:
  - version_history and revision_history remain exact append-only prefixes
  - version/stage transitions remain canonical and non-self-approved
  - known failures, stable lessons, and soul principles cannot change without a
    matching approved revision entry
  - writes are atomic (temp file + fsync + os.replace)

Evidence-derived descriptive fields may be recomputed between saves. Pure
stdlib, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .identity_profile import AgentIdentityProfile, from_record

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _history_prefix(old: Sequence[Dict], new: Sequence[Dict]) -> bool:
    return len(new) >= len(old) and tuple(new[:len(old)]) == tuple(old)


def _validate_approver(entry: Dict, agent_id: str) -> None:
    approver = str(entry.get("approved_by", "")).strip()
    if not approver:
        raise ValueError("identity-history transition requires a named approver")
    if approver == agent_id:
        raise ValueError("an agent cannot approve its own identity transition")


def _validate_version_transition(
    entry: Dict,
    current_version: str,
    agent_id: str,
) -> str:
    from .promotion_policy import VERSION_GATES

    if not {"from_version", "to_version", "gate_id"}.issubset(entry):
        raise ValueError(
            "version transition requires from_version, to_version, and gate_id")
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
    _validate_approver(entry, agent_id)
    return to_version


def _validate_stage_transition(
    entry: Dict,
    current_status: str,
    agent_id: str,
) -> str:
    from .promotion_policy import STAGE_NAMES

    if not {"from_status", "to_status"}.issubset(entry):
        raise ValueError("stage transition requires from_status and to_status")
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
        if not _AGENT_ID_RE.match(agent_id or ""):
            raise ValueError(
                f"agent_id {agent_id!r} is not filesystem-safe "
                "(allowed: letters, digits, dot, underscore, hyphen)")
        return self.directory / f"{agent_id}.json"

    def save_profile(self, profile: AgentIdentityProfile) -> Path:
        """Atomically save a profile without permitting history rollback."""
        path = self._path_for(profile.agent_id)
        self.directory.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = self.load_profile(profile.agent_id)
            if existing is None:
                raise ValueError("existing identity profile could not be loaded")
            _validate_appended_history(existing, profile)
            _validate_appended_revisions(existing, profile)
        elif profile.revision_history:
            raise ValueError(
                "a new identity profile must be saved before self-revisions are "
                "appended; bootstrap fields may be curated, history may not")

        payload = json.dumps(
            profile.to_record(),
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
        """Load one profile; None means it has never been saved."""
        path = self._path_for(agent_id)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            return from_record(record)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"identity profile {path} is unreadable or corrupt") from exc

    def all_profiles(self) -> List[AgentIdentityProfile]:
        """Load every profile in deterministic order; corruption is never hidden."""
        if not self.directory.exists():
            return []
        profiles: List[AgentIdentityProfile] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                profiles.append(from_record(record))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"identity profile {path} is unreadable or corrupt") from exc
        return profiles
