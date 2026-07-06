"""
Phase 26F — Process Reward Miner.

This module turns CED's multi-phase traces into process-reward training signals.
Preference mining answers: "which final-looking answer is better?"
Process mining answers: "which reasoning step improved the dialogue?"

It stays parallel to the CED core:
  - no provider calls;
  - no training/fine-tuning;
  - no prompt/routing/scoring/ratification changes;
  - no mutation of SessionState or CEDOrchestrator.

The output is JSONL-ready data for future process reward models, critique/revision
SFT, and DPO/RLHF/RLAIF process preferences.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from .learning_foundation import (
    LearningDataset,
    LearningTrace,
    PreferenceExample,
    build_preference_example,
    render_trace_answer,
    sanitize_public_payload,
)
from .learning_preference_miner import TracePreferenceScore, score_trace_for_preference


class ProcessSignal(str, Enum):
    SOCRATIC_QUESTION = "socratic_question"
    OBJECTION = "objection"
    REFLECTION = "reflection"
    RECONSTRUCTION = "reconstruction"
    SYNTHESIS = "synthesis"
    SCORE_DELTA = "score_delta"
    CALIBRATION_DELTA = "calibration_delta"
    ASSEMBLY_DELTA = "assembly_delta"


class ProcessMiningMode(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class ProcessMiningPolicy(BaseModel):
    mode: ProcessMiningMode = ProcessMiningMode.CONSERVATIVE
    min_process_gain: float = 0.50
    min_score_delta: float = 0.40
    min_confidence_gain: float = 0.05
    max_examples_per_question: int = 6
    require_after_eligible: bool = True
    require_before_valid: bool = True
    include_sft_examples: bool = True
    include_preference_examples: bool = True

    @classmethod
    def conservative(cls) -> "ProcessMiningPolicy":
        return cls()

    @classmethod
    def balanced(cls) -> "ProcessMiningPolicy":
        return cls(
            mode=ProcessMiningMode.BALANCED,
            min_process_gain=0.30,
            min_score_delta=0.25,
            min_confidence_gain=0.03,
            max_examples_per_question=10,
        )

    @classmethod
    def aggressive(cls) -> "ProcessMiningPolicy":
        return cls(
            mode=ProcessMiningMode.AGGRESSIVE,
            min_process_gain=0.15,
            min_score_delta=0.10,
            min_confidence_gain=0.00,
            max_examples_per_question=16,
        )


PHASE_ORDER: Dict[str, int] = {
    "opening": 0,
    "initial_response": 1,
    "elenchus": 2,
    "reflection": 3,
    "reconstruction": 4,
    "synthesis": 5,
    "ratification": 6,
}

PROCESS_TASKS = {
    "socratic_question",
    "initial_response",
    "elenchus_objection",
    "reflection_revision",
    "reconstruction_proposal",
    "synthesis_draft",
}


class ProcessStepScore(BaseModel):
    trace_id: str
    phase: str
    task_kind: Optional[str] = None
    provider_id: str
    score: float = 0.0
    signals: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)

    def signal(self, name: ProcessSignal, value: float, reason: str) -> None:
        self.signals[name.value] = round(float(value), 6)
        self.score += float(value)
        self.reasons.append(reason)


class ProcessTransition(BaseModel):
    transition_id: str
    question: str
    before_trace_id: str
    after_trace_id: str
    before_phase: str
    after_phase: str
    gain: float
    rationale: str
    signals: Dict[str, Any] = Field(default_factory=dict)


class ProcessSFTExample(BaseModel):
    """A supervised example for teaching useful process moves."""

    process_id: str
    prompt: str
    response: str
    phase: str
    task_kind: Optional[str] = None
    rationale: str
    source_trace_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_jsonl_record(self) -> Dict[str, Any]:
        return sanitize_public_payload(self.model_dump(mode="json", exclude_none=True))


class ProcessMiningReport(BaseModel):
    policy_mode: str
    traces_seen: int = 0
    process_traces_seen: int = 0
    prompts_seen: int = 0
    transitions: List[ProcessTransition] = Field(default_factory=list)
    sft_examples: List[ProcessSFTExample] = Field(default_factory=list)
    preferences: List[PreferenceExample] = Field(default_factory=list)
    skipped: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def transition_count(self) -> int:
        return len(self.transitions)

    @property
    def preference_count(self) -> int:
        return len(self.preferences)

    @property
    def sft_count(self) -> int:
        return len(self.sft_examples)

    def process_sft_jsonl(self) -> str:
        lines = [json.dumps(e.to_jsonl_record(), ensure_ascii=False, sort_keys=True)
                 for e in self.sft_examples]
        return "\n".join(lines) + ("\n" if lines else "")


# ── scoring ──────────────────────────────────────────────────────────────────

def _phase_rank(trace: LearningTrace) -> int:
    return PHASE_ORDER.get(str(trace.phase), 99)


def _is_process_trace(trace: LearningTrace) -> bool:
    return trace.signal_kind.value == "provider_move" and (trace.task_kind or "") in PROCESS_TASKS


def _eligible(trace: LearningTrace) -> bool:
    return bool(trace.ok and trace.eligibility and trace.eligibility.eligible)


def _content_has_any(trace: LearningTrace, terms: Iterable[str]) -> bool:
    text = render_trace_answer(trace).lower()
    return any(term.lower() in text for term in terms)


def score_process_step(trace: LearningTrace) -> ProcessStepScore:
    """Score a single trace as a process move, not just an answer."""
    base: TracePreferenceScore = score_trace_for_preference(trace)
    step = ProcessStepScore(
        trace_id=trace.trace_id,
        phase=str(trace.phase),
        task_kind=trace.task_kind,
        provider_id=trace.provider_id,
        score=round(base.score * 0.35, 6),
        signals={"answer_quality_prior": round(base.score * 0.35, 6)},
        reasons=["answer-quality prior from preference scorer"],
    )

    task = trace.task_kind or ""
    if task == "socratic_question":
        if _content_has_any(trace, ["assumption", "clarify", "what would", "question", "premise"]):
            step.signal(ProcessSignal.SOCRATIC_QUESTION, 1.0, "opening question appears to expose assumptions or clarify premises")
        else:
            step.signal(ProcessSignal.SOCRATIC_QUESTION, 0.25, "valid Socratic opening")
    elif task == "elenchus_objection":
        if _content_has_any(trace, ["assumption", "contradiction", "evidence", "falsify", "weakness", "blind spot"]):
            step.signal(ProcessSignal.OBJECTION, 1.2, "objection targets assumptions/evidence/weakness")
        else:
            step.signal(ProcessSignal.OBJECTION, 0.35, "valid objection move")
    elif task == "reflection_revision":
        if _content_has_any(trace, ["revise", "concede", "update", "because", "objection", "uncertain"]):
            step.signal(ProcessSignal.REFLECTION, 1.1, "reflection appears to revise in response to critique")
        else:
            step.signal(ProcessSignal.REFLECTION, 0.30, "valid reflection move")
    elif task == "reconstruction_proposal":
        if _content_has_any(trace, ["therefore", "stronger", "repair", "integrate", "model", "reconstruct"]):
            step.signal(ProcessSignal.RECONSTRUCTION, 1.15, "reconstruction appears to integrate/repair earlier positions")
        else:
            step.signal(ProcessSignal.RECONSTRUCTION, 0.35, "valid reconstruction move")
    elif task == "synthesis_draft":
        if trace.winner_sections:
            step.signal(ProcessSignal.SYNTHESIS, 1.0 + 0.25 * len(trace.winner_sections), "synthesis contributed selected final sections")
        else:
            step.signal(ProcessSignal.SYNTHESIS, 0.25, "valid synthesis draft")

    if trace.confidence is not None:
        if 0.45 <= trace.confidence <= 0.85:
            step.signal(ProcessSignal.CALIBRATION_DELTA, 0.20, "confidence is in calibrated middle band")
        elif trace.confidence > 0.95 and not trace.external_eval_result:
            step.signal(ProcessSignal.CALIBRATION_DELTA, -0.25, "very high confidence without external eval")

    step.score = round(step.score, 6)
    return step


def _group_process_traces(dataset: LearningDataset) -> Dict[str, List[LearningTrace]]:
    groups: Dict[str, List[LearningTrace]] = {}
    for trace in dataset.traces:
        if _is_process_trace(trace):
            groups.setdefault(trace.question, []).append(trace)
    for traces in groups.values():
        traces.sort(key=lambda t: (_phase_rank(t), t.created_at.isoformat(), t.trace_id))
    return groups


def _transition_rationale(before: ProcessStepScore, after: ProcessStepScore) -> str:
    delta = after.score - before.score
    parts = [
        f"Process gain {delta:.2f}: {before.phase}/{before.task_kind} → {after.phase}/{after.task_kind}.",
    ]
    good = [r for r in after.reasons if not r.startswith("no ")][:4]
    if good:
        parts.append("After-step signals: " + "; ".join(good) + ".")
    return " ".join(parts)


def _transition_ok(
    before: LearningTrace,
    after: LearningTrace,
    before_score: ProcessStepScore,
    after_score: ProcessStepScore,
    policy: ProcessMiningPolicy,
) -> Tuple[bool, str]:
    if before.trace_id == after.trace_id:
        return False, "same trace"
    if before.question != after.question:
        return False, "different question"
    if _phase_rank(after) <= _phase_rank(before):
        return False, "not a forward process transition"
    if policy.require_after_eligible and not _eligible(after):
        return False, "after trace not eligible"
    if policy.require_before_valid and not before.ok:
        return False, "before trace is not valid"
    if render_trace_answer(before).strip() == render_trace_answer(after).strip():
        return False, "identical rendered text"
    gain = after_score.score - before_score.score
    if gain < policy.min_process_gain:
        return False, f"gain {gain:.3f} below threshold {policy.min_process_gain:.3f}"
    return True, "ok"


def mine_process_transitions(
    dataset: LearningDataset,
    *,
    policy: Optional[ProcessMiningPolicy] = None,
) -> ProcessMiningReport:
    policy = policy or ProcessMiningPolicy.conservative()
    groups = _group_process_traces(dataset)
    report = ProcessMiningReport(
        policy_mode=policy.mode.value,
        traces_seen=len(dataset.traces),
        process_traces_seen=sum(len(v) for v in groups.values()),
        prompts_seen=len(groups),
    )

    scores = {t.trace_id: score_process_step(t) for traces in groups.values() for t in traces}

    for question, traces in groups.items():
        count = 0
        for i, before in enumerate(traces):
            for after in traces[i + 1:]:
                before_score = scores[before.trace_id]
                after_score = scores[after.trace_id]
                ok, reason = _transition_ok(before, after, before_score, after_score, policy)
                if not ok:
                    report.skipped.append({
                        "question": question,
                        "before_trace_id": before.trace_id,
                        "after_trace_id": after.trace_id,
                        "reason": reason,
                    })
                    continue
                gain = round(after_score.score - before_score.score, 6)
                report.transitions.append(ProcessTransition(
                    transition_id=f"proc_{before.trace_id}_{after.trace_id}",
                    question=question,
                    before_trace_id=before.trace_id,
                    after_trace_id=after.trace_id,
                    before_phase=str(before.phase),
                    after_phase=str(after.phase),
                    gain=gain,
                    rationale=_transition_rationale(before_score, after_score),
                    signals=sanitize_public_payload({
                        "before": before_score.model_dump(mode="json"),
                        "after": after_score.model_dump(mode="json"),
                    }),
                ))
                count += 1
                if count >= policy.max_examples_per_question:
                    break
            if count >= policy.max_examples_per_question:
                break
    return report


def _process_prompt(before: LearningTrace, after: LearningTrace) -> str:
    return (
        f"Question: {before.question}\n"
        f"Earlier phase ({before.phase}/{before.task_kind}) output:\n"
        f"{render_trace_answer(before)}\n\n"
        f"Produce the improved next process move for phase {after.phase}/{after.task_kind}."
    )


def mine_process_examples(
    dataset: LearningDataset,
    *,
    policy: Optional[ProcessMiningPolicy] = None,
    attach_preferences: bool = False,
) -> ProcessMiningReport:
    """Mine both process SFT examples and optional chosen/rejected preferences."""
    policy = policy or ProcessMiningPolicy.conservative()
    report = mine_process_transitions(dataset, policy=policy)
    by_id = {t.trace_id: t for t in dataset.traces}

    for transition in report.transitions:
        before = by_id[transition.before_trace_id]
        after = by_id[transition.after_trace_id]

        if policy.include_sft_examples:
            report.sft_examples.append(ProcessSFTExample(
                process_id=transition.transition_id,
                prompt=_process_prompt(before, after),
                response=render_trace_answer(after),
                phase=str(after.phase),
                task_kind=after.task_kind,
                rationale=transition.rationale,
                source_trace_id=after.trace_id,
                metadata={
                    "miner": "phase_26f",
                    "before_trace_id": before.trace_id,
                    "after_trace_id": after.trace_id,
                    "gain": transition.gain,
                    "signals": transition.signals,
                },
            ))

        if policy.include_preference_examples:
            try:
                pref = build_preference_example(
                    after,
                    before,
                    rationale=transition.rationale,
                    constitution=dataset.constitution,
                    metadata={
                        "miner": "phase_26f_process_reward",
                        "transition_id": transition.transition_id,
                        "process_gain": transition.gain,
                        "before_phase": transition.before_phase,
                        "after_phase": transition.after_phase,
                        "signals": transition.signals,
                    },
                )
            except ValueError as exc:
                report.skipped.append({
                    "transition_id": transition.transition_id,
                    "reason": f"preference build rejected: {exc}",
                })
                continue
            report.preferences.append(pref)
            if attach_preferences:
                dataset.add_preference(pref)

    return report


def process_reward_summary(report: ProcessMiningReport) -> Dict[str, Any]:
    gains = [t.gain for t in report.transitions]
    return sanitize_public_payload({
        "policy_mode": report.policy_mode,
        "traces_seen": report.traces_seen,
        "process_traces_seen": report.process_traces_seen,
        "prompts_seen": report.prompts_seen,
        "transition_count": report.transition_count,
        "sft_count": report.sft_count,
        "preference_count": report.preference_count,
        "skipped_count": len(report.skipped),
        "max_gain": max(gains) if gains else None,
        "min_gain": min(gains) if gains else None,
    })
