from backend.epistemic.claim import Claim, Evidence
from backend.epistemic.epistemic_graph import EdgeType, EpistemicGraph, NodeType
from backend.epistemic.epistemic_state import EpistemicState
from backend.reasoning.answer_quality import AnswerQualityEngine, QUALITY_VERSION, socratic_pressure_level
from backend.reasoning.synthesis_engine import SynthesisEngine


def _claim(graph, text, *, state=EpistemicState.SUPPORTED, confidence=0.55, evidence=True):
    claim = Claim(text=text, author_model="tester", confidence=confidence)
    claim.state = state
    graph.add_claim(claim)
    if evidence:
        ev = Evidence(
            evidence_id=f"ev_{claim.claim_id}",
            summary=f"Evidence supporting {text[:40]}",
            source="test",
            quality=0.8,
            supports=True,
        )
        claim.add_evidence(ev)
        ev_node = graph.add_node(NodeType.EVIDENCE, ev.summary, payload={"claim_id": claim.claim_id})
        graph.link(ev_node, claim.claim_id, EdgeType.SUPPORTS, weight=ev.quality)
    return claim


def test_v10_synthesis_exposes_practical_answer_quality_contract():
    graph = EpistemicGraph()
    claim = _claim(
        graph,
        "A useful knowledge answer should state the answer, give an example, test objections, and say what remains uncertain."
    )

    data = SynthesisEngine().synthesize("What makes an answer useful?", graph, ["trace"]).to_dict()

    assert data["answer_quality"]["quality_version"] == QUALITY_VERSION
    assert data["answer_quality"]["contract"]["has_direct_answer"] is True
    assert data["answer_quality"]["contract"]["has_practical_example"] is True
    assert data["practical_answer"]["direct_answer"]
    assert data["practical_answer"]["practical_example"]
    assert data["practical_answer"]["strongest_objection"]
    assert data["practical_answer"]["uncertainty"]
    assert len(data["practical_answer"]["next_steps"]) >= 2
    assert claim.claim_id in data["practical_answer"]["source_claim_ids"]


def test_answer_quality_penalizes_empty_abstract_answer_more_than_practical_answer():
    engine = AnswerQualityEngine()
    abstract = "Knowledge is a dynamic epistemic process of emergent dialectical truth."
    practical = "A good answer gives a direct answer. For example, test one claim against evidence and a counterexample."

    assert engine.abstraction_penalty(abstract) > engine.abstraction_penalty(practical)
    assert engine.practicality_score(practical) > engine.practicality_score(abstract)


def test_socratic_pressure_escalates_by_round():
    early = socratic_pressure_level(1)
    late = socratic_pressure_level(5)

    assert early["pressure_level"] < late["pressure_level"]
    assert early["stance"] == "understand"
    assert late["stance"] == "compress"
    assert "missing examples" in late["targets"]


def test_quality_engine_lists_unresolved_disagreement_as_strongest_objection():
    graph = EpistemicGraph()
    supported = _claim(graph, "A useful answer must be practical and evidence-aware.")
    objection = _claim(graph, "Practical answers can oversimplify complex questions.", confidence=0.7)
    graph.record_contradiction(supported.claim_id, objection.claim_id)

    data = SynthesisEngine().synthesize("How practical should answers be?", graph, []).to_dict()

    assert data["unresolved_disagreements"]
    assert "Unresolved objection" in data["practical_answer"]["strongest_objection"]
    assert data["answer_quality"]["contract"]["has_strongest_objection"] is True


def test_quality_contract_does_not_create_or_delete_claims():
    graph = EpistemicGraph()
    _claim(graph, "The CBE should be rendered without inventing new claims.")
    before = set(graph.claims.keys())

    SynthesisEngine().synthesize("Does quality rendering mutate claims?", graph, [])

    assert set(graph.claims.keys()) == before


def test_quality_contract_exposes_scope_narrowing_rule():
    graph = EpistemicGraph()
    _claim(graph, "A broad question should be narrowed into answer, example, objection, uncertainty, and next step.")

    data = SynthesisEngine().synthesize("Explain everything about knowledge and truth", graph, []).to_dict()

    scope = data["practical_answer"]["scope"]
    assert scope["answerable_question"] == "Explain everything about knowledge and truth"
    assert "separate answer" in scope["narrowing_rule"]


def test_low_quality_empty_graph_is_marked_not_useful_yet_but_safe():
    graph = EpistemicGraph()

    data = SynthesisEngine().synthesize("Empty graph?", graph, []).to_dict()

    assert data["answer_quality"]["quality_version"] == QUALITY_VERSION
    assert data["answer_quality"]["level"] in {"weak", "not_useful_yet"}
    assert data["practical_answer"]["direct_answer"].startswith("No direct answer")
    assert data["practical_answer"]["source_claim_ids"] == []
