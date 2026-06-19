from types import SimpleNamespace

from backend.epistemic.epistemic_graph import EdgeType, NodeType
from backend.orchestrator.live_epistemics import record_epistemic_claim
from backend.orchestrator.structured_epistemic_parser import StructuredEpistemicParser


def _session(topic="Is knowledge a process?"):
    return SimpleNamespace(config=SimpleNamespace(topic=topic), history=[])


def test_structured_parser_extracts_epistemic_fields():
    parsed = StructuredEpistemicParser().parse(
        "Knowledge is a revisable process because evidence changes over time. "
        "Assuming evidence is reliable, the claim holds. "
        "However, fixed dogma would challenge it. "
        "Maybe it should be revised when new data appears."
    )

    assert parsed.main_claims
    assert parsed.supporting_evidence
    assert parsed.assumptions
    assert parsed.objections
    assert parsed.revision_suggestions
    assert parsed.uncertainty_level == "high"


def test_live_writer_embeds_structured_payload_on_claim():
    s = _session()
    claim_id = record_epistemic_claim(
        s,
        "claude",
        "Knowledge is a process because evidence changes. "
        "Assuming memory is reliable, this remains plausible. "
        "Maybe the claim should be revised with new evidence.",
        1,
    )

    payload = s.epistemic_graph.nodes[claim_id].payload

    assert payload["structured_parser_version"] == "v2"
    assert payload["uncertainty_level"] == "high"
    assert payload["structured_counts"]["supporting_evidence"] >= 1
    assert payload["structured_counts"]["assumptions"] == 1
    assert payload["structured_counts"]["revision_suggestions"] >= 1


def test_live_writer_creates_assumption_objection_and_revision_nodes():
    s = _session()
    claim_id = record_epistemic_claim(
        s,
        "gemini",
        "Knowledge is dynamic because data changes across time. "
        "Assuming the data source is trustworthy, the explanation is stronger. "
        "However, missing context is a weakness. "
        "The claim should be revised when further evidence appears.",
        1,
    )

    graph = s.epistemic_graph
    assumption_nodes = [
        node for node in graph.nodes.values()
        if (node.payload or {}).get("category") == "assumption"
    ]
    objection_nodes = [
        node for node in graph.nodes.values()
        if (node.payload or {}).get("category") == "objection"
    ]
    revision_nodes = [
        node for node in graph.nodes.values()
        if (node.payload or {}).get("category") == "revision_suggestion"
    ]

    assert assumption_nodes
    assert objection_nodes
    assert revision_nodes
    assert any(edge.edge_type == EdgeType.DEPENDS_ON and edge.src == claim_id for edge in graph.edges.values())
    assert any(edge.edge_type == EdgeType.CONTRADICTS for edge in graph.edges.values())
    assert any(edge.edge_type == EdgeType.REFINES for edge in graph.edges.values())


def test_v2_keeps_v1_evidence_nodes_compatible():
    s = _session()
    claim_id = record_epistemic_claim(
        s,
        "chatgpt",
        "Knowledge is revisable because new evidence can overturn older explanations.",
        1,
    )

    graph = s.epistemic_graph

    assert graph.nodes[claim_id].payload["evidence_count"] == 1
    assert any(node.node_type == NodeType.EVIDENCE for node in graph.nodes.values())
    assert any(edge.edge_type == EdgeType.SUPPORTS and edge.dst == claim_id for edge in graph.edges.values())
