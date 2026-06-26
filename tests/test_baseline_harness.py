"""
Research R1 — external-ground-truth baseline harness (offline).

Validates the MEASUREMENT INSTRUMENT (verifiers, accuracy, ECE, cost, self-
consistency detection, non-circularity) on inputs with known answers. Makes NO
claim about CED capability. No live calls, no keys, no .env.
"""

import json

import pytest

from backend.evaluation.baseline_harness import (
    SCHEMA_VERSION, EvalTask, synthetic_tasks, load_verifiable_tasks,
    extract_final_answer, verify, verify_numeric, verify_exact, verify_set,
    OracleAnswerer, SelfConsistencyAnswerer, CouncilAnswerer,
    run_benchmark, compare, expected_calibration_error, TaskOutcome,
)


# ── verifiers (external ground truth, no LLM judge) ──────────────────────────

def test_numeric_verifier_extracts_final_number():
    assert verify_numeric("the answer is 42", "42")
    assert verify_numeric("#### 7", "7")
    assert not verify_numeric("8", "7")
    assert not verify_numeric("no number here", "7")


def test_exact_and_set_verifiers():
    assert verify_exact("Final answer: Paris", "paris")
    assert not verify_exact("London", "paris")
    assert verify_set("a, b, c", "a|b")
    assert not verify_set("a", "a|b")


def test_extract_final_answer_prefers_markers():
    assert extract_final_answer("blah #### 12") == "12"
    assert extract_final_answer("Answer: yes") == "yes"
    assert extract_final_answer("...the total is 9") == "9"


# ── dataset + loader ─────────────────────────────────────────────────────────

def test_synthetic_tasks_are_deterministic_and_verifiable():
    a, b = synthetic_tasks(20), synthetic_tasks(20)
    assert [t.gold for t in a] == [t.gold for t in b]      # deterministic
    # gold answers actually satisfy their own verifier
    for t in a:
        assert verify(t, t.gold)


def test_loader_round_trip_and_schema_guard(tmp_path):
    tasks = load_verifiable_tasks()                         # on-disk set loads
    assert len(tasks) >= 40 and all(isinstance(t, EvalTask) for t in tasks)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "WRONG", "tasks": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_verifiable_tasks(bad)


# ── accuracy measurement (oracle controls) ───────────────────────────────────

def test_perfect_and_broken_oracle_bound_accuracy():
    tasks = synthetic_tasks(48)
    assert run_benchmark(OracleAnswerer(0.0), tasks).accuracy == 1.0
    assert run_benchmark(OracleAnswerer(1.0), tasks).accuracy == 0.0


def test_oracle_is_deterministic():
    tasks = synthetic_tasks(30)
    r1 = run_benchmark(OracleAnswerer(0.4, seed="z"), tasks)
    r2 = run_benchmark(OracleAnswerer(0.4, seed="z"), tasks)
    assert r1.accuracy == r2.accuracy


# ── self-consistency: detects ensembling gain AND its cost (H2 + H3) ─────────

def test_self_consistency_beats_noisy_base_at_5x_cost():
    tasks = synthetic_tasks(48)
    base = OracleAnswerer(error_rate=0.4, seed="b")
    rb = run_benchmark(base, tasks)
    rs = run_benchmark(SelfConsistencyAnswerer(base, k=5), tasks)
    assert rs.accuracy > rb.accuracy                        # ensembling gain detected
    assert rs.cost_per_task == pytest.approx(5 * rb.cost_per_task)  # and its 5x cost


# ── calibration (ECE) ────────────────────────────────────────────────────────

def test_ece_distinguishes_calibrated_from_overconfident():
    tasks = synthetic_tasks(48)
    cal = run_benchmark(OracleAnswerer(0.3, confidence_mode="calibrated"), tasks).ece
    over = run_benchmark(OracleAnswerer(0.3, confidence_mode="overconfident"), tasks).ece
    assert over > cal


def test_ece_zero_for_perfectly_calibrated_certain_correct():
    outs = [TaskOutcome(f"t{i}", correct=True, confidence=1.0, cost_units=1.0, prediction="x")
            for i in range(10)]
    assert expected_calibration_error(outs) == 0.0


# ── compare() Pareto view ────────────────────────────────────────────────────

def test_compare_reports_quality_per_cost():
    tasks = synthetic_tasks(24)
    base = OracleAnswerer(0.2, seed="c")
    rows = compare([base, SelfConsistencyAnswerer(base, k=5)], tasks)
    assert len(rows) == 2
    # self-consistency costs 5x → quality-per-cost must drop even if accuracy rises
    assert rows[1].quality_per_cost < rows[0].quality_per_cost


# ── NON-CIRCULARITY: mock council scored by external truth ~ chance ──────────

def _mock_council():
    from backend.dialogues.providers import FakeProvider
    from backend.dialogues.agent import SocraticAgent
    from backend.dialogues.ced import CEDOrchestrator
    from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    reg.register(ScriptedMockProvider("m_a"))
    reg.register(ScriptedMockProvider("m_b"))
    return CouncilAnswerer(CEDOrchestrator(agents, p, registry=reg))


def test_mock_council_scores_chance_on_external_truth():
    # The mock council is 'ratified' by CED's own scorer, yet must score ~chance on
    # EXTERNAL numeric truth — proving the harness is non-circular (not CED-inflated).
    tasks = synthetic_tasks(6)
    rep = run_benchmark(_mock_council(), tasks)
    assert rep.accuracy <= 0.2                               # template content can't do arithmetic
    assert rep.cost_per_task > 1                             # council costs >> a single call (H3)


def test_harness_makes_no_capability_claim():
    rep = run_benchmark(OracleAnswerer(0.0), synthetic_tasks(4))
    assert "No claim about CED capability" in rep.disclaimer


# ── runner smoke ─────────────────────────────────────────────────────────────

def test_runner_renders_offline():
    from backend.evaluation import run_baseline_eval as r
    report = r.render_report()
    assert "NON-CIRCULARITY CHECK" in report
    assert "no real api calls" in report.lower()
