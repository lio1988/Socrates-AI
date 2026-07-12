"""Tamper-evident Micro-Socratic receipts and their immutable store.

A receipt binds one canonical request digest to one canonical check digest plus
the isolation flags and provider status. It stores no keys, no auth headers, and
no hidden auditor reasoning. The store is append-only and idempotent: the same
(request, check) writes once; a different content under the same request_id is
refused.

The store reuses the repository's hardened receipt-persistence conventions
(hashed containment-checked filenames, unique temp, atomic no-overwrite publish)
and additionally fixes the Windows ``DELETE_PENDING`` race: a fallback publisher
whose lock acquire hits ``PermissionError`` (ERROR_ACCESS_DENIED while a peer's
lock is being unlinked) treats it as contention and waits, never leaking a raw
filesystem exception.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional

from .schemas import (
    RECEIPT_VERSION,
    MicroSocraticCheck,
    MicroSocraticError,
    MicroSocraticRequest,
    clean_hex64,
    clean_id,
    clean_iso,
    clean_request_id,
    digest,
    sha256_text,
)

_RECEIPT_FIELDS = {
    "schema_version", "request_id", "request_digest", "result_digest",
    "agent_id", "mode", "provider", "model", "decision", "worker_id",
    "isolated_check", "tools_executed", "consultation_executed", "inner_rounds",
    "started_at", "completed_at", "provider_status", "token_usage",
    "receipt_digest",
}

#: Bounded wait for a fallback publisher to finish (never an infinite loop).
_PUBLISH_LOCK_TIMEOUT = 5.0
_PUBLISH_LOCK_POLL = 0.005


def build_receipt(
    request: MicroSocraticRequest,
    check: MicroSocraticCheck,
    *,
    worker_id: str,
    started_at: str,
    completed_at: str,
    token_usage: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """Bind request+check into an unforgeable receipt record."""
    if check.request_digest != request.request_digest:
        raise MicroSocraticError("receipt check does not match its request")
    usage: Optional[Dict[str, int]] = None
    if token_usage is not None:
        usage = {}
        for key, value in token_usage.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise MicroSocraticError("token_usage values must be counts")
            usage[clean_id(str(key), field="token_usage key")] = value

    unsigned = {
        "schema_version": RECEIPT_VERSION,
        "request_id": request.request_id,
        "request_digest": request.request_digest,
        "result_digest": check.response_digest,
        "agent_id": request.agent_id,
        "mode": request.mode,
        "provider": check.provider,
        "model": check.model,
        # The bounded recommendation, surfaced for audit - NOT an approval.
        "decision": check.decision,
        "worker_id": clean_id(worker_id, field="worker_id"),
        "isolated_check": True,
        "tools_executed": False,
        "consultation_executed": False,
        "inner_rounds": check.inner_rounds,
        "started_at": clean_iso(started_at, field="started_at"),
        "completed_at": clean_iso(completed_at, field="completed_at"),
        "provider_status": check.provider_status,
        "token_usage": usage,
    }
    record = dict(unsigned)
    record["receipt_digest"] = digest(unsigned)
    return record


def verify_receipt(record: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != _RECEIPT_FIELDS:
        raise MicroSocraticError("receipt has missing or unknown fields")
    if record.get("schema_version") != RECEIPT_VERSION:
        raise MicroSocraticError("unknown kernel receipt schema version")
    clean_hex64(record["request_digest"], field="request_digest")
    clean_hex64(record["result_digest"], field="result_digest")
    supplied = str(record.get("receipt_digest", ""))
    unsigned = {key: value for key, value in record.items()
                if key != "receipt_digest"}
    if digest(unsigned) != supplied:
        raise MicroSocraticError("kernel receipt digest mismatch")
    return dict(record)


class MicroSocraticReceiptStore:
    """One JSON file per request_id, keyed by a HASHED filename (never the raw
    request_id), so a hostile request_id can neither traverse out of the store
    nor collide with a drive/stream marker. Writes are atomic and immutable:
    the first distinct content for a request_id wins; identical content is an
    idempotent success; different content is refused - even under concurrent
    writers.

    Publication is atomic and no-overwrite. The primary path is an atomic
    ``os.link``. On a filesystem without hard-link support, writers serialize on
    an exclusive sibling *publication lock*, then atomically ``os.replace`` the
    already-complete temp into place. A racing lock acquire that hits Windows
    DELETE_PENDING (``PermissionError``) is treated as contention (bounded wait),
    so no raw filesystem exception escapes and a stuck lock times out as a clean
    MicroSocraticError without ever overwriting an existing receipt.
    """

    def __init__(self, directory: pathlib.Path | str, *,
                 lock_timeout: float = _PUBLISH_LOCK_TIMEOUT,
                 lock_poll: float = _PUBLISH_LOCK_POLL) -> None:
        self.directory = pathlib.Path(directory)
        self._lock_timeout = lock_timeout
        self._lock_poll = lock_poll

    def _path_for(self, request_id: str) -> pathlib.Path:
        safe = clean_request_id(request_id, field="request_id")
        name = f"{sha256_text(safe)}.receipt.json"
        base = self.directory.resolve()
        path = (base / name)
        if path.resolve().parent != base:
            raise MicroSocraticError("receipt path escapes the store directory")
        return path

    @staticmethod
    def _lock_for(path: pathlib.Path) -> pathlib.Path:
        stem = path.name.split(".", 1)[0]           # the sha256 hex
        return path.parent / f"{stem}.receipt.lock"

    def _reconcile(self, path: pathlib.Path,
                   verified: Mapping[str, Any]) -> pathlib.Path:
        """A final receipt already exists: verify it, then return idempotently
        if it is byte-for-byte the same check, else refuse the conflict. Any
        read/parse failure is normalized to MicroSocraticError (no raw JSON/
        filesystem exception, no raw file contents)."""
        try:
            existing = verify_receipt(json.loads(
                path.read_text(encoding="utf-8")))
        except MicroSocraticError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, TypeError,
                ValueError):
            raise MicroSocraticError(
                "existing kernel receipt could not be read for reconciliation")
        if existing["receipt_digest"] != verified["receipt_digest"]:
            raise MicroSocraticError(
                "conflicting kernel receipt for the same request_id")
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
            except (FileExistsError, PermissionError):
                # Held by a peer, OR Windows DELETE_PENDING while a peer unlinks
                # its lock (ERROR_ACCESS_DENIED -> PermissionError). Both are
                # transient contention: wait (bounded), then reconcile.
                if time.monotonic() >= deadline:
                    raise MicroSocraticError(
                        "kernel receipt publication lock timed out")
                time.sleep(self._lock_poll)
                continue
            try:
                if path.exists():
                    return self._reconcile(path, verified)   # never overwrite
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
        tmp = self.directory / f".{uuid.uuid4().hex}.receipt.tmp"
        try:
            with open(tmp, "x", encoding="utf-8") as handle:
                handle.write(payload)
            try:
                os.link(tmp, path)          # primary: atomic, fails if exists
            except FileExistsError:
                return self._reconcile(path, verified)
            except (OSError, NotImplementedError):
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
    "build_receipt", "verify_receipt", "MicroSocraticReceiptStore",
]
