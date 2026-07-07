"""
Phase 26M — Deterministic Live Learner Ledger.

CED is the orchestrator. The Live Learner is the student.

This module observes sanitized dialogue/pipeline outputs and updates a deterministic
learner ledger after each session. It does not train models, call providers, write
files, mutate CED state, or change CED core behavior.

The learner is "live" because it can be invoked after every completed session, and
"deterministic" because the same prior ledger + same observation always produces
the same next ledger.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import sanitize_public_payload
from .learning_health_audit import HealthStatus, LearningHealthAudit, learning_health_summary
from .learning_pipeline import LearningPipelineResult, learning_pipeline_summary


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_learner_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


class LearnerSignal(str, Enum):
    STRENGTH = "strength"
    WEAKNESS = "weakness"
    NEXT_FOCUS = "next_focus"
    SAFETY = "safety"
    DATA_NEED = "data_need"


class LearnerLesson(BaseModel):
    lesson_id: str
    signal: LearnerSignal
    topic: str
    statement: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    support_count: int = 1
    last_seen_session_id: Optional[str] = None


class LearnerObservation(BaseModel):
    observation_id: str
    session_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    pipeline_summary: Dict[str, Any] = Field(default_factory=dict)
    health_summary: Dict[str, Any] = Field(default_factory=dict)
    derived_lessons: List[LearnerLesson] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LearnerState(BaseModel):
    learner_version: str = "phase_26m"
    learner_id: str = "deterministic_live_learner"
    observations_seen: int = 0
    sessions_seen: List[str] = Field(default_factory=list)
    lessons: Dict[str, LearnerLesson] = Field(default_factory=dict)
    strengths: Dict[str, int] = Field(default_factory=dict)
    weaknesses: Dict[str, int] = Field(default_factory=dict)
    next_focus: List[str] = Field(default_factory=list)
    safety_flags: List[str] = Field(default_factory=list)
    last_observation_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


# ── lesson derivation ────────────────────────────────────────────────────────

def _lesson(signal: LearnerSignal, topic: str, statement: str, *, session_id: str,
            evidence: Optional[Dict[str, Any]] = None) -> LearnerLesson:
    payload = {"signal": signal.value, "topic": topic, "statement": statement}
    return LearnerLesson(
        lesson_id=stable_learner_hash(payload, prefix="lesson_"),
        signal=signal,
        topic=topic,
        statement=statement,
        evidence=sanitize_public_payload(evidence or {}),
        last_seen_session_id=session_id,
    )


def derive_lessons_from_pipeline(
    pipeline: LearningPipelineResult,
    audit: LearningHealthAudit,
) -> List[LearnerLesson]:
    """Derive deterministic lessons from pipeline + health summaries."""
    session_id = pipeline.dataset.session_id if hasattr(pipeline.dataset, "session_id") else None
    # LearningDataset may not have session_id as a top-level field; fall back to traces.
    if not session_id and pipeline.dataset.traces:
        session_id = pipeline.dataset.traces[0].session_id
    session_id = session_id or "unknown_session"

    lessons: List[LearnerLesson] = []
    pipe_summary = learning_pipeline_summary(pipeline)
    health = learning_health_summary(audit)

    learning = pipe_summary.get("learning", {})
    trace_count = int(learning.get("trace_count", 0) or 0)
    eligible_count = int(learning.get("eligible_trace_count", 0) or 0)
    if trace_count > 0:
        lessons.append(_lesson(
            LearnerSignal.STRENGTH,
            "collector",
            "The learner observed a completed dialogue trace stream.",
            session_id=session_id,
            evidence={"trace_count": trace_count, "eligible_trace_count": eligible_count},
        ))
    if trace_count > 0 and eligible_count == 0:
        lessons.append(_lesson(
            LearnerSignal.WEAKNESS,
            "collector",
            "Traces were collected but none were eligible for training data.",
            session_id=session_id,
            evidence={"trace_count": trace_count, "eligible_trace_count": eligible_count},
        ))
        lessons.append(_lesson(
            LearnerSignal.NEXT_FOCUS,
            "collector",
            "Improve provider move validity, confidence calibration, or eligibility thresholds.",
            session_id=session_id,
        ))

    preferences = pipe_summary.get("preferences", {})
    pref_count = int(preferences.get("preference_count", 0) or 0)
    if pref_count > 0:
        lessons.append(_lesson(
            LearnerSignal.STRENGTH,
            "preference_miner",
            "Answer-level preference pairs were mined from the dialogue.",
            session_id=session_id,
            evidence={"preference_count": pref_count},
        ))
    else:
        lessons.append(_lesson(
            LearnerSignal.DATA_NEED,
            "preference_miner",
            "Need more competing valid provider moves to mine answer-level preferences.",
            session_id=session_id,
            evidence={"preference_count": pref_count},
        ))

    process = pipe_summary.get("process", {})
    process_examples = int(process.get("sft_count", 0) or 0) + int(process.get("preference_count", 0) or 0)
    if process_examples > 0:
        lessons.append(_lesson(
            LearnerSignal.STRENGTH,
            "process_miner",
            "Process-level learning examples were mined from phase progression.",
            session_id=session_id,
            evidence={"process_examples": process_examples},
        ))
    else:
        lessons.append(_lesson(
            LearnerSignal.DATA_NEED,
            "process_miner",
            "Need clearer forward dialogue progression to mine process-learning examples.",
            session_id=session_id,
            evidence={"process_examples": process_examples},
        ))

    quality = pipe_summary.get("quality", {})
    quality_verdict = quality.get("verdict")
    if quality_verdict == "pass":
        lessons.append(_lesson(
            LearnerSignal.STRENGTH,
            "quality_gates",
            "Exported learning artifacts passed quality gates.",
            session_id=session_id,
            evidence=quality,
        ))
    elif quality_verdict:
        lessons.append(_lesson(
            LearnerSignal.WEAKNESS,
            "quality_gates",
            f"Quality gates returned {quality_verdict}; training should remain blocked or inspect-only.",
            session_id=session_id,
            evidence=quality,
        ))

    plan = pipe_summary.get("plan", {})
    ready_jobs = plan.get("ready_jobs", []) or []
    inspect_jobs = plan.get("inspect_only_jobs", []) or []
    blocked_jobs = plan.get("blocked_jobs", []) or []
    if ready_jobs or inspect_jobs:
        lessons.append(_lesson(
            LearnerSignal.STRENGTH,
            "dry_run_planner",
            "At least one learning family is ready or inspect-only in the dry-run plan.",
            session_id=session_id,
            evidence={"ready_jobs": ready_jobs, "inspect_only_jobs": inspect_jobs},
        ))
    if blocked_jobs:
        lessons.append(_lesson(
            LearnerSignal.NEXT_FOCUS,
            "dry_run_planner",
            "Resolve blocked learning families before enabling any trainer adapter.",
            session_id=session_id,
            evidence={"blocked_jobs": blocked_jobs},
        ))

    if pipe_summary.get("no_training_executed") is True and health.get("overall_status") in {"pass", "warn", "fail"}:
        lessons.append(_lesson(
            LearnerSignal.SAFETY,
            "safety_invariants",
            "The learner observed without training, provider calls, or CED mutation.",
            session_id=session_id,
            evidence={"no_training_executed": True, "health_status": health.get("overall_status")},
        ))
    else:
        lessons.append(_lesson(
            LearnerSignal.WEAKNESS,
            "safety_invariants",
            "The observation did not clearly confirm dry-run-only behavior.",
            session_id=session_id,
            evidence={"no_training_executed": pipe_summary.get("no_training_executed")},
        ))

    # Deterministic order for stable observations.
    return sorted(lessons, key=lambda lesson: (lesson.signal.value, lesson.topic, lesson.statement))


# ── observation / state update ───────────────────────────────────────────────

def observe_learning_pipeline(
    pipeline: LearningPipelineResult,
    audit: LearningHealthAudit,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearnerObservation:
    pipe_summary = learning_pipeline_summary(pipeline)
    health_summary = learning_health_summary(audit)
    session_id = "unknown_session"
    if pipeline.dataset.traces:
        session_id = pipeline.dataset.traces[0].session_id
    lessons = derive_lessons_from_pipeline(pipeline, audit)
    observation_payload = {
        "session_id": session_id,
        "pipeline_summary": pipe_summary,
        "health_summary": health_summary,
        "lessons": [lesson.lesson_id for lesson in lessons],
        "metadata": sanitize_public_payload(metadata or {}),
    }
    return LearnerObservation(
        observation_id=stable_learner_hash(observation_payload, prefix="obs_"),
        session_id=session_id,
        pipeline_summary=pipe_summary,
        health_summary=health_summary,
        derived_lessons=lessons,
        metadata=sanitize_public_payload(metadata or {}),
    )


def update_learner_state(
    state: Optional[LearnerState],
    observation: LearnerObservation,
) -> LearnerState:
    """Apply an observation to learner state deterministically."""
    next_state = state.model_copy(deep=True) if state else LearnerState()
    if observation.observation_id == next_state.last_observation_id:
        return next_state

    if observation.session_id not in next_state.sessions_seen:
        next_state.sessions_seen.append(observation.session_id)
        next_state.sessions_seen.sort()
    next_state.observations_seen += 1
    next_state.last_observation_id = observation.observation_id

    for lesson in observation.derived_lessons:
        existing = next_state.lessons.get(lesson.lesson_id)
        if existing:
            existing.support_count += 1
            existing.last_seen_session_id = observation.session_id
            existing.evidence = sanitize_public_payload({**existing.evidence, **lesson.evidence})
        else:
            next_state.lessons[lesson.lesson_id] = lesson.model_copy(deep=True)

        bucket: Optional[Dict[str, int]] = None
        if lesson.signal == LearnerSignal.STRENGTH:
            bucket = next_state.strengths
        elif lesson.signal in {LearnerSignal.WEAKNESS, LearnerSignal.DATA_NEED}:
            bucket = next_state.weaknesses
        if bucket is not None:
            bucket[lesson.topic] = bucket.get(lesson.topic, 0) + 1

        if lesson.signal == LearnerSignal.NEXT_FOCUS and lesson.statement not in next_state.next_focus:
            next_state.next_focus.append(lesson.statement)
        if lesson.signal == LearnerSignal.SAFETY and lesson.statement not in next_state.safety_flags:
            next_state.safety_flags.append(lesson.statement)

    next_state.next_focus = sorted(next_state.next_focus)
    next_state.safety_flags = sorted(next_state.safety_flags)
    next_state.strengths = dict(sorted(next_state.strengths.items()))
    next_state.weaknesses = dict(sorted(next_state.weaknesses.items()))
    next_state.lessons = dict(sorted(next_state.lessons.items()))
    return next_state


def deterministic_live_learn(
    pipeline: LearningPipelineResult,
    audit: LearningHealthAudit,
    *,
    state: Optional[LearnerState] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearnerState:
    observation = observe_learning_pipeline(pipeline, audit, metadata=metadata)
    return update_learner_state(state, observation)


def learner_state_summary(state: LearnerState) -> Dict[str, Any]:
    return sanitize_public_payload({
        "learner_version": state.learner_version,
        "learner_id": state.learner_id,
        "observations_seen": state.observations_seen,
        "sessions_seen": state.sessions_seen,
        "lesson_count": len(state.lessons),
        "strengths": state.strengths,
        "weaknesses": state.weaknesses,
        "next_focus": state.next_focus,
        "safety_flags": state.safety_flags,
        "last_observation_id": state.last_observation_id,
    })
