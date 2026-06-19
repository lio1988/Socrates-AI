from types import SimpleNamespace

from backend.epistemic.epistemic_graph import EdgeType, NodeType
from backend.orchestrator.live_epistemics import record_epistemic_claim


def _session(topic="Is knowledge a process?"):
    return SimpleNamespace(config=SimpleNamespace(topic=topic))


def test_live_answer_with_evidence_writes_claim_and_evidence_node():
    s = _session()
    claim_id = record_epistemic_claim(
        s,
        "chatgpt",
        "Knowledge is a revisable process because it changes when new evidence appears.",
        1,
    )

    graph = s.epistemic_graph
    claim = graph.claims[claim_id]

    assert claim.evidence
    assert graph.nodes[claim_id].payload["evidence_count"] == 1
    assert any(node.node_type == NodeType.EVIDENCE for node in graph.nodes.values())
    assert any(edge.edge_type == EdgeType.SUPPORTS and edge.dst == claim_id for edge in graph.edges.values())


def test_live_answer_without_evidence_records_evidence_gap():
    s = _session()
    claim_id = record_epistemic_claim(s, "claude", "Knowledge is a living process.", 1)

    graph = s.epistemic_graph
    gaps = [node for node in graph.nodes.values() if node.node_type == NodeType.OPEN_PROBLEM]

    assert gaps
    assert gaps[0].payload["claim_id"] == claim_id
    assert any(edge.edge_type == EdgeType.DEPENDS_ON and edge.src == claim_id for edge in graph.edges.values())


def test_live_opposition_creates_contradiction_edge():
    s = _session()
    first = record_epistemic_claim(
        s,
        "chatgpt",
        "Knowledge is a process because it changes with new evidence.",
        1,
    )
    second = record_epistemic_claim(
        s,
        "grok",
        "Knowledge is not a process because final answers are fixed.",
        1,
    )

    graph = s.epistemic_graph

    assert second in graph.claims[first].contradictions
    assert any(edge.edge_type == EdgeType.CONTRADICTS for edge in graph.edges.values())


def test_live_ced_trace_records_enriched_claim_summary():
    s = _session()
    record_epistemic_claim(
        s,
        "gemini",
        "A claim needs evidence because unsupported agreement is weak.",
        1,
    )

    assert any("evidence=1" in event for event in s.epistemic_trace)
