"""Fail-closed authorization for an exact experiment protocol manifest."""

from __future__ import annotations

import gc
import hashlib
import json
import pickle
import weakref
from pathlib import Path

import pytest

import backend.dialogues.socrates_zero.protocol_authorization_v1 as authorization
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.protocol_authorization_v1 import (
    AuthorizedProtocolAttemptCapabilityV1,
    AuthorizedProtocolReceiptV1,
    assert_authorized_protocol_attempt_consumed_v1,
    assert_exact_authorized_protocol_v1,
    bind_authorized_protocol_attempt_v1,
    consume_authorized_protocol_attempt_v1,
)


RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "branches"
    / "feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs"
)


class _LiveBuilder:
    pass


class _EqualLookingBuilder:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, _EqualLookingBuilder)

    def __hash__(self) -> int:
        return 1


def _write_manifest(path: Path, payload: dict) -> str:
    raw = canonical_json(payload).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_exact_digest_payload_and_canonical_bytes_pass(tmp_path: Path) -> None:
    payload = {"schema_version": "example/v1", "value": 3}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)

    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )

    assert receipt.authorized_sha256 == digest
    assert receipt.observed_sha256 == digest
    assert receipt.protocol_file == "protocol.json"
    assert receipt.as_record()["schema_version"] == "example/v1"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        "A" * 64,
        "0" * 63,
        "0" * 65,
        " " + "0" * 64,
        "0" * 64 + "\n",
    ],
)
def test_digest_syntax_has_no_coercion_or_trimming(
    tmp_path: Path, value: str
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    _write_manifest(path, payload)

    with pytest.raises(ContractValidationError, match="lowercase SHA-256"):
        assert_exact_authorized_protocol_v1(
            protocol_path=path,
            authorized_sha256=value,
            expected_schema_version="example/v1",
            expected_payload=payload,
        )


def test_whitespace_or_one_byte_manifest_drift_refuses(tmp_path: Path) -> None:
    payload = {"schema_version": "example/v1", "value": 3}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)

    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ContractValidationError, match="digest mismatch"):
        assert_exact_authorized_protocol_v1(
            protocol_path=path,
            authorized_sha256=digest,
            expected_schema_version="example/v1",
            expected_payload=payload,
        )


def test_noncanonical_and_duplicate_key_json_refuse_even_when_digest_matches(
    tmp_path: Path,
) -> None:
    path = tmp_path / "protocol.json"
    noncanonical = b'{"schema_version": "example/v1", "value": 3}'
    path.write_bytes(noncanonical)
    with pytest.raises(ContractValidationError, match="canonical JSON"):
        assert_exact_authorized_protocol_v1(
            protocol_path=path,
            authorized_sha256=hashlib.sha256(noncanonical).hexdigest(),
            expected_schema_version="example/v1",
            expected_payload={"schema_version": "example/v1", "value": 3},
        )

    duplicate = b'{"schema_version":"example/v1","value":2,"value":3}'
    path.write_bytes(duplicate)
    with pytest.raises(ContractValidationError, match="duplicate JSON key"):
        assert_exact_authorized_protocol_v1(
            protocol_path=path,
            authorized_sha256=hashlib.sha256(duplicate).hexdigest(),
            expected_schema_version="example/v1",
            expected_payload={"schema_version": "example/v1", "value": 3},
        )


def test_q2c_historical_stale_authorization_digest_now_refuses() -> None:
    v1_digest = (
        "ee9fa22e32d99f81d80f7865763b241ec05e65b051e4e6b60e3ee83754c816f0"
    )
    v2_path = RUNS / "q2c_frozen_protocol_v2.json"
    v2_payload = json.loads(v2_path.read_text(encoding="utf-8"))

    with pytest.raises(ContractValidationError, match="digest mismatch"):
        assert_exact_authorized_protocol_v1(
            protocol_path=v2_path,
            authorized_sha256=v1_digest,
            expected_schema_version="socrates-q2c-freeze/v2",
            expected_payload=v2_payload,
        )


def test_expected_payload_drift_invalidates_an_otherwise_matching_digest(
    tmp_path: Path,
) -> None:
    payload = {"schema_version": "example/v1", "implementation": "old"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)

    with pytest.raises(ContractValidationError, match="expected payload"):
        assert_exact_authorized_protocol_v1(
            protocol_path=path,
            authorized_sha256=digest,
            expected_schema_version="example/v1",
            expected_payload={
                "schema_version": "example/v1",
                "implementation": "new",
            },
        )


def test_authorized_protocol_attempt_latch_is_one_shot(tmp_path: Path) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )

    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    builder = _LiveBuilder()
    assert (
        bind_authorized_protocol_attempt_v1(
            capability=capability, builder=builder
        )
        is capability
    )
    assert isinstance(capability, AuthorizedProtocolAttemptCapabilityV1)
    assert not isinstance(capability, dict)
    public_record = capability.as_record()
    assert public_record["authorized_protocol_sha256"] == digest
    assert public_record["session_id"] == "fixed-session"
    assert (
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )
        is capability
    )

    with pytest.raises(ContractValidationError, match="already consumed"):
        consume_authorized_protocol_attempt_v1(
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )
    with pytest.raises(ContractValidationError, match="already bound"):
        bind_authorized_protocol_attempt_v1(
            capability=capability, builder=_LiveBuilder()
        )


