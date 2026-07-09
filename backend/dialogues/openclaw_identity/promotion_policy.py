"""
OpenClaw Agent Identity — the promotion policy (ladder, gates, promotions).

Three mechanically enforced principles:

  1. NO automatic self-promotion. ``evaluate_gate`` only RECOMMENDS; a
     promotion record requires a passing gate result AND a named approver who
     is not the agent itself. The system verifies; a human promotes — the same
     never-auto-promote symmetry as the OpenClaw lesson lifecycle and the
     Teacher-Loop Promotion Arena.
  2. Evidence or nothing. Gates are declarative (metric, op, threshold)
     evaluated against an explicit evidence dict. A missing metric FAILS with
     an honest reason — absence of evidence is never treated as success.
  3. One step at a time. Version gates form an ordered chain; ladder stages
     advance one rung per approval. No agent skips to authority.

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .identity_profile import AgentIdentityProfile

# ── The identity ladder (Stage 0 → Stage 7) ──────────────────────────────────

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

STAGE_NAMES: Tuple[str, ...] = tuple(s["name"] for s in IDENTITY_LADDER)


# ── Version gates (every promotion is evidence-backed) ───────────────────────

@dataclass(frozen=True)
class VersionGate:
    """A declarative, auditable promotion requirement: metric OP threshold."""
    gate_id: str
    from_version: str
    to_version: str
    description: str
    metric: str
    op: str            # one of <=, >=, <, >, ==
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
    "<":  lambda a, b: a < b,
    ">":  lambda a, b: a > b,
    "==": lambda a, b: a == b,
}


@dataclass(frozen=True)
class GateResult:
    """The outcome of evaluating one gate against explicit evidence.

    A recommendation, never an action: nothing is promoted by this object.
    """
    gate_id: str
    passed: bool
    reasons: Tuple[str, ...]
    evidence_used: Dict[str, Any]


def next_gate_for(version: str) -> Optional[VersionGate]:
    """The gate that starts at ``version`` (None past the end of the chain)."""
    for gate in VERSION_GATES:
        if gate.from_version == version:
            return gate
    return None


def evaluate_gate(gate: VersionGate, evidence: Mapping[str, Any]) -> GateResult:
    """Mechanically evaluate one gate. Missing/invalid evidence FAILS honestly."""
    value = evidence.get(gate.metric)
    if value is None:
        return GateResult(gate.gate_id, False,
                          (f"missing evidence metric {gate.metric!r}",),
                          {})
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return GateResult(gate.gate_id, False,
                          (f"evidence metric {gate.metric!r} is not numeric: "
                           f"{value!r}",),
                          {gate.metric: value})
    passed = _OPS[gate.op](numeric, float(gate.threshold))
    reason = (f"{gate.metric}={numeric} {gate.op} {gate.threshold} -> "
              f"{'pass' if passed else 'fail'}")
    return GateResult(gate.gate_id, passed, (reason,), {gate.metric: numeric})


# ── Recording a promotion (system verifies, a human approves) ────────────────

def record_promotion(
    profile: AgentIdentityProfile,
    gate_result: GateResult,
    *,
    approved_by: str,
    approved_on: str = "",
) -> AgentIdentityProfile:
    """Return a NEW profile with the earned version. Refuses (ValueError):
    a failing gate, a gate that does not start at the profile's current
    version, an unnamed approver, or self-approval. The input profile is
    never mutated — history is append-only and auditable."""
    gate = next((g for g in VERSION_GATES if g.gate_id == gate_result.gate_id), None)
    if gate is None:
        raise ValueError(f"unknown gate {gate_result.gate_id!r}")
    if gate.from_version != profile.identity_version:
        raise ValueError(
            f"gate {gate.gate_id!r} starts at {gate.from_version}, but the "
            f"profile is at {profile.identity_version}")
    if not gate_result.passed:
        raise ValueError("promotion requires a PASSING gate result "
                         "(no promotion without evidence)")
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
        "evidence": dict(gate_result.evidence_used),
        "reasons": list(gate_result.reasons),
    }
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
) -> AgentIdentityProfile:
    """Advance the ladder rank by EXACTLY one rung (human-approved, non-self).
    Rank and version are orthogonal axes; both are earned, neither is claimed."""
    if new_status not in STAGE_NAMES:
        raise ValueError(f"unknown ladder stage {new_status!r}")
    current = STAGE_NAMES.index(profile.promotion_status) \
        if profile.promotion_status in STAGE_NAMES else 0
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
    return dataclasses.replace(
        profile,
        promotion_status=new_status,
        version_history=profile.version_history + (entry,),
    )
