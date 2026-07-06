"""
Phase 26C — CED Learning Foundation.

This module builds the data foundation needed before adding RLHF / DPO / RLAIF /
reward-model / distillation / NeMo alignment loops. It deliberately does NOT
train, fine-tune, call providers, mutate CED scoring, or let failed outputs become
training data.

Core idea:
  - trace everything useful for audit and future analysis;
  - export only sanitized, eligible records for learning;
  - create preference/eval examples only when the evidence is valid;
  - preserve CED's invariant: evidence beats agreement, and failures never
    fabricate knowledge.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field, model_validator

from .models import AgentTask, ProviderResponse, ProviderStatus, TaskKind


# ── generic helpers ──────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str) -> str:
    # Stable enough for local/offline dataset generation; not a security token.
    return f"{prefix}{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"


_SECRET_PATTERN = re.compile(r"(sk|nvapi|xai|ghp|github_pat)-[A-Za-z0-9_\-]{6,}")

DEFAULT_BLOCKED_KEYS = frozenset({
    "api_key", "authorization", "bearer", "token", "secret", "password",
    "provider_key", "raw_prompt", "system_prompt", "hidden_prompt",
    "hidden_audit", "audit_log", "task_log", "scoreboard", "leaderboard",
    "private_context", "provider_mapping", "provider_map", "full_trace",
})


def redact_secrets(value: str) -> str:
    return _SECRET_PATTERN.sub("***REDACTED***", value)


def sanitize_public_payload(value: Any, *, blocked_keys: Iterable[str] = DEFAULT_BLOCKED_KEYS) -> Any:
    """
    Recursively remove keys that should not enter training/eval exports and redact
    obvious key-like strings. This is intentionally conservative: if a field name
    looks hidden/private/secret, it is dropped from the public learning payload.
    """
    blocked = {str(k).lower() for k in blocked_keys}
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            low = key.lower()
            if low in blocked or "secret" in low or "api_key" in low or "hidden" in low:
                continue
            out[key] = sanitize_public_payload(v, blocked_keys=blocked)
        return out
    if isinstance(value, list):
        return [sanitize_public_payload(v, blocked_keys=blocked) for v in value]
    if isinstance(value, tuple):
        return [sanitize_public_payload(v, blocked_keys=blocked) for v in value]
    if isinstance(value, str):
        return redact_secrets(value)
    return value


def jsonl(records: Iterable[BaseModel | Dict[str, Any]]) -> str:
    """Serialize Pydantic/dict records as JSONL with Pydantic v2 JSON mode."""
    lines: List[str] = []
    for record in records:
        if isinstance(record, BaseModel):
            payload = record.model_dump(mode="json", exclude_none=True)
        else:
            payload = sanitize_public_payload(record)
        lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines) + ("\n" if lines else "")


# ── constitution / policy ────────────────────────────────────────────────────

class LearningUse(str, Enum):
    TRACE_ONLY = "trace_only"
    SUPERVISED_DISTILLATION = "supervised_distillation"
    PREFERENCE_TRAINING = "preference_training"
    REWARD_MODEL = "reward_model"
    EVAL_BENCHMARK = "eval_benchmark"


class LearningSignalKind(str, Enum):
    PROVIDER_MOVE = "provider_move"
    PEER_SCORE = "peer_score"
    RATIFICATION = "ratification"
    HUMAN_FEEDBACK = "human_feedback"
    EXTERNAL_EVAL = "external_eval"
    CONSTITUTIONAL_REVIEW = "constitutional_review"


class SocratesPrinciple(BaseModel):
    principle_id: str
    title: str
    rule: str
    rationale: str = ""
    failure_modes: List[str] = Field(default_factory=list)


class SocratesConstitution(BaseModel):
    """
    The learning constitution is not a prompt trick. It is a data-governance policy:
    which outputs are allowed into training data, which are trace-only, and which
    CED principles every future learning loop must preserve.
    """

    version: str = "ced_learning_constitution_v1"
    principles: List[SocratesPrinciple] = Field(default_factory=list)
    min_confidence_for_training: float = Field(default=0.60, ge=0.0, le=1.0)
    allow_failed_provider_outputs: bool = False
    allow_unratified_final_answers: bool = False
    trainable_task_kinds: List[str] = Field(default_factory=lambda: [
        TaskKind.SOCRATIC_QUESTION.value,
        TaskKind.INITIAL_RESPONSE.value,
        TaskKind.ELENCHUS_OBJECTION.value,
        TaskKind.REFLECTION_REVISION.value,
        TaskKind.RECONSTRUCTION_PROPOSAL.value,
        TaskKind.SYNTHESIS_DRAFT.value,
        TaskKind.RATIFICATION_REVISION.value,
    ])
    trace_only_task_kinds: List[str] = Field(default_factory=lambda: [
        TaskKind.MOVE_SCORE.value,
        TaskKind.SECTION_SCORE.value,
        TaskKind.COUNCIL_RATIFICATION.value,
        TaskKind.LESSON_RELEVANCE.value,
        TaskKind.LESSON_CONSOLIDATION.value,
        TaskKind.PROCESS_REVIEW.value,
    ])

    @classmethod
    def default(cls) -> "SocratesConstitution":
        return cls(principles=[
            SocratesPrinciple(
                principle_id="evidence_over_agreement",
                title="Evidence beats consensus",
                rule="Never treat model agreement as proof; prefer external evidence and explicit reasoning.",
                rationale="CED exists to prevent agreement from becoming authority.",
                failure_modes=["herding", "sycophancy", "consensus laundering"],
            ),
            SocratesPrinciple(
                principle_id="no_overclaiming",
                title="No overclaiming",
                rule="Do not present hypotheses, guesses, or weakly-supported claims as established facts.",
                rationale="Training data must preserve calibrated epistemic status.",
                failure_modes=["hallucination", "false certainty", "unsupported universal claims"],
            ),
            SocratesPrinciple(
                principle_id="failed_outputs_are_not_training_targets",
                title="Failed outputs are trace-only",
                rule="Invalid JSON, schema errors, missing keys, timeouts, refusals, and failed providers may be logged but never used as chosen training targets.",
                rationale="A learning loop must not reward broken provider behavior.",
                failure_modes=["self-reinforcing errors", "format drift", "reward hacking"],
            ),
            SocratesPrinciple(
                principle_id="hidden_audit_is_not_training_prompt",
                title="Protect hidden audit state",
                rule="Provider mappings, hidden scores, keys, raw system prompts, and task logs must not enter public learning examples.",
                rationale="The learning dataset should improve reasoning, not leak orchestration internals.",
                failure_modes=["prompt leakage", "provider leakage", "score gaming"],
            ),
            SocratesPrinciple(
                principle_id="process_matters",
                title="Reward the reasoning process",
                rule="Prefer examples where critique, reconstruction, and synthesis corrected an identifiable weakness.",
                rationale="CED is process-based; future reward models should learn good epistemic moves, not only final prose.",
                failure_modes=["answer-only optimization", "shallow polish", "lost objections"],
            ),
        ])

    def principle_block(self) -> str:
        lines = [f"Socrates Learning Constitution ({self.version})"]
        for p in self.principles:
            lines.append(f"- {p.principle_id}: {p.rule}")
        return "\n".join(lines)


class TrainingEligibility(BaseModel):
    eligible: bool
    uses: List[LearningUse] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)

    @classmethod
    def reject(cls, *reasons: str) -> "TrainingEligibility":
        return cls(eligible=False, uses=[LearningUse.TRACE_ONLY], reasons=list(reasons))

    @classmethod
    def accept(cls, *uses: LearningUse, reasons: Optional[List[str]] = None) -> "TrainingEligibility":
        return cls(eligible=True, uses=list(uses), reasons=reasons or ["valid CED move"])


# ── trace records ────────────────────────────────────────────────────────────

class LearningTrace(BaseModel):
    """
    Sanitized, provider-agnostic record for future learning systems.

    This is intentionally narrower than the full CED audit. It can reference audit
    ids, but it must not carry raw hidden scoreboards, provider keys, or prompts.
    """

    trace_id: str = Field(default_factory=lambda: _uid("trace_"))
    created_at: datetime = Field(default_factory=_utcnow)
    signal_kind: LearningSignalKind = LearningSignalKind.PROVIDER_MOVE

    session_id: str
    task_id: str
    question: str
    provider_id: str
    provider_family: str = "unknown"
    model: str = "unknown"
    agent_id: Optional[str] = None
    role: str
    phase: str
    task_kind: Optional[str] = None
    status: str

    content: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    epistemic_markers: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None

    peer_scores: Dict[str, Any] = Field(default_factory=dict)
    ratification_vote: Optional[Dict[str, Any]] = None
    final_answer: Optional[Dict[str, Any]] = None
    winner_sections: List[str] = Field(default_factory=list)
    failed_sections: List[str] = Field(default_factory=list)
    human_feedback: Optional[Dict[str, Any]] = None
    external_eval_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    eligibility: Optional[TrainingEligibility] = None

    @classmethod
    def from_provider_response(
        cls,
        task: AgentTask,
        response: ProviderResponse,
        *,
        provider_family: str = "unknown",
        model: str = "unknown",
        include_raw_text: bool = False,
        peer_scores: Optional[Dict[str, Any]] = None,
        ratification_vote: Optional[Dict[str, Any]] = None,
        final_answer: Optional[Dict[str, Any]] = None,
        winner_sections: Optional[Sequence[str]] = None,
        failed_sections: Optional[Sequence[str]] = None,
        human_feedback: Optional[Dict[str, Any]] = None,
        external_eval_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        constitution: Optional[SocratesConstitution] = None,
    ) -> "LearningTrace":
        move = response.parsed_move
        content: Dict[str, Any] = {}
        confidence: Optional[float] = None
        markers: List[str] = []
        if move is not None:
            content = sanitize_public_payload(move.content)
            confidence = move.confidence
            markers = [m.value if hasattr(m, "value") else str(m) for m in move.epistemic_markers]

        trace = cls(
            session_id=task.session_id,
            task_id=task.task_id,
            question=redact_secrets(task.question),
            provider_id=response.provider_id,
            provider_family=provider_family,
            model=model,
            agent_id=response.agent_id or task.agent_id,
            role=task.role.value if hasattr(task.role, "value") else str(task.role),
            phase=task.phase.value if hasattr(task.phase, "value") else str(task.phase),
            task_kind=task.task_kind.value if task.task_kind else None,
            status=response.status.value if hasattr(response.status, "value") else str(response.status),
            content=content,
            confidence=confidence,
            epistemic_markers=markers,
            raw_text=redact_secrets(response.raw_text or "") if include_raw_text and response.raw_text else None,
            peer_scores=sanitize_public_payload(peer_scores or {}),
            ratification_vote=sanitize_public_payload(ratification_vote) if ratification_vote else None,
            final_answer=sanitize_public_payload(final_answer) if final_answer else None,
            winner_sections=list(winner_sections or []),
            failed_sections=list(failed_sections or []),
            human_feedback=sanitize_public_payload(human_feedback) if human_feedback else None,
            external_eval_result=sanitize_public_payload(external_eval_result) if external_eval_result else None,
            metadata=sanitize_public_payload(metadata or {}),
        )
        trace.eligibility = assess_training_eligibility(trace, constitution or SocratesConstitution.default())
        return trace

    @property
    def ok(self) -> bool:
        return self.status == ProviderStatus.OK.value and bool(self.content)

    def public_payload(self) -> Dict[str, Any]:
        payload = self.model_dump(mode="json", exclude_none=True)
        # Keep raw text out of public exports unless a caller explicitly chooses a
        # separate private/audit export path later.
        payload.pop("raw_text", None)
        return sanitize_public_payload(payload)

    def to_jsonl_record(self) -> Dict[str, Any]:
        return self.public_payload()


# ── eligibility / preference / eval data ─────────────────────────────────────

def assess_training_eligibility(
    trace: LearningTrace, constitution: Optional[SocratesConstitution] = None,
) -> TrainingEligibility:
    policy = constitution or SocratesConstitution.default()
    reasons: List[str] = []

    if trace.status != ProviderStatus.OK.value:
        return TrainingEligibility.reject(f"provider status is {trace.status}")
    if not trace.content:
        return TrainingEligibility.reject("empty validated content")
    if trace.task_kind in policy.trace_only_task_kinds:
        return TrainingEligibility.reject(f"task_kind {trace.task_kind} is trace-only")
    if trace.task_kind and trace.task_kind not in policy.trainable_task_kinds:
        return TrainingEligibility.reject(f"task_kind {trace.task_kind} is not explicitly trainable")
    if trace.confidence is not None and trace.confidence < policy.min_confidence_for_training:
        return TrainingEligibility.reject(
            f"confidence {trace.confidence:.3f} below minimum {policy.min_confidence_for_training:.3f}"
        )
    if trace.external_eval_result and trace.external_eval_result.get("passed") is False:
        return TrainingEligibility.reject("external eval failed")
    if trace.failed_sections:
        reasons.append("has failed sections; eligible only if downstream policy filters sections")
    if trace.ratification_vote and trace.ratification_vote.get("verdict") in {"blocking_objection", "reject"}:
        return TrainingEligibility.reject("ratification rejected/blocking objection")

    return TrainingEligibility.accept(
        LearningUse.SUPERVISED_DISTILLATION,
        reasons=reasons or ["valid provider move under constitution"],
    )


def render_trace_answer(trace: LearningTrace) -> str:
    if "text" in trace.content and isinstance(trace.content["text"], str):
        return trace.content["text"]
    return json.dumps(sanitize_public_payload(trace.content), ensure_ascii=False, sort_keys=True)


class PreferenceExample(BaseModel):
    """DPO/RLHF/RLAIF-ready chosen-vs-rejected example."""

    preference_id: str = Field(default_factory=lambda: _uid("pref_"))
    created_at: datetime = Field(default_factory=_utcnow)
    prompt: str
    chosen: str
    rejected: str
    rationale: str
    chosen_trace_id: str
    rejected_trace_id: str
    source: str = "ced_learning_foundation"
    uses: List[LearningUse] = Field(default_factory=lambda: [LearningUse.PREFERENCE_TRAINING, LearningUse.REWARD_MODEL])
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _non_empty_pair(self):
        if not self.prompt.strip():
            raise ValueError("preference prompt is empty")
        if not self.chosen.strip() or not self.rejected.strip():
            raise ValueError("preference choices must be non-empty")
        if self.chosen.strip() == self.rejected.strip():
            raise ValueError("chosen and rejected text must differ")
        if not self.rationale.strip():
            raise ValueError("preference rationale is required")
        return self

    def to_dpo_record(self) -> Dict[str, Any]:
        return sanitize_public_payload({
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "metadata": {
                "preference_id": self.preference_id,
                "chosen_trace_id": self.chosen_trace_id,
                "rejected_trace_id": self.rejected_trace_id,
                "rationale": self.rationale,
                **self.metadata,
            },
        })


def build_preference_example(
    chosen: LearningTrace,
    rejected: LearningTrace,
    *,
    rationale: str,
    constitution: Optional[SocratesConstitution] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> PreferenceExample:
    policy = constitution or SocratesConstitution.default()
    chosen_elig = chosen.eligibility or assess_training_eligibility(chosen, policy)
    rejected_elig = rejected.eligibility or assess_training_eligibility(rejected, policy)

    if not chosen_elig.eligible:
        raise ValueError(f"chosen trace is not training-eligible: {chosen_elig.reasons}")
    if not rejected.ok:
        raise ValueError("rejected trace must be a valid move; provider failures are trace-only, not DPO negatives")
    if chosen.question != rejected.question:
        raise ValueError("preference pair requires the same source question")
    if not rationale.strip():
        raise ValueError("preference pair requires a rationale")

    return PreferenceExample(
        prompt=chosen.question,
        chosen=render_trace_answer(chosen),
        rejected=render_trace_answer(rejected),
        rationale=rationale,
        chosen_trace_id=chosen.trace_id,
        rejected_trace_id=rejected.trace_id,
        metadata=sanitize_public_payload({
            "constitution_version": policy.version,
            "chosen_provider": chosen.provider_id,
            "rejected_provider": rejected.provider_id,
            "chosen_confidence": chosen.confidence,
            "rejected_confidence": rejected.confidence,
            "rejected_eligibility": rejected_elig.model_dump(mode="json"),
            **(metadata or {}),
        }),
    )


class EvalVerifierType(str, Enum):
    EXACT = "exact"
    NUMERIC = "numeric"
    SET_MATCH = "set_match"
    RUBRIC = "rubric"
    HUMAN = "human"
    EXTERNAL_PROGRAM = "external_program"


class EvalExample(BaseModel):
    """External-eval-ready benchmark item generated from a CED trace or authoring flow."""

    eval_id: str = Field(default_factory=lambda: _uid("eval_"))
    created_at: datetime = Field(default_factory=_utcnow)
    question: str
    verifier_type: EvalVerifierType
    expected_answer: Optional[Any] = None
    accepted_answers: List[Any] = Field(default_factory=list)
    rubric: Optional[Dict[str, Any]] = None
    source_trace_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _has_verification_signal(self):
        if self.verifier_type in {EvalVerifierType.EXACT, EvalVerifierType.NUMERIC, EvalVerifierType.SET_MATCH}:
            if self.expected_answer is None and not self.accepted_answers:
                raise ValueError("verifiable evals need expected_answer or accepted_answers")
        if self.verifier_type == EvalVerifierType.RUBRIC and not self.rubric:
            raise ValueError("rubric evals need a rubric")
        return self

    def to_jsonl_record(self) -> Dict[str, Any]:
        return sanitize_public_payload(self.model_dump(mode="json", exclude_none=True))


class LearningDataset(BaseModel):
    """Small in-memory dataset bundle with safe JSONL exporters."""

    constitution: SocratesConstitution = Field(default_factory=SocratesConstitution.default)
    traces: List[LearningTrace] = Field(default_factory=list)
    preferences: List[PreferenceExample] = Field(default_factory=list)
    evals: List[EvalExample] = Field(default_factory=list)

    def eligible_traces(self) -> List[LearningTrace]:
        out: List[LearningTrace] = []
        for t in self.traces:
            elig = t.eligibility or assess_training_eligibility(t, self.constitution)
            if elig.eligible:
                out.append(t)
        return out

    def trace_jsonl(self, *, eligible_only: bool = False) -> str:
        records = self.eligible_traces() if eligible_only else self.traces
        return jsonl([r.to_jsonl_record() for r in records])

    def dpo_jsonl(self) -> str:
        return jsonl([p.to_dpo_record() for p in self.preferences])

    def eval_jsonl(self) -> str:
        return jsonl([e.to_jsonl_record() for e in self.evals])

    def add_trace(self, trace: LearningTrace) -> LearningTrace:
        if trace.eligibility is None:
            trace.eligibility = assess_training_eligibility(trace, self.constitution)
        self.traces.append(trace)
        return trace

    def add_preference(self, preference: PreferenceExample) -> PreferenceExample:
        self.preferences.append(preference)
        return preference

    def add_eval(self, eval_example: EvalExample) -> EvalExample:
        self.evals.append(eval_example)
        return eval_example
