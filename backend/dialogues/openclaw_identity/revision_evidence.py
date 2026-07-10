"""Trusted evidence records for governed agent self-revision.

A self-revision proposal cites evidence IDs, but the agent must never author the
trusted manifest that validates those IDs. This module provides immutable,
atomic evidence records written by a named non-self instrument or reviewer.

Each reference is globally unique inside the registry. Rewriting a reference
with different content is refused; identical re-registration is idempotent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .self_revision import REVISION_TARGET_ACTIONS

EVIDENCE_SCHEMA_VERSION = "openclaw_self_revision_evidence_v1"

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_REFERENCE_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)
_ALLOWED_SUPPORTS = frozenset(
    f"{target}:{action}"
    for target, actions in REVISION_TARGET_ACTIONS.items()
    for action in actions
)


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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _record_hash(record_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(record_without_hash).encode("utf-8")
    ).hexdigest()


def _reference_filename(reference: str) -> str:
    return hashlib.sha256(reference.encode("utf-8")).hexdigest() + ".json"


def _clean_supports(values: Iterable[Any]) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("supports must be a sequence, not text")
    supports = tuple(sorted({
        _clean_text(value, field="support", maximum=128)
        for value in values
    }))
    if not supports:
        raise ValueError("evidence record requires at least one support")
    unknown = sorted(set(supports) - _ALLOWED_SUPPORTS)
    if unknown:
        raise ValueError(f"unknown self-revision supports: {unknown}")
    return supports


@dataclass(frozen=True)
class RevisionEvidenceRecord:
    """One immutable, verified evidence claim owned by one agent seat."""

    reference: str
    agent_id: str
    source: str
    supports: Tuple[str, ...]
    value: str
    verified_by: str
    verification_reference: str
    observed_on: str = ""

    def __post_init__(self) -> None:
        reference = _clean_text(
            self.reference, field="reference", maximum=256)
        if not _REFERENCE_RE.fullmatch(reference):
            raise ValueError("evidence reference contains unsupported characters")
        agent_id = _clean_text(self.agent_id, field="agent_id", maximum=128)
        if not _AGENT_ID_RE.fullmatch(agent_id):
            raise ValueError("evidence agent_id is not filesystem-safe")
        source = _clean_text(self.source, field="source", maximum=512)
        supports = _clean_supports(self.supports)
        value = _clean_text(self.value, field="value", maximum=500)
        verified_by = _clean_text(
            self.verified_by, field="verified_by", maximum=128)
        if verified_by == agent_id:
            raise ValueError("an agent cannot verify its own self-revision evidence")
        verification_reference = _clean_text(
            self.verification_reference,
            field="verification_reference",
            maximum=512,
        )
        observed_on = str(self.observed_on or "").strip()

        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "supports", supports)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "verified_by", verified_by)
        object.__setattr__(self, "verification_reference", verification_reference)
        object.__setattr__(self, "observed_on", observed_on)

    def to_record(self) -> Dict[str, Any]:
        return {
            "reference": self.reference,
            "agent_id": self.agent_id,
            "source": self.source,
            "supports": list(self.supports),
            "value": self.value,
            "verified": True,
            "verified_by": self.verified_by,
            "verification_reference": self.verification_reference,
            "observed_on": self.observed_on,
        }

    def to_manifest_entry(self) -> Dict[str, Any]:
        """Return the exact shape consumed by self-revision evaluation."""
        return {
            "agent_id": self.agent_id,
            "verified": True,
            "source": self.source,
            "supports": list(self.supports),
            "value": self.value,
            "verified_by": self.verified_by,
            "verification_reference": self.verification_reference,
            "observed_on": self.observed_on,
        }


def evidence_from_record(record: Mapping[str, Any]) -> RevisionEvidenceRecord:
    if not isinstance(record, Mapping):
        raise ValueError("evidence record must be a mapping")
    allowed = {
        "reference", "agent_id", "source", "supports", "value", "verified",
        "verified_by", "verification_reference", "observed_on",
    }
    extras = set(record) - allowed
    if extras:
        raise ValueError(f"evidence record contains unknown fields: {sorted(extras)}")
    if record.get("verified") is not True:
        raise ValueError("trusted evidence records must be explicitly verified")
    raw_supports = record.get("supports") or ()
    if isinstance(raw_supports, (str, bytes)):
        raise ValueError("supports must be a sequence, not text")
    return RevisionEvidenceRecord(
        reference=record.get("reference", ""),
        agent_id=record.get("agent_id", ""),
        source=record.get("source", ""),
        supports=tuple(raw_supports),
        value=record.get("value", ""),
        verified_by=record.get("verified_by", ""),
        verification_reference=record.get("verification_reference", ""),
        observed_on=record.get("observed_on", ""),
    )


class RevisionEvidenceRegistry:
    """Atomic immutable storage for system-owned verified evidence records."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path_for(self, reference: str) -> Path:
        reference = _clean_text(reference, field="reference", maximum=256)
        if not _REFERENCE_RE.fullmatch(reference):
            raise ValueError("evidence reference contains unsupported characters")
        return self.directory / _reference_filename(reference)

    def _envelope(self, evidence: RevisionEvidenceRecord) -> Dict[str, Any]:
        envelope = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "evidence": evidence.to_record(),
        }
        envelope["record_hash"] = _record_hash(envelope)
        return envelope

    def _validate_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        expected_reference: str = "",
    ) -> RevisionEvidenceRecord:
        if not isinstance(envelope, Mapping):
            raise ValueError("evidence envelope must be a mapping")
        if envelope.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unknown self-revision evidence schema version")
        supplied_hash = str(envelope.get("record_hash", ""))
        unhashed = dict(envelope)
        unhashed.pop("record_hash", None)
        if _record_hash(unhashed) != supplied_hash:
            raise ValueError("evidence envelope content does not match record_hash")
        evidence = evidence_from_record(envelope.get("evidence") or {})
        if expected_reference and evidence.reference != expected_reference:
            raise ValueError("evidence reference does not match requested record")
        return evidence

    def register(self, evidence: RevisionEvidenceRecord) -> Path:
        """Register evidence once; identical repetition is idempotent."""
        path = self._path_for(evidence.reference)
        envelope = self._envelope(evidence)
        if path.exists():
            existing = self.load(evidence.reference)
            if existing == evidence:
                return path
            raise ValueError(
                "evidence reference already exists with conflicting content")

        self.directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            envelope,
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
                prefix=".evidence.",
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

    def load(self, reference: str) -> Optional[RevisionEvidenceRecord]:
        path = self._path_for(reference)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            return self._validate_envelope(
                envelope, expected_reference=reference)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"self-revision evidence record {path} is unreadable or corrupt"
            ) from exc

    def all_records(self, agent_id: str = "") -> List[RevisionEvidenceRecord]:
        if agent_id and not _AGENT_ID_RE.fullmatch(agent_id):
            raise ValueError("agent_id is not filesystem-safe")
        if not self.directory.exists():
            return []
        records = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                evidence = self._validate_envelope(envelope)
                if path.name != _reference_filename(evidence.reference):
                    raise ValueError("evidence filename does not match reference")
                if not agent_id or evidence.agent_id == agent_id:
                    records.append(evidence)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"self-revision evidence record {path} is unreadable or corrupt"
                ) from exc
        return sorted(records, key=lambda record: record.reference)

    def manifest(self, agent_id: str = "") -> Dict[str, Dict[str, Any]]:
        """Build the trusted mapping consumed by snapshot and evaluation APIs."""
        return {
            evidence.reference: evidence.to_manifest_entry()
            for evidence in self.all_records(agent_id)
        }
