import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.dialogues.socrates_zero.reduced_benchmark_evaluation_v1 import (
    HIDDEN_EVALUATOR_CANARY_V1,
    build_reduced_benchmark_evaluation_v1,
    classify_commitment_revisions_v1,
    classify_novel_contributions_v1,
    evaluate_answer_v1,
    hidden_evaluator_key_audit_v1,
    render_reduced_benchmark_markdown_v1,
)


def test_objective_keys_score_the_three_public_questions():
    q1 = evaluate_answer_v1(
        "Q1",
        "Yes. If Mira signed without checking, she violated procedure and could "
        "not chair, contradicting that she chaired. The either/or signer rule is "
        "exhaustive, so the remaining branch is that she checked.",
    )
    assert q1["correctness"] == "CORRECT"
    assert all(q1["features"].values())

    q2 = evaluate_answer_v1(
        "Q2",
        "The full causal claim is not justified. Voluntary application creates "
        "selection bias and training is a confound. Randomly assign the tool and "
        "hold training constant, or use a 2x2 factorial tool-by-training design.",
    )
    assert q2["correctness"] == "CORRECT"
    assert q2["selection_bias"] is True
    assert q2["training_confounding"] is True

    q3 = evaluate_answer_v1(
        "Q3",
        "The actor cannot be determined. Omar's token was used and workstation M "
        "was involved, but a credential or logged-in session does not identify the "
        "human actor. Neither Priya nor Omar can be accused on these facts.",
    )
    assert q3["correctness"] == "CORRECT"
    assert q3["unsupported_attribution_to_priya"] is False
    assert q3["unsupported_attribution_to_omar"] is False


def test_q2_requires_both_selection_and_training_plus_a_design():
    partial = evaluate_answer_v1(
        "Q2",
        "The conclusion is not justified because managers self-selected. Randomize "
        "teams to tool access and compare outcomes.",
    )
    assert partial["correctness"] == "PARTIALLY_CORRECT"
    assert "training_confound" in partial["important_omissions"]


def test_novel_useful_is_first_key_issue_not_stylistic_paraphrase():
    state = {
        "moves": [
            {
                "move_id": "m1",
                "phase": "initial_response",
                "role": "synthesizer",
                "task_kind": "initial_response",
                "provider_id": "Alpha",
                "content": {"text": "Voluntary uptake creates selection bias."},
            },
            {
                "move_id": "m2",
                "phase": "elenchus",
                "role": "elenchus_critic",
                "task_kind": "elenchus_objection",
                "provider_id": "Beta",
                "content": {"text": "This is self-selection by applicant managers."},
            },
            {
                "move_id": "m3",
                "phase": "elenchus",
                "role": "empiricist",
                "task_kind": "elenchus_objection",
                "provider_id": "Gamma",
                "content": {"text": "Training is a confound; use a factorial design."},
            },
        ]
    }
    rows = classify_novel_contributions_v1(
        state, {"Alpha": "openai/gpt-5-mini", "Beta": "openai/gpt-5-mini", "Gamma": "openai/gpt-5-mini"}
    )
    assert [row["classification"] for row in rows] == [
        "NOVEL_USEFUL",
        "REDUNDANT",
        "NOVEL_USEFUL",
    ]
    assert rows[2]["novel_useful_features"] == ["factorial_design", "training_confound"]


def test_revision_metric_uses_declared_append_only_commitment_events():
    ledger = [
        {
            "commitment_id": "c1",
            "source_move_id": "m1",
            "claim": "The AI tool caused the full 18% increase.",
            "status": "asserted",
        },
        {
            "commitment_id": "c2",
            "source_move_id": "m2",
            "claim": (
                "The causal claim is not justified because selection bias and "
                "training confounding remain."
            ),
            "status": "revised",
            "target_commitment_id": "c1",
            "provider_id": "Alpha",
            "model_id": "openai/gpt-5-mini",
        },
    ]
    rows = classify_commitment_revisions_v1(ledger)
    assert len(rows) == 1
    assert rows[0]["classification"] == "USEFUL_REVISION"


