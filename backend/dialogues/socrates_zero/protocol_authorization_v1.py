"""Fail-closed authorization for an exact experiment protocol manifest.

Authorization is deliberately byte-exact.  A caller must present the exact
lowercase SHA-256 digest of a canonical JSON manifest, and must independently
reconstruct the payload it expects to execute.  The resulting receipt is
runtime-inert until it is consumed through the write-once attempt latch.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from .contracts import ContractValidationError, canonical_json


_LOWERCASE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class AuthorizedProtocolReceiptV1:
    """Evidence that one exact manifest matched one exact expected payload."""

    protocol_file: str
    authorized_sha256: str
    observed_sha256: str
    schema_version: str
    byte_length: int

    def __post_init__(self) -> None:
        _assert_receipt_fields_v1(self)

    def as_record(self) -> Dict[str, object]:
        """Return the canonical public fields used by run artifacts."""

        return {
            "protocol_file": self.protocol_file,
            "authorized_sha256": self.authorized_sha256,
            "observed_sha256": self.observed_sha256,
            "schema_version": self.schema_version,
            "byte_length": self.byte_length,
        }


class AuthorizedProtocolAttemptCapabilityV1:
    """Opaque authority for one run, issued only after a fresh latch write.

    The persisted latch is audit evidence, not a bearer credential.  Validity
    also depends on this exact registered object and the process that issued
    it, so neither reconstructing the public record nor inheriting an old latch
    can authorize a later builder or process.
    """

    __slots__ = (
        "_attempt_directory",
        "_issuer_pid",
        "_receipt",
        "_receipt_record_bytes",
        "_record_bytes",
        "_session_id",
        "__weakref__",
    )

    def __new__(
        cls, *args: object, **kwargs: object
    ) -> "AuthorizedProtocolAttemptCapabilityV1":
        del args, kwargs
        raise TypeError(
            "protocol attempt capabilities can only be issued by fresh consumption"
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise TypeError("protocol attempt capabilities are immutable")

    def __repr__(self) -> str:
        return "AuthorizedProtocolAttemptCapabilityV1(<opaque>)"

    def __reduce__(self) -> object:
        raise TypeError("protocol attempt capabilities cannot be serialized")

    def as_record(self) -> Dict[str, object]:
        """Return the canonical non-secret record suitable for artifacts."""

        _assert_process_local_capability_v1(self)
        parsed = _load_exact_json_object_v1(self._record_bytes)
        return dict(parsed)


_ACTIVE_ATTEMPT_CAPABILITIES_V1: weakref.WeakValueDictionary[
    int, AuthorizedProtocolAttemptCapabilityV1
] = weakref.WeakValueDictionary()
_BOUND_BUILDERS_BY_CAPABILITY_V1: weakref.WeakKeyDictionary[
    AuthorizedProtocolAttemptCapabilityV1, weakref.ReferenceType[object]
] = weakref.WeakKeyDictionary()
_BOUND_AUTHORIZED_BUILDERS_V1: weakref.WeakSet[object] = weakref.WeakSet()
_CAPABILITY_REGISTRY_LOCK_V1 = threading.RLock()


def _assert_receipt_fields_v1(receipt: AuthorizedProtocolReceiptV1) -> None:
    for label, value in (
        ("authorized", receipt.authorized_sha256),
        ("observed", receipt.observed_sha256),
    ):
        if not isinstance(value, str) or not _LOWERCASE_SHA256_RE.fullmatch(value):
            raise ContractValidationError(
                f"protocol receipt {label} digest must be lowercase SHA-256"
            )
    if not hmac.compare_digest(
        receipt.authorized_sha256, receipt.observed_sha256
    ):
        raise ContractValidationError("protocol receipt digests must match")
    if (
        not isinstance(receipt.protocol_file, str)
        or not receipt.protocol_file
        or receipt.protocol_file in (".", "..")
        or "/" in receipt.protocol_file
        or "\\" in receipt.protocol_file
        or "\x00" in receipt.protocol_file
    ):
        raise ContractValidationError("protocol receipt file must be a safe basename")
    if (
        not isinstance(receipt.schema_version, str)
        or not receipt.schema_version.strip()
    ):
        raise ContractValidationError("protocol receipt schema must be non-empty")
    if type(receipt.byte_length) is not int or receipt.byte_length <= 0:
        raise ContractValidationError("protocol receipt byte length must be positive")


def _reject_duplicate_keys_v1(
    pairs: Tuple[Tuple[str, Any], ...] | list[Tuple[str, Any]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError(
                f"authorized protocol contains duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _load_exact_json_object_v1(raw: bytes) -> Dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractValidationError(
            "authorized protocol must be strict UTF-8 JSON"
        ) from exc
    try:
        parsed = json.loads(text, object_pairs_hook=_reject_duplicate_keys_v1)
    except ContractValidationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            "authorized protocol must be valid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ContractValidationError("authorized protocol must be a JSON object")
    return parsed


def assert_exact_authorized_protocol_v1(
    *,
    protocol_path: Path,
    authorized_sha256: str,
    expected_schema_version: str,
    expected_payload: Mapping[str, Any],
) -> AuthorizedProtocolReceiptV1:
    """Verify an exact canonical manifest without coercion or fallback.

    The digest check happens against the bytes read from disk.  Matching bytes
    are then parsed with duplicate-key rejection, checked for repository
    canonical JSON encoding, and compared with the caller's independently
    reconstructed expected payload.
    """

    if not isinstance(authorized_sha256, str) or not _LOWERCASE_SHA256_RE.fullmatch(
        authorized_sha256
    ):
        raise ContractValidationError(
            "authorized protocol digest must be an exact lowercase SHA-256"
        )
    if not isinstance(expected_schema_version, str) or not expected_schema_version:
        raise ContractValidationError(
            "expected protocol schema version must be a non-empty string"
        )
    if not isinstance(expected_payload, Mapping):
        raise ContractValidationError("expected payload must be a JSON object")

    path = Path(protocol_path)
    try:
        raw = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise ContractValidationError("authorized protocol could not be read") from exc

    observed_sha256 = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(observed_sha256, authorized_sha256):
        raise ContractValidationError("authorized protocol digest mismatch")

    parsed = _load_exact_json_object_v1(raw)
    try:
        canonical_raw = canonical_json(parsed).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(
            "authorized protocol cannot be represented as canonical JSON"
        ) from exc
    if raw != canonical_raw:
        raise ContractValidationError(
            "authorized protocol must use exact canonical JSON bytes"
        )

    observed_schema_version = parsed.get("schema_version")
    if observed_schema_version != expected_schema_version:
        raise ContractValidationError(
            "authorized protocol schema version does not match expected schema"
        )
    try:
        expected_raw = canonical_json(dict(expected_payload)).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(
            "expected payload cannot be represented as canonical JSON"
        ) from exc
    if canonical_raw != expected_raw:
        raise ContractValidationError(
            "authorized protocol does not match the expected payload"
        )

    return AuthorizedProtocolReceiptV1(
        protocol_file=path.name,
        authorized_sha256=authorized_sha256,
        observed_sha256=observed_sha256,
        schema_version=expected_schema_version,
        byte_length=len(raw),
    )


def _attempt_record_v1(
    *, receipt: AuthorizedProtocolReceiptV1, session_id: str
) -> Dict[str, object]:
    return {
        "schema_version": "socrates-zero-authorized-protocol-attempt/v1",
        "authorized_protocol_sha256": receipt.authorized_sha256,
        "protocol_file": receipt.protocol_file,
        "protocol_schema_version": receipt.schema_version,
        "protocol_byte_length": receipt.byte_length,
        "session_id": session_id,
    }


def _resolved_attempt_directory_v1(
    attempt_directory: Path, *, create: bool
) -> Path:
    try:
        resolved = Path(attempt_directory).resolve(strict=False)
        if create:
            resolved.mkdir(parents=True, exist_ok=True)
        resolved = resolved.resolve(strict=True)
    except (OSError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            "authorized protocol attempt directory is unavailable"
        ) from exc
    if not resolved.is_dir():
        raise ContractValidationError(
            "authorized protocol attempt directory must be a directory"
        )
    return resolved


def _assert_process_local_capability_v1(
    capability: AuthorizedProtocolAttemptCapabilityV1,
) -> None:
    if type(capability) is not AuthorizedProtocolAttemptCapabilityV1:
        raise ContractValidationError(
            "protocol attempt check requires an exact process-local capability"
        )
    with _CAPABILITY_REGISTRY_LOCK_V1:
        registered = _ACTIVE_ATTEMPT_CAPABILITIES_V1.get(id(capability))
    if registered is not capability:
        raise ContractValidationError(
            "protocol attempt capability was not issued in this process"
        )
    if capability._issuer_pid != os.getpid():
        raise ContractValidationError(
            "protocol attempt capability belongs to a different process"
        )


def _issue_attempt_capability_v1(
    *,
    receipt: AuthorizedProtocolReceiptV1,
    attempt_directory: Path,
    session_id: str,
    record_bytes: bytes,
) -> AuthorizedProtocolAttemptCapabilityV1:
    capability = object.__new__(AuthorizedProtocolAttemptCapabilityV1)
    object.__setattr__(capability, "_attempt_directory", attempt_directory)
    object.__setattr__(capability, "_issuer_pid", os.getpid())
    object.__setattr__(capability, "_receipt", receipt)
    object.__setattr__(
        capability,
        "_receipt_record_bytes",
        canonical_json(receipt.as_record()).encode("utf-8"),
    )
    object.__setattr__(capability, "_record_bytes", record_bytes)
    object.__setattr__(capability, "_session_id", session_id)
    with _CAPABILITY_REGISTRY_LOCK_V1:
        _ACTIVE_ATTEMPT_CAPABILITIES_V1[id(capability)] = capability
    return capability


def _assert_capability_bound_to_live_builder_v1(
    capability: AuthorizedProtocolAttemptCapabilityV1,
) -> object:
    with _CAPABILITY_REGISTRY_LOCK_V1:
        builder_ref = _BOUND_BUILDERS_BY_CAPABILITY_V1.get(capability)
    if builder_ref is None:
        raise ContractValidationError(
            "protocol attempt capability has not been bound to a live builder"
        )
    builder = builder_ref()
    if builder is None:
        raise ContractValidationError(
            "protocol attempt capability's bound builder is no longer live"
        )
    return builder


def bind_authorized_protocol_attempt_v1(
    *, capability: AuthorizedProtocolAttemptCapabilityV1, builder: object
) -> AuthorizedProtocolAttemptCapabilityV1:
    """Claim one process-local capability for exactly one live builder."""

    _assert_process_local_capability_v1(capability)
    if builder is None:
        raise ContractValidationError("protocol attempt builder must be live")
    try:
        builder_ref = weakref.ref(builder)
        hash(builder)
    except TypeError as exc:
        raise ContractValidationError(
            "protocol attempt builder must support weak identity binding"
        ) from exc
    with _CAPABILITY_REGISTRY_LOCK_V1:
        if capability in _BOUND_BUILDERS_BY_CAPABILITY_V1:
            raise ContractValidationError(
                "protocol attempt capability is already bound to a builder"
            )
        if builder in _BOUND_AUTHORIZED_BUILDERS_V1:
            raise ContractValidationError(
                "live builder is already bound to an authorized protocol attempt"
            )
        _BOUND_BUILDERS_BY_CAPABILITY_V1[capability] = builder_ref
        _BOUND_AUTHORIZED_BUILDERS_V1.add(builder)
    return capability


def consume_authorized_protocol_attempt_v1(
    *,
    receipt: AuthorizedProtocolReceiptV1,
    attempt_directory: Path,
    session_id: str,
) -> AuthorizedProtocolAttemptCapabilityV1:
    """Atomically consume one authorized digest before any network dispatch."""

    if type(receipt) is not AuthorizedProtocolReceiptV1:
        raise ContractValidationError(
            "protocol attempt requires an exact authorization receipt"
        )
    _assert_receipt_fields_v1(receipt)
    if not isinstance(session_id, str) or not session_id.strip():
        raise ContractValidationError("protocol attempt session_id must be non-empty")

    record = _attempt_record_v1(receipt=receipt, session_id=session_id)
    encoded = canonical_json(record).encode("utf-8")
    directory = _resolved_attempt_directory_v1(attempt_directory, create=True)
    try:
        target = directory / f"{receipt.authorized_sha256}.json"
        with target.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except FileExistsError as exc:
        raise ContractValidationError(
            "authorized protocol attempt was already consumed"
        ) from exc
    except (OSError, ValueError) as exc:
        raise ContractValidationError(
            "authorized protocol attempt latch could not be persisted"
        ) from exc
    return _issue_attempt_capability_v1(
        receipt=receipt,
        attempt_directory=directory,
        session_id=session_id,
        record_bytes=encoded,
    )


def assert_authorized_protocol_attempt_consumed_v1(
    *,
    capability: AuthorizedProtocolAttemptCapabilityV1,
    expected_builder: object,
    receipt: AuthorizedProtocolReceiptV1,
    attempt_directory: Path,
    session_id: str,
) -> AuthorizedProtocolAttemptCapabilityV1:
    """Require live authority and recheck its exact canonical latch bytes."""

    _assert_process_local_capability_v1(capability)
    bound_builder = _assert_capability_bound_to_live_builder_v1(capability)
    if bound_builder is not expected_builder:
        raise ContractValidationError(
            "protocol attempt capability is bound to a different live builder"
        )
    if type(receipt) is not AuthorizedProtocolReceiptV1:
        raise ContractValidationError(
            "protocol attempt check requires an exact authorization receipt"
        )
    _assert_receipt_fields_v1(receipt)
    if not isinstance(session_id, str) or not session_id.strip():
        raise ContractValidationError("protocol attempt session_id must be non-empty")
    directory = _resolved_attempt_directory_v1(attempt_directory, create=False)
    if capability._receipt is not receipt:
        raise ContractValidationError(
            "protocol attempt capability is bound to a different receipt"
        )
    receipt_record_bytes = canonical_json(receipt.as_record()).encode("utf-8")
    if capability._receipt_record_bytes != receipt_record_bytes:
        raise ContractValidationError("protocol attempt receipt binding drifted")
    if capability._session_id != session_id:
        raise ContractValidationError(
            "protocol attempt capability is bound to a different session"
        )
    if capability._attempt_directory != directory:
        raise ContractValidationError(
            "protocol attempt capability is bound to a different directory"
        )

    expected = _attempt_record_v1(receipt=receipt, session_id=session_id)
    expected_bytes = canonical_json(expected).encode("utf-8")
    if capability._record_bytes != expected_bytes:
        raise ContractValidationError("protocol attempt capability record drifted")
    target = directory / f"{receipt.authorized_sha256}.json"
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise ContractValidationError(
            "authorized protocol attempt has not been consumed"
        ) from exc
    if raw != expected_bytes:
        raise ContractValidationError("authorized protocol attempt latch drifted")
    del bound_builder
    return capability


__all__ = [
    "AuthorizedProtocolAttemptCapabilityV1",
    "AuthorizedProtocolReceiptV1",
    "assert_authorized_protocol_attempt_consumed_v1",
    "assert_exact_authorized_protocol_v1",
    "bind_authorized_protocol_attempt_v1",
    "consume_authorized_protocol_attempt_v1",
]
