"""CED Graph v5 — Knowledge Evolution Memory / Claim Lineage tests.

Deterministic, local, offline. Verifies that claims carry a historical lineage,
revisions preserve previous text, lineage events are ordered, and the Current
Best Explanation exposes lineage metadata for its strongest claims.
"""

from types import SimpleNamespace

from backend.orchestrator.live_epistemics import (
    record_epistemic_claim,
    apply_elenchus_to_claim,
    apply_revision_to_claim,
    produce_current_best_explanation,
)
from backend.orchestrator.knowledge_evolution_memory import (
    KnowledgeEvolutionMemory,
    ensure_knowledge_evolution_memory,
    EVENT_CREATED,
    EVENT_CHALLENGED,
    EVENT_REVISED,
    EVENT_SUPPORTED_AFTER_REVISION,
    EVENT_SUPERSEDED,
    EVENT_USED_IN_CBE,
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


# --- module-level unit behavior --------------------------------------------

def test_memory_rejects_unknown_event_type():
    mem = KnowledgeEvolutionMemory()
    import pytest
    with pytest.raises(ValueError):
        mem.record("c1", "teleported", actor="x", reason="r",
                   text_snapshot="t", confidence_snapshot=0.5, state_snapshot="HYPOTHESIS")


# --- 1. A newly recorded claim gets a lineage history ----------------------

def test_new_claim_gets_lineage_history():
    s = _session()
    claim_id = record_epistemic_claim(
        s, "claude", "Knowledge requires a non-accidental link to truth.", 1)

    mem = ensure_knowledge_evolution_memory(s)
    events = mem.lineage_for(claim_id)

    assert len(events) == 1
    assert events[0].event_type == EVENT_CREATED
    assert events[0].actor == "claude"
    assert events[0].text_snapshot.startswith("Knowledge requires")

    # Node payload mirrors the lineage.
    node = s.epistemic_graph.nodes[claim_id]
    assert node.payload["lineage_event_count"] == 1
    assert node.payload["lineage_id"] is not None


# --- 2. A revised claim preserves previous text ----------------------------

def test_revised_claim_preserves_previous_text():
    s = _session()
    original = "Justification is purely internal access to good reasons."
    claim_id = record_epistemic_claim(s, "claude", original, 1)

    apply_elenchus_to_claim(s, _elenchus(claim_id, falsified=True))
    apply_revision_to_claim(
        s, claim_id,
        "Justification may be internal or externally reliable; the case is contested.",
        actor="claude",
    )

    mem = ensure_knowledge_evolution_memory(s)

    # Previous text is preserved verbatim.
    assert mem.previous_text_snapshot(claim_id) == original[:400]
    assert original[:400] in mem.text_versions(claim_id)

    # Live claim text is the revised version.
    revised_text = s.epistemic_graph.claims[claim_id].text
    assert "externally reliable" in revised_text

    # Node payload exposes the preserved previous text + reviser.
    node = s.epistemic_graph.nodes[claim_id]
    assert node.payload["previous_text_snapshot"] == original[:400]
    assert node.payload["latest_revision_actor"] == "claude"


# --- 3. Challenge/revision events are ordered ------------------------------

def test_challenge_and_revision_events_are_ordered():
    s = _session()
    claim_id = record_epistemic_claim(s, "claude", "Knowledge is JTB.", 1)
    apply_elenchus_to_claim(s, _elenchus(claim_id, falsified=True))
    apply_revision_to_claim(s, claim_id, "Knowledge is JTB plus a reliability condition.",
                            actor="claude")

    mem = ensure_knowledge_evolution_memory(s)
    events = mem.lineage_for(claim_id)
    types = [e.event_type for e in events]

    # Expected ordering of the lifecycle.
    assert types == [
        EVENT_CREATED,
        EVENT_CHALLENGED,
        EVENT_SUPERSEDED,
        EVENT_REVISED,
        EVENT_SUPPORTED_AFTER_REVISION,
    ]
    # Sequence numbers strictly increase (deterministic ordering).
    seqs = [e.sequence for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    # Challenge strictly precedes revision.
    assert types.index(EVENT_CHALLENGED) < types.index(EVENT_REVISED)


# --- 4. CBE strongest claims expose lineage metadata -----------------------

def test_cbe_strongest_claims_expose_lineage():
    s = _session()
    claim_id = record_epistemic_claim(
        s, "claude", "Knowledge requires a non-accidental connection to truth.", 1)
    # Survives a challenge -> becomes SUPPORTED -> strong candidate.
    apply_elenchus_to_claim(s, _elenchus(claim_id, falsified=False))

    cbe = produce_current_best_explanation(s)
    data = cbe.to_dict()

    # Top-level lineage map is exposed and references existing claim_ids only.
    assert "lineage" in data
    assert claim_id in data["lineage"]
    for cid in data["lineage"]:
        assert cid in s.epistemic_graph.claims

    # The strongest claim carries lineage metadata including CBE usage.
    strongest = data["strongest_claims"][0]
    assert "lineage" in strongest
    assert strongest["lineage"]["lineage_event_count"] >= 1
    assert EVENT_USED_IN_CBE in strongest["lineage"]["event_types"]
    assert strongest["lineage"]["used_in_current_best_explanation"] is True


def test_cbe_invents_no_new_claims():
    """v5 must not let synthesis mint claims: CBE claim_ids ⊆ graph claim_ids."""
    s = _session()
    record_epistemic_claim(s, "claude", "Knowledge is a revisable process.", 1)
    record_epistemic_claim(s, "chatgpt", "Knowledge is fixed once justified.", 1)

    cbe = produce_current_best_explanation(s)
    graph_ids = set(s.epistemic_graph.claims)

    assert set(cbe.summary_claim_ids).issubset(graph_ids)
    for row in cbe.to_dict()["ranked_claims"]:
        assert row["claim_id"] in graph_ids