def test_historical_latch_or_forged_object_is_not_run_authority(
    tmp_path: Path,
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )
    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    unbound_builder = _LiveBuilder()

    forged = object.__new__(AuthorizedProtocolAttemptCapabilityV1)
    with pytest.raises(ContractValidationError, match="not issued in this process"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=forged,
            expected_builder=unbound_builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )
    with pytest.raises(ContractValidationError, match="exact process-local"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability.as_record(),  # type: ignore[arg-type]
            expected_builder=unbound_builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )

    with pytest.raises(TypeError, match="fresh consumption"):
        AuthorizedProtocolAttemptCapabilityV1()


def test_forged_receipt_cannot_escape_the_attempt_directory(tmp_path: Path) -> None:
    with pytest.raises(ContractValidationError, match="lowercase SHA-256"):
        AuthorizedProtocolReceiptV1(
            protocol_file="protocol.json",
            authorized_sha256="../escaped",
            observed_sha256="../escaped",
            schema_version="example/v1",
            byte_length=10,
        )
    assert not (tmp_path.parent / "escaped.json").exists()


def test_attempt_check_refuses_absent_or_drifted_latch(tmp_path: Path) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )

    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    builder = _LiveBuilder()
    bind_authorized_protocol_attempt_v1(
        capability=capability, builder=builder
    )
    latch = tmp_path / "attempts" / f"{digest}.json"
    exact_latch = latch.read_bytes()
    latch.unlink()
    with pytest.raises(ContractValidationError, match="has not been consumed"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )
    latch.write_bytes(exact_latch + b"\n")
    with pytest.raises(ContractValidationError, match="latch drifted"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )


def test_attempt_capability_binds_exact_receipt_session_and_directory(
    tmp_path: Path,
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )
    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    builder = _LiveBuilder()
    bind_authorized_protocol_attempt_v1(
        capability=capability, builder=builder
    )
    equal_but_fresh_receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )

    with pytest.raises(ContractValidationError, match="different receipt"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=equal_but_fresh_receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )
    with pytest.raises(ContractValidationError, match="different session"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="other-session",
        )
    (tmp_path / "other-attempts").mkdir()
    with pytest.raises(ContractValidationError, match="different directory"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "other-attempts",
            session_id="fixed-session",
        )


def test_attempt_capability_is_immutable_nonserializable_and_process_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )
    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    builder = _LiveBuilder()
    bind_authorized_protocol_attempt_v1(
        capability=capability, builder=builder
    )

    with pytest.raises(TypeError, match="immutable"):
        capability._session_id = "other-session"  # type: ignore[misc]
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(capability)

    issuer_pid = authorization.os.getpid()
    monkeypatch.setattr(authorization.os, "getpid", lambda: issuer_pid + 1)
    with pytest.raises(ContractValidationError, match="different process"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )


def test_attempt_assertion_requires_one_live_builder_and_is_repeatable(
    tmp_path: Path,
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )
    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    builder = _LiveBuilder()

    with pytest.raises(ContractValidationError, match="not been bound"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )

    bind_authorized_protocol_attempt_v1(
        capability=capability, builder=builder
    )
    for _ in range(2):
        assert (
            assert_authorized_protocol_attempt_consumed_v1(
                capability=capability,
                expected_builder=builder,
                receipt=receipt,
                attempt_directory=tmp_path / "attempts",
                session_id="fixed-session",
            )
            is capability
        )


def test_attempt_assertion_refuses_equal_looking_wrong_builder_identity(
    tmp_path: Path,
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )
    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    bound_builder = _EqualLookingBuilder()
    wrong_builder = _EqualLookingBuilder()
    assert bound_builder == wrong_builder
    assert bound_builder is not wrong_builder
    bind_authorized_protocol_attempt_v1(
        capability=capability, builder=bound_builder
    )

    with pytest.raises(ContractValidationError, match="different live builder"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=wrong_builder,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )


def test_attempt_assertion_refuses_after_bound_builder_is_gone(
    tmp_path: Path,
) -> None:
    payload = {"schema_version": "example/v1"}
    path = tmp_path / "protocol.json"
    digest = _write_manifest(path, payload)
    receipt = assert_exact_authorized_protocol_v1(
        protocol_path=path,
        authorized_sha256=digest,
        expected_schema_version="example/v1",
        expected_payload=payload,
    )
    capability = consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=tmp_path / "attempts",
        session_id="fixed-session",
    )
    builder = _LiveBuilder()
    bind_authorized_protocol_attempt_v1(
        capability=capability, builder=builder
    )
    builder_proxy = weakref.proxy(builder)
    del builder
    gc.collect()

    with pytest.raises(ContractValidationError, match="no longer live"):
        assert_authorized_protocol_attempt_consumed_v1(
            capability=capability,
            expected_builder=builder_proxy,
            receipt=receipt,
            attempt_directory=tmp_path / "attempts",
            session_id="fixed-session",
        )
