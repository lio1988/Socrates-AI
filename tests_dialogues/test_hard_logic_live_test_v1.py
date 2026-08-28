from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
    render_dynamic_turn_v1,
)
from scripts import run_hard_logic_live_test_v1 as runner
from scripts import run_socrates_live_v1 as normal
from scripts.run_reduced_socrates_benchmark_v1 import baseline_response_format_v1


def _endpoint_bytes() -> bytes:
    return json.dumps(
        {
            "data": {
                "id": "openai/gpt-5-mini",
                "endpoints": [
                    {
                        "name": "OpenAI | openai/gpt-5-mini-2025-08-07",
                        "tag": "openai/flex",
                        "provider_name": "OpenAI",
                        "model_id": "openai/gpt-5-mini",
                        "status": 0,
                        "context_length": 400_000,
                        "max_prompt_tokens": 272_000,
                        "max_completion_tokens": 128_000,
                        "supported_parameters": [
                            "reasoning",
                            "include_reasoning",
                            "structured_outputs",
                            "response_format",
                            "seed",
                            "max_tokens",
                            "tools",
                            "tool_choice",
                            "reasoning_effort",
                        ],
                        "pricing": {
                            "prompt": "0.000000125",
                            "completion": "0.000001",
                        },
                    }
                ],
            }
        },
        sort_keys=True,
    ).encode("utf-8")


def test_question_and_combined_cost_are_frozen() -> None:
    # The frozen question changed once, deliberately: statements 3 and 4 said
    # "is not allowed to", which a model could read deontically and so escape
    # the contradiction without any logical error.  They are now plain material
    # implications.  This digest pins the corrected wording.
    assert hashlib.sha256(runner.QUESTION_V1.encode()).hexdigest() == (
        "ac62ad0e11f5517e361399391643c583ae166be771de13c6a8d10dda404b2ead"
    )
    # The runner's own declared digest must agree with the bytes it holds.
    assert runner.QUESTION_SHA256_V1 == hashlib.sha256(
        runner.QUESTION_V1.encode()
    ).hexdigest()
    static = runner.assert_static_contract_v1()
    assert static["spend"] == {
        "baseline_picodollars": 66_384_000_000,
        "ced_picodollars": 3_552_256_000_000,
        "combined_picodollars": 3_618_640_000_000,
        "maximum_per_call_picodollars": 66_384_000_000,
    }
    assert runner.MAXIMUM_LIVE_CALLS_V1 == 65
    # Remaining spend fell when the prior-observed figure was corrected upward
    # to the real cumulative total; the earlier constant understated it.
    assert runner.PRIOR_OBSERVED_SPEND_PICODOLLARS_V1 == 858_383_365_000
    assert runner.REMAINING_SPEND_PICODOLLARS_V1 == 7_141_616_635_000
    assert (
        runner.REMAINING_SPEND_PICODOLLARS_V1
        - static["spend"]["combined_picodollars"]
        == 3_522_976_635_000
    )


def test_baseline_and_ced_use_the_same_exact_question(tmp_path: Path) -> None:
    prepared = normal.prepare_normal_live_run_v1(
        runner.QUESTION_V1,
        _endpoint_bytes(),
        claim_directory=tmp_path,
        dispatch=lambda **_kwargs: None,
    )
    turn = runner._baseline_turn_v1(prepared.session_id)
    assert turn.user_content == runner.QUESTION_V1 == prepared.question


def test_baseline_body_is_direct_frozen_and_uses_16384(tmp_path: Path) -> None:
    prepared = normal.prepare_normal_live_run_v1(
        runner.QUESTION_V1,
        _endpoint_bytes(),
        claim_directory=tmp_path,
        dispatch=lambda **_kwargs: None,
    )
    turn = runner._baseline_turn_v1(prepared.session_id)
    rendered = render_dynamic_turn_v1(
        prepared.policies[16_384],
        prepared.profile,
        turn,
        response_format_override=baseline_response_format_v1(),
    )
    runner._baseline_guard_v1(None, rendered)
    body = json.loads(rendered.canonical_body_json)
    assert body["max_tokens"] == 16_384
    assert body["messages"][1]["content"] == runner.QUESTION_V1
    assert body["response_format"] == baseline_response_format_v1()
    for forbidden in runner.FORBIDDEN_COLLECTION_VALUES_V1:
        assert forbidden not in rendered.canonical_body_json


