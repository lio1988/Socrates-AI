"""
OpenClaw Agent Identity — the auditable identity profile ("soul", non-mystical).

An AgentIdentityProfile is the versioned, evidence-backed record of ONE agent
seat: where it is strong, where it fails, which stable lessons and approved
principles apply to it, what version it has earned, and what gate comes next.

The guiding sentence:

    The agent does not become powerful because it claims identity.
    The agent earns identity through evidence.

Mechanics, not judgement:
  - ``role_strengths`` are derived ONLY from Goal 5 session traces.
  - ``known_failures`` and ``stable_lessons`` begin as curator inputs and can
    later change only through governed, append-only self-revisions.
  - ``soul_principles`` are approved descriptive commitments, never runtime
    permissions and never automatic prompt mutations.
  - The profile is SYSTEM-owned, runtime-inert, and never grants authority.

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

SECTION_NAMES: Tuple[str, ...] = (
    "core_answer", "crucial_stress_test", "blind_spots", "nuance", "final_verdict",
)

_PROFILE_FIELDS = {
    "agent_id", "identity_version", "promotion_status", "role_strengths",
    "section_wins", "section_opportunities", "sessions_analyzed",
    "ratified_sessions", "known_failures", "stable_lessons", "soul_principles",
    "next_gate", "version_history", "revision_history",
}
_DRAFT_PREFIX = "draft_"


@dataclass(frozen=True)
class AgentIdentityProfile:
    """Versioned, auditable identity record for one agent seat."""

    agent_id: str
    identity_version: str = "v0.1"
    promotion_status: str = "base_agent"
    role_strengths: Dict[str, float] = field(default_factory=dict)
    section_wins: Dict[str, int] = field(default_factory=dict)
    section_opportunities: Dict[str, int] = field(default_factory=dict)
    sessions_analyzed: int = 0
    ratified_sessions: int = 0
    known_failures: Tuple[str, ...] = ()
    stable_lessons: Tuple[str, ...] = ()
    soul_principles: Tuple[str, ...] = ()
    next_gate: Optional[str] = None
    version_history: Tuple[Dict[str, Any], ...] = ()
    revision_history: Tuple[Dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        # next_gate is DERIVED from identity_version. A bare constructor call
        # must never produce a profile the governed registry refuses on its
        # first save, so an unset gate is filled from the version here (an
        # explicitly supplied gate is kept and validated at save time).
        if self.next_gate is None:
            from .promotion_policy import next_gate_for
            gate = next_gate_for(self.identity_version)
            if gate is not None:
                object.__setattr__(self, "next_gate", gate.gate_id)

    def to_record(self) -> Dict[str, Any]:
        """Return the complete JSON-ready identity record."""
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
            "soul_principles": list(self.soul_principles),
            "next_gate": self.next_gate,
            "version_history": [dict(entry) for entry in self.version_history],
            "revision_history": [dict(entry) for entry in self.revision_history],
        }


def _mapping(record: Mapping[str, Any], field_name: str) -> Mapping[Any, Any]:
    value = record.get(field_name) or {}
    if not isinstance(value, Mapping):
        raise ValueError(f"identity field {field_name!r} must be a mapping")
    return value


def _sequence(record: Mapping[str, Any], field_name: str) -> Sequence[Any]:
    value = record.get(field_name) or ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"identity field {field_name!r} must be a sequence")
    return value


def _string_tuple(record: Mapping[str, Any], field_name: str) -> Tuple[str, ...]:
    values = _sequence(record, field_name)
    result = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(
                f"identity field {field_name!r} must contain only text")
        result.append(value)
    return tuple(result)


def _history_tuple(
    record: Mapping[str, Any], field_name: str
) -> Tuple[Dict[str, Any], ...]:
    values = _sequence(record, field_name)
    history = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError(
                f"identity field {field_name!r} must contain mappings")
        history.append(dict(value))
    return tuple(history)


def _section_float_mapping(
    record: Mapping[str, Any], field_name: str
) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for raw_key, raw_value in _mapping(record, field_name).items():
        key = str(raw_key)
        if key not in SECTION_NAMES:
            raise ValueError(
                f"identity field {field_name!r} contains unknown section {key!r}")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"identity field {field_name!r} contains a non-numeric value") from exc
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"identity field {field_name!r} values must be between 0 and 1")
        result[key] = value
    return result


def _section_int_mapping(
    record: Mapping[str, Any], field_name: str
) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for raw_key, raw_value in _mapping(record, field_name).items():
        key = str(raw_key)
        if key not in SECTION_NAMES:
            raise ValueError(
                f"identity field {field_name!r} contains unknown section {key!r}")
        if isinstance(raw_value, bool):
            raise ValueError(
                f"identity field {field_name!r} contains a boolean count")
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"identity field {field_name!r} contains a non-integer value") from exc
        if value < 0 or value != raw_value:
            raise ValueError(
                f"identity field {field_name!r} counts must be non-negative integers")
        result[key] = value
    return result


def _non_negative_int(record: Mapping[str, Any], field_name: str) -> int:
    raw_value = record.get(field_name, 0)
    if isinstance(raw_value, bool):
        raise ValueError(f"identity field {field_name!r} cannot be boolean")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"identity field {field_name!r} must be an integer") from exc
    if value < 0 or value != raw_value:
        raise ValueError(
            f"identity field {field_name!r} must be a non-negative integer")
    return value


def from_record(record: Dict[str, Any]) -> AgentIdentityProfile:
    """Rebuild a profile from untrusted JSON with strict schema/type checks."""
    if not isinstance(record, Mapping):
        raise ValueError("identity record must be a mapping")
    extras = set(record) - _PROFILE_FIELDS
    if extras:
        raise ValueError(
            f"identity record contains unknown fields: {sorted(extras)}")

    agent_id = str(record.get("agent_id", "")).strip()
    if not agent_id:
        raise ValueError("identity record requires a non-empty agent_id")
    identity_version = str(record.get("identity_version", "v0.1")).strip()
    promotion_status = str(record.get("promotion_status", "base_agent")).strip()
    if not identity_version or not promotion_status:
        raise ValueError("identity version and promotion status must be non-empty")

    role_strengths = _section_float_mapping(record, "role_strengths")
    section_wins = _section_int_mapping(record, "section_wins")
    section_opportunities = _section_int_mapping(record, "section_opportunities")
    for section, wins in section_wins.items():
        if wins > section_opportunities.get(section, 0):
            raise ValueError(
                f"identity section wins exceed opportunities for {section!r}")
    for section, rate in role_strengths.items():
        opportunities = section_opportunities.get(section, 0)
        wins = section_wins.get(section, 0)
        expected = round(wins / opportunities, 4) if opportunities else 0.0
        if abs(rate - expected) > 0.0001:
            raise ValueError(
                f"identity role strength for {section!r} does not match counts")

    sessions_analyzed = _non_negative_int(record, "sessions_analyzed")
    ratified_sessions = _non_negative_int(record, "ratified_sessions")
    if ratified_sessions > sessions_analyzed:
        raise ValueError("ratified_sessions cannot exceed sessions_analyzed")

    next_gate = record.get("next_gate")
    if next_gate is not None and not isinstance(next_gate, str):
        raise ValueError("identity next_gate must be text or null")

    return AgentIdentityProfile(
        agent_id=agent_id,
        identity_version=identity_version,
        promotion_status=promotion_status,
        role_strengths=role_strengths,
        section_wins=section_wins,
        section_opportunities=section_opportunities,
        sessions_analyzed=sessions_analyzed,
        ratified_sessions=ratified_sessions,
        known_failures=_string_tuple(record, "known_failures"),
        stable_lessons=_string_tuple(record, "stable_lessons"),
        soul_principles=_string_tuple(record, "soul_principles"),
        next_gate=next_gate,
        version_history=_history_tuple(record, "version_history"),
        revision_history=_history_tuple(record, "revision_history"),
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
    soul_principles: Iterable[str] = (),
    identity_version: str = "v0.1",
    promotion_status: str = "base_agent",
) -> AgentIdentityProfile:
    """Build one agent's descriptive profile from public session outcomes."""
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
                continue
            opportunities[name] = opportunities.get(name, 0) + 1
            move_id = src[len(_DRAFT_PREFIX):] if src.startswith(_DRAFT_PREFIX) else ""
            if by_move.get(move_id) == agent_id:
                wins[name] = wins.get(name, 0) + 1

    strengths = {
        name: round(wins.get(name, 0) / opportunities[name], 4)
        for name in sorted(opportunities)
    }

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
        soul_principles=tuple(soul_principles),
        next_gate=gate.gate_id if gate else None,
    )
