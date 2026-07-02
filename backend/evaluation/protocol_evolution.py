"""
Phase 13C — Protocol Evolution: measured self-improvement of the protocol itself.

The self-improvement trap is cargo-cult mutation: "improving" prompts/configs
with no evidence. This module makes protocol change EARN its way in:

    variant (config/prompt/council-shape change)
        → evaluated on EXTERNAL-truth tasks (dialectic delta: accuracy + net_gain)
        → PROMOTED only if it beats the incumbent by a pre-registered margin
        → otherwise the incumbent stays (status-quo bias is the safety default)

Promotion is a pure, deterministic rule — no LLM judge, no vibes. With mock
councils all variants measure ~equal, so nothing gets promoted on noise (the
margin guard). A real promotion decision requires real/recorded runs (gated).

No live calls here; the caller supplies whatever council factories it has.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .baseline_harness import EvalTask
from .dialectic_delta import DialecticReport, measure_dialectic_delta

DISCLAIMER = (
    "Protocol promotion requires beating the incumbent on EXTERNAL metrics by the "
    "pre-registered margin. Mock-based measurements cannot promote anything "
    "meaningful; a real decision needs live/recorded runs (gated)."
)

# Pre-registered default margin: a challenger must beat the incumbent's external
# accuracy by at least this much (absolute) to be promoted.
DEFAULT_MIN_GAIN = 0.02


@dataclass(frozen=True)
class VariantResult:
    """External-truth measurement of ONE protocol variant."""
    name: str
    final_accuracy: float
    net_gain: int                 # dialectic corrected − degraded
    n: int
    notes: str = ""


@dataclass(frozen=True)
class PromotionDecision:
    winner: str
    promoted: bool                # True only if the CHALLENGER won
    reason: str
    incumbent: str = ""
    challenger: str = ""


def evaluate_variant(
    name: str,
    council_factory: Callable[[], Any],
    tasks: Sequence[EvalTask],
    measure_fn: Callable[..., DialecticReport] = measure_dialectic_delta,
) -> VariantResult:
    """Measure one variant: build its council, run the dialectic delta on the
    task set, report external accuracy + error-correction dynamics."""
    ced = council_factory()
    report = measure_fn(ced, tasks, session_prefix=f"evo_{name}")
    return VariantResult(name=name, final_accuracy=report.final_accuracy,
                         net_gain=report.net_gain, n=report.n)


def promote(incumbent: VariantResult, challenger: VariantResult,
            min_gain: float = DEFAULT_MIN_GAIN) -> PromotionDecision:
    """
    Deterministic promotion rule (pre-registered; the challenger must EARN it):
      1. challenger.final_accuracy >= incumbent.final_accuracy + min_gain → promote
      2. accuracy within the margin but strictly better AND better net_gain →
         still NOT promoted (insufficient evidence — margin exists for a reason)
      3. anything else → incumbent stays
    """
    base = dict(incumbent=incumbent.name, challenger=challenger.name)
    if challenger.n == 0 or incumbent.n == 0:
        return PromotionDecision(winner=incumbent.name, promoted=False,
                                 reason="no evidence (empty run)", **base)
    if challenger.final_accuracy >= incumbent.final_accuracy + min_gain:
        return PromotionDecision(
            winner=challenger.name, promoted=True,
            reason=(f"external accuracy {challenger.final_accuracy:.4f} beats "
                    f"{incumbent.final_accuracy:.4f} by ≥ {min_gain:.2%} margin"),
            **base)
    return PromotionDecision(
        winner=incumbent.name, promoted=False,
        reason=(f"challenger {challenger.final_accuracy:.4f} did not exceed "
                f"incumbent {incumbent.final_accuracy:.4f} by the {min_gain:.2%} "
                "pre-registered margin — status quo retained"),
        **base)


@dataclass(frozen=True)
class ExperimentReport:
    incumbent: VariantResult
    challengers: List[VariantResult]
    decisions: List[PromotionDecision]
    adopted: str                   # the config the system should now use
    disclaimer: str = DISCLAIMER


def run_experiment(
    incumbent_name: str,
    factories: Dict[str, Callable[[], Any]],
    tasks: Sequence[EvalTask],
    min_gain: float = DEFAULT_MIN_GAIN,
    measure_fn: Callable[..., DialecticReport] = measure_dialectic_delta,
) -> ExperimentReport:
    """
    Evaluate the incumbent and every challenger on the SAME task set; challengers
    face the (possibly updated) champion sequentially in deterministic name order.
    The final `adopted` name is the config that survived all comparisons.
    """
    if incumbent_name not in factories:
        raise ValueError(f"unknown incumbent: {incumbent_name!r}")
    incumbent = evaluate_variant(incumbent_name, factories[incumbent_name], tasks, measure_fn)
    champion = incumbent
    challengers: List[VariantResult] = []
    decisions: List[PromotionDecision] = []
    for name in sorted(n for n in factories if n != incumbent_name):
        challenger = evaluate_variant(name, factories[name], tasks, measure_fn)
        challengers.append(challenger)
        decision = promote(champion, challenger, min_gain=min_gain)
        decisions.append(decision)
        if decision.promoted:
            champion = challenger
    return ExperimentReport(incumbent=incumbent, challengers=challengers,
                            decisions=decisions, adopted=champion.name)
