"""Terminal-aware and semantics-aware self-revision transaction recovery.

A committed application journal binds the lifecycle's unique `applied` event.
Later probation outcomes append `confirmed` or `reverted` events, so recovery
verifies the original application event rather than assuming it remains the
final event forever.

This wrapper also revalidates journal semantics beyond the internal hash chain:
non-self application actor, endpoint fingerprints, lifecycle hash shape, and the
final commit digest.
"""

from __future__ import annotations

import re

from .revision_transaction import (
    SelfRevisionTransactionCoordinator as _BaseCoordinator,
    _digest,
)
from .self_review import profile_fingerprint

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class SelfRevisionTransactionCoordinator(_BaseCoordinator):
    """Coordinator with terminal-aware and semantic journal verification."""

    def _load_path(self, path):
        record = super()._load_path(path)
        if record is None:
            return None
        payload = record["payload"]
        agent_id = record["agent_id"]
        proposal_id = record["proposal_id"]
        actor = str(payload.get("application_actor", "")).strip()
        if not actor or actor == agent_id:
            raise ValueError(
                f"self-revision transaction {path} has invalid application actor")

        events = record["events"]
        updated = str(payload["updated_governed_fingerprint"])
        if len(events) >= 2:
            identity_saved = events[1]
            if identity_saved.get("governed_profile_fingerprint") != updated:
                raise ValueError(
                    f"self-revision transaction {path} identity endpoint mismatch")
            observational = str(
                identity_saved.get("observational_profile_fingerprint", ""))
            if not _HEX64_RE.fullmatch(observational):
                raise ValueError(
                    f"self-revision transaction {path} has invalid observational "
                    "fingerprint")
        if len(events) >= 3:
            lifecycle_recorded = events[2]
            if lifecycle_recorded.get("governed_profile_fingerprint") != updated:
                raise ValueError(
                    f"self-revision transaction {path} lifecycle endpoint mismatch")
            lifecycle_hash = str(
                lifecycle_recorded.get("lifecycle_event_hash", ""))
            if not _HEX64_RE.fullmatch(lifecycle_hash):
                raise ValueError(
                    f"self-revision transaction {path} has invalid lifecycle hash")
        if len(events) == 4:
            lifecycle_hash = events[2]["lifecycle_event_hash"]
            expected = _digest({
                "agent_id": agent_id,
                "proposal_id": proposal_id,
                "updated_governed_fingerprint": updated,
                "lifecycle_event_hash": lifecycle_hash,
            })
            if events[3].get("commit_digest") != expected:
                raise ValueError(
                    f"self-revision transaction {path} commit digest mismatch")
        return record

    def recover(self, agent_id: str, proposal_id: str):
        """Complete an interrupted journal or verify a committed application.

        `probationary`, `confirmed`, and `reverted` are all valid lifecycle
        states after the application transaction has committed. The journal is
        anchored to the unique `applied` event hash, not to the mutable tail of
        the later probation lifecycle.
        """
        path = self._path_for(agent_id, proposal_id)
        with self._locked(path):
            record = self._load_path(path)
            if record is None:
                raise ValueError("self-revision transaction does not exist")
            if record["state"] != "committed":
                return self._continue_locked(path, record)

            payload = record["payload"]
            current = self.identity_registry.load_profile(agent_id)
            if current is None or profile_fingerprint(current) != \
                    payload["updated_governed_fingerprint"]:
                raise ValueError(
                    "committed transaction no longer matches identity state")

            lifecycle = self.lifecycle_registry.load(agent_id, proposal_id)
            if lifecycle is None or lifecycle["status"] not in {
                    "probationary", "confirmed", "reverted"}:
                raise ValueError(
                    "committed transaction no longer matches lifecycle state")
            applied_events = [
                event for event in lifecycle["events"]
                if event.get("event_type") == "applied"
            ]
            if len(applied_events) != 1:
                raise ValueError(
                    "committed transaction requires exactly one lifecycle "
                    "application event")
            lifecycle_recorded = record["events"][-2]
            if lifecycle_recorded.get("event_type") != "lifecycle_recorded":
                raise ValueError(
                    "committed transaction is missing lifecycle_recorded event")
            if applied_events[0]["event_hash"] != \
                    lifecycle_recorded["lifecycle_event_hash"]:
                raise ValueError(
                    "committed transaction application hash no longer matches")
            return current
