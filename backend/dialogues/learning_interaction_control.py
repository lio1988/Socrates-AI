"""
Phase 26N — Learner / Trainer / CED Interaction Control Plane.

CED is the orchestrator. The learner is the student. The trainer is a future
capability that remains behind quality gates and dry-run planning.

This module defines a deterministic communication protocol between the three
without letting any side mutate the others implicitly.

Key invariant:
  - CED may receive only safe advisories, never automatic prompt/core/weight edits.
  - Learner may observe and remember, never train models directly.
  - Trainer may report readiness or blocked capability, never execute training here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import sanitize_public_payload
from .learning_health_audit import LearningHealthAudit, learning_health_summary
from .learning_live_learner import (
    LearnerState,
    LearnerObservation,
    deterministic_live_learn,
    learner_state_summary,
    observe_learning_pipeline,
)
from .learning_pipeline import LearningPipelineResult, learning_pipeline_summary
from .learning_training_planner import TrainingReadiness


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def interaction_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


class ControlActor(str, Enum):
    CED = "ced"
    LEARNER = "learner"
    TRAINER = "trainer"
    HUMAN = "human"


class ControlMessageKind(str, Enum):
    OBSERVATION = "observation"
    LESSON_UPDATE = "lesson_update"
    TRAINER_READINESS = "trainer_readiness"
    CED_ADVISORY = "ced_advisory"
    SAFETY_BLOCK = "safety_block"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


class AdvisoryScope(str, Enum):
    DATA_COLLECTION = "data_collection"
    EVAL_SELECTION = "eval_selection"
    SESSION_FOCUS = "session_focus"
    MINER_REVIEW = "miner_review"
    QUALITY_REPAIR = "quality_repair"
    TRAINER_DRY_RUN = "trainer_dry_run"


class AdvisoryStatus(str, Enum):
    SAFE_TO_SHOW_CED = "safe_to_show_ced"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    BLOCKED = "blocked"


class ControlMessage(BaseModel):
    message_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    sender: ControlActor
    recipient: ControlActor
    kind: ControlMessageKind
    payload: Dict[str, Any] = Field(default_factory=dict)
    requires_human_approval: bool = False


class CEDAdvisory(BaseModel):
    advisory_id: str
    scope: AdvisoryScope
    status: AdvisoryStatus
    title: str
    rationale: str
    suggested_action: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: List[str] = Field(default_factory=lambda: [
        "do_not_modify_ced_core",
        "do_not_modify_prompts_automatically",
        "do_not_modify_model_weights",
        "do_not_bypass_quality_gates",
    ])


class TrainerCapabilityReport(BaseModel):
    ready_families: List[str] = Field(default_factory=list)
    inspect_only_families: List[str] = Field(default_factory=list)
    blocked_families: List[str] = Field(default_factory=list)
    global_readiness: str = "blocked"
    no_training_executed: bool = True


class InteractionControlPolicy(BaseModel):
    allow_ced_data_collection_advisories: bool = True
    allow_ced_eval_selection_advisories: bool = True
    allow_ced_session_focus_advisories: bool = True
    allow_trainer_dry_run_advisories: bool = True
    require_human_for_prompt_changes: bool = True
    require_human_for_core_changes: bool = True
    require_human_for_real_training: bool = True

    @classmethod
    def safe_default(cls) -> "InteractionControlPolicy":
        return cls()


class InteractionCycle(BaseModel):
    cycle_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    pipeline_summary: Dict[str, Any] = Field(default_factory=dict)
    health_summary: Dict[str, Any] = Field(default_factory=dict)
    learner_observation: LearnerObservation
    learner_state: LearnerState
    trainer_report: TrainerCapabilityReport
    ced_advisories: List[CEDAdvisory] = Field(default_factory=list)
    messages: List[ControlMessage] = Field(default_factory=list)
    blocked_actions: List[str] = Field(default_factory=list)
    no_training_executed: bool = True

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


# ── message/advisory construction ────────────────────────────────────────────

def _message(sender: ControlActor, recipient: ControlActor, kind: ControlMessageKind,
             payload: Dict[str, Any], *, requires_human_approval: bool = False) -> ControlMessage:
    clean = sanitize_public_payload(payload)
    return ControlMessage(
        message_id=interaction_hash({
            "sender": sender.value,
            "recipient": recipient.value,
            "kind": kind.value,
            "payload": clean,
            "requires_human_approval": requires_human_approval,
        }, prefix="msg_"),
        sender=sender,
        recipient=recipient,
        kind=kind,
        payload=clean,
        requires_human_approval=requires_human_approval,
    )


def _advisory(scope: AdvisoryScope, status: AdvisoryStatus, title: str, rationale: str,
              suggested_action: str, evidence: Optional[Dict[str, Any]] = None) -> CEDAdvisory:
    clean = sanitize_public_payload(evidence or {})
    return CEDAdvisory(
        advisory_id=interaction_hash({
            "scope": scope.value,
            "status": status.value,
            "title": title,
            "rationale": rationale,
            "suggested_action": suggested_action,
            "evidence": clean,
        }, prefix="adv_"),
        scope=scope,
        status=status,
        title=title,
        rationale=rationale,
        suggested_action=suggested_action,
        evidence=clean,
    )


def build_trainer_capability_report(pipeline: LearningPipelineResult) -> TrainerCapabilityReport:
    ready: List[str] = []
    inspect: List[str] = []
    blocked: List[str] = []
    for job in pipeline.dry_run_plan.jobs:
        if job.readiness == TrainingReadiness.READY:
            ready.append(job.family.value)
        elif job.readiness == TrainingReadiness.INSPECT_ONLY:
            inspect.append(job.family.value)
        else:
            blocked.append(job.family.value)
    return TrainerCapabilityReport(
        ready_families=sorted(ready),
        inspect_only_families=sorted(inspect),
        blocked_families=sorted(blocked),
        global_readiness=pipeline.dry_run_plan.global_readiness.value,
        no_training_executed=True,
    )


def build_ced_advisories(
    learner_state: LearnerState,
    trainer_report: TrainerCapabilityReport,
    health: LearningHealthAudit,
    *,
    policy: Optional[InteractionControlPolicy] = None,
) -> List[CEDAdvisory]:
    policy = policy or InteractionControlPolicy.safe_default()
    health_summary = learning_health_summary(health)
    advisories: List[CEDAdvisory] = []

    if health_summary.get("overall_status") == "fail":
        advisories.append(_advisory(
            AdvisoryScope.QUALITY_REPAIR,
            AdvisoryStatus.SAFE_TO_SHOW_CED,
            "Repair learning pipeline before training escalation",
            "The health audit reports failed stages; CED should not treat learning outputs as ready.",
            "Run diagnostic sessions and fix failed learning stages before trainer integration.",
            evidence={"failures": health_summary.get("failures", [])},
        ))

    if learner_state.weaknesses and policy.allow_ced_data_collection_advisories:
        weakest = sorted(learner_state.weaknesses.items(), key=lambda item: (-item[1], item[0]))[0]
        advisories.append(_advisory(
            AdvisoryScope.DATA_COLLECTION,
            AdvisoryStatus.SAFE_TO_SHOW_CED,
            f"Collect better data for {weakest[0]}",
            "The live learner repeatedly observed this as a weak or data-needing area.",
            f"Prefer future diagnostic sessions that produce clearer evidence for {weakest[0]} without changing CED core behavior.",
            evidence={"weaknesses": learner_state.weaknesses, "top_weakness": weakest[0]},
        ))

    if learner_state.next_focus and policy.allow_ced_session_focus_advisories:
        advisories.append(_advisory(
            AdvisoryScope.SESSION_FOCUS,
            AdvisoryStatus.SAFE_TO_SHOW_CED,
            "Use learner next-focus items as session planning hints",
            "The learner has deterministic next-focus items from prior observations.",
            "Expose these items as optional diagnostic focus, not as prompt rewrites or scoring rules.",
            evidence={"next_focus": learner_state.next_focus[:10]},
        ))

    if trainer_report.ready_families and policy.allow_trainer_dry_run_advisories:
        advisories.append(_advisory(
            AdvisoryScope.TRAINER_DRY_RUN,
            AdvisoryStatus.HUMAN_APPROVAL_REQUIRED,
            "Trainer dry-run families are ready for human review",
            "The dry-run planner reports some families as READY, but real training remains blocked by policy.",
            "Human may inspect artifacts and decide whether to create a separate explicit trainer-adapter task.",
            evidence={"ready_families": trainer_report.ready_families},
        ))

    if trainer_report.blocked_families:
        advisories.append(_advisory(
            AdvisoryScope.MINER_REVIEW,
            AdvisoryStatus.SAFE_TO_SHOW_CED,
            "Some trainer families remain blocked",
            "The trainer planner reports blocked families; learner should keep collecting targeted evidence.",
            "Use blocked family list to guide diagnostics and dataset generation, not to change model behavior automatically.",
            evidence={"blocked_families": trainer_report.blocked_families},
        ))

    # Explicitly encode prohibited escalation paths.
    advisories.append(_advisory(
        AdvisoryScope.TRAINER_DRY_RUN,
        AdvisoryStatus.BLOCKED,
        "No automatic real training or CED mutation",
        "The interaction cycle is advisory-only and deterministic.",
        "Require a separate explicit human-approved trainer adapter before any real training or model mutation.",
        evidence={
            "require_human_for_real_training": policy.require_human_for_real_training,
            "require_human_for_core_changes": policy.require_human_for_core_changes,
            "require_human_for_prompt_changes": policy.require_human_for_prompt_changes,
        },
    ))

    # Deterministic order.
    return sorted(advisories, key=lambda adv: (adv.status.value, adv.scope.value, adv.title))


# ── full interaction cycle ───────────────────────────────────────────────────

def run_interaction_cycle(
    pipeline: LearningPipelineResult,
    health: LearningHealthAudit,
    *,
    learner_state: Optional[LearnerState] = None,
    policy: Optional[InteractionControlPolicy] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> InteractionCycle:
    policy = policy or InteractionControlPolicy.safe_default()
    pipeline_summary = learning_pipeline_summary(pipeline)
    health_summary = learning_health_summary(health)

    observation = observe_learning_pipeline(pipeline, health, metadata=metadata)
    updated_learner = deterministic_live_learn(pipeline, health, state=learner_state, metadata=metadata)
    trainer_report = build_trainer_capability_report(pipeline)
    advisories = build_ced_advisories(updated_learner, trainer_report, health, policy=policy)

    messages: List[ControlMessage] = [
        _message(
            ControlActor.CED,
            ControlActor.LEARNER,
            ControlMessageKind.OBSERVATION,
            {
                "session_id": observation.session_id,
                "observation_id": observation.observation_id,
                "pipeline_version": pipeline_summary.get("pipeline_version"),
                "health_status": health_summary.get("overall_status"),
            },
        ),
        _message(
            ControlActor.LEARNER,
            ControlActor.TRAINER,
            ControlMessageKind.LESSON_UPDATE,
            learner_state_summary(updated_learner),
        ),
        _message(
            ControlActor.TRAINER,
            ControlActor.LEARNER,
            ControlMessageKind.TRAINER_READINESS,
            trainer_report.model_dump(mode="json"),
        ),
    ]

    for advisory in advisories:
        messages.append(_message(
            ControlActor.LEARNER,
            ControlActor.CED,
            ControlMessageKind.CED_ADVISORY if advisory.status != AdvisoryStatus.BLOCKED else ControlMessageKind.SAFETY_BLOCK,
            advisory.model_dump(mode="json"),
            requires_human_approval=advisory.status == AdvisoryStatus.HUMAN_APPROVAL_REQUIRED,
        ))

    blocked_actions = [
        "automatic_ced_core_change",
        "automatic_prompt_change",
        "automatic_weight_update",
        "real_training_without_explicit_human_task",
        "bypass_quality_gates",
    ]

    cycle_payload = {
        "pipeline": pipeline_summary,
        "health": health_summary,
        "learner": learner_state_summary(updated_learner),
        "trainer": trainer_report.model_dump(mode="json"),
        "advisories": [adv.advisory_id for adv in advisories],
        "messages": [msg.message_id for msg in messages],
        "blocked_actions": blocked_actions,
        "metadata": sanitize_public_payload(metadata or {}),
    }
    return InteractionCycle(
        cycle_id=interaction_hash(cycle_payload, prefix="cycle_"),
        pipeline_summary=pipeline_summary,
        health_summary=health_summary,
        learner_observation=observation,
        learner_state=updated_learner,
        trainer_report=trainer_report,
        ced_advisories=advisories,
        messages=messages,
        blocked_actions=blocked_actions,
        no_training_executed=True,
    )


def interaction_cycle_summary(cycle: InteractionCycle) -> Dict[str, Any]:
    return sanitize_public_payload({
        "cycle_id": cycle.cycle_id,
        "message_count": len(cycle.messages),
        "advisory_count": len(cycle.ced_advisories),
        "safe_advisories": [a.title for a in cycle.ced_advisories if a.status == AdvisoryStatus.SAFE_TO_SHOW_CED],
        "human_required_advisories": [a.title for a in cycle.ced_advisories if a.status == AdvisoryStatus.HUMAN_APPROVAL_REQUIRED],
        "blocked_advisories": [a.title for a in cycle.ced_advisories if a.status == AdvisoryStatus.BLOCKED],
        "trainer": cycle.trainer_report.model_dump(mode="json"),
        "learner": learner_state_summary(cycle.learner_state),
        "blocked_actions": cycle.blocked_actions,
        "no_training_executed": cycle.no_training_executed,
    })
