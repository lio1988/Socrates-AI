from types import SimpleNamespace

from backend.orchestrator.epistemic_scoring import EpistemicScoringEngine
from backend.orchestrator.live_epistemics import record_epistemic_claim


def _session(topic="Is knowledge a process?"):
    return SimpleNamespace(config=SimpleNamespace(topic=topic))


def test_v3_score_increases_with_evidence_and_low_uncertainty():
    s = _session()
    claim_id = record_epistemic_claim(
        s,
        "chatgpt",
        "Knowledge is clearly a revisable process because evidence shows it changes with new evidence.",
        1,
    )

    graph = s.epistemic_graph
    claim = graph.claims[claim_id]
    payload = graph.nodes[claim_id].payload
    score = payload["epistemic_score"]

    assert 0.0 <= score["score"] <= 1.0
    assert score["support_score"] > 0
    assert score["evidence_gap_penalty"] == 0
    assert score["confidence_level"] in {"supported", "strong"}
    assert claim.confidence == score["confidence_after"]


def test_v3_score_penalizes_evidence_gap_and_high_uncertainty():
    s = _session()
    claim_id = record_epistemic_claim(s, "claude", "Maybe knowledge is a living process.", 1)

    payload = s.epistemic_graph.nodes[claim_id].payload
    score = payload["epistemic_score"]

    assert score["evidence_count"] == 0
    assert score["evidence_gap_penalty"] > 0
    assert score["uncertainty_penalty"] > 0
    assert score["score"] < 0.5
    assert score["confidence_level"] == "weak"


def test_v3_contradiction_pressure_reduces_disputed_claim_score():
    s = _session()
    record_epistemic_claim(
        s,
        "chatgpt",
        "Knowledge is a process because it changes with new evidence.",
        1,
    )
    second_id = record_epistemic_claim(
        s,
        "grok",
        "Knowledge is not a process because final answers are fixed.",
        1,
    )

    payload = s.epistemic_graph.nodes[second_id].payload
    score = payload["epistemic_score"]

    assert score["contradiction_pressure"] > 0
    assert score["score"] < 0.5
    assert payload["confidence_level"] in {"weak", "tentative"}


def test_v3_trace_records_score_summary():
    s = _session()
    record_epistemic_claim(
        s,
        "gemini",
        "A claim needs evidence because unsupported agreement is weak.",
        1,
    )

    assert any("score=" in event for event in s.epistemic_trace)


def test_v3_scoring_engine_is_deterministic_for_same_graph_state():
    s = _session()
    claim_id = record_epistemic_claim(
        s,
        "chatgpt",
        "Knowledge is clearly revisable because new evidence can update it.",
        1,
    )

    graph = s.epistemic_graph
    claim = graph.claims[claim_id]
    engine = EpistemicScoringEngine()

    score_a = engine.score(graph, claim).score
    score_b = engine.score(graph, claim).score

    assert score_a == score_b