def test_hidden_key_audit_digests_every_exact_body_and_fails_on_canary():
    clean = hidden_evaluator_key_audit_v1(["{\"model\":\"x\"}", "{\"model\":\"y\"}"])
    assert clean["request_body_count"] == 2
    assert clean["passed"] is True
    assert len(clean["ordered_body_manifest_sha256"]) == 64

    tainted = hidden_evaluator_key_audit_v1([f"x {HIDDEN_EVALUATOR_CANARY_V1} y"])
    assert tainted["passed"] is False
    assert tainted["canary_match_indices"] == [0]


def test_reduced_report_never_invents_removed_heterogeneous_arm():
    collection = {
        "maximum_live_calls": 151,
        "actual_live_calls": 4,
        "hard_total_spend_usd": "8.00",
        "model": "openai/gpt-5-mini",
        "provider_selector": "openai/flex",
        "baselines": {
            "Q1": {"assistant_output": "No.", "usage": {}},
            "Q2": {
                "assistant_output": (
                    "Not justified: selection bias and training confounding. "
                    "Randomize tool access."
                ),
                "usage": {"observed_cost_picodollars": 10},
            },
            "Q3": {"assistant_output": "Cannot determine the actor.", "usage": {}},
        },
        "homogeneous_q2": {
            "final": {
                "answer": (
                    "Not justified due to selection bias and training confounding. "
                    "Use randomized assignment."
                ),
                "synthesis": {},
                "audit_summary": {"commitment_ledger": []},
            },
            "state": {"moves": []},
            "provider_models": {},
            "turns": [{"observed_cost_picodollars": 20}],
            "calls_consumed": 1,
        },
        "wire_evidence": {"provider_bound_bodies": [json.dumps({"model": "x"})]},
    }
    evaluation = build_reduced_benchmark_evaluation_v1(collection)
    assert evaluation["scientific_scope"]["diversity_signal"] == "NOT_TESTED"
    assert evaluation["scientific_scope"]["heterogeneous_comparison_available"] is False
    report = render_reduced_benchmark_markdown_v1(collection, evaluation)
    assert "cannot measure model diversity" in report
    assert "HETEROGENEOUS SOCRATES 3-QUESTION BENCHMARK COMPLETE" not in report


def _flex_endpoint_bytes() -> bytes:
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


def test_runner_derives_148_ced_calls_plus_three_baselines():
    from scripts.run_reduced_socrates_benchmark_v1 import (
        derive_reduced_call_budget_v1,
    )

    assert derive_reduced_call_budget_v1() == {
        "socratic_questions": 3,
        "initial_responses": 3,
        "elenchus_objections": 4,
        "reflections": 6,
        "reconstruction": 1,
        "synthesis": 4,
        "move_scores": 63,
        "section_scores": 60,
        "ratification": 4,
        "homogeneous_objection_verification": 0,
        "ced_maximum": 148,
        "baselines": 3,
        "total_maximum": 151,
    }


def test_authorization_manifest_binds_questions_ced_schemas_route_and_budget(
    monkeypatch,
):
    import scripts.run_reduced_socrates_benchmark_v1 as runner
    from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
        build_reduced_flex_policy_v1,
        flex_profile_from_evidence_v1,
        validate_flex_endpoint_listing_v1,
    )

    policy = build_reduced_flex_policy_v1()
    profile = flex_profile_from_evidence_v1(
        validate_flex_endpoint_listing_v1(_flex_endpoint_bytes())
    )
    manifest = runner.build_benchmark_authorization_manifest_v1(policy, profile)
    assert manifest["policy_id"] == policy.policy_id
    assert manifest["profile_id"] == profile.profile_id
    assert manifest["maximum_live_calls"] == 151
    assert manifest["hard_total_spend_usd"] == "8.00"
    assert manifest["automatic_retries"] == 0
    assert len(manifest["questions"]) == 3
    assert len(manifest["ced_source_sha256"]) == 64
    assert len(manifest["structured_schemas"]["ced_variants"]) == 14

    changed = list(runner.PUBLIC_QUESTIONS_V1)
    qid, title, question = changed[0]
    changed[0] = (qid, title, question + " changed")
    monkeypatch.setattr(runner, "PUBLIC_QUESTIONS_V1", tuple(changed))
    with pytest.raises(Exception, match="question bytes have drifted"):
        runner.build_benchmark_authorization_manifest_v1(policy, profile)


