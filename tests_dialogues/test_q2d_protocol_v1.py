"""Offline locks for the Q2d output-envelope and protocol repair."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    TaskKind,
)
from backend.dialogues.role_assignment import stable_hash
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    build_turn_user_content_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterDynamicTurnRequestV1,
    render_dynamic_turn_v1,
)
from scripts import run_multimodel_q1_ced_v1 as q2d


RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "branches"
    / "feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs"
)

Q2D_FROZEN_PROTOCOL_SHA256_V1 = (
    "2729d4bd82af1ddc29ba6526daa4cd00ee3132540e01dbee7a73dba723581075"
)
Q2D_FROZEN_PROTOCOL_BYTE_LENGTH_V1 = 32_320


def _task(kind: TaskKind) -> AgentTask:
    phase = {
        TaskKind.SOCRATIC_QUESTION: DialogPhase.ELENCHUS,
        TaskKind.INITIAL_RESPONSE: DialogPhase.INITIAL_RESPONSE,
        TaskKind.ELENCHUS_OBJECTION: DialogPhase.ELENCHUS,
        TaskKind.REFLECTION_REVISION: DialogPhase.REFLECTION,
        TaskKind.RECONSTRUCTION_PROPOSAL: DialogPhase.RECONSTRUCTION,
        TaskKind.SYNTHESIS_DRAFT: DialogPhase.SYNTHESIS,
        TaskKind.MOVE_SCORE: DialogPhase.ELENCHUS,
        TaskKind.SECTION_SCORE: DialogPhase.SYNTHESIS,
        TaskKind.COUNCIL_RATIFICATION: DialogPhase.RATIFICATION,
        TaskKind.OBJECTION_VERIFICATION: DialogPhase.ELENCHUS,
    }[kind]
    return AgentTask(
        task_id=f"q2d_{kind.value}",
        session_id=q2d.Q2D_SESSION_ID_V1,
        agent_id="agent_0",
        role=(
            AgentRole.ELENCHUS_CRITIC
            if kind is TaskKind.ELENCHUS_OBJECTION
            else AgentRole.FINAL_EVALUATOR
        ),
        phase=phase,
        question="Which inference is invalid?",
        task_kind=kind,
    )


def test_only_gpt5_elenchus_receives_the_proven_8192_envelope() -> None:
    assert q2d.output_limit_for_seat_task_v1(
        "gpt_5_mini", _task(TaskKind.ELENCHUS_OBJECTION)
    ) == 8_192

    for kind, expected in (
        (TaskKind.SOCRATIC_QUESTION, 4_096),
        (TaskKind.INITIAL_RESPONSE, 8_192),
        (TaskKind.REFLECTION_REVISION, 8_192),
        (TaskKind.RECONSTRUCTION_PROPOSAL, 8_192),
        (TaskKind.SYNTHESIS_DRAFT, 16_384),
        (TaskKind.MOVE_SCORE, 4_096),
        (TaskKind.OBJECTION_VERIFICATION, 4_096),
    ):
        assert q2d.output_limit_for_seat_task_v1(
            "gpt_5_mini", _task(kind)
        ) == expected

    for seat in ("gemini_3_7_flash_standard", "gpt_4_1_mini"):
        assert q2d.output_limit_for_seat_task_v1(
            seat, _task(TaskKind.ELENCHUS_OBJECTION)
        ) == 4_096


def test_seat_policy_factory_uses_the_same_task_specific_router() -> None:
    task = _task(TaskKind.ELENCHUS_OBJECTION)
    for seat, expected in (
        ("gpt_5_mini", 8_192),
        ("gemini_3_7_flash_standard", 4_096),
        ("gpt_4_1_mini", 4_096),
    ):
        policies = q2d.build_seat_policy_family_v1(seat)
        selected = q2d.seat_policy_for_task_factory_v1(seat, policies)(task)
        assert selected.output_limit_tokens == expected


def test_q2d_preserves_each_endpoint_output_parameter_name() -> None:
    for seat, expected_field in (
        ("gpt_5_mini", "max_tokens"),
        ("gemini_3_7_flash_standard", "max_tokens"),
        ("gpt_4_1_mini", "max_completion_tokens"),
    ):
        profile = q2d.q1.load_profile_v1(seat)
        assert profile.output_limit_parameter == expected_field
        assert q2d.q1.FAMILIES_V1[seat]["output_field"] == expected_field


def test_output_parameter_is_exclusive_not_merely_present() -> None:
    q2d.assert_exact_seat_output_parameter_v1(
        "gpt_4_1_mini", {"max_completion_tokens": 4_096}, 4_096
    )
    with pytest.raises(ContractValidationError, match="parameter set drifted"):
        q2d.assert_exact_seat_output_parameter_v1(
            "gpt_4_1_mini",
            {"max_completion_tokens": 4_096, "max_tokens": 4_096},
            4_096,
        )
    with pytest.raises(ContractValidationError, match="parameter set drifted"):
        q2d.assert_exact_seat_output_parameter_v1(
            "gpt_5_mini",
            {"max_tokens": 8_192, "max_completion_tokens": 8_192},
            8_192,
        )


def test_q2d_fixed_session_and_one_model_one_agent_call_plan_are_exact() -> None:
    # Retain the predeclared session id after the topology repair. Its modulo-3
    # offset is pinned, not searched or optimized for cost.
    assert stable_hash(q2d.Q2D_SESSION_ID_V1) % 3 == 1
    plan = q2d.derive_q2d_call_plan_v1()

    assert plan["logical_agents"] == 3
    assert plan["seat_mapping"] == "one_logical_agent_per_physical_model"
    assert plan["logical_agent_to_seat"] == {
        "agent_0": "gpt_5_mini",
        "agent_1": "gemini_3_7_flash_standard",
        "agent_2": "gpt_4_1_mini",
    }
    assert plan["maximum_calls"] == 107
    assert plan["stage_calls"] == {
        "deliberation": 20,
        "move_scores": 40,
        "section_scores": 30,
        "ratification": 3,
        "objection_verification": 14,
    }
    assert plan["elenchus_objections_by_seat"] == {
        "gpt_5_mini": 1,
        "gemini_3_7_flash_standard": 2,
        "gpt_4_1_mini": 1,
    }
    assert plan["calls_by_seat_and_output_limit"] == {
        "gpt_5_mini": {"4096": 30, "8192": 5, "16384": 1},
        "gemini_3_7_flash_standard": {"4096": 31, "8192": 3, "16384": 1},
        "gpt_4_1_mini": {"4096": 32, "8192": 3, "16384": 1},
    }


def test_q2d_cost_bound_proves_the_five_dollar_ceiling_is_impossible() -> None:
    bound = q2d.conservative_q2d_bound_v1()
    assert q2d.conservative_ced_bound_v1() == bound
    assert bound["seat_total_picodollars"] == {
        "gpt_5_mini": 770_048_000_000,
        "gemini_3_7_flash_standard": 2_035_200_000_000,
        "gpt_4_1_mini": 2_378_956_800_000,
    }
    assert bound["total_picodollars"] == 5_184_204_800_000
    assert bound["maximum_per_call_picodollars"] == 86_507_520_000
    assert bound["prior_observed_picodollars"] == 651_915_000_000
    assert bound["required_cumulative_picodollars"] == 5_836_119_800_000
    assert bound["required_cumulative_picodollars"] > 5_000_000_000_000


def _finish_rows() -> list[dict]:
    path = RUNS / "q1_condition_c_provider_errors" / "finish_reasons.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_q2c_failures_are_classified_separately_from_retained_evidence() -> None:
    artifact = json.loads(
        (RUNS / "q2c_ethics_council_v1.json").read_text(encoding="utf-8")
    )
    finishes = _finish_rows()

    gpt = next(
        turn
        for turn in artifact["turns"]
        if turn["model"] == "openai/gpt-5-mini"
        and turn["completion_tokens"] == 4096
        and not turn["ced_move_accepted"]
    )
    gpt_finish = next(
        row
        for row in finishes
        if row["model_requested"] == gpt["model"]
        and (row.get("usage") or {}).get("prompt_tokens") == gpt["prompt_tokens"]
        and (row.get("usage") or {}).get("completion_tokens")
        == gpt["completion_tokens"]
    )
    assert q2d.classify_q2c_failure_v1(gpt, gpt_finish) == (
        "completion_envelope_exhausted_before_valid_visible_payload"
    )

    gemini = next(
        turn
        for turn in artifact["turns"]
        if turn["model"] == "google/gemini-3.7-flash"
        and not turn["ced_move_accepted"]
    )
    gemini_finish = next(
        row
        for row in finishes
        if row["model_requested"] == gemini["model"]
        and (row.get("usage") or {}).get("prompt_tokens")
        == gemini["prompt_tokens"]
        and (row.get("usage") or {}).get("completion_tokens")
        == gemini["completion_tokens"]
    )
    assert q2d.classify_q2c_failure_v1(gemini, gemini_finish) == (
        "provider_structured_output_contract_violation"
    )


def test_gemini_failure_schema_really_required_all_seven_fields() -> None:
    task = AgentTask(
        task_id="q2d_socratic_schema",
        session_id=q2d.Q2D_SESSION_ID_V1,
        agent_id="agent_1",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.ELENCHUS,
        question="Which inference is invalid?",
        task_kind=TaskKind.SOCRATIC_QUESTION,
    )
    response_format = q2d.normal.ced_structured_response_format_v1(task)
    root_schema = response_format["json_schema"]["schema"]
    content_ref = root_schema["properties"]["content"]["$ref"]
    content_schema = root_schema["$defs"][content_ref.rsplit("/", 1)[-1]]
    assert content_schema["additionalProperties"] is False
    assert set(content_schema["required"]) == {
        "aporia",
        "epistemic_marker",
        "grounded_in",
        "inquiry_state",
        "introduces_new_proposition",
        "operator",
        "question",
    }


def test_privacy_safe_dispatch_evidence_never_persists_raw_prompts(
    tmp_path: Path,
) -> None:
    body = json.dumps(
        {
            "model": "openai/gpt-5-mini",
            "messages": [
                {
                    "role": "user",
                    "content": "Patient Alice secret sk-or-v1-THISISASECRET123",
                }
            ],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    raw_response = json.dumps(
        {
            "error": {
                "code": 429,
                "message": "Patient Alice must never be copied",
            },
            "choices": [],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 3,
                "total_tokens": 15,
                "cost": 123.45,
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
        }
    ).encode("utf-8")
    result = SimpleNamespace(raw_response_body=raw_response)

    def inner(**_kwargs):
        return result

    wrapped = q2d.privacy_safe_dispatch_evidence_v1(tmp_path, inner)
    assert wrapped(body_bytes=body, model="openai/gpt-5-mini") is result

    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    persisted = files[0].read_text(encoding="utf-8")
    assert "Patient Alice" not in persisted
    assert "THISISASECRET123" not in persisted
    assert "messages" not in persisted
    receipt = json.loads(persisted)
    assert receipt["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["response_body_sha256"] == hashlib.sha256(raw_response).hexdigest()
    assert receipt["provider_error_code"] == 429
    assert receipt["usage"] == {
        "completion_tokens": 3,
        "prompt_tokens": 12,
        "reasoning_tokens": 2,
        "total_tokens": 15,
    }
    assert not list(tmp_path.glob("*.request.json"))
    assert set(receipt) == {
        "body_length",
        "body_sha256",
        "finish_reason",
        "model_requested",
        "native_finish_reason",
        "provider_error_class",
        "provider_error_code",
        "response_body_length",
        "response_body_sha256",
        "schema_version",
        "transport_failure_class",
        "usage",
    }
    assert "cost" not in persisted


def test_dispatch_sidecar_redacts_provider_controlled_string_values(
    tmp_path: Path,
) -> None:
    secret = "Patient Alice sk-or-v1-THISISASECRET123"
    body = json.dumps({"model": secret, "messages": []}).encode("utf-8")
    raw = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": {"raw_secret": secret},
                    "native_finish_reason": secret,
                }
            ],
            "error": {"code": secret, "message": secret},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
    ).encode("utf-8")
    result = SimpleNamespace(raw_response_body=raw)
    wrapped = q2d.privacy_safe_dispatch_evidence_v1(
        tmp_path, lambda **_kwargs: result
    )
    wrapped(body_bytes=body)

    persisted = next(tmp_path.iterdir()).read_text(encoding="utf-8")
    assert secret not in persisted
    receipt = json.loads(persisted)
    assert receipt["model_requested"] == "unrecognized_model"
    assert receipt["finish_reason"] == "unrecognized"
    assert receipt["native_finish_reason"] == "unrecognized"
    assert receipt["provider_error_code"] == "unrecognized"


def test_stale_protocol_digest_stops_before_live_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = tmp_path / "attempts"
    run_directory = tmp_path / "q2d-run"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    monkeypatch.setattr(q2d, "Q2D_RUN_DIRECTORY_V1", run_directory)
    monkeypatch.setattr(q2d, "CLAIM_STORE", tmp_path / "claims")
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    manifest.write_bytes(canonical_json(payload).encode("utf-8"))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("live construction was reached after a stale digest")

    monkeypatch.setattr(q2d, "OpenRouterSessionLedgerV1", forbidden)
    monkeypatch.setattr(q2d, "build_heterogeneous_council_v1", forbidden)
    with pytest.raises(ContractValidationError, match="digest mismatch"):
        q2d.run_condition_c_v1(
            question_name="q2",
            protocol_path=manifest,
            authorized_protocol_sha256="0" * 64,
        )

    assert not run_directory.exists()
    assert not attempts.exists()


def test_reused_process_dispatch_latch_stops_before_protocol_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = tmp_path / "attempts"
    run_directory = tmp_path / "q2d-run"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    monkeypatch.setattr(q2d, "Q2D_RUN_DIRECTORY_V1", run_directory)
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)

    class StaleProcessLatch:
        @staticmethod
        def count(kind: str) -> int:
            assert kind == "live_inference_post"
            return 1

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a stale process must stop before state acquisition")

    monkeypatch.setattr(q2d, "OPENROUTER_DISPATCH_LATCH_V1", StaleProcessLatch())
    monkeypatch.setattr(q2d, "OpenRouterSessionLedgerV1", forbidden)
    monkeypatch.setattr(q2d, "consume_authorized_protocol_attempt_v1", forbidden)
    monkeypatch.setattr(q2d, "build_heterogeneous_council_v1", forbidden)
    with pytest.raises(ContractValidationError, match="fresh inference-dispatch"):
        q2d.run_condition_c_v1(
            question_name="q2",
            protocol_path=manifest,
            authorized_protocol_sha256=hashlib.sha256(raw).hexdigest(),
        )

    assert not attempts.exists(), "the unique protocol attempt was not consumed"


def test_q2d_run_directory_and_artifacts_are_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_directory = tmp_path / "q2d-run"
    monkeypatch.setattr(q2d, "Q2D_RUN_DIRECTORY_V1", run_directory)

    acquired = q2d._create_q2d_run_directory_v1()
    assert acquired == run_directory
    assert (
        run_directory / q2d.Q2D_DISPATCH_EVIDENCE_DIRECTORY_NAME_V1
    ).is_dir()
    with pytest.raises(ContractValidationError, match="already exists"):
        q2d._create_q2d_run_directory_v1()

    target = run_directory / q2d.Q2D_RESULT_ARTIFACT_NAME_V1
    q2d._write_exclusive_fsynced_bytes_v1(target, b"first")
    with pytest.raises(ContractValidationError, match="already exists"):
        q2d._write_exclusive_fsynced_bytes_v1(target, b"second")
    assert target.read_bytes() == b"first"


def _run_q2d_with_fake_council_v1(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    council: object,
) -> dict:
    attempts = tmp_path / "attempts"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    monkeypatch.setattr(q2d, "Q2D_RUN_DIRECTORY_V1", tmp_path / "q2d-run")
    monkeypatch.setattr(
        q2d,
        "OPENROUTER_DISPATCH_LATCH_V1",
        SimpleNamespace(count=lambda kind: 0),
    )
    monkeypatch.setattr(q2d, "_assert_q2d_live_host_v1", lambda: None)
    monkeypatch.setattr(
        q2d, "build_heterogeneous_council_v1", lambda *_args, **_kwargs: council
    )
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)
    return q2d.run_condition_c_v1(
        question_name="q2",
        protocol_path=manifest,
        authorized_protocol_sha256=hashlib.sha256(raw).hexdigest(),
    )


def test_q2d_top_level_error_persists_only_a_safe_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "Patient Alice sk-or-v1-THISISASECRET123"

    class FailingCouncil:
        registry = SimpleNamespace(assess_readiness=lambda: (True, None))

        async def run_registry_session(self, _question: str, *, session_id: str):
            assert session_id == q2d.Q2D_SESSION_ID_V1
            raise RuntimeError(secret)

        @staticmethod
        def observability_rows():
            return ()

    record = _run_q2d_with_fake_council_v1(
        tmp_path=tmp_path, monkeypatch=monkeypatch, council=FailingCouncil()
    )
    persisted = canonical_json(record)
    assert record["error"] == "orchestration:RuntimeError"
    assert "Patient Alice" not in persisted
    assert "THISISASECRET123" not in persisted


def test_q2d_blocking_objections_are_sanitized_before_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "Blocking sk-or-v1-THISISASECRET123"

    class CompletedCouncil:
        registry = SimpleNamespace(assess_readiness=lambda: (True, None))

        async def run_registry_session(self, _question: str, *, session_id: str):
            assert session_id == q2d.Q2D_SESSION_ID_V1
            return SimpleNamespace(
                synthesis=None,
                ratified=False,
                ratification_status=None,
                release_decision=None,
                governing_epistemic_status=None,
                audit_summary=None,
                blocking_objections=[secret],
            )

        @staticmethod
        def observability_rows():
            return ()

    record = _run_q2d_with_fake_council_v1(
        tmp_path=tmp_path, monkeypatch=monkeypatch, council=CompletedCouncil()
    )
    persisted = canonical_json(record)
    assert record["blocking_objections"] == ["Blocking [REDACTED]"]
    assert "THISISASECRET123" not in persisted


def test_predispatch_guard_rechecks_the_exact_manifest_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = tmp_path / "attempts"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    monkeypatch.setattr(q2d, "CLAIM_STORE", tmp_path / "claims")
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    receipt = q2d.assert_exact_authorized_protocol_v1(
        protocol_path=manifest,
        authorized_sha256=digest,
        expected_schema_version=q2d.Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=payload,
    )
    capability = q2d.consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=attempts,
        session_id=q2d.Q2D_SESSION_ID_V1,
    )
    builder_scope = q2d._issue_and_bind_q2d_builder_scope_v1(capability)
    guard = q2d._seat_predispatch_guard_v1(
        "gpt_5_mini",
        protocol_path=manifest,
        protocol_receipt=receipt,
        expected_protocol_payload=payload,
        attempt_capability=capability,
        builder_scope=builder_scope,
    )

    manifest.write_bytes(raw + b"\n")
    with pytest.raises(ContractValidationError, match="digest mismatch"):
        guard(None, None)


def test_live_guard_cannot_be_built_without_protocol_authorization() -> None:
    with pytest.raises(TypeError):
        q2d._seat_predispatch_guard_v1("gpt_5_mini")


def test_q2d_guard_rejects_generic_externally_bound_builder_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = tmp_path / "attempts"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)
    receipt = q2d.assert_exact_authorized_protocol_v1(
        protocol_path=manifest,
        authorized_sha256=hashlib.sha256(raw).hexdigest(),
        expected_schema_version=q2d.Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=payload,
    )
    capability = q2d.consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=attempts,
        session_id=q2d.Q2D_SESSION_ID_V1,
    )

    class ExternalBuilder:
        pass

    external = ExternalBuilder()
    q2d.bind_authorized_protocol_attempt_v1(
        capability=capability,
        builder=external,
    )
    with pytest.raises(ContractValidationError, match="scope provenance"):
        q2d._seat_predispatch_guard_v1(
            "gpt_5_mini",
            protocol_path=manifest,
            protocol_receipt=receipt,
            expected_protocol_payload=payload,
            attempt_capability=capability,
            builder_scope=external,
        )
    with pytest.raises(TypeError, match="only be issued"):
        q2d._Q2DAuthorizedBuilderScopeV1()


def test_q2d_live_entry_has_no_attempt_claim_or_dispatch_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first-attempts"
    second = tmp_path / "second-attempts"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", first)
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)
    receipt = q2d.assert_exact_authorized_protocol_v1(
        protocol_path=manifest,
        authorized_sha256=hashlib.sha256(raw).hexdigest(),
        expected_schema_version=q2d.Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=payload,
    )
    capability = q2d.consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=first,
        session_id=q2d.Q2D_SESSION_ID_V1,
    )
    scope = q2d._issue_and_bind_q2d_builder_scope_v1(capability)
    guard = q2d._seat_predispatch_guard_v1(
        "gpt_5_mini",
        protocol_path=manifest,
        protocol_receipt=receipt,
        expected_protocol_payload=payload,
        attempt_capability=capability,
        builder_scope=scope,
    )

    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", second)
    second.mkdir()
    with pytest.raises(ContractValidationError, match="execution boundary drifted"):
        guard(None, None)
    assert not any(second.iterdir())

    assert "attempt_directory" not in inspect.signature(
        q2d.run_condition_c_v1
    ).parameters
    assert "out" not in inspect.signature(q2d.run_condition_c_v1).parameters
    live_builder_parameters = inspect.signature(
        q2d.build_heterogeneous_council_v1
    ).parameters
    assert "claim_directory" not in live_builder_parameters
    assert "dispatch" not in live_builder_parameters
    assert "attempt_directory" not in live_builder_parameters
    assert "evidence_directory" not in live_builder_parameters
    assert "attempt_directory" not in inspect.signature(
        q2d._seat_predispatch_guard_v1
    ).parameters


def test_q2d_seat_task_mapping_rejects_cross_seat_and_unreachable_tasks() -> None:
    opening = AgentTask(
        session_id=q2d.Q2D_SESSION_ID_V1,
        agent_id="agent_1",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.OPENING,
        question="q",
        task_kind=TaskKind.SOCRATIC_QUESTION,
    )
    q2d._assert_q2d_seat_task_mapping_v1(
        "gemini_3_7_flash_standard", opening
    )
    with pytest.raises(ContractValidationError, match="schedule signature"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gpt_5_mini", opening.model_copy(update={"agent_id": "agent_0"})
        )
    with pytest.raises(ContractValidationError, match="schedule signature"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gemini_3_7_flash_standard",
            opening.model_copy(update={"round_number": 1}),
        )

    initial = AgentTask(
        session_id=q2d.Q2D_SESSION_ID_V1,
        agent_id="agent_0",
        role=AgentRole.EMPIRICIST,
        phase=DialogPhase.INITIAL_RESPONSE,
        question="q",
        task_kind=TaskKind.INITIAL_RESPONSE,
    )
    q2d._assert_q2d_seat_task_mapping_v1("gpt_5_mini", initial)
    with pytest.raises(ContractValidationError, match="schedule signature"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gpt_5_mini", initial.model_copy(update={"round_number": 1})
        )

    beta_provider = q2d.normal.WORKER_PROVIDER_IDS_V1[1]
    beta_score = AgentTask(
        session_id=q2d.Q2D_SESSION_ID_V1,
        agent_id=beta_provider,
        role=AgentRole.FINAL_EVALUATOR,
        phase=DialogPhase.OPENING,
        question="q",
        task_kind=TaskKind.MOVE_SCORE,
    )
    q2d._assert_q2d_seat_task_mapping_v1(
        "gemini_3_7_flash_standard", beta_score
    )
    with pytest.raises(ContractValidationError, match="schedule signature"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gemini_3_7_flash_standard",
            beta_score.model_copy(update={"round_number": 1}),
        )
    with pytest.raises(ContractValidationError, match="not bound to worker_beta"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gemini_3_7_flash_standard",
            beta_score.model_copy(update={"agent_id": "worker_alpha"}),
        )

    # Objection verification intentionally identifies a target claim rather
    # than a logical agent/provider and is therefore allowed on every peer.
    q2d._assert_q2d_seat_task_mapping_v1(
        "gemini_3_7_flash_standard",
        AgentTask(
            session_id=q2d.Q2D_SESSION_ID_V1,
            agent_id="claim_123",
            role=AgentRole.FINAL_EVALUATOR,
            phase=DialogPhase.ELENCHUS,
            question="q",
            task_kind=TaskKind.OBJECTION_VERIFICATION,
        ),
    )

    with pytest.raises(ContractValidationError, match="phase/role relationship"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gpt_5_mini",
            AgentTask(
                session_id=q2d.Q2D_SESSION_ID_V1,
                agent_id="agent_0",
                role=AgentRole.FINAL_EVALUATOR,
                phase=DialogPhase.OPENING,
                question="q",
                task_kind=TaskKind.SOCRATIC_QUESTION,
            ),
        )
    with pytest.raises(ContractValidationError, match="not reachable"):
        q2d._assert_q2d_seat_task_mapping_v1(
            "gpt_5_mini",
            AgentTask(
                session_id=q2d.Q2D_SESSION_ID_V1,
                agent_id="agent_0",
                role=AgentRole.SYNTHESIZER,
                phase=DialogPhase.SYNTHESIS,
                question="q",
                task_kind=TaskKind.TREE_REVISION,
            ),
        )


def test_guard_requires_consumed_latch_and_binds_session_question_and_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = tmp_path / "attempts"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    receipt = q2d.assert_exact_authorized_protocol_v1(
        protocol_path=manifest,
        authorized_sha256=digest,
        expected_schema_version=q2d.Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=payload,
    )
    capability = q2d.consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=attempts,
        session_id=q2d.Q2D_SESSION_ID_V1,
    )
    builder_scope = q2d._issue_and_bind_q2d_builder_scope_v1(capability)
    guard = q2d._seat_predispatch_guard_v1(
        "gpt_5_mini",
        protocol_path=manifest,
        protocol_receipt=receipt,
        expected_protocol_payload=payload,
        attempt_capability=capability,
        builder_scope=builder_scope,
    )
    question = q2d._question_v1("q2")[0]
    task = AgentTask(
        task_id="q2d_guard_task",
        session_id=q2d.Q2D_SESSION_ID_V1,
        agent_id="agent_0",
        role=AgentRole.ELENCHUS_CRITIC,
        phase=DialogPhase.ELENCHUS,
        question=question,
        task_kind=TaskKind.ELENCHUS_OBJECTION,
    )
    state = AgentState(
        agent_id="agent_0",
        primary_role=AgentRole.ELENCHUS_CRITIC,
        assigned_role=AgentRole.ELENCHUS_CRITIC,
    )
    profile = q2d.q1.load_profile_v1("gpt_5_mini")

    def rendered_for(user_content: str, candidate: AgentTask = task):
        candidate_policy = q2d.build_seat_policy_v1(
            "gpt_5_mini",
            q2d.output_limit_for_seat_task_v1("gpt_5_mini", candidate),
        )
        turn = OpenRouterDynamicTurnRequestV1(
            system_prompt=q2d.build_reasoning_system_prompt(
                candidate.role,
                candidate.phase,
                candidate.task_kind,
                model=None,
            ),
            user_content=user_content,
            role_seat=candidate.role.value,
            dialogue_id=candidate.session_id,
            turn_id=candidate.task_id,
            dialogue_phase=candidate.phase.value,
        )
        return render_dynamic_turn_v1(
            candidate_policy,
            profile,
            turn,
            response_format_override=(
                q2d.normal.ced_structured_response_format_v1(candidate)
            ),
        )

    user_content = build_turn_user_content_v1(
        task,
        state,
        outbound_task_state_projector=q2d.normal.make_worker_payload_projector_v1(),
    )
    valid_rendered = rendered_for(user_content)
    guard(task, valid_rendered)

    forged_turn_identity = valid_rendered.model_copy(
        update={"turn_content_id": "forged-turn-content", "request_id": None}
    )
    with pytest.raises(ContractValidationError, match="turn-content identity"):
        guard(task, forged_turn_identity)
    forged_header_identity = valid_rendered.model_copy(
        update={"semantic_headers_sha256": "0" * 64, "request_id": None}
    )
    with pytest.raises(ContractValidationError, match="semantic-header identity"):
        guard(task, forged_header_identity)

    # The Beta wire body is otherwise valid for the Gemini seat, but it still
    # carries Alpha's logical agent. Physical seat and logical author cannot be
    # crossed even when every model/provider/body field is correct.
    beta_guard = q2d._seat_predispatch_guard_v1(
        "gemini_3_7_flash_standard",
        protocol_path=manifest,
        protocol_receipt=receipt,
        expected_protocol_payload=payload,
        attempt_capability=capability,
        builder_scope=builder_scope,
    )
    beta_policy = q2d.build_seat_policy_v1(
        "gemini_3_7_flash_standard", 4_096
    )
    beta_profile = q2d.q1.load_profile_v1("gemini_3_7_flash_standard")
    beta_turn = OpenRouterDynamicTurnRequestV1(
        system_prompt=q2d.build_reasoning_system_prompt(
            task.role, task.phase, task.task_kind, model=None
        ),
        user_content=user_content,
        role_seat=task.role.value,
        dialogue_id=task.session_id,
        turn_id=task.task_id,
        dialogue_phase=task.phase.value,
    )
    beta_rendered = render_dynamic_turn_v1(
        beta_policy,
        beta_profile,
        beta_turn,
        response_format_override=q2d.normal.ced_structured_response_format_v1(
            task
        ),
    )
    with pytest.raises(ContractValidationError, match="not bound to agent_1"):
        beta_guard(task, beta_rendered)

    round_one = task.model_copy(
        update={
            "task_id": "q2d_guard_task_round_1",
            "round_number": 1,
            "role": AgentRole.SOCRATES,
            "task_kind": TaskKind.SOCRATIC_QUESTION,
        }
    )
    round_one_state = state.model_copy(
        update={"assigned_role": AgentRole.SOCRATES}
    )
    round_one_user = build_turn_user_content_v1(
        round_one,
        round_one_state,
        outbound_task_state_projector=q2d.normal.make_worker_payload_projector_v1(),
    )
    guard(round_one, rendered_for(round_one_user, round_one))
    with pytest.raises(ContractValidationError, match="retries are prohibited"):
        guard(task.model_copy(update={"attempt_index": 1}), valid_rendered)
    with pytest.raises(ContractValidationError, match="schedule signature"):
        guard(task.model_copy(update={"round_number": 2}), valid_rendered)

    wrong_session = task.model_copy(update={"session_id": "NOT-Q2D"})
    with pytest.raises(ContractValidationError, match="session_id drifted"):
        guard(wrong_session, valid_rendered)
    wrong_question = task.model_copy(update={"question": "UNAUTHORIZED QUESTION"})
    with pytest.raises(ContractValidationError, match="question drifted"):
        guard(wrong_question, valid_rendered)
    malicious_rendered = rendered_for(
        q2d._COUNCIL_USER_PREFIX_V1
        + json.dumps(
            {
                "agent_state": state.model_dump(mode="json"),
                "response_contract": {
                    "format": "json_object",
                    "required": ["content", "confidence"],
                    "content_must_be_object": True,
                },
                "task": {"question": "UNAUTHORIZED BODY"},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    with pytest.raises(ContractValidationError, match="rendered task differs"):
        guard(task, malicious_rendered)

    valid_payload_text = user_content[len(q2d._COUNCIL_USER_PREFIX_V1) :]
    duplicate_task_payload = (
        valid_payload_text[:-1]
        + ', "task": {"question": "MALICIOUS OVERRIDE"}}'
    )
    duplicate_task_rendered = rendered_for(
        q2d._COUNCIL_USER_PREFIX_V1 + duplicate_task_payload
    )
    with pytest.raises(ContractValidationError, match="duplicate key: task"):
        guard(task, duplicate_task_rendered)

    extra_control_body = json.loads(valid_rendered.canonical_body_json)
    extra_control_body["top_p"] = 0.01
    extra_control_json = canonical_json(extra_control_body)
    extra_control_rendered = type(valid_rendered)(
        policy_id=valid_rendered.policy_id,
        profile_id=valid_rendered.profile_id,
        turn_content_id=valid_rendered.turn_content_id,
        canonical_body_json=extra_control_json,
        body_sha256=hashlib.sha256(extra_control_json.encode("utf-8")).hexdigest(),
        body_length=len(extra_control_json.encode("utf-8")),
        semantic_headers_sha256=valid_rendered.semantic_headers_sha256,
    )
    with pytest.raises(ContractValidationError, match="field set drifted"):
        guard(task, extra_control_rendered)

    duplicate_body_json = (
        valid_rendered.canonical_body_json[:-1]
        + ',"top_p":0.01,"top_p":0.02}'
    )
    duplicate_body_rendered = type(valid_rendered)(
        policy_id=valid_rendered.policy_id,
        profile_id=valid_rendered.profile_id,
        turn_content_id=valid_rendered.turn_content_id,
        canonical_body_json=duplicate_body_json,
        body_sha256=hashlib.sha256(duplicate_body_json.encode("utf-8")).hexdigest(),
        body_length=len(duplicate_body_json.encode("utf-8")),
        semantic_headers_sha256=valid_rendered.semantic_headers_sha256,
    )
    with pytest.raises(ContractValidationError, match="duplicate key: top_p"):
        guard(task, duplicate_body_rendered)

    wrong_state_payload = json.loads(valid_payload_text)
    wrong_state_payload["agent_state"]["primary_role"] = AgentRole.SOCRATES.value
    wrong_state_rendered = rendered_for(
        q2d._COUNCIL_USER_PREFIX_V1
        + json.dumps(wrong_state_payload, ensure_ascii=False, sort_keys=True)
    )
    with pytest.raises(ContractValidationError, match="state/task binding drifted"):
        guard(task, wrong_state_rendered)


def test_live_builder_is_one_shot_and_maps_one_model_to_one_logical_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = tmp_path / "attempts"
    monkeypatch.setattr(q2d, "RUN_ATTEMPT_LATCH_DIRECTORY_V1", attempts)
    monkeypatch.setattr(q2d, "CLAIM_STORE", tmp_path / "claims")
    payload = q2d.build_q2d_protocol_payload_v1()
    manifest = tmp_path / "q2d.json"
    raw = canonical_json(payload).encode("utf-8")
    manifest.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    receipt = q2d.assert_exact_authorized_protocol_v1(
        protocol_path=manifest,
        authorized_sha256=digest,
        expected_schema_version=q2d.Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=payload,
    )
    capability = q2d.consume_authorized_protocol_attempt_v1(
        receipt=receipt,
        attempt_directory=attempts,
        session_id=q2d.Q2D_SESSION_ID_V1,
    )
    bound = q2d.conservative_q2d_bound_v1()
    alpha_key = q2d.q1.COUNCIL_SEATS_V1[0][1]
    alpha_policy = q2d.build_seat_policy_v1(alpha_key, 16_384)
    authorization = q2d.OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement="Offline Q2d builder topology test; no dispatch.",
        policy_id=alpha_policy.policy_id or "",
        profile_id=q2d.q1.load_profile_v1(alpha_key).profile_id or "",
        model="multi-model",
        provider_selector="multi-endpoint",
        maximum_calls=bound["maximum_calls"],
        maximum_total_spend_picodollars=bound["total_picodollars"],
        maximum_per_call_spend_picodollars=bound[
            "maximum_per_call_picodollars"
        ],
        session_id=q2d.Q2D_SESSION_ID_V1,
    )
    ledger = q2d.OpenRouterSessionLedgerV1(authorization)

    council = q2d._build_heterogeneous_council_core_v1(
        ledger,
        claim_directory=tmp_path / "claims",
        dispatch=lambda **_kwargs: None,
        protocol_path=manifest,
        protocol_receipt=receipt,
        expected_protocol_payload=payload,
        attempt_capability=capability,
    )
    assert council.registry.assess_readiness() == (True, None)
    assert not hasattr(council.registry, "all_adapters")
    assert q2d.Q2D_LOGICAL_AGENTS_V1 == 3
    assert len({key for _alias, key in q2d.q1.COUNCIL_SEATS_V1}) == 3
    assert not hasattr(council, "agents")
    assert not hasattr(council, "create_session")

    with pytest.raises(ContractValidationError, match="already bound"):
        q2d._build_heterogeneous_council_core_v1(
            ledger,
            claim_directory=tmp_path / "fresh-claims",
            dispatch=lambda **_kwargs: None,
            protocol_path=manifest,
            protocol_receipt=receipt,
            expected_protocol_payload=payload,
            attempt_capability=capability,
        )


def test_authorized_council_consumes_run_before_delegate_failure() -> None:
    class StubAdapter:
        def observability_rows(self):
            return []

    class FailingCED:
        def __init__(self) -> None:
            self.registry = SimpleNamespace(assess_readiness=lambda: (True, None))
            self.calls = 0

        async def run_registry_session(self, question: str, *, session_id: str):
            self.calls += 1
            raise RuntimeError("first trajectory failed")

    delegate = FailingCED()
    council = q2d.Q2DAuthorizedCouncilV1(
        tuple(StubAdapter() for _ in range(q2d.Q2D_LOGICAL_AGENTS_V1)),
        delegate,
    )
    copied_before_start = copy.copy(council)
    question = q2d._question_v1("q2")[0]
    with pytest.raises(RuntimeError, match="first trajectory failed"):
        asyncio.run(
            council.run_registry_session(
                question, session_id=q2d.Q2D_SESSION_ID_V1
            )
        )
    assert delegate.calls == 1

    with pytest.raises(ContractValidationError, match="already started"):
        asyncio.run(
            copied_before_start.run_registry_session(
                question, session_id=q2d.Q2D_SESSION_ID_V1
            )
        )
    assert delegate.calls == 1


def test_authorized_council_returns_delegate_result_and_still_blocks_replay() -> None:
    class StubAdapter:
        def observability_rows(self):
            return []

    class SuccessfulCED:
        def __init__(self) -> None:
            self.registry = SimpleNamespace(assess_readiness=lambda: (True, None))
            self.calls = 0
            self.result = object()

        async def run_registry_session(self, question: str, *, session_id: str):
            self.calls += 1
            return self.result

    delegate = SuccessfulCED()
    council = q2d.Q2DAuthorizedCouncilV1(
        tuple(StubAdapter() for _ in range(q2d.Q2D_LOGICAL_AGENTS_V1)),
        delegate,
    )
    question = q2d._question_v1("q2")[0]
    assert asyncio.run(
        council.run_registry_session(
            question, session_id=q2d.Q2D_SESSION_ID_V1
        )
    ) is delegate.result
    with pytest.raises(ContractValidationError, match="already started"):
        asyncio.run(
            council.run_registry_session(
                question, session_id=q2d.Q2D_SESSION_ID_V1
            )
        )
    assert delegate.calls == 1


def test_q2d_protocol_payload_binds_exact_plan_and_retained_controls() -> None:
    payload = q2d.build_q2d_protocol_payload_v1()
    assert payload["schema_version"] == "socrates-q2d-freeze/v1"
    assert payload["session_id"] == q2d.Q2D_SESSION_ID_V1
    assert payload["attempt_latch"] == {
        "directory": str(q2d.RUN_ATTEMPT_LATCH_DIRECTORY_V1),
        "path_flavor": "windows_declared_absolute_path",
        "directory_control": "runner_owned_no_public_override",
        "consumption": "write_once_before_live_construction",
        "required_process_dispatch_class": "live_inference_post",
        "required_initial_process_dispatch_count": 0,
        "filesystem_trust_model": {
            "label": q2d.OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1,
            "threats_included": list(
                q2d.FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1
            ),
            "threats_excluded": list(
                q2d.FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1
            ),
        },
    }
    assert payload["local_execution_boundary"] == {
        "claim_store_declared": str(q2d.CLAIM_STORE),
        "claim_store_path_flavor": "windows_declared_absolute_path",
        "live_dispatch": "fixed_privacy_safe_openrouter_dispatch_v1",
        "local_code_threat_model": q2d.Q2D_TRUST_MODEL_V1,
        "claim_store_trust_model": {
            "label": q2d.OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1,
            "threats_included": list(
                q2d.FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1
            ),
            "threats_excluded": list(
                q2d.FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1
            ),
        },
    }
    assert payload["run_artifacts"] == {
        "run_directory": q2d.Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1,
        "result_artifact": (
            f"{q2d.Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1}/"
            f"{q2d.Q2D_RESULT_ARTIFACT_NAME_V1}"
        ),
        "dispatch_evidence_directory": (
            f"{q2d.Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1}/"
            f"{q2d.Q2D_DISPATCH_EVIDENCE_DIRECTORY_NAME_V1}"
        ),
        "directory_acquisition": "atomic_mkdir_exist_ok_false",
        "file_creation": "exclusive_xb_flush_fsync_no_overwrite",
    }
    assert set(payload["runtime_environment"]) == {
        "python_implementation",
        "python_version",
        "pydantic_version",
        "pydantic_core_version",
    }
    assert payload["runtime_environment"] == q2d._q2d_runtime_environment_v1()
    assert payload["scientific_classification"] == (
        "new_protocol_exploratory_reliability_run_not_confirmatory_replication"
    )
    assert payload["maximum_ced_calls"] == 107
    assert payload["required_cumulative_spend_picodollars"] == 5_836_119_800_000
    assert payload["retries"] == 0
    assert payload["substitution"] == "prohibited"
    assert payload["topology_repair"] == {
        "q2b_q2c_logical_agents": 4,
        "q2b_q2c_physical_models": 3,
        "q2d_logical_agents": 3,
        "q2d_physical_models": 3,
        "mapping": "one_logical_agent_per_physical_model",
        "reason": "unique_provider_quorum_and_one_to_one_authoring_identity",
    }
    assert payload["frozen_controls"]["question_sha256"] == (
        "1b20ffe116ab1f78e9cd63fc5722c5b0383d71492e311977d19d6cc7f375f8ad"
    )
    assert payload["failure_repairs"] == {
        "gemini_socratic_question": "no_change_provider_contract_violation",
        "gpt_5_mini_elenchus_objection": "output_limit_4096_to_8192",
    }
    assert payload["privacy_evidence"] == {
        "schema_version": "socrates-q2d-dispatch-evidence/v1",
        "raw_http_request_body_persisted": False,
        "raw_http_response_body_persisted": False,
        "sanitized_visible_assistant_output_persisted_in_main_artifact": True,
        "keyed_by": "body_sha256",
    }
    repository_root = Path(__file__).resolve().parents[1]
    expected_backend = {
        path.relative_to(repository_root).as_posix()
        for path in (repository_root / "backend" / "dialogues").rglob("*.py")
        if path.is_file()
    }
    expected_scripts = {
        ".gitattributes",
        "scripts/q2_ethics_question_v1.py",
        "scripts/score_q2_ethics_v1.py",
        "scripts/run_hard_logic_live_test_v1.py",
        "scripts/run_multimodel_q1_ced_v1.py",
        "scripts/run_multimodel_q1_v1.py",
        "scripts/run_reduced_socrates_benchmark_v1.py",
        "scripts/run_socrates_live_v1.py",
    }
    assert set(payload["implementation_sha256"]) == (
        expected_backend | expected_scripts
    )
    assert payload["implementation_hash_closure"] == {
        "backend": "all_backend/dialogues_recursive_python_files",
        "scripts": list(q2d.Q2D_RUNTIME_SCRIPT_FILES_V1),
        "repository_controls": [".gitattributes"],
        "ordering": "sorted_repository_relative_posix_paths",
    }
    assert set(payload["retained_evidence_sha256"]) == {
        "attribution_correction_ledger",
        "protocol_nonconformance_ledger",
        "q2b_council_trajectory",
        "q2b_matched_baselines",
        "q2b_protocol",
        "q2b_scored_baselines",
        "q2c_finish_reasons",
        "q2c_protocol_v1",
        "q2c_protocol_v2",
        "q2c_result",
    }
    expected_schema_keys = {
        "socratic.opening",
        "socratic.followup",
        "initial.elenchus_critic",
        "initial.empiricist",
        "initial.synthesizer",
        "elenchus.critic",
        "elenchus.empiricist",
        "reflection",
        "reconstruction",
        "synthesis",
        "move_score.opening",
        "move_score.initial_response",
        "move_score.elenchus",
        "move_score.reflection",
        "move_score.reconstruction",
        "move_score.synthesis",
        "section_score",
        "ratification",
        "objection_verification",
    }
    assert set(payload["reachable_response_schema_sha256"]) == expected_schema_keys
    assert payload["reachable_response_schema_sha256"] == (
        q2d._q2d_reachable_response_schema_sha256_v1()
    )


def test_all_six_frozen_controls_are_recomputed_not_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.q2_ethics_question_v1 as q2_key

    with monkeypatch.context() as scoped:
        scoped.setattr(q2_key, "QUESTION_V1", q2_key.QUESTION_V1 + " drift")
        with pytest.raises(ContractValidationError, match="digests drifted"):
            q2d.build_q2d_protocol_payload_v1()
    with monkeypatch.context() as scoped:
        scoped.setattr(
            q2_key,
            "CRITERIA_V1",
            q2_key.CRITERIA_V1 + (("DRIFT", "drift", 0),),
        )
        with pytest.raises(ContractValidationError, match="digests drifted"):
            q2d.build_q2d_protocol_payload_v1()
    with monkeypatch.context() as scoped:
        scoped.setattr(q2_key, "DIAGNOSIS_V1", q2_key.DIAGNOSIS_V1 + " drift")
        with pytest.raises(ContractValidationError, match="digests drifted"):
            q2d.build_q2d_protocol_payload_v1()
    with monkeypatch.context() as scoped:
        original = q2d.q1.reduced.baseline_response_format_v1
        scoped.setattr(
            q2d.q1.reduced,
            "baseline_response_format_v1",
            lambda: {**original(), "drift": True},
        )
        with pytest.raises(ContractValidationError, match="digests drifted"):
            q2d.build_q2d_protocol_payload_v1()
    with monkeypatch.context() as scoped:
        scoped.setattr(
            q2d.q1,
            "BASELINE_SYSTEM_PROMPT_V1",
            q2d.q1.BASELINE_SYSTEM_PROMPT_V1 + " drift",
        )
        with pytest.raises(ContractValidationError, match="digests drifted"):
            q2d.build_q2d_protocol_payload_v1()
    with monkeypatch.context() as scoped:
        original_load = q2d.q1.load_profile_v1

        def drifted_profile(key: str):
            profile = original_load(key)
            if key == "gpt_5_mini":
                return profile.model_copy(update={"evidence_sha256": "0" * 64})
            return profile

        scoped.setattr(q2d.q1, "load_profile_v1", drifted_profile)
        with pytest.raises(ContractValidationError, match="evidence_sha256 drifted"):
            q2d.build_q2d_protocol_payload_v1()


def test_q2d_frozen_protocol_is_exact_canonical_builder_output() -> None:
    path = RUNS / "q2d_frozen_protocol_v1.json"
    raw = path.read_bytes()
    frozen = json.loads(raw)
    expected_payload = q2d.build_q2d_protocol_payload_v1()
    frozen_python = frozen["runtime_environment"]["python_version"]
    expected_python = expected_payload["runtime_environment"]["python_version"]

    assert frozen_python.split(".")[:2] == expected_python.split(".")[:2]
    expected_payload["runtime_environment"]["python_version"] = frozen_python
    expected = canonical_json(expected_payload).encode("utf-8")

    assert len(raw) == Q2D_FROZEN_PROTOCOL_BYTE_LENGTH_V1
    assert hashlib.sha256(raw).hexdigest() == Q2D_FROZEN_PROTOCOL_SHA256_V1
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.endswith(b"\n")
    assert raw == expected
    assert frozen == expected_payload
