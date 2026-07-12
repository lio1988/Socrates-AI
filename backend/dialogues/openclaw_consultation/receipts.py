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


#: Bounded wait for a publisher to finish (never an infinite loop).
_PUBLISH_LOCK_TIMEOUT = 5.0
_PUBLISH_LOCK_POLL = 0.005
#: Bounded retries if a freshly generated temp name already exists (a foreign
#: temp we must never touch); a fresh UUID is tried each time.
_TEMP_CREATE_ATTEMPTS = 8


class ConsultationReceiptStore:
    """One JSON file per request_id, keyed by a HASHED filename (never the raw
    request_id), so a hostile request_id can neither traverse out of the store
    nor collide with a drive/stream marker. Writes are atomic and immutable:
    the first distinct content for a request_id wins; identical content is an
    idempotent success; different content is refused - even under concurrent
    writers mixing hard-link-capable and hard-link-less filesystems.

    ALL publication participates in ONE exclusive sibling *publication lock*.
    The single lock holder re-checks that the final is absent, then publishes
    with the preferred atomic ``os.link`` (falling back to ``os.replace`` of an
    already-complete temp only when hard links are unsupported) - both executed
    while it still owns the lock, so a primary and a fallback writer can never
    both publish. Losers wait (bounded, on a single monotonic deadline), then
    verify/reconcile; a stuck lock times out as a ConsultationError and NEVER
    overwrites an existing receipt. Expected filesystem/decoding/parsing/data
    failures on the public API surface are normalized to ConsultationError.
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

    # ── strict, normalized read of an existing final receipt ─────────────────

    def _read_verified_final(self, path: pathlib.Path, *,
                             deadline: Optional[float] = None) -> Dict[str, Any]:
        """Read + parse + schema-verify one final receipt. Every expected
        filesystem/decoding/parsing/data failure becomes ConsultationError with
        a safe message (never a raw exception, never raw file contents). A
        transient Windows sharing denial (PermissionError) right after a peer
        publishes is retried, but ONLY within the single publication deadline
        and never as a filesystem operation started after it expires."""
        while True:
            try:
                return verify_receipt(json.loads(
                    path.read_text(encoding="utf-8")))
            except ConsultationError:
                raise                                # already safe + specific
            except PermissionError:
                if deadline is None:
                    raise ConsultationError(
                        "existing consultation receipt could not be read for "
                        "reconciliation") from None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ConsultationError(
                        "consultation receipt reconciliation timed out"
                    ) from None
                time.sleep(min(self._lock_poll, remaining))
                if time.monotonic() >= deadline:     # no post-deadline re-read
                    raise ConsultationError(
                        "consultation receipt reconciliation timed out"
                    ) from None
            except (json.JSONDecodeError, UnicodeDecodeError, OSError,
                    TypeError, ValueError):
                raise ConsultationError(
                    "existing consultation receipt could not be read for "
                    "reconciliation") from None

    def _reconcile(self, path: pathlib.Path, verified: Mapping[str, Any], *,
                   deadline: Optional[float] = None) -> pathlib.Path:
        """A final receipt already exists: verify it, then return idempotently
        if it is byte-for-byte the same consultation, else refuse the conflict.
        The existing final is re-verified before any idempotent return."""
        existing = self._read_verified_final(path, deadline=deadline)
        if existing["receipt_digest"] != verified["receipt_digest"]:
            raise ConsultationError(
                "conflicting consultation receipt for the same request_id")
        return path

    # ── the single publication protocol ──────────────────────────────────────

    def _acquire_lock(self, lock: pathlib.Path, path: pathlib.Path,
                      deadline: float) -> Optional[int]:
        """Acquire the exclusive publication lock, or return None if the final
        was already published (caller reconciles - never overwrites). Bounded by
        the single deadline; contention (peer-held lock, or Windows
        DELETE_PENDING PermissionError while a peer unlinks its lock) waits and
        retries, other OSErrors and timeout become ConsultationError."""
        while True:
            if path.exists():
                return None                          # already published
            try:
                return os.open(os.fspath(lock),
                               os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except (FileExistsError, PermissionError):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ConsultationError(
                        "consultation receipt publication lock timed out"
                    ) from None
                time.sleep(min(self._lock_poll, remaining))
                if time.monotonic() >= deadline:     # no post-deadline acquire
                    raise ConsultationError(
                        "consultation receipt publication lock timed out"
                    ) from None
            except OSError:
                raise ConsultationError(
                    "consultation receipt publication lock acquisition failed"
                ) from None

    def _create_temp(self, payload: str) -> pathlib.Path:
        """Create and fully write a UNIQUE per-writer temp. On the (astronomic)
        chance the generated name already exists it is a FOREIGN temp: never
        touched, a fresh UUID is tried, bounded. Returns a temp this writer owns."""
        for _ in range(_TEMP_CREATE_ATTEMPTS):
            candidate = self.directory / f".{uuid.uuid4().hex}.receipt.tmp"
            try:
                with open(candidate, "x", encoding="utf-8") as handle:
                    handle.write(payload)
                return candidate                     # created + owned by us
            except FileExistsError:
                continue                             # foreign temp: do not touch
            except OSError:
                raise ConsultationError(
                    "consultation receipt temp write failed") from None
        raise ConsultationError(
            "consultation receipt temp allocation failed after retries")

    def _cleanup(self, *, lock_fd: Optional[int], lock: pathlib.Path,
                 lock_owned: bool, tmp: Optional[pathlib.Path],
                 temp_owned: bool) -> List[str]:
        """Independently attempt every writer-owned cleanup. One failure never
        blocks the others; a foreign lock/temp is never removed; the published
        final is never touched. Returns non-fatal cleanup error tags (never
        raises), so the caller can preserve the primary cause."""
        errors: List[str] = []
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError as exc:
                errors.append(f"lock-close {exc.__class__.__name__}")
        if lock_owned:
            try:
                os.unlink(lock)
            except FileNotFoundError:
                pass
            except OSError as exc:
                errors.append(f"lock-unlink {exc.__class__.__name__}")
        if temp_owned and tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            except OSError as exc:
                errors.append(f"temp-unlink {exc.__class__.__name__}")
        return errors

    def save(self, record: Mapping[str, Any]) -> pathlib.Path:
        verified = verify_receipt(record)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(verified["request_id"])
        lock = self._lock_for(path)
        # ONE monotonic deadline for the ENTIRE publication attempt - never
        # reset when switching from lock acquisition to publication/reconcile.
        deadline = time.monotonic() + self._lock_timeout

        lock_fd: Optional[int] = None
        lock_owned = False
        tmp: Optional[pathlib.Path] = None
        temp_owned = False
        primary_exc: Optional[ConsultationError] = None
        result: Optional[pathlib.Path] = None
        try:
            lock_fd = self._acquire_lock(lock, path, deadline)
            if lock_fd is None:
                # Already published (peer or prior run): reconcile, never overwrite.
                result = self._reconcile(path, verified, deadline=deadline)
            else:
                lock_owned = True
                if path.exists():                    # never overwrite an existing final
                    result = self._reconcile(path, verified, deadline=deadline)
                else:
                    payload = json.dumps(verified, ensure_ascii=False,
                                         sort_keys=True, indent=2) + "\n"
                    tmp = self._create_temp(payload)
                    temp_owned = True
                    # Prefer os.link; fall back to os.replace - BOTH under the lock.
                    try:
                        os.link(tmp, path)
                    except FileExistsError:
                        # Cannot happen under the lock, but never overwrite.
                        result = self._reconcile(path, verified,
                                                 deadline=deadline)
                    except (OSError, NotImplementedError):
                        try:
                            os.replace(tmp, path)
                            temp_owned = False       # replace consumed the temp
                        except OSError:
                            raise ConsultationError(
                                "consultation receipt publication failed"
                            ) from None
                        result = path
                    else:
                        result = path
        except ConsultationError as exc:
            primary_exc = exc
        finally:
            cleanup_errors = self._cleanup(
                lock_fd=lock_fd, lock=lock, lock_owned=lock_owned,
                tmp=tmp, temp_owned=temp_owned)

        if primary_exc is not None:
            if cleanup_errors:
                # Principal cause stays the publication failure; cleanup is
                # appended as secondary diagnostic context.
                raise ConsultationError(
                    f"{primary_exc} | cleanup also failed: "
                    f"{'; '.join(cleanup_errors)}") from primary_exc
            raise primary_exc
        if cleanup_errors:
            # Publication succeeded but a writer-owned cleanup failed: the final
            # is valid and unchanged, but surface the failure canonically.
            raise ConsultationError(
                "consultation receipt cleanup failed: "
                + "; ".join(cleanup_errors))
        return result

    def load(self, request_id: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(request_id)
        if not path.exists():
            return None
        return self._read_verified_final(path)

    def all_receipts(self) -> List[Dict[str, Any]]:
        if not self.directory.exists():
            return []
        # Deterministic ordering; malformed receipts fail closed (never skipped).
        return [self._read_verified_final(p)
                for p in sorted(self.directory.glob("*.receipt.json"))]


__all__ = [
    "build_receipt", "verify_receipt", "ConsultationReceiptStore",
]
