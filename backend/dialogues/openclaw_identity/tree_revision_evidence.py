"""Governed Identity evidence from strict Deliberation Tree observations.

Repeated regressions can support ``identity:add_known_failure``. A matched
regression-to-improvement window can support ``identity:resolve_known_failure``.
Nothing here auto-links Memory, changes prompts, promotes an agent, or mutates CED.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .revision_evidence import RevisionEvidenceRecord
from .revision_evidence_builders_hardened import (
    IDENTITY_FAILURE_REPORT_VERSION,
    IDENTITY_RESOLUTION_REPORT_VERSION,
    build_identity_failure_evidence,
    build_identity_resolution_evidence,
)
from .tree_revision_observation import extract_tree_revision_observations
from .tree_revision_schema import (
    TREE_REVISION_OBSERVATION_VERSION,
    TreeRevisionObservation,
    clean_agent,
    digest,
)

TREE_EVIDENCE_SOURCE = "CEDDeliberationTreeEvidence/v1"


def _observations(
    values: Iterable[TreeRevisionObservation | Mapping[str, Any]],
) -> Tuple[TreeRevisionObservation, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("tree observations must be a sequence")
    result = tuple(
        value if isinstance(value, TreeRevisionObservation)
        else TreeRevisionObservation.from_record(value)
        for value in values
    )
    if not result:
        raise ValueError("tree evidence requires at least one observation")
    return tuple(sorted(
        result,
        key=lambda item: (
            item.comparison_key, item.session_id, item.child_draft_id,
            item.observation_digest,
        ),
    ))


def summarize_tree_revision_observations(
    values: Iterable[TreeRevisionObservation | Mapping[str, Any]],
    *,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    items = _observations(values)
    target = clean_agent(agent_id or items[0].agent_id)
    if any(item.agent_id != target for item in items):
        raise ValueError("tree observation summary mixes different agents")
    margins = [item.margin for item in items]
    return {
        "agent_id": target,
        "observations": len(items),
        "sessions": sorted({item.session_id for item in items}),
        "counts": {
            outcome: sum(item.outcome == outcome for item in items)
            for outcome in ("improved", "neutral", "regressed")
        },
        "mean_margin": round(sum(margins) / len(margins), 6),
        "min_margin": round(min(margins), 6),
        "max_margin": round(max(margins), 6),
        "matched_scores": sum(item.matched_score_count for item in items),
        "observation_digests": sorted(item.observation_digest for item in items),
    }


def build_tree_revision_failure_evidence(
    values: Iterable[TreeRevisionObservation | Mapping[str, Any]],
    *,
    reference: str,
    agent_id: str,
    pattern_key: str,
    weakness: str,
    verified_by: str,
    verification_reference: str,
    observed_on: str = "",
    min_regressions: int = 2,
) -> RevisionEvidenceRecord:
    """Convert repeated, distinct-session tree regressions to Identity evidence."""
    items = _observations(values)
    target = clean_agent(agent_id)
    if str(verified_by or "").strip().casefold() == target.casefold():
        raise ValueError("an agent cannot verify its own tree evidence")
    if min_regressions < 2 or len(items) < min_regressions:
        raise ValueError("tree failure evidence needs repeated regressions")
    if any(item.agent_id != target for item in items):
        raise ValueError("tree failure evidence mixes different agents")
    if any(item.outcome != "regressed" or item.margin >= 0 for item in items):
        raise ValueError("tree failure evidence accepts only concrete regressions")
    sessions = [item.session_id for item in items]
    traces = [item.source_trace for item in items]
    if len(set(sessions)) != len(sessions):
        raise ValueError("tree failure evidence requires distinct sessions")
    if len(set(traces)) != len(traces):
        raise ValueError("tree failure evidence requires distinct source traces")

    report_digest = digest({
        "kind": "tree_revision_failure",
        "pattern_key": pattern_key,
        "weakness": weakness,
        "summary": summarize_tree_revision_observations(items, agent_id=target),
        "observations": [item.to_record() for item in items],
    })
    report = {
        "schema_version": IDENTITY_FAILURE_REPORT_VERSION,
        "reference": reference,
        "agent_id": target,
        "pattern_key": pattern_key,
        "weakness": weakness,
        "observations": [
            {
                "session_id": item.session_id,
                "attributed_agent_id": target,
                "pattern_key": pattern_key,
                "attribution_verified": True,
                "source_trace": item.source_trace,
            }
            for item in items
        ],
        "source": f"{TREE_EVIDENCE_SOURCE}/failure/{report_digest[:16]}",
        "verified_by": verified_by,
        "verification_reference": verification_reference,
        "observed_on": observed_on,
    }
    return build_identity_failure_evidence(report, min_occurrences=min_regressions)


def build_tree_revision_resolution_evidence(
    before_values: Iterable[TreeRevisionObservation | Mapping[str, Any]],
    after_values: Iterable[TreeRevisionObservation | Mapping[str, Any]],
    *,
    reference: str,
    agent_id: str,
    pattern_key: str,
    weakness: str,
    verified_by: str,
    verification_reference: str,
    observed_on: str = "",
    min_window: int = 2,
) -> RevisionEvidenceRecord:
    """Build matched resolution evidence: regressions before, improvements after."""
    before = _observations(before_values)
    after = _observations(after_values)
    target = clean_agent(agent_id)
    if str(verified_by or "").strip().casefold() == target.casefold():
        raise ValueError("an agent cannot verify its own tree evidence")
    if min_window < 2 or len(before) != len(after) or len(before) < min_window:
        raise ValueError("tree resolution windows must be equal and sufficiently large")
    if any(item.agent_id != target for item in before + after):
        raise ValueError("tree resolution evidence mixes different agents")
    if any(item.outcome != "regressed" or item.margin >= 0 for item in before):
        raise ValueError("tree resolution before-window must contain regressions")
    if any(item.outcome != "improved" or item.margin <= 0 for item in after):
        raise ValueError("tree resolution after-window must contain improvements")

    before_sessions = [item.session_id for item in before]
    after_sessions = [item.session_id for item in after]
    if len(set(before_sessions)) != len(before_sessions):
        raise ValueError("tree resolution before-window repeats sessions")
    if len(set(after_sessions)) != len(after_sessions):
        raise ValueError("tree resolution after-window repeats sessions")
    if set(before_sessions) & set(after_sessions):
        raise ValueError("tree resolution windows overlap")

    before_by_key = {item.comparison_key: item for item in before}
    after_by_key = {item.comparison_key: item for item in after}
    if len(before_by_key) != len(before) or len(after_by_key) != len(after):
        raise ValueError("tree resolution comparison keys must be unique per window")
    if set(before_by_key) != set(after_by_key):
        raise ValueError("tree resolution requires matched comparison keys")
    for key, left in before_by_key.items():
        right = after_by_key[key]
        if left.question_hash != right.question_hash:
            raise ValueError("tree resolution matched items use different questions")
        if left.provider_id != right.provider_id:
            raise ValueError("tree resolution matched items use different providers")
        if left.judge_ids != right.judge_ids:
            raise ValueError("tree resolution matched items use different judges")
        if left.matched_sections != right.matched_sections:
            raise ValueError("tree resolution matched items use different sections")
        if left.matched_score_count != right.matched_score_count:
            raise ValueError("tree resolution matched items use different score counts")
        if left.effect_margin != right.effect_margin:
            raise ValueError("tree resolution matched items use different effect margins")
        if left.tree_exploration != right.tree_exploration:
            raise ValueError("tree resolution matched items use different exploration")
        if left.tree_total_expansions != right.tree_total_expansions:
            raise ValueError("tree resolution matched items use different budgets")

    report_digest = digest({
        "kind": "tree_revision_resolution",
        "pattern_key": pattern_key,
        "weakness": weakness,
        "before": [item.to_record() for item in sorted(before, key=lambda x: x.comparison_key)],
        "after": [item.to_record() for item in sorted(after, key=lambda x: x.comparison_key)],
    })
    report = {
        "schema_version": IDENTITY_RESOLUTION_REPORT_VERSION,
        "reference": reference,
        "agent_id": target,
        "pattern_key": pattern_key,
        "weakness": weakness,
        "before_session_ids": before_sessions,
        "after_session_ids": after_sessions,
        "before_failures": len(before),
        "after_failures": 0,
        "matched_window": True,
        "source": f"{TREE_EVIDENCE_SOURCE}/resolution/{report_digest[:16]}",
        "verified_by": verified_by,
        "verification_reference": verification_reference,
        "observed_on": observed_on,
    }
    return build_identity_resolution_evidence(report, min_window=min_window)


__all__ = [
    "TREE_REVISION_OBSERVATION_VERSION",
    "TREE_EVIDENCE_SOURCE",
    "TreeRevisionObservation",
    "extract_tree_revision_observations",
    "summarize_tree_revision_observations",
    "build_tree_revision_failure_evidence",
    "build_tree_revision_resolution_evidence",
]
