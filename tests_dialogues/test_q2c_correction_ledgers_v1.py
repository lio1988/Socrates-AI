"""Integrity locks for the append-only Q2c correction records.

These tests do not reinterpret the historical run.  They pin its retained
evidence, prove that the first four attribution corrections were not rewritten,
and validate the protocol-nonconformance event's canonical SHA-256 chain.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.dialogues.socrates_zero.contracts import canonical_json


RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "branches"
    / "feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs"
)
ATTRIBUTION_LEDGER = RUNS / "attribution_correction_ledger_v1.json"
PROTOCOL_LEDGER = RUNS / "protocol_nonconformance_ledger_v1.json"
Q2C_ARTIFACT = RUNS / "q2c_ethics_council_v1.json"
FINISH_REASONS = RUNS / "q1_condition_c_provider_errors" / "finish_reasons.jsonl"

Q2C_ARTIFACT_SHA256 = (
    "011c9e8ddaa05c6bba908821555c3c786657f04f2aa1da8caa24c6c515572b20"
)
Q2C_AUTHORIZED_PROTOCOL_SHA256 = (
    "ee9fa22e32d99f81d80f7865763b241ec05e65b051e4e6b60e3ee83754c816f0"
)
Q2C_EXECUTED_PROTOCOL_SHA256 = (
    "3b88603b694585f779ffb941d61f1b92da3600237f82b916b09f91c0eef17233"
)
ORIGINAL_ATTRIBUTION_EVENTS_SHA256 = (
    "af9c718e075b63966dd295c87cb066f3c6f92c1fc6e93ac0f351b86c7f42363d"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_canonical(path: Path) -> dict:
    raw = path.read_bytes()
    value = json.loads(raw)
    canonical = canonical_json(value).encode("utf-8")
    assert raw in (canonical, canonical + b"\n", canonical + b"\r\n")
    return value


def test_q2c_attribution_correction_is_additive_and_evidence_backed() -> None:
    ledger = _load_canonical(ATTRIBUTION_LEDGER)

    assert ledger["append_only"] is True
    assert len(ledger["events"]) == 5
    original_events = canonical_json(ledger["events"][:4]).encode("utf-8")
    assert hashlib.sha256(original_events).hexdigest() == (
        ORIGINAL_ATTRIBUTION_EVENTS_SHA256
    )

    correction = ledger["events"][4]
    assert correction["artifact"] == Q2C_ARTIFACT.name
    assert correction["corrected_attribution"] == (
        "provider_structured_output_contract_violation"
    )
    assert correction["dispatch_evidence_present"] is True
    assert correction["provider_response_evidence_present"] is True
    assert correction["terminal_classification"] == (
        "provider_structured_output_contract_violation:"
        "http_200_finish_stop_schema_invalid"
    )

    artifact = json.loads(Q2C_ARTIFACT.read_text(encoding="utf-8"))
    failed = next(
        turn
        for turn in artifact["turns"]
        if turn["record_id"]
        == "szorturnrecordv1_99fb730479b05020b08ee32ee44b4ab059d4ad7b7fb26c07e1c38751d6ac5495"
    )
    assert failed["transport_completed"] is True
    assert failed["http_status"] == 200
    assert failed["provider_structured_output_valid"] is False
    assert failed["ced_move_accepted"] is False
    assert failed["completion_tokens"] == 761
    assert json.loads(failed["assistant_output_sanitized"])["content"] == {}
    assert correction["evidence_digest"] == failed["response_body_sha256"]
    assert "7 validation errors" in failed["provider_structured_output_error"]

    finish = next(
        json.loads(line)
        for line in FINISH_REASONS.read_text(encoding="utf-8").splitlines()
        if '"prompt_tokens": 21429' in line
        and '"completion_tokens": 761' in line
        and '"reasoning_tokens": 739' in line
    )
    assert finish["model_requested"] == "google/gemini-3.7-flash"
    assert finish["finish_reason"] == "stop"
    assert finish["usage"]["completion_tokens_details"]["reasoning_tokens"] == 739


def test_q2c_protocol_nonconformance_ledger_has_valid_canonical_chain() -> None:
    ledger = _load_canonical(PROTOCOL_LEDGER)

    assert set(ledger) == {
        "append_only",
        "chain_algorithm",
        "events",
        "invariant",
        "note",
        "schema_version",
    }
    assert ledger["append_only"] is True
    assert ledger["chain_algorithm"] == (
        "sha256(canonical_json(event_without_event_sha256))"
    )
    assert ledger["schema_version"] == (
        "socrates-protocol-nonconformance-ledger/v1"
    )

    previous = ""
    for index, raw_event in enumerate(ledger["events"]):
        event = dict(raw_event)
        assert event["event_index"] == index
        assert event["previous_event_sha256"] == previous
        supplied = event.pop("event_sha256")
        observed = hashlib.sha256(
            canonical_json(event).encode("utf-8")
        ).hexdigest()
        assert supplied == observed
        previous = supplied

    assert len(ledger["events"]) == 1
    event = ledger["events"][0]
    assert event["classification"] == "executed_manifest_not_operator_authorized"
    assert event["consequence"] == (
        "q2c_is_protocol_nonconformant_and_not_confirmatory"
    )
    assert event["authorized_protocol_sha256"] == Q2C_AUTHORIZED_PROTOCOL_SHA256
    assert event["executed_protocol_sha256"] == Q2C_EXECUTED_PROTOCOL_SHA256
    assert event["calls_consumed"] == 13
    assert event["observed_cost_picodollars"] == 58_986_715_000
    assert event["raw_historical_artifacts_modified"] is False


def test_q2c_protocol_event_pins_unchanged_historical_artifacts() -> None:
    ledger = _load_canonical(PROTOCOL_LEDGER)
    event = ledger["events"][0]

    assert _sha256(Q2C_ARTIFACT) == Q2C_ARTIFACT_SHA256
    assert event["artifact_sha256"] == Q2C_ARTIFACT_SHA256
    assert _sha256(RUNS / event["authorized_protocol_artifact"]) == (
        Q2C_AUTHORIZED_PROTOCOL_SHA256
    )
    assert _sha256(RUNS / event["executed_protocol_artifact"]) == (
        Q2C_EXECUTED_PROTOCOL_SHA256
    )

    artifact = json.loads(Q2C_ARTIFACT.read_text(encoding="utf-8"))
    assert artifact["calls_consumed"] == event["calls_consumed"]
    assert artifact["observed_cost_picodollars"] == (
        event["observed_cost_picodollars"]
    )
    assert artifact["outcome"]["synthesis_present"] is False
    assert artifact["outcome"]["ratified"] is False
