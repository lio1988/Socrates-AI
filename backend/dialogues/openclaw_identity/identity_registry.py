"""
OpenClaw Agent Identity — the identity registry (persistence).

Profiles must survive across sessions to be identities at all: a promotion
earned last week is meaningless if the record evaporates with the process.
The registry stores one human-readable JSON file per agent
(``<directory>/<agent_id>.json``, sorted keys) so every profile — and its
append-only version history — is diffable, reviewable, and auditable in git
or on disk.

Storage only. The registry grants nothing: loading a profile confers no
authority, and nothing in the runtime pipeline reads it (the CED core does
not import this package — test-locked).

Pure stdlib, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from .identity_profile import AgentIdentityProfile, from_record

#: agent_id must be filesystem-safe (it becomes the file name).
_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class IdentityRegistry:
    """One JSON file per agent profile under a chosen directory."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path_for(self, agent_id: str) -> Path:
        if not _AGENT_ID_RE.match(agent_id or ""):
            raise ValueError(
                f"agent_id {agent_id!r} is not filesystem-safe "
                "(allowed: letters, digits, dot, underscore, hyphen)")
        return self.directory / f"{agent_id}.json"

    def save_profile(self, profile: AgentIdentityProfile) -> Path:
        """Write the profile as sorted-key JSON. Overwrites the agent's own
        previous file only — history inside the record is append-only by
        construction (record_promotion never drops entries)."""
        path = self._path_for(profile.agent_id)
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(profile.to_record(), ensure_ascii=False,
                       sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        return path

    def load_profile(self, agent_id: str) -> Optional[AgentIdentityProfile]:
        """Load one agent's profile; None when it has never been saved."""
        path = self._path_for(agent_id)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        return from_record(record)

    def all_profiles(self) -> List[AgentIdentityProfile]:
        """Every stored profile, deterministically ordered by agent_id."""
        if not self.directory.exists():
            return []
        profiles: List[AgentIdentityProfile] = []
        for path in sorted(self.directory.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            profiles.append(from_record(record))
        return profiles