def test_combined_authorization_can_be_shared_by_exact_normal_workers(
    tmp_path: Path,
) -> None:
    prepared = normal.prepare_normal_live_run_v1(
        runner.QUESTION_V1,
        _endpoint_bytes(),
        claim_directory=tmp_path,
        dispatch=lambda **_kwargs: None,
    )
    envelope = prepared.policies[16_384]
    authorization = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement="offline hard-logic test authorization",
        policy_id=envelope.policy_id or "",
        profile_id=prepared.profile.profile_id or "",
        model=runner.MODEL_V1,
        provider_selector=runner.PROVIDER_SELECTOR_V1,
        maximum_calls=65,
        maximum_total_spend_picodollars=3_618_640_000_000,
        maximum_per_call_spend_picodollars=66_384_000_000,
        session_id="hard-logic-offline-test",
    )
    ledger = OpenRouterSessionLedgerV1(authorization)
    for adapter in prepared.adapters:
        adapter.ledger = ledger
        adapter._pre_dispatch_guard = runner._ced_guard_v1
    assert len(prepared.adapters) == 2
    assert all(adapter.ledger is ledger for adapter in prepared.adapters)
    assert ledger.authorization.maximum_calls == 65
    assert all(adapter.ced_parse_repair_attempts == 0 for adapter in prepared.adapters)


def test_manifest_has_no_evaluator_material(tmp_path: Path) -> None:
    prepared = normal.prepare_normal_live_run_v1(
        runner.QUESTION_V1,
        _endpoint_bytes(),
        claim_directory=tmp_path,
        dispatch=lambda **_kwargs: None,
    )
    manifest = runner._manifest_v1(
        profile_id=prepared.profile.profile_id or "",
        session_id="hard-logic-offline-test",
    )
    encoded = json.dumps(manifest, sort_keys=True)
    assert manifest["evaluator_material_present"] is False
    assert manifest["protocol_frozen_before_first_post"] is True
    for forbidden in runner.FORBIDDEN_COLLECTION_VALUES_V1:
        assert forbidden not in encoded


def test_attempt_latch_and_artifact_are_write_once(tmp_path: Path) -> None:
    manifest = {
        "schema_version": runner.SCHEMA_VERSION_V1,
        "question_sha256": runner.QUESTION_SHA256_V1,
    }
    first = runner._consume_attempt_v1(manifest, tmp_path / "attempt")
    assert Path(first["latch_path"]).exists()
    with pytest.raises(ContractValidationError, match="already consumed"):
        runner._consume_attempt_v1(manifest, tmp_path / "attempt")

    artifact = tmp_path / "collection.json"
    original_sha = runner._write_once_json_v1(artifact, {"ok": True})
    original = artifact.read_bytes()
    assert original_sha == hashlib.sha256(original).hexdigest()
    with pytest.raises(ContractValidationError, match="already exists"):
        runner._write_once_json_v1(artifact, {"ok": False})
    assert artifact.read_bytes() == original


def test_existing_artifact_refuses_before_endpoint_fetch(tmp_path: Path) -> None:
    target = tmp_path / "already.json"
    target.write_text("{}", encoding="utf-8")
    endpoint_calls = []
    with pytest.raises(ContractValidationError, match="already exists"):
        runner.run_hard_logic_test_v1(
            output_path=target,
            endpoint_fetch=lambda **kwargs: endpoint_calls.append(kwargs),
            dispatch=lambda **_kwargs: None,
            claim_directory=tmp_path / "claims",
            attempt_directory=tmp_path / "attempt",
        )
    assert endpoint_calls == []
