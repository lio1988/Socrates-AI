"""
Deliberation Tree Search tests (docs/deliberation_tree/ARCHITECTURE.md).

Unit: the pure tree mechanism (UCB selection, backup, best node, amplification
gain, improvement pairs) — zero LLM/provider involvement.

Integration (mock council):
  - default OFF = byte-for-byte unchanged (no tree audit, no extra moves)
  - ON = enriched draft pool, TREE_REVISION moves, incremental scorecards,
    CED-owned audit present
  - never-worse: assembled per-section scores with the tree >= without it
    (same session_id on two separate orchestrators → deterministic mocks give
    identical original drafts/scores; the tree only ADDS candidates)
  - no leakage: the revision task context contains the parent draft's section
    texts and NO scores / tree statistics / draft ids / identities

No provider calls, no network, no keys.
"""

import asyncio
import json

import pytest

from backend.dialogues.deliberation_tree import DeliberationTree
from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode, TaskKind
from backend.dialogues.reasoning_prompts import build_reasoning_system_prompt
from backend.dialogues.models import AgentRole, DialogPhase


# --------------------------------------------------------------------------- #
# Unit: pure tree mechanism
# --------------------------------------------------------------------------- #

def test_select_prefers_higher_score():
    t = DeliberationTree()
    t.add_root_draft("draft_a", 8.0)
    t.add_root_draft("draft_b", 4.0)
    assert t.select() == "draft_a"


def test_first_selection_is_greedy():
    # ln(1 + 0) = 0 → the exploration term vanishes on the very first pick.
    t = DeliberationTree(exploration=100.0)
    t.add_root_draft("draft_a", 8.0)
    t.add_root_draft("draft_b", 7.9)
    assert t.select() == "draft_a"


def test_exploration_eventually_selects_second_best():
    t = DeliberationTree(exploration=5.0)   # heavy exploration
    t.add_root_draft("draft_a", 8.0)
    t.add_root_draft("draft_b", 4.0)
    picks = {t.select() for _ in range(4)}
    assert "draft_b" in picks


def test_zero_exploration_stays_greedy():
    t = DeliberationTree(exploration=0.0)
    t.add_root_draft("draft_a", 8.0)
    t.add_root_draft("draft_b", 7.0)
    assert all(t.select() == "draft_a" for _ in range(5))


def test_backup_updates_ancestors():
    t = DeliberationTree()
    t.add_root_draft("root", 6.0)
    t.attach("root", "child", 8.0)
    t.attach("child", "grandchild", 9.0)
    root = t.nodes["root"]
    # root subtree: own 6 + child 8 + grandchild 9
    assert root.visits == 3
    assert root.value_sum == pytest.approx(23.0)
    assert root.mean_value == pytest.approx(23.0 / 3)
    assert t.nodes["child"].visits == 2
    assert t.nodes["grandchild"].depth == 3


def test_best_node_and_amplification_gain():
    t = DeliberationTree()
    t.add_root_draft("draft_a", 8.0)
    t.add_root_draft("draft_b", 6.0)
    t.attach("draft_a", "rev_1", 9.2)
    best = t.best_node()
    assert best.node_id == "rev_1"
    assert t.amplification_gain() == pytest.approx(1.2)


def test_weaker_revision_gain_floors_at_zero():
    # Assembly works on a superset pool, so a weak revision costs nothing —
    # the gain is honestly floored at 0, and the best node stays the root.
    t = DeliberationTree()
    t.add_root_draft("draft_a", 8.0)
    t.attach("draft_a", "rev_1", 5.0)
    assert t.best_node().node_id == "draft_a"
    assert t.amplification_gain() == 0.0


def test_unscored_nodes_never_win():
    t = DeliberationTree()
    t.add_root_draft("draft_a", 7.0)
    t.attach("draft_a", "rev_unscored", None)   # every peer score failed
    assert t.best_node().node_id == "draft_a"
    audit = t.audit()
    assert audit["best_draft_id"] == "draft_a"


def test_improvement_pairs_margin_gated():
    t = DeliberationTree()
    t.add_root_draft("draft_a", 7.0)
    t.attach("draft_a", "rev_big", 8.5)     # +1.5 → pair
    t.attach("draft_a", "rev_small", 7.4)   # +0.4 → below default margin
    pairs = t.improvement_pairs(min_margin=1.0)
    assert pairs == [("rev_big", "draft_a", 1.5)]


def test_audit_shape():
    t = DeliberationTree()
    t.add_root_draft("draft_a", 8.0)
    t.select()
    t.attach("draft_a", "rev_1", 8.6)
    audit = t.audit()
    for key in ("enabled", "node_count", "root_count", "revision_count",
                "max_depth", "total_expansions", "best_draft_id",
                "best_own_score", "best_root_score", "amplification_gain",
                "improvement_pairs"):
        assert key in audit
    assert audit["enabled"] is True
    assert audit["node_count"] == 2
    assert audit["revision_count"] == 1
    assert audit["max_depth"] == 2


# --------------------------------------------------------------------------- #
# Integration: mock council
# --------------------------------------------------------------------------- #

