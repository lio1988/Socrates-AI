"""
Tree distillation tests — the AlphaGo DISTILL step
(docs/deliberation_tree/ARCHITECTURE.md §1 row 4 and §6.1).

Search trajectories (expansion_log: who revised whom) where the revision BEAT
its parent by a real recomputed peer-score margin become whole-draft preference
pairs in the Phase 22 TrainingCorpus: chosen = the search-discovered draft,
rejected = the one-shot draft, prompt = the same question. Training on these
compresses the amplified behavior back into the base policy.

Verifies:
  - trajectory extraction with margins recomputed from REAL scorecards
    (never trusted second-hand from the audit)
  - margin gating with the corpus's own min_margin
  - failed expansions / unscored / missing drafts never produce a pair
  - no tree = zero tree pairs, existing corpus behavior byte-identical
  - schema stays teacher_corpus_v0 (provenance is additive with a default)
  - end-to-end: mock council with tree_expansions + training_corpus composes

No provider calls, no network, no keys.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.training import (
    PreferencePair,
    TrainingCorpus,
    harvest_tree_preferences,
)
from backend.training.corpus import TREE_PREF_PROMPT
from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode


# --------------------------------------------------------------------------- #
# Duck-typed session fixtures (only the attributes the harvester reads)
# --------------------------------------------------------------------------- #

def _draft(draft_id, text):
    return SimpleNamespace(
        draft_id=draft_id,
        core_answer=f"{text} core", crucial_stress_test=f"{text} stress",
        blind_spots=f"{text} blind", nuance=f"{text} nuance",
        final_verdict=f"{text} verdict")


def _card(draft_id, scores):
    return SimpleNamespace(section_scores=[
        SimpleNamespace(draft_id=draft_id, overall_score=s) for s in scores])


def _state(drafts, cards, sid="dist_s1", question="Ti einai h areth;"):
    return SimpleNamespace(session_id=sid, question=question,
                           section_drafts=drafts, draft_scorecards=cards)


def _final(expansion_log):
    return SimpleNamespace(audit_summary={
        "deliberation_tree": {"enabled": True, "expansion_log": expansion_log}})


# --------------------------------------------------------------------------- #
# Trajectory extraction
# --------------------------------------------------------------------------- #

def test_improving_trajectory_becomes_pair():
    state = _state(
        drafts=[_draft("d_parent", "old"), _draft("d_child", "new")],
        cards=[_card("d_parent", [6.0, 6.0]), _card("d_child", [8.0, 8.0])])
    final = _final([{"parent": "d_parent", "child": "d_child", "ok": True}])
    pairs = harvest_tree_preferences(state, final, min_margin=1.0)
    assert len(pairs) == 1
    p = pairs[0]
    assert p.provenance == "tree_revision"
    assert p.section == "full_draft"
    assert p.margin == pytest.approx(2.0)              # 8 − 6, recomputed
    assert p.prompt == TREE_PREF_PROMPT.format(question=state.question)
    assert json.loads(p.chosen)["core_answer"] == "new core"
    assert json.loads(p.rejected)["core_answer"] == "old core"
    assert p.source_session == "dist_s1"


def test_margin_recomputed_from_real_scorecards_not_audit():
    # The audit could carry any cached numbers — only scorecards count.
    state = _state(
        drafts=[_draft("d_p", "a"), _draft("d_c", "b")],
        cards=[_card("d_p", [7.0]), _card("d_c", [7.5])])   # real gap 0.5
    final = _final([{"parent": "d_p", "child": "d_c", "ok": True,
                     "child_score": 99.0}])                 # lying cache
    assert harvest_tree_preferences(state, final, min_margin=1.0) == []
    pairs = harvest_tree_preferences(state, final, min_margin=0.5)
    assert len(pairs) == 1 and pairs[0].margin == pytest.approx(0.5)


def test_worse_revision_never_becomes_pair():
    state = _state(
        drafts=[_draft("d_p", "good"), _draft("d_c", "worse")],
        cards=[_card("d_p", [8.0]), _card("d_c", [5.0])])
    final = _final([{"parent": "d_p", "child": "d_c", "ok": True}])
    assert harvest_tree_preferences(state, final, min_margin=1.0) == []


def test_failed_expansion_skipped():
    state = _state(drafts=[_draft("d_p", "x")], cards=[_card("d_p", [7.0])])
    final = _final([{"parent": "d_p", "ok": False, "provider_id": "m0"}])
    assert harvest_tree_preferences(state, final) == []


def test_unscored_child_skipped():
    # A revision whose every peer score failed has no real margin — no pair.
    state = _state(
        drafts=[_draft("d_p", "a"), _draft("d_c", "b")],
        cards=[_card("d_p", [7.0])])                        # child unscored
    final = _final([{"parent": "d_p", "child": "d_c", "ok": True}])
    assert harvest_tree_preferences(state, final) == []


def test_no_tree_audit_returns_empty():
    state = _state(drafts=[_draft("d_p", "a")], cards=[_card("d_p", [7.0])])
    final = SimpleNamespace(audit_summary={})
    assert harvest_tree_preferences(state, final) == []
    final_off = SimpleNamespace(audit_summary={"deliberation_tree": {"enabled": False}})
    assert harvest_tree_preferences(state, final_off) == []


def test_multi_step_trajectory_yields_pair_per_improving_edge():
    # parent -> child1 (improves) -> child2 (improves further): two edges.
    state = _state(
        drafts=[_draft("d_p", "v0"), _draft("d_c1", "v1"), _draft("d_c2", "v2")],
        cards=[_card("d_p", [5.0]), _card("d_c1", [6.5]), _card("d_c2", [8.0])])
    final = _final([
        {"parent": "d_p", "child": "d_c1", "ok": True},
        {"parent": "d_c1", "child": "d_c2", "ok": True},
    ])
    pairs = harvest_tree_preferences(state, final, min_margin=1.0)
    assert len(pairs) == 2
    assert {(json.loads(p.rejected)["core_answer"],
             json.loads(p.chosen)["core_answer"]) for p in pairs} == {
        ("v0 core", "v1 core"), ("v1 core", "v2 core")}


# --------------------------------------------------------------------------- #
# Corpus integration (schema, stats, dedupe stay intact)
# --------------------------------------------------------------------------- #

def test_provenance_is_additive_with_default():
    p = PreferencePair(prompt="p", chosen="a", rejected="b", margin=2.0,
                       section="core_answer", source_session="s")
    assert p.provenance == "section_score"     # old constructions untouched


def test_corpus_counts_tree_pairs_in_stats(tmp_path):
    corpus = TrainingCorpus(min_margin=1.0)
    state = _state(
        drafts=[_draft("d_p", "old"), _draft("d_c", "new")],
        cards=[_card("d_p", [6.0]), _card("d_c", [8.0])])
    # Minimal final that satisfies the full harvest path.
    final = SimpleNamespace(
        ratified=False, synthesis=None,
        audit_summary={"deliberation_tree": {
            "enabled": True,
            "expansion_log": [{"parent": "d_p", "child": "d_c", "ok": True}]}})
    state.assembled_answer = None              # skip section-pair harvest
    state.moves_for_phase = lambda phase: []
    added = corpus.ingest_session(state, final)
    assert added["preferences_added"] == 1
    stats = corpus.stats()
    assert stats["schema_version"] == "teacher_corpus_v0"    # unchanged
    assert stats["tree_preference_pairs"] == 1
    assert stats["preferences_by_section"].get("full_draft") == 1
    # Dedupe: identical session re-ingested adds nothing.
    assert corpus.ingest_session(state, final)["preferences_added"] == 0
    # Export carries provenance in the JSONL rows.
    paths = corpus.save(str(tmp_path))
    rows = [json.loads(l) for l in open(paths["preferences"], encoding="utf-8")]
    assert rows and rows[0]["provenance"] == "tree_revision"


# --------------------------------------------------------------------------- #
# End-to-end: mock council + tree + corpus compose
# --------------------------------------------------------------------------- #

def test_e2e_tree_session_feeds_corpus():
    corpus = TrainingCorpus(min_margin=0.0)    # mock margins may be tiny
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           tree_expansions=2, training_corpus=corpus)
    final = asyncio.run(ced.run_registry_session(
        "test distillation", session_id="dist_e2e"))
    assert final.audit_summary["deliberation_tree"]["enabled"] is True
    # Every harvested tree pair is a real improving trajectory.
    tree_pairs = [p for p in corpus.preference_pairs()
                  if p.provenance == "tree_revision"]
    for p in tree_pairs:
        assert p.margin >= 0.0
        assert p.section == "full_draft"
        assert json.loads(p.chosen) != json.loads(p.rejected)
    assert corpus.stats()["tree_preference_pairs"] == len(tree_pairs)


def test_e2e_without_tree_no_tree_pairs():
    corpus = TrainingCorpus(min_margin=0.0)
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           training_corpus=corpus)
    asyncio.run(ced.run_registry_session("test", session_id="dist_off"))
    assert corpus.stats()["tree_preference_pairs"] == 0
    assert all(p.provenance == "section_score" for p in corpus.preference_pairs())
