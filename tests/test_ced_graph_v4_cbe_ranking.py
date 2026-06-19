from backend.epistemic.claim import Claim, Evidence
from backend.epistemic.epistemic_graph import EdgeType, EpistemicGraph, NodeType
from backend.epistemic.epistemic_state import EpistemicState
from backend.reasoning.synthesis_engine import SynthesisEngine


def _claim(
    graph: EpistemicGraph,
    text: str,
    *,
    author: str = "model",
    state: EpistemicState = EpistemicState.SUPPORTED,
    confidence: float = 0.5,
    evidence_sources: tuple[str, ...] = (),
) -> Claim:
    claim = Claim(text=text, author_model=author, confidence=confidence)
    claim.state = state
    graph.add_claim(claim)

    for idx, source in enumerate(evidence_sources):
        ev = Evidence(
            evidence_id=f"ev_{claim.claim_id}_{idx}",
            summary=f"Evidence {idx} because it supports {text}",
            source=source,
            quality=0.8,
            supports=True,
        )
        claim.add_evidence(ev)
        ev_node = graph.add_node(
            NodeType.EVIDENCE,
            ev.summary,
            payload={"claim_id": claim.claim_id, "source_model": source, "quality": ev.quality},
        )
        graph.link(ev_node, claim.claim_id, EdgeType.SUPPORTS, weight=ev.quality)

    return claim


def test_cbe_ranking_prefers_evidence_backed_claim_over_unbacked_confident_claim():
    graph = EpistemicGraph()
    weak = _claim(
        graph,
        "Knowledge is a final answer.",
        author="grok",
        state=EpistemicState.SUPPORTED,
        confidence=0.95,
    )
    strong = _claim(
        graph,
        "Knowledge is a revisable process backed by evidence.",
        author="chatgpt",
        state=EpistemicState.SUPPORTED,
        confidence=0.5,
        evidence_sources=("chatgpt", "gemini"),
    )

    cbe = SynthesisEngine().synthesize("Is knowledge final?", graph, ["trace"])
    data = cbe.to_dict()

    assert data["ranking_version"] == "v4"
    assert data["summary_claim_ids"][0] == strong.claim_id
    assert data["strongest_claims"][0]["claim_id"] == strong.claim_id
    assert data["strongest_claims"][0]["cbe_ranking"]["rank"] == 1
    assert data["ranked_claims"][0]["claim_id"] == strong.claim_id
    assert data["ranked_claims"][1]["claim_id"] == weak.claim_id
    assert data["ranked_claims"][0]["cbe_score"] > data["ranked_claims"][1]["cbe_score"]


def test_cbe_ranking_penalizes_open_problems_and_contradictions():
    graph = EpistemicGraph()
    stable = _claim(
        graph,
        "Evidence-backed claims should outrank unresolved claims.",
        author="gemini",
        state=EpistemicState.SUPPORTED,
        evidence_sources=("source-a", "source-b"),
    )
    disputed = _claim(
        graph,
        "Unresolved claims should outrank evidence-backed claims.",
        author="grok",
        state=EpistemicState.SUPPORTED,
        confidence=0.9,
        evidence_sources=("source-c",),
    )
    graph.record_contradiction(stable.claim_id, disputed.claim_id)
    open_problem = graph.add_node(
        NodeType.OPEN_PROBLEM,
        "This claim has an unresolved objection.",
        payload={"claim_id": disputed.claim_id},
    )
    graph.link(disputed.claim_id, open_problem, EdgeType.DEPENDS_ON, weight=0.5)

    cbe = SynthesisEngine().synthesize("Which claim is preferred?", graph, [])
    data = cbe.to_dict()

    assert data["summary_claim_ids"][0] == stable.claim_id
    disputed_rank = next(row for row in data["ranked_claims"] if row["claim_id"] == disputed.claim_id)
    assert disputed_rank["open_problem_penalty"] > 0
    assert any("open_problems" in reason for reason in disputed_rank["reasons"])
    assert data["unresolved_disagreements"]


def test_cbe_ranking_excludes_rejected_claims_from_ranked_candidates():
    graph = EpistemicGraph()
    rejected = _claim(
        graph,
        "A rejected claim should not become the current best explanation.",
        state=EpistemicState.REJECTED,
        confidence=1.0,
        evidence_sources=("source-a", "source-b"),
    )
    live = _claim(
        graph,
        "A live supported claim can be ranked as the current best explanation.",
        state=EpistemicState.SUPPORTED,
        confidence=0.5,
        evidence_sources=("source-c",),
    )

    data = SynthesisEngine().synthesize("What survives?", graph, []).to_dict()

    assert rejected.claim_id not in data["summary_claim_ids"]
    assert rejected.claim_id not in [row["claim_id"] for row in data["ranked_claims"]]
    assert data["summary_claim_ids"][0] == live.claim_id
    assert data["rejected_hypotheses"][0]["claim_id"] == rejected.claim_id