def _run(session_id, question="Τι είναι η γνώση;", **kw):
    ced, _ = build_council(
        council_size=2, shadow_scoring_mode=ShadowScoringMode.OFF, **kw)
    ced.debug_task_log = True
    final = asyncio.run(ced.run_registry_session(question, session_id=session_id))
    return ced, final, ced.get_session(session_id)


def test_default_off_no_tree():
    ced, final, state = _run("tree_off_1")
    assert ced.tree_expansions == 0
    assert final.audit_summary["deliberation_tree"] == {"enabled": False}
    kinds = {m.task_kind for m in state.moves if m.task_kind}
    assert TaskKind.TREE_REVISION not in kinds
    assert len(state.section_drafts) == 2    # council_size drafts, nothing more


def test_tree_on_enriches_pool():
    ced, final, state = _run("tree_on_1", tree_expansions=2)
    revisions = [m for m in state.moves if m.task_kind == TaskKind.TREE_REVISION]
    assert len(revisions) == 2
    assert len(state.section_drafts) == 4    # 2 originals + 2 revisions
    audit = final.audit_summary["deliberation_tree"]
    assert audit["enabled"] is True
    assert audit["revision_count"] == 2
    assert audit["total_expansions"] == 2
    assert len(audit["expansion_log"]) == 2
    assert all(e["ok"] for e in audit["expansion_log"])
    # Revisions were peer-scored through the normal path (incremental cards).
    scored_ids = {ss.draft_id for card in state.draft_scorecards
                  for ss in card.section_scores}
    for m in revisions:
        assert f"draft_{m.move_id}" in scored_ids


def test_tree_never_worse_than_one_shot():
    # Same session_id + question on two SEPARATE orchestrators → deterministic
    # mocks produce identical original drafts and scores. The tree run's pool is
    # a superset, so every assembled section's winning score must be >= baseline.
    _, base_final, base_state = _run("tree_cmp")
    _, tree_final, tree_state = _run("tree_cmp", tree_expansions=3)
    base = {s.section_name: s for s in base_state.assembled_answer.sections}
    tree = {s.section_name: s for s in tree_state.assembled_answer.sections}
    assert set(base) == set(tree)
    for name in base:
        assert tree[name].average_score >= base[name].average_score


def test_revision_context_has_parent_sections_and_no_leaks():
    ced, final, state = _run("tree_leak_1", tree_expansions=2)
    entries = [e for e in state.task_log
               if e.task_kind == TaskKind.TREE_REVISION]
    assert len(entries) == 2
    forbidden = ("average_score", "amplification", "visit", "ucb",
                 "value_sum", "leaderboard", "score_count", "draft_id",
                 "expansions", "scorecard")
    for e in entries:
        ctx = e.debug_context or {}
        draft = ctx.get("draft_under_revision")
        assert isinstance(draft, dict)
        assert set(draft.keys()) == {"core_answer", "crucial_stress_test",
                                     "blind_spots", "nuance", "final_verdict"}
        blob = json.dumps(ctx, ensure_ascii=False, default=str)
        for token in forbidden:
            assert token not in blob, f"revision context leaked {token!r}"


def test_failed_revision_never_fabricated():
    # A tree with no adapters/authors can't happen in a real session; instead
    # verify the audit records honest per-expansion outcomes and that the
    # revision count always equals the number of ok expansions.
    ced, final, state = _run("tree_honest_1", tree_expansions=2)
    audit = final.audit_summary["deliberation_tree"]
    ok = sum(1 for e in audit["expansion_log"] if e["ok"])
    assert audit["revision_count"] == ok


def test_build_council_passthrough():
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           tree_expansions=3, tree_exploration=0.9)
    assert ced.tree_expansions == 3
    assert ced.tree_exploration == pytest.approx(0.9)


def test_negative_expansions_rejected():
    with pytest.raises(ValueError):
        build_council(council_size=2, tree_expansions=-1)


def test_tree_revision_prompt_includes_synthesis_contract():
    prompt = build_reasoning_system_prompt(
        AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS, TaskKind.TREE_REVISION)
    assert "core_answer" in prompt                 # 5-section contract present
    assert "draft_under_revision" in prompt        # revision mandate present
    # Judging anonymity untouched: a revision is a deliberation task, so the
    # telos directive applies (it is NOT an evaluative kind).
    score_prompt = build_reasoning_system_prompt(
        AgentRole.FINAL_EVALUATOR, None, TaskKind.SECTION_SCORE)
    assert "draft_under_revision" not in score_prompt


def test_trace_capture_records_tree_moves():
    # The layers compose: OpenClaw traces automatically include tree revisions.
    from backend.dialogues.openclaw_memory import TraceCapturer
    capturer = TraceCapturer()
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           tree_expansions=1, trace_capturer=capturer)
    asyncio.run(ced.run_registry_session("test", session_id="tree_trace_1"))
    trace = capturer.latest_trace()
    kinds = {m.get("task_kind") for m in trace["moves"]}
    assert "tree_revision" in kinds
