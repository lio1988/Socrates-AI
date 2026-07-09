"""
OpenClaw Memory Lessons — lesson retriever tests (Goal 3).

Deterministic relevance retrieval only. No provider calls, no network, no keys.
Verifies the acceptance criteria from FUTURE_GOALS.md Goal 3:
  - exact-output tasks retrieve LESSON-0001
  - synthesis tasks retrieve synthesis lessons
  - evidence-verifier role retrieves unsupported-claim lessons
  - retrieval remains deterministic
"""

import inspect
import io
import tokenize

import pytest

from backend.dialogues.models import AgentRole, DialogPhase, PenaltyFlag, TaskKind
from backend.dialogues.openclaw_memory import (
    RetrievedLesson,
    load_memory_lessons,
    retrieve_for_task,
    retrieve_lessons,
    score_lesson,
)
from backend.dialogues.openclaw_memory import lesson_retriever


def _ids(results):
    return [r.lesson_id for r in results]


# --------------------------------------------------------------------------- #
# Acceptance criteria
# --------------------------------------------------------------------------- #

def test_exact_output_task_retrieves_lesson_0001():
    results = retrieve_for_task(task_text="Answer with exactly one word: yes or no.")
    assert "LESSON-0001" in _ids(results)
    # exact-output signal should make it the top hit
    assert results[0].lesson_id == "LESSON-0001"


def test_synthesis_phase_retrieves_synthesis_lessons():
    results = retrieve_for_task(phase=DialogPhase.SYNTHESIS)
    ids = _ids(results)
    # both stable/verified synthesis-quality lessons
    assert "LESSON-0002" in ids
    assert "LESSON-0006" in ids
    assert all(r.lesson.lesson_type == "synthesis_quality" for r in results)


def test_evidence_verifier_role_retrieves_unsupported_claim_lesson():
    # design-doc role name
    doc = retrieve_for_task(role="evidence_verifier")
    assert "LESSON-0003" in _ids(doc)

    # code enum equivalent (empiricist)
    enum = retrieve_for_task(role=AgentRole.EMPIRICIST)
    assert "LESSON-0003" in _ids(enum)


def test_retrieval_is_deterministic():
    a = retrieve_for_task(phase=DialogPhase.SYNTHESIS, task_text="assemble the final draft")
    b = retrieve_for_task(phase=DialogPhase.SYNTHESIS, task_text="assemble the final draft")
    assert _ids(a) == _ids(b)
    assert [r.score for r in a] == [r.score for r in b]


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #

def test_failure_tag_is_strongest_signal():
    # A prior unsupported_claim failure should push LESSON-0003 to the top,
    # outweighing an unrelated synthesis phase.
    results = retrieve_for_task(
        phase=DialogPhase.SYNTHESIS,
        failure_tags=[PenaltyFlag.UNSUPPORTED_CLAIM],
    )
    assert results[0].lesson_id == "LESSON-0003"
    assert results[0].score >= lesson_retriever.WEIGHT_FAILURE_TAG


def test_failure_tag_accepts_plain_strings():
    results = retrieve_for_task(failure_tags=["overconfidence"])
    # overconfidence -> uncertainty_control -> LESSON-0004
    assert "LESSON-0004" in _ids(results)


def test_task_kind_signal():
    results = retrieve_for_task(task_kind=TaskKind.SYNTHESIS_DRAFT)
    assert {"LESSON-0002", "LESSON-0006"} <= set(_ids(results))


def test_reasons_are_recorded_for_audit():
    results = retrieve_for_task(role=AgentRole.EMPIRICIST, task_text="check the evidence")
    top = next(r for r in results if r.lesson_id == "LESSON-0003")
    joined = " ".join(top.reasons)
    assert "role:empiricist->unsupported_claim" in joined
    assert "keywords:" in joined


# --------------------------------------------------------------------------- #
# Guards: no dump, cap, pool
# --------------------------------------------------------------------------- #

def test_irrelevant_query_returns_nothing():
    # No matching signal at all -> empty (never pad with unrelated lessons).
    results = retrieve_for_task(task_text="the weather in Lisbon on Tuesday")
    assert results == []


def test_max_lessons_is_capped():
    results = retrieve_for_task(
        role=AgentRole.EMPIRICIST,
        phase=DialogPhase.ELENCHUS,
        task_text="evidence support uncertainty synthesis section",
        max_lessons=2,
    )
    assert len(results) <= 2


def test_max_lessons_must_be_positive():
    with pytest.raises(ValueError):
        retrieve_for_task(role=AgentRole.EMPIRICIST, max_lessons=0)


def test_default_pool_excludes_proposed_lessons():
    # LESSON-0010 (ratification_quality) is *proposed*; the stable default pool
    # must not surface it even though final_evaluator maps to ratification.
    stable = retrieve_for_task(role=AgentRole.FINAL_EVALUATOR)
    assert "LESSON-0010" not in _ids(stable)

    # But an explicit full pool can include it.
    full = retrieve_for_task(
        role=AgentRole.FINAL_EVALUATOR,
        lessons=load_memory_lessons(),  # all non-deprecated, incl. proposed
    )
    assert "LESSON-0010" in _ids(full)


def test_explicit_pool_is_ranked_not_dumped():
    pool = load_memory_lessons()
    results = retrieve_lessons(pool, role=AgentRole.SYNTHESIZER)
    # Only synthesis-quality lessons match a bare synthesizer role.
    assert set(_ids(results)) == {"LESSON-0002", "LESSON-0006"}
    assert len(results) < len(pool)


def test_returned_items_are_retrieved_lessons_with_scores():
    results = retrieve_for_task(role=AgentRole.SYNTHESIZER)
    assert results and all(isinstance(r, RetrievedLesson) for r in results)
    assert all(r.score > 0 for r in results)
    record = results[0].to_record()
    assert "relevance_score" in record and "match_reasons" in record


# --------------------------------------------------------------------------- #
# Invariant: retriever touches no scores / leaderboard / network.
# --------------------------------------------------------------------------- #

def _code_identifiers(module):
    """NAME tokens in a module's source, excluding strings and comments."""
    source = inspect.getsource(module)
    names = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


def test_retriever_has_no_score_or_network_dependencies():
    # Scan executable identifiers only — the docstring legitimately *names*
    # what the retriever must NOT touch (leaderboard/scorecard), so a raw text
    # scan would false-positive on its own prose.
    names = _code_identifiers(lesson_retriever)
    forbidden = (
        "leaderboard",
        "scorecard",
        "peer_score",
        "SectionScore",
        "requests",
        "anthropic",
        "openai",
        "environ",
        "api_key",
    )
    for token in forbidden:
        assert token not in names, f"retriever code must not reference {token!r}"
