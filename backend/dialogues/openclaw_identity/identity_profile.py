"""
OpenClaw Agent Identity — the auditable identity profile ("soul", non-mystical).

An AgentIdentityProfile is the versioned, evidence-backed record of ONE agent
seat: where it is strong, where it fails, which stable lessons apply to it,
what version it has earned, and what gate comes next.

The guiding sentence (docs/openclaw_memory_lessons/SELF_IMPROVING_AGENT_IDENTITY.md):

    The agent does not become powerful because it claims identity.
    The agent earns identity through evidence.

Mechanics, not judgement:
  - ``role_strengths`` are derived ONLY from Goal 5 session traces: an
    assembled section's ``source_draft_id`` is ``draft_<move_id>``, and the
    trace's move list maps that move to its producing provider. Wins /
    opportunities per section is a mechanical count over public assembly
    outcomes — no raw hidden scorecards are read or stored.
  - ``known_failures`` and ``stable_lessons`` are INPUTS (curator- or
    lesson-proposer-supplied), never invented here.
  - The profile is a SYSTEM-owned artifact. It is never injected into agent
    contexts and grants no runtime authority (test-locked: the CED core does
    not import this package).

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: The five locked synthesis sections (mirrors SYNTHESIS_5_SECTION.md).
SECTION_NAMES: Tuple[str, ...] = (
    "core_answer", "crucial_stress_test", "blind_spots", "nuance", "final_verdict",
)

_DRAFT_PREFIX = "draft_"


@dataclass(frozen=True)
class AgentIdentityProfile:
    """Versioned, auditable identity record for one agent seat.

    Descriptive, not authority: nothing in this record changes what the agent
    is allowed to do at runtime. Promotion is recorded here only AFTER the
    evidence passed a gate and a named (non-self) approver signed it.
    """

    agent_id: str
    identity_version: str = "v0.1"
    promotion_status: str = "base_agent"        # ladder stage name (see policy)
    role_strengths: Dict[str, float] = field(default_factory=dict)
    section_wins: Dict[str, int] = field(default_factory=dict)
    section_opportunities: Dict[str, int] = field(default_factory=dict)
    sessions_analyzed: int = 0
    ratified_sessions: int = 0
    known_failures: Tuple[str, ...] = ()
    stable_lessons: Tuple[str, ...] = ()
    next_gate: Optional[str] = None
    version_history: Tuple[Dict[str, Any], ...] = ()

    def to_record(self) -> Dict[str, Any]:
        """JSON-ready dict (the design-target schema of the identity layer)."""
        return {
            "agent_id": self.agent_id,
            "identity_version": self.identity_version,
            "promotion_status": self.promotion_status,
            "role_strengths": dict(self.role_strengths),
            "section_wins": dict(self.section_wins),
            "section_opportunities": dict(self.section_opportunities),
            "sessions_analyzed": self.sessions_analyzed,
            "ratified_sessions": self.ratified_sessions,
            "known_failures": list(self.known_failures),
            "stable_lessons": list(self.stable_lessons),
            "next_gate": self.next_gate,
            "version_history": [dict(entry) for entry in self.version_history],
        }


def from_record(record: Dict[str, Any]) -> AgentIdentityProfile:
    """Rebuild a profile from ``to_record()`` output (registry load path).

    ``agent_id`` is required; every other field falls back to the same
    defaults a fresh profile has. Round-trips: from_record(p.to_record()) == p.
    """
    agent_id = str(record.get("agent_id", "")).strip()
    if not agent_id:
        raise ValueError("identity record requires a non-empty agent_id")
    return AgentIdentityProfile(
        agent_id=agent_id,
        identity_version=str(record.get("identity_version", "v0.1")),
        promotion_status=str(record.get("promotion_status", "base_agent")),
        role_strengths={str(k): float(v)
                        for k, v in (record.get("role_strengths") or {}).items()},
        section_wins={str(k): int(v)
                      for k, v in (record.get("section_wins") or {}).items()},
        section_opportunities={str(k): int(v)
                               for k, v in (record.get("section_opportunities")
                                            or {}).items()},
        sessions_analyzed=int(record.get("sessions_analyzed", 0)),
        ratified_sessions=int(record.get("ratified_sessions", 0)),
        known_failures=tuple(record.get("known_failures") or ()),
        stable_lessons=tuple(record.get("stable_lessons") or ()),
        next_gate=record.get("next_gate"),
        version_history=tuple(dict(e) for e in (record.get("version_history")
                                                or ())),
    )


def _provider_by_move(trace: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for move in trace.get("moves", []) or []:
        move_id = str(move.get("move_id", ""))
        provider = str(move.get("provider_id", "") or "")
        if move_id and provider:
            out[move_id] = provider
    return out


def build_identity_profile(
    agent_id: str,
    traces: Sequence[Dict[str, Any]],
    *,
    known_failures: Iterable[str] = (),
    stable_lessons: Iterable[str] = (),
    identity_version: str = "v0.1",
    promotion_status: str = "base_agent",
) -> AgentIdentityProfile:
    """Build one agent's identity profile from Goal 5 session traces.

    Every number is a mechanical count over trace-level public outcomes:
      - opportunity: the agent authored a synthesis draft in a session and a
        given section was resolved at assembly (someone's draft won it);
      - win: the winning draft for that section was THIS agent's.

    Sessions where the agent never appears contribute nothing. ``None`` /
    missing assemblies contribute no opportunities (never fabricated).
    """
    wins: Dict[str, int] = {}
    opportunities: Dict[str, int] = {}
    sessions_analyzed = 0
    ratified_sessions = 0

    for trace in traces:
        moves = trace.get("moves", []) or []
        if not any(str(m.get("provider_id", "") or "") == agent_id for m in moves):
            continue
        sessions_analyzed += 1
        ratification = trace.get("ratification") or {}
        if ratification.get("ratified") is True:
            ratified_sessions += 1

        agent_drafted = any(
            str(m.get("provider_id", "") or "") == agent_id
            and str(m.get("phase", "")) == "synthesis"
            for m in moves)
        assembly = trace.get("assembly")
        if not agent_drafted or assembly is None:
            continue

        by_move = _provider_by_move(trace)
        for section in assembly.get("sections", []) or []:
            name = str(section.get("section_name", ""))
            src = str(section.get("source_draft_id", "") or "")
            if name not in SECTION_NAMES or not src.strip():
                continue                       # unresolved section: no contest
            opportunities[name] = opportunities.get(name, 0) + 1
            move_id = src[len(_DRAFT_PREFIX):] if src.startswith(_DRAFT_PREFIX) else ""
            if by_move.get(move_id) == agent_id:
                wins[name] = wins.get(name, 0) + 1

    strengths = {
        name: round(wins.get(name, 0) / opportunities[name], 4)
        for name in sorted(opportunities)
    }

    # next_gate is resolved lazily from the promotion policy so the profile
    # module stays import-clean (policy imports profile, not vice versa).
    from .promotion_policy import next_gate_for
    gate = next_gate_for(identity_version)

    return AgentIdentityProfile(
        agent_id=agent_id,
        identity_version=identity_version,
        promotion_status=promotion_status,
        role_strengths=strengths,
        section_wins={k: wins[k] for k in sorted(wins)},
        section_opportunities={k: opportunities[k] for k in sorted(opportunities)},
        sessions_analyzed=sessions_analyzed,
        ratified_sessions=ratified_sessions,
        known_failures=tuple(known_failures),
        stable_lessons=tuple(stable_lessons),
        next_gate=gate.gate_id if gate else None,
    )
