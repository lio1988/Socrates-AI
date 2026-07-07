"""
Phase 26O — CED / Learner / Trainer Triad Loop.

One deterministic facade that connects:

  SessionState -> pipeline -> health audit -> learner update -> interaction cycle
  -> safe feedback packet for CED inspection.

This module is advisory-only and side-effect free.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import SocratesConstitution, sanitize_public_payload
from .learning_health_audit import LearningHealthAudit, LearningHealthPolicy, audit_learning_pipeline_result
from .learning_interaction_control import (
    AdvisoryStatus,
    InteractionControlPolicy,
    InteractionCycle,
    interaction_cycle_summary,
    run_interaction_cycle,
)
from .learning_live_learner import LearnerState, learner_state_summary
from .learning_pipeline import LearningPipelinePolicy, LearningPipelineResult, run_learning_pipeline_from_state
from .models import SessionState
from .provider_registry import CouncilProviderRegistry


_VOLATILE_ID_KEYS = {
    "created_at",
    "trace_id",
    "preference_id",
    "eval_id",
    "manifest_id",
    "observation_id",
    "last_observation_id",
    "message_id",
    "advisory_id",
    "cycle_id",
    "interaction_cycle_id",
    "packet_id",
    "feedback_packet_id",
    "loop_id",
    "sha" + "256",
    "content_" + "sha256",
    "artifact_" + "hashes",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def triad_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


def _stable_identity_payload(value: Any) -> Any:
    """Remove volatile runtime identifiers before computing deterministic triad IDs."""
    clean = sanitize_public_payload(value)
    if isinstance(clean, dict):
        return {
            str(key): _stable_identity_payload(item)
            for key, item in clean.items()
            if str(key) not in _VOLATILE_ID_KEYS
        }
    if isinstance(clean, list):
        return [_stable_identity_payload(item) for item in clean]
    if isinstance(clean, tuple):
        return [_stable_identity_payload(item) for item in clean]
    return clean


class TriadLoopPolicy(BaseModel):
    pipeline: LearningPipelinePolicy = Field(default_factory=LearningPipelinePolicy.conservative)
    health: LearningHealthPolicy = Field(default_factory=LearningHealthPolicy.strict)
    interaction: InteractionControlPolicy = Field(default_factory=InteractionControlPolicy.safe_default)
    max_focus_items: int = 8
    max_advisories: int = 8
    include_human_review_items: bool = True

    @classmethod
    def conservative(cls) -> "TriadLoopPolicy":
        return cls()

    @classmethod
    def exploratory(cls) -> "TriadLoopPolicy":
        return cls(
            pipeline=LearningPipelinePolicy.exploratory(),
            health=LearningHealthPolicy.exploratory(),
            interaction=InteractionControlPolicy.safe_default(),
        )


class CEDFeedbackPacket(BaseModel):
    packet_id: str
    session_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    safe_focus_hints: List[str] = Field(default_factory=list)
    data_collection_requests: List[str] = Field(default_factory=list)
    eval_recommendations: List[str] = Field(default_factory=list)
    trainer_readiness: Dict[str, Any] = Field(default_factory=dict)
    blocked_actions: List[str] = Field(default_factory=list)
    human_review_items: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    dry_run_only: bool = True


class TriadLoopResult(BaseModel):
    loop_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    session_id: str
    learner_before_hash: Optional[str] = None
    learner_after_hash: str
    pipeline: LearningPipelineResult
    health: LearningHealthAudit
    interaction: InteractionCycle
    feedback_packet: CEDFeedbackPacket
    dry_run_only: bool = True

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


def _safe_take(items: List[str], maximum: int) -> List[str]:
    return sorted(dict.fromkeys(items))[: max(0, maximum)]


def _learner_identity_hash(state: LearnerState, *, prefix: str = "learner_") -> str:
    return triad_hash(_stable_identity_payload(learner_state_summary(state)), prefix=prefix)


def build_ced_feedback_packet(
    interaction: InteractionCycle,
    *,
    session_id: str,
    policy: Optional[TriadLoopPolicy] = None,
) -> CEDFeedbackPacket:
    """Build a safe, non-mutating packet CED may inspect after a session."""
    policy = policy or TriadLoopPolicy.conservative()
    safe_focus: List[str] = []
    data_requests: List[str] = []
    eval_recs: List[str] = []
    human_review: List[str] = []

    for advisory in interaction.ced_advisories[: policy.max_advisories]:
        if advisory.status == AdvisoryStatus.BLOCKED:
            continue
        if advisory.status == AdvisoryStatus.HUMAN_APPROVAL_REQUIRED:
            if policy.include_human_review_items:
                human_review.append(advisory.title)
            continue

        suggestion = advisory.suggested_action or advisory.title
        scope = advisory.scope.value
        if scope in {"session_focus", "miner_review"}:
            safe_focus.append(suggestion)
        elif scope == "data_collection":
            data_requests.append(suggestion)
        elif scope in {"eval_selection", "quality_repair"}:
            eval_recs.append(suggestion)
        else:
            safe_focus.append(suggestion)

    learner_summary = learner_state_summary(interaction.learner_state)
    if learner_summary.get("next_focus"):
        safe_focus.extend(learner_summary["next_focus"][: policy.max_focus_items])
    if learner_summary.get("weaknesses"):
        data_requests.append("Collect more diagnostic sessions for the learner's weakest observed areas.")

    payload = {
        "session_id": session_id,
        "safe_focus_hints": _safe_take(safe_focus, policy.max_focus_items),
        "data_collection_requests": _safe_take(data_requests, policy.max_focus_items),
        "eval_recommendations": _safe_take(eval_recs, policy.max_focus_items),
        "trainer_readiness": interaction.trainer_report.model_dump(mode="json"),
        "blocked_actions": interaction.blocked_actions,
        "human_review_items": _safe_take(human_review, policy.max_focus_items),
        "evidence": {
            "interaction_cycle_id": interaction.cycle_id,
            "learner": learner_summary,
            "interaction": interaction_cycle_summary(interaction),
        },
        "dry_run_only": True,
    }
    packet_id = triad_hash(_stable_identity_payload(payload), prefix="ced_feedback_")
    return CEDFeedbackPacket(packet_id=packet_id, **payload)


def run_triad_learning_loop(
    state: SessionState,
    *,
    registry: Optional[CouncilProviderRegistry] = None,
    constitution: Optional[SocratesConstitution] = None,
    learner_state: Optional[LearnerState] = None,
    policy: Optional[TriadLoopPolicy] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TriadLoopResult:
    """Run the canonical deterministic triad loop after a completed CED session."""
    policy = policy or TriadLoopPolicy.conservative()
    learner_before_hash = _learner_identity_hash(learner_state) if learner_state else None

    pipeline = run_learning_pipeline_from_state(
        state,
        registry=registry,
        constitution=constitution,
        policy=policy.pipeline,
        metadata={"runner": "phase_26o_triad_loop", **(metadata or {})},
    )
    health = audit_learning_pipeline_result(pipeline, policy=policy.health)
    interaction = run_interaction_cycle(
        pipeline,
        health,
        learner_state=learner_state,
        policy=policy.interaction,
        metadata={"runner": "phase_26o_triad_loop", **(metadata or {})},
    )
    feedback = build_ced_feedback_packet(interaction, session_id=state.session_id, policy=policy)
    learner_after_hash = _learner_identity_hash(interaction.learner_state)

    loop_payload = {
        "session_id": state.session_id,
        "learner_before_hash": learner_before_hash,
        "learner_after_hash": learner_after_hash,
        "pipeline_summary": _stable_identity_payload(pipeline.summary),
        "health_summary": _stable_identity_payload(health.summary),
        "interaction_summary": _stable_identity_payload(interaction_cycle_summary(interaction)),
        "feedback_packet": _stable_identity_payload(feedback.model_dump(mode="json")),
        "metadata": sanitize_public_payload(metadata or {}),
    }
    return TriadLoopResult(
        loop_id=triad_hash(loop_payload, prefix="triad_"),
        session_id=state.session_id,
        learner_before_hash=learner_before_hash,
        learner_after_hash=learner_after_hash,
        pipeline=pipeline,
        health=health,
        interaction=interaction,
        feedback_packet=feedback,
        dry_run_only=True,
    )


def triad_loop_summary(result: TriadLoopResult) -> Dict[str, Any]:
    return sanitize_public_payload({
        "loop_id": result.loop_id,
        "session_id": result.session_id,
        "learner_before_hash": result.learner_before_hash,
        "learner_after_hash": result.learner_after_hash,
        "pipeline_version": result.pipeline.pipeline_version,
        "health_status": result.health.overall_status.value,
        "interaction_cycle_id": result.interaction.cycle_id,
        "feedback_packet_id": result.feedback_packet.packet_id,
        "safe_focus_hints": result.feedback_packet.safe_focus_hints,
        "data_collection_requests": result.feedback_packet.data_collection_requests,
        "eval_recommendations": result.feedback_packet.eval_recommendations,
        "trainer_readiness": result.feedback_packet.trainer_readiness,
        "human_review_items": result.feedback_packet.human_review_items,
        "blocked_actions": result.feedback_packet.blocked_actions,
        "dry_run_only": result.dry_run_only,
    })
