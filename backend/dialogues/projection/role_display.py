"""
Council Live View Foundation — role display contract (§6.2, audited).

The future UI must show the REAL Socrates role loop, derived EXCLUSIVELY from
canonical ``SessionState.role_history`` rows (``{phase, round_index, agent_id,
role}``) or their future ledger projection.

Locked rules (mapping §8, audited):

- **No role recalculation.** This module never invokes or reimplements
  ``assign_roles_for_phase`` / ``assign_primary_roles`` — even a row that
  LOOKS wrong (e.g. the same agent as Socrates in every phase) is projected
  verbatim, because the canonical record is the authority, not the scheduler
  formula.
- **No inferred primary role.** The projection reports exactly the per-phase
  assignments that were recorded; it never derives a "primary" or "dominant"
  role for an agent.
- **No silent repair of malformed rows.** A row missing a required key is a
  contract error and raises; the projection never fills in, reorders, or
  corrects canonical data.
- Anonymous labels (reveal.py) never replace persistent agent identity here —
  role display is post-blind and identity-bearing by design. The frontend
  renders these rows; it never computes them.

Pure contract: imports nothing from ced.py / providers / registry.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pydantic import BaseModel, ConfigDict, Field


ROLE_DISPLAY_SCHEMA = "ced_role_display_v1"

_REQUIRED_ROW_KEYS = ("phase", "round_index", "agent_id", "role")


class RoleDisplayRow(BaseModel):
    """One canonical role assignment, frozen for display."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = Field(default=ROLE_DISPLAY_SCHEMA,
                             serialization_alias="schema")
    phase:       str
    round_index: int
    agent_id:    str
    role:        str
    # Position within the recorded role_history — preserves canonical order
    # even inside groupings.
    recorded_index: int = Field(ge=0)


def project_role_history(
    role_history: List[Mapping[str, Any]],
) -> List[RoleDisplayRow]:
    """
    Pure projection of canonical role_history rows. Raises on any missing or
    malformed key — the projection NEVER repairs, recalculates, or invents
    canonical data.
    """
    rows: List[RoleDisplayRow] = []
    for index, raw in enumerate(role_history):
        missing = [k for k in _REQUIRED_ROW_KEYS if k not in raw]
        if missing:
            raise ValueError(
                f"role_history[{index}] is missing required keys: {missing} "
                "— refusing to project malformed canonical data"
            )
        rows.append(RoleDisplayRow(
            phase=str(raw["phase"]),
            round_index=int(raw["round_index"]),
            agent_id=str(raw["agent_id"]),
            role=str(raw["role"]),
            recorded_index=index,
        ))
    return rows


def group_by_round(
    rows: List[RoleDisplayRow],
) -> Dict[int, List[RoleDisplayRow]]:
    """§6.2 'Round N: agent — role' grouping, canonical order preserved."""
    grouped: Dict[int, List[RoleDisplayRow]] = {}
    for row in rows:
        grouped.setdefault(row.round_index, []).append(row)
    return grouped


def group_by_phase(
    rows: List[RoleDisplayRow],
) -> Dict[str, List[RoleDisplayRow]]:
    """Per-phase grouping for the advanced view, canonical order preserved."""
    grouped: Dict[str, List[RoleDisplayRow]] = {}
    for row in rows:
        grouped.setdefault(row.phase, []).append(row)
    return grouped
