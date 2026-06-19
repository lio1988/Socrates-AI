from backend.epistemic_graph import EpistemicGraph, ClaimStatus, ContradictionGraphEngine


def test_claims_can_be_created_with_stable_ids():
    g = EpistemicGraph(question="Is knowledge a process?")
    a = g.add_claim("Knowledge is a process.", author_model="chatgpt")
    b = g.add_claim("Knowledge is a process.", author_model="chatgpt")
    assert a.claim_id == b.claim_id
    assert a.status == ClaimStatus.PROPOSED


def test_contradictions_link_two_claims():
    g = EpistemicGraph()
    a = g.add_claim("Knowledge is a process.", author_model="chatgpt")
    b = g.add_claim("Knowledge is a final answer.", author_model="grok")
    con = g.add_contradiction(a.claim_id, b.claim_id, reason="process vs final answer")
    assert con.claim_a == a.claim_id
    assert b.claim_id in g.get_claim(a.claim_id).contradicts


def test_revision_keeps_history_link():
    g = EpistemicGraph()
    original = g.add_claim("Knowledge is final.", author_model="claude")
    revised = g.revise_claim(original.claim_id, "Knowledge is provisional and revisable.", actor="claude")
    assert g.get_claim(original.claim_id).status == ClaimStatus.REVISED
    assert revised.revision_of == original.claim_id


def test_cbe_generated_from_active_claims():
    g = EpistemicGraph(question="What is knowledge?")
    claim = g.add_claim("Knowledge is a revisable process.", author_model="chatgpt", confidence=0.8)
    g.add_evidence(claim.claim_id, "Claim survived a challenge.", source="elenchus", quality=0.7)
    cbe = g.build_current_best_explanation()
    assert cbe.provisional is True
    assert claim.claim_id in cbe.based_on_claims
    assert "Current Best Explanation" in cbe.to_dict()["note"]


def test_deterministic_contradiction_engine_catches_explicit_opposition():
    g = EpistemicGraph()
    a = g.add_claim("Knowledge is a process.", author_model="a")
    b = g.add_claim("Knowledge is a final answer.", author_model="b")
    contradictions = ContradictionGraphEngine().detect([a, b])
    assert contradictions

