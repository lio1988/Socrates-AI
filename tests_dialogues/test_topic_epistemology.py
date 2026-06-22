"""
Phase 6 — Epistemology topic awareness + draft diversity.

Covers:
  - topic classification for epistemology questions
  - final-response relevance (mentions Gettier / anti-luck / necessary-sufficient,
    avoids scientific-causality language)
  - meaningfully different synthesizer drafts
"""

import pytest

from backend.dialogues.topic import Topic, classify_topic
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


EPI_Q = "Is knowledge merely justified true belief?"

RELEVANT_TERMS = [
    "gettier", "anti-luck", "reliability", "reliabilis", "defeater",
    "necessary", "sufficient", "justified true belief",
]
FORBIDDEN_TERMS = [
    "correlation", "causation", "effect size", "sample characteristic",
    "underlying studies", "causal mechanism",
]


def _make_ced(n: int = 4) -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


# ── Topic classification ──────────────────────────────────────────────────────

@pytest.mark.parametrize("question", [
    "Is knowledge merely justified true belief?",
    "Gettier problem",
    "What is justification?",
    "Does reliabilism solve the Gettier problem?",
    "Is knowledge possible under radical skepticism?",
])
def test_epistemology_questions_classified(question):
    assert classify_topic(question) == Topic.EPISTEMOLOGY


def test_non_epistemology_questions_not_misclassified():
    assert classify_topic("Is mathematics discovered or invented?") == \
        Topic.MATHEMATICS_PHILOSOPHY
    assert classify_topic("What is the nature of time?") == Topic.GENERAL
    assert classify_topic("") == Topic.GENERAL


# ── Final-response relevance ──────────────────────────────────────────────────

def test_epistemology_final_answer_is_domain_relevant():
    ced = _make_ced()
    final = ced.run_session(EPI_Q, session_id="epi-relevance")
    answer = final.answer.lower()

    assert any(t in answer for t in RELEVANT_TERMS), (
        f"Epistemology answer should mention at least one of {RELEVANT_TERMS}; "
        f"got: {final.answer[:200]}"
    )


def test_epistemology_final_answer_avoids_causality_language():
    ced = _make_ced()
    final = ced.run_session(EPI_Q, session_id="epi-no-causal")
    answer = final.answer.lower()

    for term in FORBIDDEN_TERMS:
        assert term not in answer, (
            f"Epistemology answer must not contain scientific-causality term '{term}'."
        )


def test_epistemology_dialogue_mentions_gettier():
    """Across the council moves, Gettier should surface (Socrates/critic/etc.)."""
    ced = _make_ced()
    ced.run_session(EPI_Q, session_id="epi-gettier")
    state = ced.get_session("epi-gettier")
    blob = " ".join(str(m.content) for m in state.moves).lower()
    assert "gettier" in blob


# ── Draft diversity ───────────────────────────────────────────────────────────

def test_four_synthesizer_drafts_are_not_identical():
    ced = _make_ced(4)
    ced.run_session(EPI_Q, session_id="epi-diversity")
    drafts = ced.get_session("epi-diversity").section_drafts

    assert len(drafts) == 4
    assert len(set(d.core_answer for d in drafts)) > 1
    assert len(set(d.crucial_stress_test for d in drafts)) > 1
    assert len(set(d.final_verdict for d in drafts)) > 1


def test_each_perspective_stays_5_section():
    ced = _make_ced(4)
    ced.run_session(EPI_Q, session_id="epi-5sec")
    for d in ced.get_session("epi-5sec").section_drafts:
        for field in ("core_answer", "crucial_stress_test", "blind_spots",
                      "nuance", "final_verdict"):
            assert getattr(d, field).strip(), f"{field} must be non-empty."


# ── Determinism preserved ─────────────────────────────────────────────────────

def test_fakeprovider_is_deterministic():
    """Same inputs → same output (FakeProvider must stay deterministic)."""
    p = FakeProvider()
    schema = {"_role": "synthesizer", "_sections": True, "_question": EPI_Q}
    a = p.complete("sys", "usr", dict(schema), agent_id="agent_1")
    b = p.complete("sys", "usr", dict(schema), agent_id="agent_1")
    assert a == b

    score_schema = {"_role": "__section_score__", "_target": "draft_x",
                    "_section": "core_answer", "_question": EPI_Q}
    s1 = p.complete("sys", "On Gettier, anti-luck and reliability...", dict(score_schema), agent_id="agent_2")
    s2 = p.complete("sys", "On Gettier, anti-luck and reliability...", dict(score_schema), agent_id="agent_2")
    assert s1 == s2


def test_epistemology_relevant_and_ratified_across_runs():
    """
    Section winners vary across runs (move_ids are random by design), but every
    run must stay domain-relevant and ratified.
    """
    for i in range(3):
        ced = _make_ced()
        final = ced.run_session(EPI_Q, session_id=f"epi-run-{i}")
        answer = final.answer.lower()
        assert final.ratified is True
        assert any(t in answer for t in RELEVANT_TERMS)
        assert not any(t in answer for t in FORBIDDEN_TERMS)


def test_epistemology_scores_stay_on_0_to_10():
    ced = _make_ced()
    ced.run_session(EPI_Q, session_id="epi-scale")
    state = ced.get_session("epi-scale")
    for ms in state.micro_scores:
        assert 0.0 <= ms.overall_score <= 10.0
    for card in state.draft_scorecards:
        for ss in card.section_scores:
            assert 0.0 <= ss.overall_score <= 10.0
