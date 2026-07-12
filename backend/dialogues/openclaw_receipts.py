"""Internal shared hardened receipt-persistence primitive.

This is a NEUTRAL, domain-agnostic implementation of atomic, immutable,
concurrency-safe JSON receipt publication. It does **not** define any receipt
schema, does **not** construct or verify records, and imposes no domain policy.
Domain packages own their schemas, ``build_receipt()``, ``verify_receipt()``,
error types, and field sets; they wrap this primitive with a thin subclass that
supplies:

  * ``_error_type`` — the domain error class (e.g. ConsultationError)
  * ``_noun``       — a short label used only inside messages ("consultation
                      receipt", "kernel receipt")
  * ``_verify``     — the domain ``verify_receipt`` (validates + returns a record,
                      raising the domain error on invalid data)
  * ``_clean_request_id`` — the domain request-id validator (raises the domain
                      error), used before any filesystem path is built

It provides ONLY generic immutable-publication behavior, identical to the final
CLEAN-reviewed protocol from the External Self-Consultation store:

  * request_id validation + a HASHED, containment-checked final filename
    (``sha256(request_id).receipt.json``); the raw id never touches a path
  * ONE shared exclusive publication lock across the preferred ``os.link`` and
    the ``os.replace`` fallback — no publisher bypasses the lock, so a primary
    and a fallback writer can never both publish
  * ONE absolute monotonic deadline for the whole save attempt (never reset in
    a helper); polls capped to the remaining time; no filesystem operation
    begins after expiry
  * bounded Windows ``DELETE_PENDING`` / transient sharing ``PermissionError``
    retries, only within that deadline
  * immutable no-overwrite publication: first distinct content wins; identical
    content is an idempotent success; conflicting content is refused with the
    DOMAIN error; an existing final is never overwritten, deleted, truncated, or
    repaired
  * ownership-aware, independent cleanup that never removes a foreign lock/temp
    and never touches the published final
  * strict typed reads (save-time reconciliation, ``load()``, ``all_receipts()``)
    that normalize expected filesystem/decoding/parsing/data failures to the
    domain error and never silently skip malformed files

Neither domain package depends on the other; both depend only on this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional

#: Bounded wait for a publisher to finish (never an infinite loop).
_PUBLISH_LOCK_TIMEOUT = 5.0
_PUBLISH_LOCK_POLL = 0.005
#: Bounded retries if a freshly generated temp name already exists (a foreign
#: temp we must never touch); a fresh UUID is tried each time.
_TEMP_CREATE_ATTEMPTS = 8


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AtomicReceiptStore:
    """Domain-agnostic atomic, immutable receipt store.

    Subclasses set ``_error_type`` and ``_noun`` and implement ``_verify`` and
    ``_clean_request_id``. This class owns publication, reconciliation, and
    cleanup only; it constructs and verifies nothing beyond delegating to the
    domain ``_verify`` hook.
    """

    #: Subclass responsibilities (must be provided).
    _error_type: type = RuntimeError
    _noun: str = "receipt"

    def _verify(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _clean_request_id(self, value: Any) -> str:
        raise NotImplementedError

    def __init__(self, directory: "pathlib.Path | str", *,
                 lock_timeout: float = _PUBLISH_LOCK_TIMEOUT,
                 lock_poll: float = _PUBLISH_LOCK_POLL) -> None:
        self.directory = pathlib.Path(directory)
        self._lock_timeout = lock_timeout
        self._lock_poll = lock_poll

    def _fail(self, message: str) -> Exception:
        return self._error_type(message)

    def _path_for(self, request_id: str) -> pathlib.Path:
        # request_id is validated as a strict identifier, then HASHED for the
        # on-disk name; the raw id never touches the filesystem path.
        safe = self._clean_request_id(request_id)
        name = f"{sha256_text(safe)}.receipt.json"
        try:
            base = self.directory.resolve()
        except (OSError, RuntimeError, ValueError):
            raise self._fail(
                f"{self._noun} store directory resolution failed") from None
        path = (base / name)
        # Defense-in-depth: the resolved path must stay directly under base.
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError, ValueError):
            raise self._fail(
                f"{self._noun} final path resolution failed") from None
        if resolved.parent != base:
            raise self._fail("receipt path escapes the store directory")
        return path

    @staticmethod
    def _lock_for(path: pathlib.Path) -> pathlib.Path:
        stem = path.name.split(".", 1)[0]           # the sha256 hex
        return path.parent / f"{stem}.receipt.lock"

    def _path_is_present(self, path: pathlib.Path, *, message: str,
                         deadline: Optional[float] = None) -> bool:
        """Strict existence discovery that never suppresses filesystem errors.

        Public discovery has no retry deadline and normalizes a denial
        immediately. Save-time discovery may retry only ``PermissionError``
        within the one original publication deadline, matching Windows sharing
        contention without beginning another filesystem operation after expiry.
        """
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                raise self._fail(
                    f"{self._noun} discovery timed out") from None
            try:
                path.stat()
                return True
            except FileNotFoundError:
                return False
            except PermissionError:
                if deadline is None:
                    raise self._fail(message) from None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._fail(
                        f"{self._noun} discovery timed out") from None
                time.sleep(min(self._lock_poll, remaining))
                if time.monotonic() >= deadline:
                    raise self._fail(
                        f"{self._noun} discovery timed out") from None
            except (OSError, ValueError):
                raise self._fail(message) from None

    # ── strict, normalized read of an existing final receipt ─────────────────

    def _read_verified_final(self, path: pathlib.Path, *,
                             deadline: Optional[float] = None) -> Dict[str, Any]:
        """Read + parse + domain-verify one final receipt. Every expected
        filesystem/decoding/parsing/data failure becomes the domain error with a
        safe message (never a raw exception, never raw file contents). A
        transient sharing denial (PermissionError) right after a peer publishes
        is retried, but ONLY within the single deadline and never as a filesystem
        operation started after it expires. An already-raised domain error keeps
        its own type and message."""
        while True:
            try:
                return self._verify(json.loads(
                    path.read_text(encoding="utf-8")))
            except self._error_type:
                raise                                # already safe + specific
            except PermissionError:
                if deadline is None:
                    raise self._fail(
                        f"existing {self._noun} could not be read for "
                        "reconciliation") from None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._fail(
                        f"{self._noun} reconciliation timed out") from None
                time.sleep(min(self._lock_poll, remaining))
                if time.monotonic() >= deadline:     # no post-deadline re-read
                    raise self._fail(
                        f"{self._noun} reconciliation timed out") from None
            except (json.JSONDecodeError, UnicodeDecodeError, OSError,
                    TypeError, ValueError):
                raise self._fail(
                    f"existing {self._noun} could not be read for "
                    "reconciliation") from None

    def _reconcile(self, path: pathlib.Path, verified: Mapping[str, Any], *,
                   deadline: Optional[float] = None) -> pathlib.Path:
        """A final receipt already exists: verify it, then return idempotently
        if it is byte-for-byte the same receipt, else refuse the conflict."""
        existing = self._read_verified_final(path, deadline=deadline)
        if existing["receipt_digest"] != verified["receipt_digest"]:
            raise self._fail(
                f"conflicting {self._noun} for the same request_id")
        return path

    # ── the single publication protocol ──────────────────────────────────────

    def _acquire_lock(self, lock: pathlib.Path, path: pathlib.Path,
                      deadline: float) -> Optional[int]:
        """Acquire the exclusive publication lock, or return None if the final
        was already published (caller reconciles - never overwrites). Bounded by
        the single deadline; contention (peer-held lock, or Windows
        DELETE_PENDING PermissionError while a peer unlinks its lock) waits and
        retries; other OSErrors and timeout become the domain error."""
        while True:
            if self._path_is_present(
                    path, message=f"{self._noun} final discovery failed",
                    deadline=deadline):
                return None                          # already published
            try:
                return os.open(os.fspath(lock),
                               os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except (FileExistsError, PermissionError):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._fail(
                        f"{self._noun} publication lock timed out") from None
                time.sleep(min(self._lock_poll, remaining))
                if time.monotonic() >= deadline:     # no post-deadline acquire
                    raise self._fail(
                        f"{self._noun} publication lock timed out") from None
            except OSError:
                raise self._fail(
                    f"{self._noun} publication lock acquisition failed"
                ) from None

    def _create_temp(self, payload: str) -> pathlib.Path:
        """Create and fully write a UNIQUE per-writer temp. On the (astronomic)
        chance the generated name already exists it is a FOREIGN temp: never
        touched, a fresh UUID is tried, bounded. Ownership starts immediately
        after exclusive creation. A returned path is always fully written and
        successfully closed; every post-creation failure independently attempts
        close and writer-owned unlink before raising the configured domain error.
        """
        for _ in range(_TEMP_CREATE_ATTEMPTS):
            candidate = self.directory / f".{uuid.uuid4().hex}.receipt.tmp"
            try:
                handle = open(candidate, "x", encoding="utf-8")
            except FileExistsError:
                continue                             # foreign temp: do not touch
            except OSError:
                raise self._fail(
                    f"{self._noun} temp creation failed") from None

            # Exclusive creation succeeded: this writer owns candidate NOW,
            # before any write or close operation can fail.
            temp_owned = True
            primary_message: Optional[str] = None
            cleanup_errors: List[str] = []
            try:
                try:
                    written = handle.write(payload)
                    if written != len(payload):
                        primary_message = f"{self._noun} temp write failed"
                except OSError:
                    primary_message = f"{self._noun} temp write failed"
            finally:
                try:
                    handle.close()
                except OSError as exc:
                    if primary_message is None:
                        primary_message = f"{self._noun} temp close failed"
                    else:
                        cleanup_errors.append(
                            f"temp-close {exc.__class__.__name__}")

            if primary_message is None:
                return candidate                     # complete, closed, owned

            if temp_owned:
                try:
                    os.unlink(candidate)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    cleanup_errors.append(
                        f"temp-unlink {exc.__class__.__name__}")
            if cleanup_errors:
                raise self._fail(
                    f"{primary_message} | cleanup also failed: "
                    f"{'; '.join(cleanup_errors)}") from None
            raise self._fail(primary_message) from None
        raise self._fail(
            f"{self._noun} temp allocation failed after retries")

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
        verified = self._verify(record)
        # Preserve domain validation precedence without resolving paths while a
        # peer may still be creating the configured directory.
        self._clean_request_id(verified["request_id"])
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError):
            raise self._fail(
                f"{self._noun} store directory creation failed") from None
        path = self._path_for(verified["request_id"])
        lock = self._lock_for(path)
        # ONE monotonic deadline for the ENTIRE publication attempt - never
        # reset when switching from lock acquisition to publication/reconcile.
        deadline = time.monotonic() + self._lock_timeout

        lock_fd: Optional[int] = None
        lock_owned = False
        tmp: Optional[pathlib.Path] = None
        temp_owned = False
        primary_exc: Optional[BaseException] = None
        result: Optional[pathlib.Path] = None
        try:
            lock_fd = self._acquire_lock(lock, path, deadline)
            if lock_fd is None:
                # Already published (peer or prior run): reconcile, never overwrite.
                result = self._reconcile(path, verified, deadline=deadline)
            else:
                lock_owned = True
                if self._path_is_present(
                        path,
                        message=f"{self._noun} final discovery failed",
                        deadline=deadline):           # never overwrite a final
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
                            raise self._fail(
                                f"{self._noun} publication failed") from None
                        result = path
                    else:
                        result = path
        except self._error_type as exc:
            primary_exc = exc
        finally:
            cleanup_errors = self._cleanup(
                lock_fd=lock_fd, lock=lock, lock_owned=lock_owned,
                tmp=tmp, temp_owned=temp_owned)

        if primary_exc is not None:
            if cleanup_errors:
                # Principal cause stays the publication failure; cleanup is
                # appended as secondary diagnostic context.
                raise self._fail(
                    f"{primary_exc} | cleanup also failed: "
                    f"{'; '.join(cleanup_errors)}") from primary_exc
            raise primary_exc
        if cleanup_errors:
            # Publication succeeded but a writer-owned cleanup failed: the final
            # is valid and unchanged, but surface the failure canonically.
            raise self._fail(
                f"{self._noun} cleanup failed: " + "; ".join(cleanup_errors))
        return result

    def load(self, request_id: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(request_id)
        if not self._path_is_present(
                path, message=f"{self._noun} discovery failed"):
            return None
        return self._read_verified_final(path)

    def all_receipts(self) -> List[Dict[str, Any]]:
        if not self._path_is_present(
                self.directory,
                message=f"{self._noun} store discovery failed"):
            return []

        try:
            entries = os.scandir(self.directory)
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            raise self._fail(
                f"{self._noun} enumeration failed") from None

        try:
            with entries:
                paths = sorted(
                    pathlib.Path(entry.path)
                    for entry in entries
                    if entry.name.endswith(".receipt.json")
                )
        except (OSError, ValueError):
            raise self._fail(
                f"{self._noun} enumeration failed") from None

        # Deterministic ordering; malformed receipts fail closed (never skipped).
        return [self._read_verified_final(path) for path in paths]


__all__ = ["AtomicReceiptStore", "sha256_text"]
