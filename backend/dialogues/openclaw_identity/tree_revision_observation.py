"""Extract strict per-agent observations from completed tree sessions."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .tree_revision_schema import (
    TreeRevisionObservation,
    clean_agent,
    clean_id,
    clean_text,
    digest,
    enum_text,
    finite_score,
    status_ok,
)


def _draft_scores(state: Any, draft: Any) -> Dict[Tuple[str, str], float]:
    session_id = clean_id(state.session_id, field="session_id")
    draft_id = clean_id(draft.draft_id, field="draft_id")
    author = clean_agent(draft.author_agent_id, field="author_agent_id")
    result: Dict[Tuple[str, str], float] = {}
    for card in getattr(state, "draft_scorecards", ()) or ():
        if str(getattr(card, "draft_id", "")) != draft_id:
            continue
        if str(getattr(card, "session_id", "")) != session_id:
            raise ValueError("tree scorecard belongs to another session")
        if str(getattr(card, "author_agent_id", "")) != author:
            raise ValueError("tree scorecard author mismatch")
        voter = clean_id(getattr(card, "voter_agent_id", ""), field="voter_agent_id")
        if voter == author:
            raise ValueError("tree evidence refuses self-scored drafts")
        if not status_ok(getattr(card, "provider_status", "ok")):
            if getattr(card, "section_scores", ()):
                raise ValueError("non-OK scorecard contains accepted scores")
            continue
        for score in getattr(card, "section_scores", ()) or ():
            if str(getattr(score, "session_id", "")) != session_id:
                raise ValueError("tree section score session mismatch")
            if str(getattr(score, "draft_id", "")) != draft_id:
                raise ValueError("tree section score draft mismatch")
            if str(getattr(score, "author_agent_id", "")) != author:
                raise ValueError("tree section score author mismatch")
            if str(getattr(score, "voter_agent_id", "")) != voter:
                raise ValueError("tree section score voter mismatch")
            if not status_ok(getattr(score, "provider_status", "ok")):
                continue
            section = clean_text(
                enum_text(getattr(score, "section_name", "")),
                field="section_name", maximum=64,
            )
            key = (voter, section)
            if key in result:
                raise ValueError("duplicate tree judge-section score")
            result[key] = finite_score(
                getattr(score, "overall_score", None), field="overall_score")
    return result


def _audit_maps(state: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    moves: Dict[str, Any] = {}
    tasks: Dict[str, Any] = {}
    for move in getattr(state, "moves", ()) or ():
        move_id = str(getattr(move, "move_id", "") or "").strip()
        if move_id:
            if move_id in moves:
                raise ValueError("duplicate move_id in tree session")
            moves[move_id] = move
    for entry in getattr(state, "task_log", ()) or ():
        move_id = str(getattr(entry, "move_id", "") or "").strip()
        if move_id:
            if move_id in tasks:
                raise ValueError("duplicate task-log move_id in tree session")
            tasks[move_id] = entry
    return moves, tasks


def _verify_child_attribution(
    child: Any,
    moves: Mapping[str, Any],
    tasks: Mapping[str, Any],
) -> None:
    move_id = clean_id(getattr(child, "move_id", ""), field="child_move_id")
    move = moves.get(move_id)
    task = tasks.get(move_id)
    if move is None or task is None:
        raise ValueError("tree revision child lacks move/task audit records")
    author = str(getattr(child, "author_agent_id", ""))
    provider = str(getattr(child, "provider_id", "") or "").strip()
    for record, label in ((move, "move"), (task, "task log")):
        if enum_text(getattr(record, "task_kind", "")) != "tree_revision":
            raise ValueError(f"tree revision {label} has wrong task_kind")
        if enum_text(getattr(record, "phase", "")) != "synthesis":
            raise ValueError(f"tree revision {label} has wrong phase")
        if str(getattr(record, "agent_id", "")) != author:
            raise ValueError(f"tree revision {label} attribution mismatch")
        if str(getattr(record, "provider_id", "") or "").strip() != provider:
            raise ValueError(f"tree revision {label} provider mismatch")


def extract_tree_revision_observations(
    state: Any,
    final: Any,
    *,
    comparison_key: Optional[str] = None,
    effect_margin: float = 0.5,
    min_matched_scores: int = 1,
) -> Tuple[TreeRevisionObservation, ...]:
    """Recompute matched parent/child margins from a completed CED tree session."""
    if isinstance(effect_margin, bool) or not isinstance(effect_margin, (int, float)):
        raise ValueError("effect_margin must be numeric")
    if not math.isfinite(float(effect_margin)) or effect_margin <= 0:
        raise ValueError("effect_margin must be finite and positive")
    if isinstance(min_matched_scores, bool) or not isinstance(min_matched_scores, int):
        raise ValueError("min_matched_scores must be an integer")
    if min_matched_scores < 1:
        raise ValueError("min_matched_scores must be positive")

    session_id = clean_id(getattr(state, "session_id", ""), field="session_id")
    question = clean_text(getattr(state, "question", ""), field="question", maximum=20000)
    question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
    comparison = clean_text(
        comparison_key or f"question:{question_hash}", field="comparison_key")

    audit = getattr(final, "audit_summary", None) or {}
    if not isinstance(audit, Mapping):
        raise ValueError("final audit_summary must be a mapping")
    tree = audit.get("deliberation_tree") or {}
    if not tree or tree.get("enabled") is not True:
        return ()
    log = tree.get("expansion_log") or []
    if isinstance(log, (str, bytes)) or not isinstance(log, Sequence):
        raise ValueError("tree expansion_log must be a sequence")
    raw_exploration = tree.get("exploration", 0.0)
    if isinstance(raw_exploration, bool):
        raise ValueError("tree exploration is invalid")
    exploration = float(raw_exploration)
    if not math.isfinite(exploration) or exploration < 0:
        raise ValueError("tree exploration is invalid")
    total = tree.get("total_expansions", len(log))
    if isinstance(total, bool) or not isinstance(total, int) or total != len(log):
        raise ValueError("tree total_expansions does not match expansion_log")

    drafts: Dict[str, Any] = {}
    for draft in getattr(state, "section_drafts", ()) or ():
        draft_id = clean_id(getattr(draft, "draft_id", ""), field="draft_id")
        if draft_id in drafts:
            raise ValueError("duplicate draft_id in tree session")
        if str(getattr(draft, "session_id", session_id)) != session_id:
            raise ValueError("tree draft belongs to another session")
        drafts[draft_id] = draft
    moves, tasks = _audit_maps(state)

    observations = []
    seen_children = set()
    for entry in log:
        if not isinstance(entry, Mapping):
            raise ValueError("tree expansion entry must be a mapping")
        if entry.get("ok") is not True:
            continue
        parent_id = clean_id(entry.get("parent", ""), field="parent_draft_id")
        child_id = clean_id(entry.get("child", ""), field="child_draft_id")
        if child_id in seen_children:
            raise ValueError("tree expansion_log repeats a child draft")
        seen_children.add(child_id)
        if parent_id not in drafts or child_id not in drafts:
            raise ValueError("tree expansion references a missing draft")
        parent, child = drafts[parent_id], drafts[child_id]
        _verify_child_attribution(child, moves, tasks)

        parent_scores = _draft_scores(state, parent)
        child_scores = _draft_scores(state, child)
        matched = sorted(set(parent_scores) & set(child_scores))
        if len(matched) < min_matched_scores:
            continue
        parent_mean = sum(parent_scores[key] for key in matched) / len(matched)
        child_mean = sum(child_scores[key] for key in matched) / len(matched)
        margin = child_mean - parent_mean
        outcome = (
            "improved" if margin >= effect_margin
            else "regressed" if margin <= -effect_margin
            else "neutral"
        )
        payload = [
            {
                "judge_id": judge,
                "section": section,
                "parent": round(parent_scores[(judge, section)], 6),
                "child": round(child_scores[(judge, section)], 6),
            }
            for judge, section in matched
        ]
        score_digest = digest(payload)
        agent_id = clean_agent(getattr(child, "author_agent_id", ""))
        provider_id = str(getattr(child, "provider_id", "") or "").strip()
        trace_digest = digest({
            "session_id": session_id,
            "comparison_key": comparison,
            "agent_id": agent_id,
            "provider_id": provider_id,
            "parent": parent_id,
            "child": child_id,
            "scorecard_digest": score_digest,
        })
        observations.append(TreeRevisionObservation(
            session_id=session_id,
            comparison_key=comparison,
            question_hash=question_hash,
            agent_id=agent_id,
            provider_id=provider_id,
            parent_draft_id=parent_id,
            child_draft_id=child_id,
            parent_score=round(parent_mean, 6),
            child_score=round(child_mean, 6),
            margin=round(margin, 6),
            effect_margin=float(effect_margin),
            outcome=outcome,
            matched_score_count=len(matched),
            judge_ids=tuple(judge for judge, _ in matched),
            matched_sections=tuple(section for _, section in matched),
            tree_exploration=exploration,
            tree_total_expansions=max(total, 1),
            scorecard_digest=score_digest,
            source_trace=f"ced-tree://{session_id}/{child_id}#{trace_digest[:16]}",
        ))
    return tuple(sorted(
        observations,
        key=lambda item: (item.session_id, item.child_draft_id, item.agent_id),
    ))


__all__ = ["extract_tree_revision_observations"]