def test_pre_network_gates_exactly_lock_decimal_spend_questions_and_ced():
    import scripts.run_reduced_socrates_benchmark_v1 as runner

    policy = runner.assert_runner_pre_network_gates_v1()
    assert policy.model == "openai/gpt-5-mini"
    assert runner.APPROVED_QUESTION_SHA256_V1 == {
        "Q1": "07af0cae3894d35d7c5e1e7410624ea9bf4ec397935897260beff0c7d57551fd",
        "Q2": "1726f5eed7d420c512e247b9f984830315c9641c72ef1f9a6d55fe606d782ce4",
        "Q3": "a52d7fca4e2babc9428a413edaa08d4b26cc140c32d83851e43948a584bfd941",
    }
    assert (
        runner.APPROVED_CED_SOURCE_SHA256_V1
        == "2f0396e6248db54f8985c643a69b0429f354110e6536c1edc699dcf3b9ff4a43"
    )


def test_stable_run_attempt_latch_is_endpoint_independent_and_one_shot(tmp_path):
    import scripts.run_reduced_socrates_benchmark_v1 as runner

    first_id = runner.stable_run_attempt_id_v1()
    first = runner.consume_stable_run_attempt_latch_v1(tmp_path)
    assert first["run_attempt_id"] == first_id
    assert Path(first["latch_path"]).is_file()
    with pytest.raises(Exception, match="already consumed"):
        runner.consume_stable_run_attempt_latch_v1(tmp_path)
    assert runner.stable_run_attempt_id_v1() == first_id


def test_ced_constructor_failure_precedes_latch_and_every_post(
    monkeypatch, tmp_path
):
    import scripts.run_reduced_socrates_benchmark_v1 as runner
    from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
        OpenRouterSessionLedgerV1,
    )
    from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
        build_reduced_flex_policy_v1,
        build_reduced_session_authorization_v1,
        flex_profile_from_evidence_v1,
        validate_flex_endpoint_listing_v1,
    )

    policy = build_reduced_flex_policy_v1()
    profile = flex_profile_from_evidence_v1(
        validate_flex_endpoint_listing_v1(_flex_endpoint_bytes())
    )
    session = build_reduced_session_authorization_v1(
        policy, profile, session_id="offline-constructor-order-proof"
    )
    ledger = OpenRouterSessionLedgerV1(session)
    capture = runner._ProviderBodyCaptureV1()
    post_attempts = []

    def forbidden_transport(**_kwargs):
        post_attempts.append("POST")
        raise AssertionError("offline constructor preflight reached transport")

    fatal_dispatch = runner._FatalSessionDispatchV1(
        capture, ledger, transport=forbidden_transport
    )

    class FailingAdapter:
        def __init__(self, **_kwargs):
            raise RuntimeError("injected CED adapter wiring failure")

    monkeypatch.setattr(runner, "SocratesLiveOpenRouterAdapter", FailingAdapter)
    q2 = next(
        question
        for qid, _title, question in runner.PUBLIC_QUESTIONS_V1
        if qid == "Q2"
    )
    with pytest.raises(RuntimeError, match="adapter wiring failure"):
        runner._prepare_ced_then_consume_run_attempt_v1(
            policy=policy,
            profile=profile,
            ledger=ledger,
            fatal_dispatch=fatal_dispatch,
            session_id=session.session_id,
            question=q2,
            latch_directory=tmp_path,
        )

    assert post_attempts == []
    assert ledger.calls_consumed == 0
    assert list(tmp_path.iterdir()) == []


