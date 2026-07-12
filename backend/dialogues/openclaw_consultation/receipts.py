"""Tamper-evident consultation receipts and their immutable store.

A receipt binds one canonical request digest to one canonical result digest
plus the isolation flags and provider status. It stores no keys, no auth
headers, and no hidden provider reasoning. The store is append-only and
idempotent: the same (request, result) writes once; a different content under
the same request_id is refused.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .schemas import (
    RECEIPT_VERSION,
    ConsultationError,
    ConsultationResult,
    ExternalConsultationRequest,
    canonical_json,
    clean_hex64,
    clean_id,
    clean_iso,
    clean_request_id,
    digest,
    sha256_text,
)

_RECEIPT_FIELDS = {
    "schema_version", "request_id", "request_digest", "result_digest",
    "requesting_agent_id", "mode", "provider", "model", "consultation_relation",
    "candidate_order", "worker_id", "isolated_session", "tools_disabled",
    "delegation_disabled", "started_at", "completed_at", "provider_status",
    "token_usage", "receipt_digest",
}


def build_receipt(
    request: ExternalConsultationRequest,
    result: ConsultationResult,
    *,
    worker_id: str,
    started_at: str,
    completed_at: str,
    token_usage: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """Bind request+result into an unforgeable receipt record."""
    if result.request_digest != request.request_digest:
        raise ConsultationError("receipt result does not match its request")
    usage: Optional[Dict[str, int]] = None
    if token_usage is not None:
        usage = {}
        for key, value in token_usage.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ConsultationError("token_usage values must be counts")
            usage[clean_id(str(key), field="token_usage key")] = value

    unsigned = {
        "schema_version": RECEIPT_VERSION,
        "request_id": request.request_id,
        "request_digest": request.request_digest,
        "result_digest": result.response_digest,
        "requesting_agent_id": request.requesting_agent_id,
        "mode": request.mode,
        "provider": result.provider,
        "model": result.model,
        "consultation_relation": request.consultation_relation,
        # Resolved judge order: candidate_a -> candidate_order[0],
        # candidate_b -> candidate_order[1] (empty for critic/solver). This
        # makes the verdict->original-candidate mapping auditable from the
        # receipt alone.
        "candidate_order": list(request.candidate_order),
        "worker_id": clean_id(worker_id, field="worker_id"),
        "isolated_session": True,
        "tools_disabled": True,
        "delegation_disabled": True,
        "started_at": clean_iso(started_at, field="started_at"),
        "completed_at": clean_iso(completed_at, field="completed_at"),
        "provider_status": result.provider_status,
        "token_usage": usage,
    }
    record = dict(unsigned)
    record["receipt_digest"] = digest(unsigned)
    return record


def verify_receipt(record: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != _RECEIPT_FIELDS:
        raise ConsultationError("receipt has missing or unknown fields")
    if record.get("schema_version") != RECEIPT_VERSION:
        raise ConsultationError("unknown consultation receipt schema version")
    clean_hex64(record["request_digest"], field="request_digest")
    clean_hex64(record["result_digest"], field="result_digest")
    supplied = str(record.get("receipt_digest", ""))
    unsigned = {key: value for key, value in record.items()
                if key != "receipt_digest"}
    if digest(unsigned) != supplied:
        raise ConsultationError("consultation receipt digest mismatch")
    return dict(record)


#: Bounded wait for a fallback publisher to finish (never an infinite loop).
_PUBLISH_LOCK_TIMEOUT = 5.0
_PUBLISH_LOCK_POLL = 0.005


class ConsultationReceiptStore:
    """One JSON file per request_id, keyed by a HASHED filename (never the raw
    request_id), so a hostile request_id can neither traverse out of the store
    nor collide with a drive/stream marker. Writes are atomic and immutable:
    the first distinct content for a request_id wins; identical content is an
    idempotent success; different content is refused - even under concurrent
    writers.

    Publication is atomic and no-overwrite. The primary path is an atomic
    ``os.link`` (fails if the final already exists). On a filesystem without
    hard-link support, writers serialize on an exclusive sibling *publication
    lock*: the single lock holder re-checks that the final is absent and then
    atomically ``os.replace`` its already-complete temp into place, so no reader
    ever sees an empty or partial final receipt. Losers wait (bounded) for the
    lock, then verify/reconcile; a stuck lock times out as a ConsultationError
    and NEVER overwrites an existing receipt.
    """

    def __init__(self, directory: pathlib.Path | str, *,
                 lock_timeout: float = _PUBLISH_LOCK_TIMEOUT,
                 lock_poll: float = _PUBLISH_LOCK_POLL) -> None:
        self.directory = pathlib.Path(directory)
        self._lock_timeout = lock_timeout
        self._lock_poll = lock_poll

    def _path_for(self, request_id: str) -> pathlib.Path:
        # request_id is validated as a strict identifier, then HASHED for the
        # on-disk name; the raw id never touches the filesystem path.
        safe = clean_request_id(request_id, field="request_id")
        name = f"{sha256_text(safe)}.receipt.json"
        base = self.directory.resolve()
        path = (base / name)
        # Defense-in-depth: the resolved path must stay directly under base.
        if path.resolve().parent != base:
            raise ConsultationError("receipt path escapes the store directory")
        return path

    @staticmethod
    def _lock_for(path: pathlib.Path) -> pathlib.Path:
        stem = path.name.split(".", 1)[0]           # the sha256 hex
        return path.parent / f"{stem}.receipt.lock"

    def _reconcile(self, path: pathlib.Path,
                   verified: Mapping[str, Any]) -> pathlib.Path:
        """A final receipt already exists: verify it, then return idempotently
        if it is byte-for-byte the same consultation, else refuse the conflict.
        The existing final receipt is re-verified before any idempotent return.

        Any read/parse failure is normalized to ConsultationError (defense in
        depth) with a safe message - never a raw JSON/filesystem exception and
        never raw file contents.
        """
        try:
            existing = verify_receipt(json.loads(
                path.read_text(encoding="utf-8")))
        except ConsultationError:
            raise                                    # already safe + specific
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, TypeError,
                ValueError):
            raise ConsultationError(
                "existing consultation receipt could not be read for "
                "reconciliation")
        if existing["receipt_digest"] != verified["receipt_digest"]:
            raise ConsultationError(
                "conflicting consultation receipt for the same request_id")
        return path

    def _fallback_publish(self, path: pathlib.Path, tmp: pathlib.Path,
                          verified: Mapping[str, Any]) -> pathlib.Path:
        """No hard-link support: serialize publication on an exclusive sibling
        lock, then atomically replace the already-complete temp into place."""
        lock = self._lock_for(path)
        deadline = time.monotonic() + self._lock_timeout
        while True:
            if path.exists():
                return self._reconcile(path, verified)   # already published
            try:
                fd = os.open(os.fspath(lock),
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                # Another writer is publishing: wait (bounded), then reconcile.
                if time.monotonic() >= deadline:
                    raise ConsultationError(
                        "consultation receipt publication lock timed out")
                time.sleep(self._lock_poll)
                continue
            try:
                if path.exists():
                    # Published while we were acquiring the lock: never overwrite.
                    return self._reconcile(path, verified)
                os.replace(tmp, path)   # atomic; temp is already fully written
                return path
            finally:
                os.close(fd)
                try:
                    os.unlink(lock)
                except FileNotFoundError:
                    pass

    def save(self, record: Mapping[str, Any]) -> pathlib.Path:
        verified = verify_receipt(record)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(verified["request_id"])
        if path.exists():
            return self._reconcile(path, verified)

        payload = json.dumps(verified, ensure_ascii=False, sort_keys=True,
                             indent=2) + "\n"
        # Unique per-writer temp in the SAME directory (never a shared name),
        # written in FULL before any publication is attempted.
        tmp = self.directory / f".{uuid.uuid4().hex}.receipt.tmp"
        try:
            with open(tmp, "x", encoding="utf-8") as handle:
                handle.write(payload)
            try:
                os.link(tmp, path)          # primary: atomic, fails if exists
            except FileExistsError:
                return self._reconcile(path, verified)
            except (OSError, NotImplementedError):
                # No hard-link support: lock-serialized atomic-replace publish.
                return self._fallback_publish(path, tmp, verified)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        return path

    def load(self, request_id: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(request_id)
        if not path.exists():
            return None
        return verify_receipt(json.loads(path.read_text(encoding="utf-8")))

    def all_receipts(self) -> List[Dict[str, Any]]:
        if not self.directory.exists():
            return []
        return [verify_receipt(json.loads(p.read_text(encoding="utf-8")))
                for p in sorted(self.directory.glob("*.receipt.json"))]


__all__ = [
    "build_receipt", "verify_receipt", "ConsultationReceiptStore",
]
