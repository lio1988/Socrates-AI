"""Schema-bound public wrapper for the self-revision lifecycle registry.

The lifecycle's submitted event commits to the full snapshot hash. This wrapper
also requires both submitted and stored snapshot versions to equal the current
bounded self-review schema. Stale or forged schema labels fail before any file is
written and remain visible if encountered in stored history.
"""

from __future__ import annotations

from .revision_registry import (
    REGISTRY_SCHEMA_VERSION,
    SelfRevisionRegistry as _BaseRegistry,
)
from .self_review import SNAPSHOT_VERSION, SelfReviewSnapshot
from .self_revision import SelfRevisionProposal


class SelfRevisionRegistry(_BaseRegistry):
    """Lifecycle registry restricted to the exact current snapshot schema."""

    def submit(
        self,
        proposal: SelfRevisionProposal,
        *,
        snapshot: SelfReviewSnapshot,
        submitted_on: str = "",
    ):
        if not isinstance(snapshot, SelfReviewSnapshot):
            raise ValueError("submit requires a SelfReviewSnapshot")
        if snapshot.snapshot_version != SNAPSHOT_VERSION:
            raise ValueError(
                "self-revision snapshot version is not the current governed "
                f"version {SNAPSHOT_VERSION!r}")
        return super().submit(
            proposal,
            snapshot=snapshot,
            submitted_on=submitted_on,
        )

    def _load_path(self, path):
        record = super()._load_path(path)
        if record is None:
            return None
        if record.get("snapshot_version") != SNAPSHOT_VERSION:
            raise ValueError(
                f"self-revision registry record {path} uses snapshot_version "
                f"{record.get('snapshot_version')!r}; expected {SNAPSHOT_VERSION!r}")
        submitted = record.get("events", [{}])[0]
        if submitted.get("snapshot_fingerprint") != record.get(
                "snapshot_fingerprint"):
            raise ValueError(
                f"self-revision registry record {path} does not bind its "
                "snapshot fingerprint")
        return record


__all__ = ["REGISTRY_SCHEMA_VERSION", "SelfRevisionRegistry"]
