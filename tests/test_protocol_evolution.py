"""
Phase 13C — Protocol Evolution (measured self-improvement, offline validation).

Validates the promotion machinery: a challenger is adopted ONLY when it beats
the incumbent on external metrics by the pre-registered margin; mock noise can
never promote anything. No live calls.
"""

import pytest

from backend.evaluation.baseline_harness import synthetic_tasks
from backend.evaluation.dialectic_delta import DialecticReport
from backend.evaluation.protocol_evolution import (
    DEFAULT_MIN_GAIN, VariantResult, promote, evaluate_variant, run_experiment,
)


def _vr(name, acc, net=0, n=48):
    return VariantResult(name=name, final_accuracy=acc, net_gain=net, n=n)


# ── promotion rule (pure, deterministic) ──────────────────────────────────────

def test_challenger_promoted_only_beyond_margin():
    inc = _vr("incumbent", 0.50)
    assert promote(inc, _vr("better", 0.55)).promoted is True          # +5% > 2%
    assert promote(inc, _vr("barely", 0.51)).promoted is False         # within margin
    assert promote(inc, _vr("equal", 0.50)).promoted is False
    assert promote(inc, _vr("worse", 0.40)).promoted is False


def test_margin_is_configurable_and_preregistered():
    inc = _vr("incumbent", 0.50)
    assert promote(inc, _vr("c", 0.53), min_gain=0.05).promoted is False
    assert promote(inc, _vr("c", 0.56), min_gain=0.05).promoted is True
    assert DEFAULT_MIN_GAIN == 0.02


def test_no_evidence_never_promotes():
    assert promote(_vr("i", 0.5), _vr("c", 1.0, n=0)).promoted is False
    assert promote(_vr("i", 0.5, n=0), _vr("c", 1.0)).promoted is False


def test_decision_reason_is_explicit():
    d = promote(_vr("i", 0.5), _vr("c", 0.51))
    assert "status quo retained" in d.reason
    assert d.winner == "i" and d.incumbent == "i" and d.challenger == "c"


# ── run_experiment with a controllable measurement ────────────────────────────

def _fake_measure(accuracies):
    """A measure_fn stub with designed per-variant accuracies."""
    def fn(ced, tasks, session_prefix=""):
        name = session_prefix.replace("evo_", "")
        acc = accuracies[name]
        return DialecticReport(n=len(tasks), initial_any_accuracy=0.0,
                               initial_majority_accuracy=0.0, final_accuracy=acc,
                               corrected=0, degraded=0, net_gain=0)
    return fn


def test_experiment_adopts_the_measurably_better_variant():
    factories = {"baseline": lambda: object(), "variant_b": lambda: object()}
    rep = run_experiment("baseline", factories, synthetic_tasks(8),
                         measure_fn=_fake_measure({"baseline": 0.50, "variant_b": 0.70}))
    assert rep.adopted == "variant_b"
    assert rep.decisions[0].promoted is True


def test_experiment_retains_incumbent_within_margin():
    factories = {"baseline": lambda: object(), "variant_b": lambda: object()}
    rep = run_experiment("baseline", factories, synthetic_tasks(8),
                         measure_fn=_fake_measure({"baseline": 0.50, "variant_b": 0.51}))
    assert rep.adopted == "baseline"
    assert rep.decisions[0].promoted is False


def test_sequential_champion_defense():
    factories = {n: (lambda: object()) for n in ("baseline", "a_weak", "b_strong")}
    rep = run_experiment("baseline", factories, synthetic_tasks(8),
                         measure_fn=_fake_measure(
                             {"baseline": 0.50, "a_weak": 0.51, "b_strong": 0.80}))
    # a_weak fails vs baseline; b_strong beats baseline → adopted
    assert rep.adopted == "b_strong"


def test_unknown_incumbent_raises():
    with pytest.raises(ValueError, match="unknown incumbent"):
        run_experiment("nope", {"a": lambda: object()}, synthetic_tasks(2))


# ── integration: mock councils cannot be promoted on noise ────────────────────

def _mock_factory():
    from backend.dialogues.live_providers import build_council
    from backend.dialogues.models import ShadowScoringMode

    def make():
        ced, mode = build_council(env={}, council_size=2,
                                  shadow_scoring_mode=ShadowScoringMode.OFF)
        assert mode == "mock"
        return ced
    return make


def test_mock_variants_measure_equal_and_nothing_is_promoted():
    factories = {"baseline": _mock_factory(), "challenger": _mock_factory()}
    rep = run_experiment("baseline", factories, synthetic_tasks(3))
    assert rep.adopted == "baseline"                       # noise cannot promote
    assert all(not d.promoted for d in rep.decisions)
    assert "real decision needs live/recorded runs" in rep.disclaimer.lower() \
        or "gated" in rep.disclaimer.lower()