def test_baseline_fatal_stop_preserves_first_consumed_record(monkeypatch):
    import scripts.run_reduced_socrates_benchmark_v1 as runner

    ledger = SimpleNamespace(fatal_failure=None)
    record_value = {
        "body_sha256": "a" * 64,
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "observed_cost_picodollars": 1,
        "observed_cost_usd_decimal": "0.000000000001",
    }

    def fake_execute(**_kwargs):
        ledger.fatal_failure = "returned_model_identity_mismatch"
        return SimpleNamespace(
            record=SimpleNamespace(
                model_dump=lambda **_kwargs: dict(record_value)
            ),
            assistant_text=(
                '{"conclusion":"x","reasoning":"y",'
                '"uncertainty":"","confidence":0.5}'
            ),
            failure_reason="returned_model_identity_mismatch",
        )

    monkeypatch.setattr(runner, "execute_bounded_text_turn_v1", fake_execute)
    baselines = {}
    records = []
    with pytest.raises(Exception, match="fatal session latch"):
        runner._run_baselines_v1(
            object(),
            object(),
            ledger,
            lambda *_args: None,
            lambda **_kwargs: None,
            baselines=baselines,
            records=records,
        )
    assert list(baselines) == ["Q1"]
    assert records == [record_value]


def test_main_writes_partial_failure_collection_without_evaluator_or_report(
    monkeypatch, tmp_path
):
    import scripts.run_reduced_socrates_benchmark_v1 as runner

    collection_path = tmp_path / "collection.json"
    evaluation_path = tmp_path / "evaluation.json"
    report_path = tmp_path / "report.md"

    def fail_collection(*, record, **_kwargs):
        record.update(
            {
                "actual_live_calls": 1,
                "wire_evidence": {
                    "provider_bound_bodies": ['{"model":"openai/gpt-5-mini"}']
                },
            }
        )
        raise RuntimeError("bounded partial failure")

    monkeypatch.setattr(runner, "collect_reduced_benchmark_v1", fail_collection)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(runner.__file__),
            "--execute-approved",
            "--collection-out",
            str(collection_path),
            "--evaluation-out",
            str(evaluation_path),
            "--report-out",
            str(report_path),
        ],
    )
    assert runner.main() == 1
    persisted = json.loads(collection_path.read_text(encoding="utf-8"))
    assert persisted["actual_live_calls"] == 1
    assert persisted["result"] == "REDUCED_SOCRATES_BENCHMARK_FAILED"
    assert persisted["collection_dispatch_closed"] is True
    assert len(persisted["wire_evidence"]["provider_bound_bodies"]) == 1
    assert not evaluation_path.exists()
    assert not report_path.exists()


def test_baseline_schema_is_strict_and_not_a_ced_move_envelope():
    from scripts.run_reduced_socrates_benchmark_v1 import baseline_response_format_v1

    schema = baseline_response_format_v1()["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "conclusion",
        "reasoning",
        "uncertainty",
        "confidence",
    }
    assert "content" not in schema["properties"]
    assert "epistemic_marker" not in schema["properties"]


def test_live_collector_does_not_import_hidden_evaluator_at_module_scope():
    import scripts.run_reduced_socrates_benchmark_v1 as runner

    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top_level_imports.append(node.module)
        elif isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
    assert runner.EVALUATOR_MODULE_NAME_V1 not in top_level_imports


def test_collection_refuses_before_endpoint_or_credential_when_evaluator_loaded():
    import scripts.run_reduced_socrates_benchmark_v1 as runner

    # This test module imported the evaluator at collection time. The collector
    # must reject that state before touching even injected endpoint evidence.
    with pytest.raises(Exception, match="evaluator module was imported"):
        runner.collect_reduced_benchmark_v1(endpoint_raw=_flex_endpoint_bytes())
