"""CED Evaluation Harness v0.1 — tests (deterministic, offline, CI-safe)."""

import json

import pytest

from backend.evaluation.benchmark_cases import (
    SCHEMA_VERSION,
    load_benchmark,
)
from backend.evaluation.scripted_model import ScriptedModel
from backend.evaluation.harness import run_benchmark, run_case, HARNESS_DISCLAIMER


def _by_id(report):
    return {c["case_id"]: c for c in report.cases}


# --- data + schema ---------------------------------------------------------

def test_benchmark_data_loads_and_wellformed():
    cases = load_benchmark()
    assert len(cases) >= 3
    ids = [c.id for c in cases]
    assert ids == sorted(ids)  # deterministic order
    for c in cases:
        assert c.question and c.rounds >= 1
        assert c.answer_turns()  # at least one position


def test_loader_rejects_wrong_schema_version(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "ced_eval_v9.9", "cases": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_benchmark(bad)


# --- scripted model + no-live-call guard -----------------------------------

def test_scripted_model_is_deterministic():
    m = ScriptedModel({"hello": "world"}, default="d")
    assert m.respond("say hello please") == "world"
    assert m.respond("say hello please") == "world"
    assert m.respond("nothing matches") == "d"
    assert ScriptedModel.is_scripted is True


def test_harness_does_not_call_live_models(monkeypatch):
    """Patch every live model entrypoint to explode; the scripted harness must
    still complete, proving it performs no live model calls."""
    import socrates_ai

    def boom(*args, **kwargs):
        raise AssertionError("Live model call attempted in scripted harness!")

    for name in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, name):
            monkeypatch.setattr(socrates_ai.DialogManager, name, boom, raising=False)

    report = run_benchmark()
    assert report.case_count >= 3


# --- determinism -----------------------------------------------------------

def test_harness_runs_deterministically():
    a = run_benchmark().to_dict()
    b = run_benchmark().to_dict()
    assert a == b


# --- per-metric behavior ---------------------------------------------------

def test_claim_extraction_metric_flags_wrappers():
    cases = _by_id(run_benchmark())
    # Wrapper case: instruction wrapper stripped, expected claim survived.
    assert cases["a_wrapper_jtb"]["claim_extraction"] == 1.0
    # Injection note case: note removed, expected claim survived.
    assert cases["b_injection_note_reliabilism"]["claim_extraction"] == 1.0


def test_elenchus_target_metric_detects_correct():
    cases = _by_id(run_benchmark())
    assert cases["a_wrapper_jtb"]["elenchus_target"] == 1.0
    assert cases["b_injection_note_reliabilism"]["elenchus_target"] == 1.0


def test_revision_usefulness_two_pronged_rewards_substance_penalizes_rambling():
    cases = _by_id(run_benchmark())
    good = cases["a_wrapper_jtb"]["revision_usefulness"]
    rambling = cases["c_rambling_revision"]["revision_usefulness"]
    assert good >= 0.75
    assert rambling <= 0.25
    assert good > rambling
    # The rambling revision is detected as not improving (delta) and full of filler.
    detail = cases["c_rambling_revision"]["revision_detail"]
    assert detail["improved"] is False
    assert detail["forbidden_ok"] is False


def test_single_shot_vs_ced_metric_prefers_ced_when_loop_adds_objection():
    cases = _by_id(run_benchmark())
    # The CED loop adds objection + uncertainty the single shot lacked.
    assert cases["a_wrapper_jtb"]["single_shot_vs_ced"]["score"] == 1.0
    assert cases["a_wrapper_jtb"]["single_shot_vs_ced"]["ced_at_least_single_shot"] is True


def test_cbe_quality_metric_reflects_contract():
    cases = _by_id(run_benchmark())
    # Rich cases expose the required practical-answer fields.
    assert cases["a_wrapper_jtb"]["cbe_quality"] == 1.0
    assert cases["b_injection_note_reliabilism"]["cbe_quality"] == 1.0


# --- report shape + humility -----------------------------------------------

def test_run_report_carries_humble_disclaimer():
    report = run_benchmark()
    assert report.disclaimer == HARNESS_DISCLAIMER
    assert "does NOT prove CED is globally better" in report.disclaimer
    assert report.schema_version == SCHEMA_VERSION


def test_run_report_aggregates_per_case_and_overall():
    report = run_benchmark()
    assert report.case_count == len(report.cases)
    expected = round(sum(c["run_score"] for c in report.cases) / len(report.cases), 3)
    assert report.aggregate_run_score == expected
    for c in report.cases:
        assert 0.0 <= c["run_score"] <= 1.0


def test_cli_output_is_valid_json(capsys):
    """`python -m backend.evaluation.run_eval` must print parseable JSON to
    stdout (the disclaimer lives inside the JSON, not as trailing plaintext)."""
    from backend.evaluation import run_eval

    run_eval.main()
    out = capsys.readouterr().out

    parsed = json.loads(out)  # must not raise
    assert parsed["schema_version"] == "ced_eval_v0.1"
    assert "disclaimer" in parsed and parsed["disclaimer"]
    assert "aggregate_run_score" in parsed
