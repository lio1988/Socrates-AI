"""
Phase 26E — Smart Learning Preference Miner.

This is where the parallel learning layer starts becoming useful. It takes the
sanitized LearningDataset produced by Phase 26D and mines DPO/RLHF/RLAIF-ready
preference pairs using mechanical, auditable CED signals:

  - training eligibility from SocratesConstitution;
  - winner sections from blind assembly;
  - confidence deltas;
  - peer-score aggregates;
  - external eval pass/fail markers when present;
  - ratification status / failed sections.

It does NOT train, fine-tune, call providers, mutate CED state, or change the core
CED protocol. It only creates candidate preference data with explicit rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from .learning_foundation import (
    LearningDataset,
    LearningTrace,
    PreferenceExample,
    SocratesConstitution,
    build_preference_example,
    render_trace_answer,
    sanitize_public_payload,
)


class PreferenceSignal(str, Enum):
    EXTERNAL_EVAL = "external_eval"
    ASSEMBLY_WINNER = "assembly_winner"
    PEER_SCORE_GAP = "peer_score_gap"
    CONFIDENCE_CALIBRATION = "confidence_calibration"
    RATIFICATION_STATUS = "ratification_status"
    CLEAN_ELIGIBILITY = "clean_eligibility"


class PreferenceMiningMode(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class PreferenceMiningPolicy:
    """
    Mechanical thresholds for preference mining.

    Conservative is meant for high-quality training exports. Aggressive can be
    useful for diagnostics but should not be used for actual model alignment until
    validated by external evals/human review.
    """

    mode: PreferenceMiningMode = PreferenceMiningMode.CONSERVATIVE
    min_signal_margin: float = 1.0
    min_confidence_delta: float = 0.15
    min_peer_score_delta: float = 0.75
    max_pairs_per_prompt: int = 3
    require_chosen_eligible: bool = True
    require_rejected_valid: bool = True
    allow_same_provider_pair: bool = True
    require_rationale: bool = True

    @classmethod
    def conservative(cls) -> "PreferenceMiningPolicy":
        return cls()

    @classmethod
    def balanced(cls) -> "PreferenceMiningPolicy":
        return cls(
            mode=PreferenceMiningMode.BALANCED,
            min_signal_margin=0.65,
            min_confidence_delta=0.10,
            min_peer_score_delta=0.50,
            max_pairs_per_prompt=5,
        )

    @classmethod
    def aggressive(cls) -> "PreferenceMiningPolicy":
        return cls(
            mode=PreferenceMiningMode.AGGRESSIVE,
            min_signal_margin=0.35,
            min_confidence_delta=0.05,
            min_peer_score_delta=0.25,
            max_pairs_per_prompt=8,
            require_chosen_eligible=True,
            require_rejected_valid=True,
        )


class TracePreferenceScore(BaseModel):
    trace_id: str
    question: str
    provider_id: str
    provider_family: str = "unknown"
    model: str = "unknown"
    task_kind: Optional[str] = None
    score: float = 0.0
    signals: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)

    def signal(self, name: PreferenceSignal, value: float, reason: str) -> None:
        self.signals[name.value] = round(float(value), 6)
        self.score += float(value)
        self.reasons.append(reason)


class MinedPreferenceCandidate(BaseModel):
    chosen_trace_id: str
    rejected_trace_id: str
    prompt: str
    margin: float
    chosen_score: float
    rejected_score: float
    rationale: str
    signals: Dict[str, Any] = Field(default_factory=dict)


class PreferenceMiningReport(BaseModel):
    policy_mode: str
    traces_seen: int = 0
    trainable_traces: int = 0
    prompts_seen: int = 0
    candidates: List[MinedPreferenceCandidate] = Field(default_factory=list)
    preferences: List[PreferenceExample] = Field(default_factory=list)
    skipped: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def preference_count(self) -> int:
        return len(self.preferences)


# ── signal extraction ────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_trace_trainable(trace: LearningTrace) -> bool:
    return bool(trace.ok and trace.eligibility and trace.eligibility.eligible)


def _external_eval_signal(trace: LearningTrace) -> Tuple[float, str]:
    ev = trace.external_eval_result or {}
    if not ev:
        return 0.0, "no external eval"
    if ev.get("passed") is True:
        score = 2.5 + _safe_float(ev.get("score"), 0.0)
        return score, "external eval passed"
    if ev.get("passed") is False:
        return -3.0, "external eval failed"
    return 0.0, "external eval inconclusive"


def _assembly_signal(trace: LearningTrace) -> Tuple[float, str]:
    wins = len(trace.winner_sections or [])
    failed = len(trace.failed_sections or [])
    value = wins * 0.85 - failed * 1.25
    if wins and not failed:
        return value, f"selected by assembly in {wins} section(s)"
    if wins and failed:
        return value, f"mixed assembly signal: {wins} winner section(s), {failed} failed"
    if failed:
        return value, f"failed/unresolved in {failed} section(s)"
    return 0.0, "no assembly signal"


def _peer_score_signal(trace: LearningTrace) -> Tuple[float, str]:
    scores = trace.peer_scores or {}
    # Accept a few possible summary shapes so this works with future collector
    # versions and external eval harnesses.
    if "average" in scores:
        avg = _safe_float(scores.get("average"), 0.0)
        return (avg - 5.0) / 2.0, f"peer average {avg:.2f}"
    if "overall_score" in scores:
        avg = _safe_float(scores.get("overall_score"), 0.0)
        return (avg - 5.0) / 2.0, f"peer overall {avg:.2f}"
    if "mean" in scores:
        avg = _safe_float(scores.get("mean"), 0.0)
        return (avg - 5.0) / 2.0, f"peer mean {avg:.2f}"
    return 0.0, "no peer-score summary"


def _confidence_signal(trace: LearningTrace) -> Tuple[float, str]:
    if trace.confidence is None:
        return 0.0, "no confidence"
    # Confidence is useful only as a weak tie-breaker. High confidence on its own
    # is not truth, so cap the contribution tightly.
    centered = max(-0.35, min(0.35, (trace.confidence - 0.60)))
    return centered, f"confidence {trace.confidence:.2f}"


def _ratification_signal(trace: LearningTrace) -> Tuple[float, str]:
    final = trace.final_answer or {}
    status = str(final.get("ratification_status", "")).lower()
    ratified = final.get("ratified")
    if ratified is True or status in {"ratified", "ratified_with_caveats"}:
        return 0.6, f"final answer ratification status {status or ratified}"
    if status in {"repair_required", "ratification_failed", "ratification_quorum_failed", "quorum_failed"}:
        return -1.5, f"final answer ratification status {status}"
    return 0.0, "no ratification signal"


def score_trace_for_preference(trace: LearningTrace) -> TracePreferenceScore:
    scored = TracePreferenceScore(
        trace_id=trace.trace_id,
        question=trace.question,
        provider_id=trace.provider_id,
        provider_family=trace.provider_family,
        model=trace.model,
        task_kind=trace.task_kind,
    )

    if trace.ok:
        scored.signal(PreferenceSignal.CLEAN_ELIGIBILITY, 0.35, "valid provider move")
    else:
        scored.signal(PreferenceSignal.CLEAN_ELIGIBILITY, -4.0, f"invalid status {trace.status}")

    if trace.eligibility and trace.eligibility.eligible:
        scored.signal(PreferenceSignal.CLEAN_ELIGIBILITY, 1.0, "training-eligible under constitution")
    else:
        scored.signal(PreferenceSignal.CLEAN_ELIGIBILITY, -1.0, "not training-eligible under constitution")

    for signal, fn in [
        (PreferenceSignal.EXTERNAL_EVAL, _external_eval_signal),
        (PreferenceSignal.ASSEMBLY_WINNER, _assembly_signal),
        (PreferenceSignal.PEER_SCORE_GAP, _peer_score_signal),
        (PreferenceSignal.CONFIDENCE_CALIBRATION, _confidence_signal),
        (PreferenceSignal.RATIFICATION_STATUS, _ratification_signal),
    ]:
        value, reason = fn(trace)
        if value:
            scored.signal(signal, value, reason)
        else:
            scored.reasons.append(reason)
    scored.score = round(scored.score, 6)
    return scored


# ── mining ───────────────────────────────────────────────────────────────────

def _group_by_question(traces: Iterable[LearningTrace]) -> Dict[str, List[LearningTrace]]:
    groups: Dict[str, List[LearningTrace]] = {}
    for trace in traces:
        groups.setdefault(trace.question, []).append(trace)
    return groups


def _rationale(chosen: TracePreferenceScore, rejected: TracePreferenceScore) -> str:
    positive = [r for r in chosen.reasons if not r.startswith("no ")][:4]
    negative = [r for r in rejected.reasons if not r.startswith("no ")][:4]
    parts = [
        f"Chosen score {chosen.score:.2f} vs rejected score {rejected.score:.2f}.",
    ]
    if positive:
        parts.append("Chosen signals: " + "; ".join(positive) + ".")
    if negative:
        parts.append("Rejected signals: " + "; ".join(negative) + ".")
    return " ".join(parts)


def _candidate_ok(
    chosen: LearningTrace,
    rejected: LearningTrace,
    chosen_score: TracePreferenceScore,
    rejected_score: TracePreferenceScore,
    policy: PreferenceMiningPolicy,
) -> Tuple[bool, str]:
    if chosen.trace_id == rejected.trace_id:
        return False, "same trace"
    if chosen.question != rejected.question:
        return False, "different questions"
    if policy.require_chosen_eligible and not _is_trace_trainable(chosen):
        return False, "chosen not training-eligible"
    if policy.require_rejected_valid and not rejected.ok:
        return False, "rejected is not a valid move"
    if not policy.allow_same_provider_pair and chosen.provider_id == rejected.provider_id:
        return False, "same provider pair disabled"
    if render_trace_answer(chosen).strip() == render_trace_answer(rejected).strip():
        return False, "identical rendered answers"
    margin = chosen_score.score - rejected_score.score
    if margin < policy.min_signal_margin:
        return False, f"margin {margin:.3f} below threshold {policy.min_signal_margin:.3f}"
    # If the only gap is confidence, require a larger confidence delta so the miner
    # does not create overconfident preference data.
    c_delta = (chosen.confidence or 0.0) - (rejected.confidence or 0.0)
    non_conf_signals = [
        k for k, v in chosen_score.signals.items()
        if k != PreferenceSignal.CONFIDENCE_CALIBRATION.value and abs(v) > 0
    ]
    if not non_conf_signals and c_delta < policy.min_confidence_delta:
        return False, "confidence-only gap too small"
    return True, "ok"


def mine_preference_candidates(
    dataset: LearningDataset,
    *,
    policy: Optional[PreferenceMiningPolicy] = None,
) -> PreferenceMiningReport:
    """Mine auditable chosen/rejected candidates without mutating the dataset."""
    policy = policy or PreferenceMiningPolicy.conservative()
    report = PreferenceMiningReport(
        policy_mode=policy.mode.value,
        traces_seen=len(dataset.traces),
        trainable_traces=len(dataset.eligible_traces()),
        prompts_seen=len(_group_by_question(dataset.traces)),
    )

    by_id = {t.trace_id: t for t in dataset.traces}
    scores = {t.trace_id: score_trace_for_preference(t) for t in dataset.traces}

    for question, traces in _group_by_question(dataset.traces).items():
        # Preference mining targets provider moves, not peer-score/ratification traces.
        traces = [t for t in traces if t.signal_kind.value == "provider_move"]
        if len(traces) < 2:
            report.skipped.append({"question": question, "reason": "fewer than two provider_move traces"})
            continue

        ranked = sorted(traces, key=lambda t: scores[t.trace_id].score, reverse=True)
        prompt_pairs = 0
        for i, chosen in enumerate(ranked):
            for rejected in reversed(ranked[i + 1:]):
                chosen_score = scores[chosen.trace_id]
                rejected_score = scores[rejected.trace_id]
                ok, reason = _candidate_ok(chosen, rejected, chosen_score, rejected_score, policy)
                if not ok:
                    report.skipped.append({
                        "question": question,
                        "chosen_trace_id": chosen.trace_id,
                        "rejected_trace_id": rejected.trace_id,
                        "reason": reason,
                    })
                    continue
                margin = round(chosen_score.score - rejected_score.score, 6)
                report.candidates.append(MinedPreferenceCandidate(
                    chosen_trace_id=chosen.trace_id,
                    rejected_trace_id=rejected.trace_id,
                    prompt=question,
                    margin=margin,
                    chosen_score=chosen_score.score,
                    rejected_score=rejected_score.score,
                    rationale=_rationale(chosen_score, rejected_score),
                    signals=sanitize_public_payload({
                        "chosen": chosen_score.model_dump(mode="json"),
                        "rejected": rejected_score.model_dump(mode="json"),
                    }),
                ))
                prompt_pairs += 1
                if prompt_pairs >= policy.max_pairs_per_prompt:
                    break
            if prompt_pairs >= policy.max_pairs_per_prompt:
                break

    return report


def mine_preferences(
    dataset: LearningDataset,
    *,
    policy: Optional[PreferenceMiningPolicy] = None,
    attach: bool = False,
) -> PreferenceMiningReport:
    """
    Mine PreferenceExample objects from a LearningDataset.

    If `attach=True`, valid preferences are appended to dataset.preferences. The
    default is non-mutating.
    """
    policy = policy or PreferenceMiningPolicy.conservative()
    report = mine_preference_candidates(dataset, policy=policy)
    by_id = {t.trace_id: t for t in dataset.traces}

    for candidate in report.candidates:
        chosen = by_id[candidate.chosen_trace_id]
        rejected = by_id[candidate.rejected_trace_id]
        try:
            pref = build_preference_example(
                chosen,
                rejected,
                rationale=candidate.rationale,
                constitution=dataset.constitution,
                metadata={
                    "miner": "phase_26e",
                    "policy_mode": policy.mode.value,
                    "margin": candidate.margin,
                    "chosen_score": candidate.chosen_score,
                    "rejected_score": candidate.rejected_score,
                    "signals": candidate.signals,
                },
            )
        except ValueError as exc:
            report.skipped.append({
                "chosen_trace_id": candidate.chosen_trace_id,
                "rejected_trace_id": candidate.rejected_trace_id,
                "reason": f"preference build rejected: {exc}",
            })
            continue
        report.preferences.append(pref)
        if attach:
            dataset.add_preference(pref)
    return report


def smart_learning_summary(report: PreferenceMiningReport) -> Dict[str, Any]:
    margins = [c.margin for c in report.candidates]
    return sanitize_public_payload({
        "policy_mode": report.policy_mode,
        "traces_seen": report.traces_seen,
        "trainable_traces": report.trainable_traces,
        "prompts_seen": report.prompts_seen,
        "candidate_count": len(report.candidates),
        "preference_count": len(report.preferences),
        "skipped_count": len(report.skipped),
        "max_margin": max(margins) if margins else None,
        "min_margin": min(margins) if margins else None,
    })
