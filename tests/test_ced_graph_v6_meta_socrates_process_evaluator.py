"""CED Graph v6 — Meta-Socrates / Process Evaluator tests.

Deterministic, local, offline. Verifies the process evaluator scores reasoning
quality, ranks an evidence-rich/challenged/revised dialogue above an
evidence-poor one, integrates with the live pipeline, and is deterministic.
"""

from types import SimpleNamespace

from backend.orchestrator.live_epistemics import (
    record_epistemic_claim,
    apply_elenchus_to_claim,
    apply_revision_to_claim,
    produce_current_best_explanation,
)
from backend.orchestrator.meta_socrates import (
    evaluate_session,
    evaluate_process,
    ProcessEvaluation,
    PROCESS_LEVELS,
)


def _session(topic="Is knowledge justified true belief?"):
    return SimpleNamespace(
        config=SimpleNamespace(topic=topic),
        constitution_violations=[],
        history=[],
    )


def _elenchus(claim_id, challenger="grok", round_num=1, falsified=True):
    return SimpleNamespace(
        target_claim_id=claim_id,
        challenger_model=challenger,
        round=round_num,
        falsification_successful=falsified,
        challenged_assumptions=["assumes the premise holds"],
        logic_gaps=["non sequitur"] if falsified else [],
        evidence_issues=[],
        conclusion_issues=[],
    )


def _rich_session():
    """A diverse, evidence-bearing, challenged-and-revised dialogue."""
    s = _session()
    c1 = record_epistemic_claim(
        s, "claude",
        "Knowledge is a revisable process because it changes when new evidence appears.",
        1)
    record_epistemic_claim(
        s, "chatgpt",
        "Justification matters because unsupported belief is weak evidence.",
        1)
    record_epistemic_claim(
        s, "gemini",
        "A claim needs scrutiny since assumptions are often hidden.",
        2)
    # Challenge + revise the first claim.
    apply_elenchus_to_claim(s, _elenchus(c1, falsified=True))
    apply_revision_to_claim(
        s, c1,
        "Knowledge is a revisable process, but reliability of the process matters too.",
        actor="claude")
    produce_current_best_explanation(s)
    return s


def _poor_session():
    """A thin, unsupported, unchallenged dialogue."""
    s = _session()
    record_epistemic_claim(s, "claude", "Knowledge is whatever feels certain.", 1)
    produce_current_best_explanation(s)
    return s


# --- structure --------------------------------------------------------------

def test_evaluator_returns_full_structure():
    evaluation = evaluate_session(_rich_session())
    assert isinstance(evaluation, ProcessEvaluation)
    data = evaluation.to_dict()
    for key in ("evaluation_id", "process_score", "process_level",
                "strengths", "weaknesses", "recommended_next_actions",
                "metrics", "created_at"):
        assert key in data
    assert 0.0 <= data["process_score"] <= 1.0
    assert data["process_level"] in PROCESS_LEVELS
    assert isinstance(data["strengths"], list)
    assert isinstance(data["weaknesses"], list)
    assert isinstance(data["recommended_next_actions"], list)
    assert data["recommended_next_actions"]  # always at least one


# --- relative scoring -------------------------------------------------------

def test_rich_process_scores_higher_than_poor():
    rich = evaluate_session(_rich_session())
    poor = evaluate_session(_poor_session())
    assert rich.process_score > poor.process_score


def test_poor_process_flags_weaknesses_and_actions():
    poor = evaluate_session(_poor_session())
    # An unchallenged, unsupported claim must surface weaknesses + recommendations.
    assert poor.weaknesses
    assert poor.recommended_next_actions
    assert any("challenge" in w.lower() or "evidence" in w.lower()
               for w in poor.weaknesses)


def test_rich_process_lists_strengths():
    rich = evaluate_session(_rich_session())
    assert rich.strengths
    assert any("revis" in s.lower() for s in rich.strengths)


# --- live integration -------------------------------------------------------

def test_produce_cbe_stores_process_evaluation():
    s = _rich_session()  # already calls produce_current_best_explanation
    assert hasattr(s, "process_evaluation")
    assert isinstance(s.process_evaluation, ProcessEvaluation)
    # Trace records the meta-evaluation.
    assert any("Meta-Socrates evaluated the reasoning process" in t
               for t in s.epistemic_trace)


# --- determinism ------------------------------------------------------------

def test_evaluation_is_deterministic():
    s = _rich_session()
    a = evaluate_session(s)
    b = evaluate_session(s)
    assert a.process_score == b.process_score
    assert a.process_level == b.process_level
    assert a.metrics == b.metrics
    assert a.evaluation_id == b.evaluation_id


def test_evaluate_process_handles_empty_graph():
    from backend.epistemic.epistemic_graph import EpistemicGraph
    evaluation = evaluate_process(EpistemicGraph(), cbe=None, memory=None)
    assert evaluation.process_level == "weak"
    assert evaluation.metrics["claim_count"] == 0
