"""
OpenClaw Agent Identity — promotion policy (ladder, gates, promotions).

Mechanically enforced principles:
  1. No automatic self-promotion.
  2. Evidence or nothing.
  3. One version/stage step at a time.
  4. A caller-supplied GateResult is never trusted: record_promotion
     recomputes the gate from the embedded evidence before writing history.

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .identity_profile import AgentIdentityProfile


IDENTITY_LADDER: Tuple[Dict[str, Any], ...] = (
    {"stage": 0, "name": "base_agent",
     "description": "Uses the shared prompt and assigned role only."},
    {"stage": 1, "name": "memory_aware",
     "description": "Receives selected Memory Lessons."},
    {"stage": 2, "name": "shadow_apprentice",
     "description": "Produces shadow outputs but does not affect final answers."},
    {"stage": 3, "name": "self_learning",
     "description": "Uses traces and feedback to understand recurring failures."},
    {"stage": 4, "name": "patch_proposer",
     "description": "Proposes small prompt, lesson, test, or code patches."},
    {"stage": 5, "name": "test_aware_researcher",
     "description": "Links proposals to Evidence Harness / Proof Sprint / "
                    "Tree Search tests."},
    {"stage": 6, "name": "candidate_contributor",
     "description": "Can produce reviewable, reversible patches."},
    {"stage": 7, "name": "master_branch_researcher",
     "description": "Can study main, compare feature branches, understand "
                    "risk, and propose safe improvements justified by tests "
                    "and evidence."},
)

STAGE_NAMES: Tuple[str, ...] = tuple(stage["name"] for stage in IDENTITY_LADDER)


@dataclass(frozen=True)
class VersionGate:
    gate_id: str
    from_version: str
    to_version: str
    description: str
    metric: str
    op: str
    threshold: float


VERSION_GATES: Tuple[VersionGate, ...] = (
    VersionGate("gate_v0_1_to_v0_2", "v0.1", "v0.2",
                "Agent reduced exact-output failures.",
                "exact_output_failures_delta", "<=", -1),
    VersionGate("gate_v0_2_to_v0_3", "v0.2", "v0.3",
                "Agent reduced unsupported claims.",
                "unsupported_claim_failures_delta", "<=", -1),
    VersionGate("gate_v0_3_to_v0_4", "v0.3", "v0.4",
                "Agent produced useful blind_spots in Shadow Apprentice mode.",
                "shadow_blind_spots_wins", ">=", 3),
    VersionGate("gate_v0_4_to_v0_5", "v0.4", "v0.5",
                "Agent proposed prompt patches that passed A/B tests.",
                "prompt_patches_passed_ab", ">=", 1),
    VersionGate("gate_v0_5_to_v1_0", "v0.5", "v1.0",
                "Agent can compare branch vs master and propose safe changes "
                "with tests.",
                "master_branch_proposals_verified", ">=", 1),
)

_OPS = {
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "==": lambda a, b: a == b,
}


@dataclass(frozen=True)
class GateResult:
    """A recommendation, never an action."""
    gate_id: str
    passed: bool
    reasons: Tuple[str, ...]
    evidence_used: Dict[str, Any]


def next_gate_for(version: str) -> Optional[VersionGate]:
    for gate in VERSION_GATES:
        if gate.from_version == version:
            return gate
    return None


def evaluate_gate(gate: VersionGate, evidence: Mapping[str, Any]) -> GateResult:
    """Mechanically evaluate one gate. Missing/invalid evidence fails."""
    value = evidence.get(gate.metric)
    if value is None:
        return GateResult(
            gate.gate_id,
            False,
            (f"missing evidence metric {gate.metric!r}",),
            {},
        )
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return GateResult(
            gate.gate_id,
            False,
            (f"evidence metric {gate.metric!r} is not numeric: {value!r}",),
            {gate.metric: value},
        )
    passed = _OPS[gate.op](numeric, float(gate.threshold))
    reason = (
        f"{gate.metric}={numeric} {gate.op} {gate.threshold} -> "
        f"{'pass' if passed else 'fail'}")
    return GateResult(
        gate.gate_id,
        passed,
        (reason,),
        {gate.metric: numeric},
    )


def _verified_gate_result(gate: VersionGate, supplied: GateResult) -> GateResult:
    """Recompute a caller-supplied result from its evidence.

    This closes the forged-result path: ``passed=True`` and a persuasive reason
    are irrelevant unless the actual evidence satisfies the declarative gate.
    """
    if supplied.gate_id != gate.gate_id:
        raise ValueError(
            f"gate result {supplied.gate_id!r} does not match {gate.gate_id!r}")
    verified = evaluate_gate(gate, supplied.evidence_used)
    if not supplied.passed:
        raise ValueError("promotion requires a passing gate result")
    if not verified.passed:
        raise ValueError(
            "promotion evidence does not pass the gate when independently "
            f"re-evaluated: {verified.reasons[0]}")
    return verified


def record_promotion(
    profile: AgentIdentityProfile,
    gate_result: GateResult,
    *,
    approved_by: str,
    approved_on: str = "",
    approval_reference: str = "",
) -> AgentIdentityProfile:
    """Return a new profile with one earned version step.

    The gate is resolved from the immutable policy and recomputed from
    ``gate_result.evidence_used``. A forged ``passed=True`` cannot promote.
    ``approved_by`` is an auditable attribution, not cryptographic identity.
    """
    gate = next(
        (candidate for candidate in VERSION_GATES
         if candidate.gate_id == gate_result.gate_id),
        None,
    )
    if gate is None:
        raise ValueError(f"unknown gate {gate_result.gate_id!r}")
    if gate.from_version != profile.identity_version:
        raise ValueError(
            f"gate {gate.gate_id!r} starts at {gate.from_version}, but the "
            f"profile is at {profile.identity_version}")

    verified = _verified_gate_result(gate, gate_result)

    approver = approved_by.strip()
    if not approver:
        raise ValueError("promotion requires a named approver")
    if approver == profile.agent_id:
        raise ValueError("an agent can never approve its own promotion")

    entry = {
        "from_version": gate.from_version,
        "to_version": gate.to_version,
        "gate_id": gate.gate_id,
        "gate_description": gate.description,
        "approved_by": approver,
        "approved_on": approved_on,
        "evidence": dict(verified.evidence_used),
        "reasons": list(verified.reasons),
    }
    if approval_reference.strip():
        entry["approval_reference"] = approval_reference.strip()

    following = next_gate_for(gate.to_version)
    return dataclasses.replace(
        profile,
        identity_version=gate.to_version,
        next_gate=following.gate_id if following else None,
        version_history=profile.version_history + (entry,),
    )


def advance_stage(
    profile: AgentIdentityProfile,
    new_status: str,
    *,
    approved_by: str,
    approved_on: str = "",
    evidence_reference: str = "",
) -> AgentIdentityProfile:
    """Advance the descriptive ladder rank by exactly one rung.

    Stage rank is still runtime-inert. ``evidence_reference`` can bind the
    human decision to an arena/report/trace packet and is recorded when given.
    """
    if new_status not in STAGE_NAMES:
        raise ValueError(f"unknown ladder stage {new_status!r}")
    current = (
        STAGE_NAMES.index(profile.promotion_status)
        if profile.promotion_status in STAGE_NAMES else 0)
    target = STAGE_NAMES.index(new_status)
    if target != current + 1:
        raise ValueError(
            f"stages advance one rung at a time: {profile.promotion_status!r} "
            f"-> {new_status!r} is not a single step")

    approver = approved_by.strip()
    if not approver:
        raise ValueError("stage advancement requires a named approver")
    if approver == profile.agent_id:
        raise ValueError("an agent can never approve its own advancement")

    entry = {
        "from_status": profile.promotion_status,
        "to_status": new_status,
        "approved_by": approver,
        "approved_on": approved_on,
    }
    if evidence_reference.strip():
        entry["evidence_reference"] = evidence_reference.strip()

    return dataclasses.replace(
        profile,
        promotion_status=new_status,
        version_history=profile.version_history + (entry,),
    )
