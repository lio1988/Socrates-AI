"""
Phase 26P — Learning Intervention Planner.

The triad loop returns observations and feedback. The intervention planner turns
that feedback into ranked, explicit, non-executing intervention proposals.

It is a planning layer only. It does not call providers, write files, or change
CED behavior.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import sanitize_public_payload
from .learning_triad_loop import CEDFeedbackPacket, TriadLoopResult, triad_loop_summary


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def intervention_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


class InterventionKind(str, Enum):
    COLLECT_DATA = "collect_data"
    ADD_EVAL = "add_eval"
    REVIEW_MINER = "review_miner"
    REVIEW_QUALITY = "review_quality"
    INSPECT_READINESS = "inspect_readiness"
    REVIEW_FOCUS = "review_focus"
    SAFETY_REVIEW = "safety_review"


class InterventionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InterventionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InterventionProposal(BaseModel):
    intervention_id: str
    kind: InterventionKind
    priority: InterventionPriority
    risk: InterventionRisk = InterventionRisk.LOW
    title: str
    rationale: str
    proposed_action: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    requires_human_review: bool = False
    executable: bool = False


class InterventionPlanPolicy(BaseModel):
    max_interventions: int = 12
    escalate_failed_health_to_critical: bool = True
    human_review_for_readiness: bool = True
    include_low_priority: bool = True

    @classmethod
    def conservative(cls) -> "InterventionPlanPolicy":
        return cls()

    @classmethod
    def compact(cls) -> "InterventionPlanPolicy":
        return cls(max_interventions=6, include_low_priority=False)


class InterventionPlan(BaseModel):
    plan_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    source_loop_id: str
    interventions: List[InterventionProposal] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    dry_run_only: bool = True

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


def _priority_rank(priority: InterventionPriority) -> int:
    return {
        InterventionPriority.CRITICAL: 0,
        InterventionPriority.HIGH: 1,
        InterventionPriority.MEDIUM: 2,
        InterventionPriority.LOW: 3,
    }[priority]


def _proposal(
    kind: InterventionKind,
    priority: InterventionPriority,
    title: str,
    rationale: str,
    proposed_action: str,
    *,
    risk: InterventionRisk = InterventionRisk.LOW,
    evidence: Optional[Dict[str, Any]] = None,
    requires_human_review: bool = False,
) -> InterventionProposal:
    payload = {
        "kind": kind.value,
        "priority": priority.value,
        "risk": risk.value,
        "title": title,
        "rationale": rationale,
        "proposed_action": proposed_action,
        "evidence": sanitize_public_payload(evidence or {}),
        "requires_human_review": requires_human_review,
    }
    return InterventionProposal(
        intervention_id=intervention_hash(payload, prefix="intervention_"),
        kind=kind,
        priority=priority,
        risk=risk,
        title=title,
        rationale=rationale,
        proposed_action=proposed_action,
        evidence=payload["evidence"],
        requires_human_review=requires_human_review,
        executable=False,
    )


def interventions_from_feedback(
    packet: CEDFeedbackPacket,
    *,
    health_status: str,
    policy: Optional[InterventionPlanPolicy] = None,
) -> List[InterventionProposal]:
    policy = policy or InterventionPlanPolicy.conservative()
    proposals: List[InterventionProposal] = []

    if health_status == "fail":
        proposals.append(_proposal(
            InterventionKind.REVIEW_QUALITY,
            InterventionPriority.CRITICAL if policy.escalate_failed_health_to_critical else InterventionPriority.HIGH,
            "Repair failed learning health stage",
            "The triad loop reports failed health status, so downstream learning artifacts need inspection.",
            "Inspect the health audit failures and repair the earliest failing stage first.",
            risk=InterventionRisk.LOW,
            evidence={"health_status": health_status, "packet_id": packet.packet_id},
        ))
    elif health_status == "warn":
        proposals.append(_proposal(
            InterventionKind.REVIEW_QUALITY,
            InterventionPriority.HIGH,
            "Review warning learning health stage",
            "The triad loop reports warning health status, so the data path may be usable only for inspection.",
            "Inspect warning stages before relying on the feedback packet.",
            evidence={"health_status": health_status, "packet_id": packet.packet_id},
        ))

    for request in packet.data_collection_requests:
        proposals.append(_proposal(
            InterventionKind.COLLECT_DATA,
            InterventionPriority.HIGH,
            "Collect targeted diagnostic data",
            "The learner requested more targeted evidence from future sessions.",
            request,
            evidence={"packet_id": packet.packet_id},
        ))

    for rec in packet.eval_recommendations:
        proposals.append(_proposal(
            InterventionKind.ADD_EVAL,
            InterventionPriority.HIGH,
            "Add or inspect external evaluation",
            "The feedback packet recommends evaluation support for the learning path.",
            rec,
            evidence={"packet_id": packet.packet_id},
        ))

    for focus in packet.safe_focus_hints:
        proposals.append(_proposal(
            InterventionKind.REVIEW_FOCUS,
            InterventionPriority.MEDIUM,
            "Use focus hint for the next diagnostic session",
            "The learner produced a safe focus hint from prior observations.",
            focus,
            evidence={"packet_id": packet.packet_id},
        ))

    readiness = packet.trainer_readiness or {}
    ready = readiness.get("ready_families", []) or []
    inspect_only = readiness.get("inspect_only_families", []) or []
    blocked = readiness.get("blocked_families", []) or []
    if ready or inspect_only:
        proposals.append(_proposal(
            InterventionKind.INSPECT_READINESS,
            InterventionPriority.MEDIUM,
            "Inspect readiness families",
            "The readiness summary has families available for review or inspection.",
            "Inspect artifacts and reports for ready or inspect-only families before any separate follow-up task.",
            risk=InterventionRisk.MEDIUM,
            evidence={"ready_families": ready, "inspect_only_families": inspect_only},
            requires_human_review=policy.human_review_for_readiness,
        ))
    if blocked:
        proposals.append(_proposal(
            InterventionKind.REVIEW_MINER,
            InterventionPriority.HIGH,
            "Resolve blocked readiness families",
            "Some readiness families are blocked, usually because the dataset path is incomplete.",
            "Inspect blocked families and trace them back to missing records, quality warnings, or miner output gaps.",
            evidence={"blocked_families": blocked},
        ))

    if packet.human_review_items:
        proposals.append(_proposal(
            InterventionKind.SAFETY_REVIEW,
            InterventionPriority.HIGH,
            "Human review items present",
            "The feedback packet contains items that should be inspected explicitly.",
            "Review listed items and decide whether any separate follow-up task is appropriate.",
            risk=InterventionRisk.MEDIUM,
            evidence={"human_review_items": packet.human_review_items},
            requires_human_review=True,
        ))

    if packet.blocked_actions:
        proposals.append(_proposal(
            InterventionKind.SAFETY_REVIEW,
            InterventionPriority.LOW,
            "Preserve blocked action boundaries",
            "The feedback packet includes boundaries that should remain explicit.",
            "Keep these boundaries visible in future reviews and summaries.",
            evidence={"blocked_actions": packet.blocked_actions},
        ))

    if not policy.include_low_priority:
        proposals = [p for p in proposals if p.priority != InterventionPriority.LOW]

    proposals = sorted(proposals, key=lambda p: (_priority_rank(p.priority), p.kind.value, p.title, p.intervention_id))
    return proposals[: policy.max_interventions]


def build_intervention_plan(
    triad: TriadLoopResult,
    *,
    policy: Optional[InterventionPlanPolicy] = None,
) -> InterventionPlan:
    policy = policy or InterventionPlanPolicy.conservative()
    health_status = triad.health.overall_status.value
    interventions = interventions_from_feedback(triad.feedback_packet, health_status=health_status, policy=policy)
    payload = {
        "source_loop_id": triad.loop_id,
        "health_status": health_status,
        "interventions": [i.intervention_id for i in interventions],
        "policy": policy.model_dump(mode="json"),
    }
    plan = InterventionPlan(
        plan_id=intervention_hash(payload, prefix="intervention_plan_"),
        source_loop_id=triad.loop_id,
        interventions=interventions,
        dry_run_only=True,
    )
    plan.summary = intervention_plan_summary(plan)
    return plan


def intervention_plan_summary(plan: InterventionPlan) -> Dict[str, Any]:
    by_priority: Dict[str, int] = {}
    by_kind: Dict[str, int] = {}
    for intervention in plan.interventions:
        by_priority[intervention.priority.value] = by_priority.get(intervention.priority.value, 0) + 1
        by_kind[intervention.kind.value] = by_kind.get(intervention.kind.value, 0) + 1
    return sanitize_public_payload({
        "plan_id": plan.plan_id,
        "source_loop_id": plan.source_loop_id,
        "intervention_count": len(plan.interventions),
        "by_priority": dict(sorted(by_priority.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "requires_human_review": [i.title for i in plan.interventions if i.requires_human_review],
        "top_actions": [i.proposed_action for i in plan.interventions[:5]],
        "dry_run_only": plan.dry_run_only,
    })
