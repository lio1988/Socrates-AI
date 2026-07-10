"""Schema-bound public wrapper for the self-revision lifecycle registry.

The lifecycle's submitted event already commits to the full snapshot hash. This
wrapper additionally requires the stored snapshot version to equal the current
bounded self-review schema. A rewritten or stale top-level version label cannot
silently pass as a current lifecycle record.
"""

from __future__ import annotations

from .revision_registry import (
    REGISTRY_SCHEMA_VERSION,
    SelfRevisionRegistry as _BaseRegistry,
)
from .self_review import SNAPSHOT_VERSION


class SelfRevisionRegistry(_BaseRegistry):
    """Lifecycle registry restricted to the exact current snapshot schema."""

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
