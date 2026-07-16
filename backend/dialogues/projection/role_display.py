"""
Council Live View Foundation — role display contract (§6.2, hardened).

The future UI must show the REAL Socrates role loop, derived EXCLUSIVELY from
canonical ``SessionState.role_history`` rows (``{phase, round_index, agent_id,
role}``) or their future ledger projection.

Locked rules (mapping §8, hardening round 1 finding 7):

- **No role recalculation.** This module never invokes or reimplements
  ``assign_roles_for_phase`` / ``assign_primary_roles`` — even a row that
  LOOKS wrong (e.g. the same agent as Socrates in every phase) is projected
  verbatim, because the canonical record is the authority, not the scheduler
  formula.
- **No inferred primary role.** The projection reports exactly the per-phase
  assignments that were recorded; it never derives a "primary" or "dominant"
  role for an agent.
- **No silent repair — enforced, not just documented.** The raw row is
  validated as-is by a strict model: a float or bool ``round_index``, a
  ``None`` role, a non-canonical phase/role word, or an unknown extra field
  is REJECTED, never coerced (the old ``str(...)``/``int(...)`` conversions
  were themselves silent repair and are gone).
- Anonymous labels (reveal.py) never replace persistent agent identity here —
  role display is post-blind and identity-bearing by design. The frontend
  renders these rows; it never computes them.

Pure contract: imports nothing from ced.py / providers / registry.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from .taxonomy import PhaseLiteral, RoleLiteral


ROLE_DISPLAY_SCHEMA = "ced_role_display_v1"


class RoleDisplayRow(BaseModel):
    """One canonical role assignment, frozen for display. Strict: canonical
    rows are validated verbatim — wrong types and unknown fields reject."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                              populate_by_name=True)

    schema_name: str = Field(
        default=ROLE_DISPLAY_SCHEMA,
        validation_alias=AliasChoices("schema", "schema_name"),
        serialization_alias="schema",
    )
    phase:       PhaseLiteral
    round_index: int = Field(ge=0)
    agent_id:    str = Field(min_length=1)
    role:        RoleLiteral
    # Position within the recorded role_history — preserves canonical order
    # even inside groupings. Backend-owned; never part of the raw row.
    recorded_index: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_schema(self) -> "RoleDisplayRow":
        if self.schema_name != ROLE_DISPLAY_SCHEMA:
            raise ValueError(
                f"unknown role display schema: {self.schema_name!r}"
            )
        return self


def project_role_history(
    role_history: List[Mapping[str, Any]],
) -> List[RoleDisplayRow]:
    """
    Pure projection of canonical role_history rows. The ENTIRE raw row is
    handed to the strict model — any missing key, wrong type, non-canonical
    value or unknown extra field raises. The projection NEVER repairs,
    recalculates, or invents canonical data.
    """
    rows: List[RoleDisplayRow] = []
    for index, raw in enumerate(role_history):
        try:
            rows.append(RoleDisplayRow.model_validate(
                {**dict(raw), "recorded_index": index}
            ))
        except ValidationError as exc:
            raise ValueError(
                f"role_history[{index}] violates the role display contract "
                f"— refusing to project malformed canonical data: {exc}"
            ) from exc
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
