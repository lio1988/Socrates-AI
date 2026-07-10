"""Trusted evidence records for governed agent self-revision.

An agent may cite evidence but must never author the trusted manifest that
validates its own Memory, Identity, or Soul changes. This module provides
immutable, atomic evidence records written by a named non-self instrument or
reviewer.

Each reference is globally unique inside the registry. Rewriting a reference
with different content is refused; exact re-registration is idempotent. Optional
``outcomes`` explicitly declare whether post-change evidence supports
``confirmed`` or ``reverted`` probation results.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .self_revision import REVISION_TARGET_ACTIONS

EVIDENCE_SCHEMA_VERSION = "openclaw_self_revision_evidence_v2"

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_REFERENCE_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
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
_ALLOWED_SUPPORTS = frozenset(
    f"{target}:{action}"
    for target, actions in REVISION_TARGET_ACTIONS.items()
    for action in actions
)
_ALLOWED_OUTCOMES = frozenset({"confirmed", "reverted"})
_ENVELOPE_FIELDS = {"schema_version", "evidence", "record_hash"}
_RECORD_FIELDS = {
    "reference", "agent_id", "source", "supports", "value", "verified",
    "verified_by", "verification_reference", "observed_on", "outcomes",
}


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
        raise ValueError("evidence data must be canonical JSON") from exc


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


def _clean_outcomes(values: Iterable[Any]) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("outcomes must be a sequence, not text")
    outcomes = tuple(sorted({
        _clean_text(value, field="outcome", maximum=32)
        for value in values
    }))
    unknown = sorted(set(outcomes) - _ALLOWED_OUTCOMES)
    if unknown:
        raise ValueError(f"unknown probation outcomes: {unknown}")
    return outcomes


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
    outcomes: Tuple[str, ...] = ()

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
        observed_on = _clean_optional_text(
            self.observed_on, field="observed_on", maximum=64)
        outcomes = _clean_outcomes(self.outcomes)

        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "supports", supports)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "verified_by", verified_by)
        object.__setattr__(self, "verification_reference", verification_reference)
        object.__setattr__(self, "observed_on", observed_on)
        object.__setattr__(self, "outcomes", outcomes)

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
            "outcomes": list(self.outcomes),
        }

    def to_manifest_entry(self) -> Dict[str, Any]:
        """Return the exact shape consumed by revision evaluation/outcomes."""
        return {
            "agent_id": self.agent_id,
            "verified": True,
            "source": self.source,
            "supports": list(self.supports),
            "value": self.value,
            "verified_by": self.verified_by,
            "verification_reference": self.verification_reference,
            "observed_on": self.observed_on,
            "outcomes": list(self.outcomes),
        }


def evidence_from_record(record: Mapping[str, Any]) -> RevisionEvidenceRecord:
    if not isinstance(record, Mapping):
        raise ValueError("evidence record must be a mapping")
    if set(record) != _RECORD_FIELDS:
        raise ValueError("evidence record contains missing or unknown fields")
    if record.get("verified") is not True:
        raise ValueError("trusted evidence records must be explicitly verified")
    raw_supports = record.get("supports") or ()
    raw_outcomes = record.get("outcomes") or ()
    if isinstance(raw_supports, (str, bytes)):
        raise ValueError("supports must be a sequence, not text")
    if isinstance(raw_outcomes, (str, bytes)):
        raise ValueError("outcomes must be a sequence, not text")
    return RevisionEvidenceRecord(
        reference=record.get("reference", ""),
        agent_id=record.get("agent_id", ""),
        source=record.get("source", ""),
        supports=tuple(raw_supports),
        value=record.get("value", ""),
        verified_by=record.get("verified_by", ""),
        verification_reference=record.get("verification_reference", ""),
        observed_on=record.get("observed_on", ""),
        outcomes=tuple(raw_outcomes),
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
                f"evidence record {path} is locked by another registration") from exc
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
        if set(envelope) != _ENVELOPE_FIELDS:
            raise ValueError("evidence envelope contains invalid fields")
        if envelope.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unknown self-revision evidence schema version")
        supplied_hash = str(envelope.get("record_hash", ""))
        if not _HEX64_RE.fullmatch(supplied_hash):
            raise ValueError("evidence envelope record_hash is invalid")
        unhashed = dict(envelope)
        unhashed.pop("record_hash", None)
        if _record_hash(unhashed) != supplied_hash:
            raise ValueError("evidence envelope content does not match record_hash")
        evidence = evidence_from_record(envelope.get("evidence") or {})
        if expected_reference and evidence.reference != expected_reference:
            raise ValueError("evidence reference does not match requested record")
        return evidence

    def register(self, evidence: RevisionEvidenceRecord) -> Path:
        """Register evidence once; exact repetition is idempotent."""
        path = self._path_for(evidence.reference)
        with self._locked(path):
            if path.exists():
                existing = self.load(evidence.reference)
                if existing == evidence:
                    return path
                raise ValueError(
                    "evidence reference already exists with conflicting content")

            envelope = self._envelope(evidence)
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
        """Build the trusted mapping consumed by snapshot and lifecycle APIs."""
        return {
            evidence.reference: evidence.to_manifest_entry()
            for evidence in self.all_records(agent_id)
        }
