"""
Research R3a — Dialectic Delta instrument (offline validation).

Validates the MEASUREMENT: initial-vs-final flips against external truth
(corrected / degraded / net_gain), the conservative ANY-correct convention, and
the council integration. Mock runs make NO capability claim. No live calls.
"""

import pytest

from backend.evaluation.baseline_harness import EvalTask, synthetic_tasks
from backend.evaluation.dialectic_delta import (
    DialecticOutcome, flip_outcome, summarize, measure_dialectic_delta,
    extract_final_text, DISCLAIMER,
)

T = EvalTask(task_id="t1", question="What is 2+2?", gold="4", verifier="numeric")


# ── pure flip logic ───────────────────────────────────────────────────────────

def test_corrected_flip_detected():
    o = flip_outcome(["I think it is 5", "maybe 7"], "the answer is 4", T)
    assert o.corrected and not o.degraded
    assert not o.initial_any_correct and o.final_correct


def test_degraded_flip_detected():
    o = flip_outcome(["it is 4"], "after debate we say 9", T)
    assert o.degraded and not o.corrected
    assert o.initial_any_correct and not o.final_correct


def test_any_correct_is_conservative():
    # one of three initial answers right -> initial counts as right, so a right
    # final is NOT credited as a correction (the gain must beat best-initial)
    o = flip_outcome(["5", "4", "9"], "4", T)
    assert o.initial_any_correct and not o.corrected and not o.degraded
    assert not o.initial_majority_correct                     # majority was wrong


def test_summarize_counts_net_gain():
    outs = [
        flip_outcome(["5"], "4", T),   # corrected
        flip_outcome(["5"], "4", T),   # corrected
        flip_outcome(["4"], "5", T),   # degraded
        flip_outcome(["4"], "4", T),   # kept right
    ]
    rep = summarize(outs)
    assert rep.corrected == 2 and rep.degraded == 1 and rep.net_gain == 1
    assert rep.final_accuracy == pytest.approx(0.75)
    assert rep.initial_any_accuracy == pytest.approx(0.5)
    assert "No capability claim" in rep.disclaimer or "no capability claim" in rep.disclaimer.lower()


def test_empty_report():
    rep = summarize([])
    assert rep.n == 0 and rep.net_gain == 0


# ── council integration (mock; instrument only, no capability claim) ──────────

def _mock_council():
    from backend.dialogues.live_providers import build_council
    from backend.dialogues.models import ShadowScoringMode
    ced, mode = build_council(env={}, council_size=2,
                              shadow_scoring_mode=ShadowScoringMode.OFF)
    assert mode == "mock"
    return ced


def test_measure_runs_on_mock_council():
    rep = measure_dialectic_delta(_mock_council(), synthetic_tasks(3))
    assert rep.n == 3
    # honest: mock templates can't do arithmetic — both sides ~0, no fake gain
    assert rep.final_accuracy <= 0.34
    assert rep.disclaimer == DISCLAIMER


def test_extract_final_text_prefers_core_answer():
    ced = _mock_council()
    import asyncio
    final = asyncio.run(ced.run_registry_session("test q", session_id="eft"))
    text = extract_final_text(final)
    assert text.strip()                                        # populated from synthesis
