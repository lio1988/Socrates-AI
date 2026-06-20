"""Evidence Layer v0.1 -- full test suite.

Covers: backward-compatible evidence_quality (mean), Evidence dataclass
extension + positional construction, effective_stance fallback/override, the
deterministic audit (balance/quality/mass/status), graph mirroring, the
non-mutating evidence-constrained composer (incl. the REFUTED-cannot-be-primary
failure mode), the sibling benchmark + harness metrics, no-live-call guarantee,
and unchanged KnowledgeEmergenceEngine behavior.
"""

import copy
import json

import pytest

from backend.config import EmergenceThresholds
from backend.epistemic.claim import Claim, Evidence, EvidenceStance
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.knowledge_emergence import KnowledgeEmergenceEngine
from backend.epistemic.epistemic_graph import EpistemicGraph, NodeType, EdgeType
from backend.epistemic.evidence_scoring import (
    EvidenceStatus,
    effective_stance,
    evidence_balance,
    evidence_status,
    evidence_summary,
    saturating_mass,
)
from backend.epistemic.evidence_fixtures import evidence_from_fixture, attach_evidence
from backend.reasoning.evidence_constrained_cbe import (
    compose_final_epistemic_answer,
    NO_SUPPORTED_ANSWER,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _ev(stance: EvidenceStance, strength: float, eid: str = "e") -> Evidence:
    return Evidence(
        eid,
        "summary",
        quality=strength,
        supports=(stance != EvidenceStance.CONTRADICTING),
        stance=stance,
        strength=strength,
    )


def _mk(text: str, evs) -> Claim:
    c = Claim(text=text, author_model="t")
    for e in evs:
        c.add_evidence(e)
    return c


def _raw(*claims):
    rows = [{"claim_id": c.claim_id, "text": c.text} for c in claims]
    raw_cbe = {"ranked_claims": rows, "strongest_claims": rows[:3]}
    return raw_cbe, {c.claim_id: c for c in claims}


def _ids(briefs):
    return [b["claim_id"] for b in briefs]


# --------------------------------------------------------------------------- #
# 1. legacy evidence_quality backward compatibility (MUST NOT CHANGE)
# --------------------------------------------------------------------------- #
def test_legacy_evidence_quality_single_supporting_unchanged():
    c = _mk("c", [Evidence("e1", "s", quality=0.8)])  # supports=True default
    assert c.evidence_quality == 0.8


def test_legacy_evidence_quality_multi_supporting_is_mean_0875():
    # MANDATORY regression: mean of supporting qualities, NOT clamp(sum).
    c = _mk("c", [Evidence("e1", "a", quality=0.9), Evidence("e2", "b", quality=0.85)])
    assert c.evidence_quality == 0.875


def test_evidence_positional_construction_backward_compatible():
    ev = Evidence("e1", "summary")  # two positional args, as legacy callers use
    assert ev.evidence_id == "e1" and ev.summary == "summary"
    assert ev.supports is True and ev.stance is None
    ev2 = Evidence("e2", "s", "src", 0.7, False)  # legacy positional incl. supports
    assert ev2.source == "src" and ev2.quality == 0.7 and ev2.supports is False
    assert effective_stance(ev2) == EvidenceStance.CONTRADICTING


# --------------------------------------------------------------------------- #
# 2. effective_stance: fallback + override
# --------------------------------------------------------------------------- #
def test_effective_stance_falls_back_to_supports():
    assert effective_stance(Evidence("e", "s", supports=True)) == EvidenceStance.SUPPORTING
    assert effective_stance(Evidence("e", "s", supports=False)) == EvidenceStance.CONTRADICTING


def test_explicit_stance_wins_over_supports():
    ev = Evidence("e", "s", supports=True, stance=EvidenceStance.CONTRADICTING)
    assert effective_stance(ev) == EvidenceStance.CONTRADICTING
    ev2 = Evidence("e", "s", supports=False, stance=EvidenceStance.WEAK)
    assert effective_stance(ev2) == EvidenceStance.WEAK


# --------------------------------------------------------------------------- #
# 3. evidence_status for each category
# --------------------------------------------------------------------------- #
def test_supporting_evidence_well_supported():
    c = _mk("c", [_ev(EvidenceStance.SUPPORTING, 0.9, "e1"),
                  _ev(EvidenceStance.SUPPORTING, 0.85, "e2")])
    assert evidence_status(c) == EvidenceStatus.WELL_SUPPORTED


def test_contradicting_evidence_refuted():
    c = _mk("c", [_ev(EvidenceStance.CONTRADICTING, 0.85, "e1")])
    assert evidence_status(c) == EvidenceStatus.REFUTED


def test_weak_evidence_weakly_supported():
    c = _mk("c", [_ev(EvidenceStance.WEAK, 0.5, "e1")])
    assert evidence_status(c) == EvidenceStatus.WEAKLY_SUPPORTED


def test_no_evidence_missing():
    assert evidence_status(_mk("c", [])) == EvidenceStatus.MISSING


def test_both_stances_contested_when_support_competitive():
    c = _mk("c", [_ev(EvidenceStance.SUPPORTING, 0.7, "e1"),
                  _ev(EvidenceStance.CONTRADICTING, 0.6, "e2")])
    assert evidence_status(c) == EvidenceStatus.CONTESTED


def test_dominant_contradiction_is_refuted():
    c = _mk("c", [_ev(EvidenceStance.SUPPORTING, 0.5, "e1"),
                  _ev(EvidenceStance.CONTRADICTING, 0.9, "e2")])
    assert evidence_status(c) == EvidenceStatus.REFUTED


def test_weak_alone_never_well_supported():
    # Even with several weak pieces (high mass), status stays WEAKLY_SUPPORTED.
    c = _mk("c", [_ev(EvidenceStance.WEAK, 0.6, "e1"),
                  _ev(EvidenceStance.WEAK, 0.6, "e2"),
                  _ev(EvidenceStance.WEAK, 0.6, "e3")])
    assert evidence_status(c) == EvidenceStatus.WEAKLY_SUPPORTED


# --------------------------------------------------------------------------- #
# 4. balance separates quality from mass; mass is saturating
# --------------------------------------------------------------------------- #
def test_balance_separates_quality_from_mass():
    c = _mk("c", [_ev(EvidenceStance.SUPPORTING, 0.9, "e1"),
                  _ev(EvidenceStance.SUPPORTING, 0.85, "e2")])
    b = evidence_balance(c)
    assert b.support_quality == 0.875            # mean
    assert abs(b.support_mass - 0.985) < 1e-9    # saturating noisy-OR
    assert b.support_mass != b.support_quality
    assert b.counts["supporting"] == 2


def test_evidence_mass_is_saturating_not_plain_sum():
    m = saturating_mass([0.9, 0.85])
    assert abs(m - 0.985) < 1e-9
    assert m < 0.9 + 0.85          # not a plain sum
    assert m <= 1.0
    assert saturating_mass([]) == 0.0
    assert saturating_mass([1.0, 0.5]) == 1.0     # saturates at 1.0


# --------------------------------------------------------------------------- #
# 5. graph mirroring: EVIDENCE node + SUPPORTS / CONTRADICTS edge
# --------------------------------------------------------------------------- #
def test_graph_evidence_node_and_edge_attached():
    g = EpistemicGraph()
    c = Claim(text="claim", author_model="t")
    g.add_claim(c)

    nid = attach_evidence(
        g, c.claim_id,
        evidence_from_fixture({"stance": "supporting", "strength": 0.8, "summary": "x"}),
    )
    assert g.nodes[nid].node_type == NodeType.EVIDENCE
    assert any(
        e.src == nid and e.dst == c.claim_id and e.edge_type == EdgeType.SUPPORTS
        for e in g.edges.values()
    )
    assert len(c.evidence) == 1

    nid2 = attach_evidence(
        g, c.claim_id,
        evidence_from_fixture({"stance": "contradicting", "strength": 0.7, "summary": "y"}),
    )
    assert any(
        e.src == nid2 and e.dst == c.claim_id and e.edge_type == EdgeType.CONTRADICTS
        for e in g.edges.values()
    )


def test_weak_fixture_uses_supports_edge_but_preserves_weak_status():
    g = EpistemicGraph()
    c = Claim(text="claim", author_model="t")
    g.add_claim(c)
    nid = attach_evidence(
        g, c.claim_id,
        evidence_from_fixture({"stance": "weak", "strength": 0.5, "summary": "w"}),
    )
    # SUPPORTS edge for graph compatibility...
    assert any(
        e.src == nid and e.edge_type == EdgeType.SUPPORTS for e in g.edges.values()
    )
    # ...but the WEAK stance is preserved in metadata and status.
    assert g.nodes[nid].payload["stance"] == "weak"
    assert evidence_status(c) == EvidenceStatus.WEAKLY_SUPPORTED


# --------------------------------------------------------------------------- #
# 6. raw CBE remains unchanged (composer is non-mutating & separate)
# --------------------------------------------------------------------------- #
def test_composer_does_not_mutate_raw_cbe():
    c = _mk("X", [_ev(EvidenceStance.SUPPORTING, 0.9, "e1")])
    raw, by_id = _raw(c)
    snapshot = copy.deepcopy(raw)
    compose_final_epistemic_answer(raw, by_id)
    assert raw == snapshot  # composer must not mutate the raw CBE
    for k in ("final_epistemic_answer", "flagged_unsupported",
              "flagged_refuted", "flagged_contested"):
        assert k not in raw


def test_real_cbe_has_no_evidence_layer_keys():
    from backend.evaluation.evidence_harness import _build_session, EvidenceCase
    from backend.orchestrator.live_epistemics import (
        record_epistemic_claim, produce_current_best_explanation,
    )
    case = EvidenceCase(id="t", question="q?", claim_text="A claim.",
                        evidence_fixtures=[], gold={})
    session = _build_session(case)
    record_epistemic_claim(session, "claude", case.claim_text, 1)
    cbe = produce_current_best_explanation(session).to_dict()
    for k in ("final_epistemic_answer", "flagged_unsupported",
              "flagged_refuted", "flagged_contested"):
        assert k not in cbe


# --------------------------------------------------------------------------- #
# 7. evidence-constrained composer respects status
# --------------------------------------------------------------------------- #
def test_well_supported_is_eligible_primary():
    c = _mk("X", [_ev(EvidenceStance.SUPPORTING, 0.85, "e1")])
    raw, by_id = _raw(c)
    fa = compose_final_epistemic_answer(raw, by_id)
    assert fa.primary_answer == "X"
    assert c.claim_id in _ids(fa.supported_claims)
    assert fa.confidence_label in ("well_supported", "supported")


def test_refuted_strongest_is_not_primary_single():
    c = _mk("X", [_ev(EvidenceStance.CONTRADICTING, 0.85, "e1")])
    raw, by_id = _raw(c)
    fa = compose_final_epistemic_answer(raw, by_id)
    assert fa.primary_answer == NO_SUPPORTED_ANSWER  # NOT "X"
    assert c.claim_id in _ids(fa.refuted_claims)


def test_refuted_strongest_yields_to_well_supported_weaker():
    # The exact failure mode to prevent: strongest raw claim is REFUTED.
    strong_refuted = _mk("X", [_ev(EvidenceStance.CONTRADICTING, 0.9, "e1")])
    weaker_supported = _mk("Y", [_ev(EvidenceStance.SUPPORTING, 0.8, "e2")])
    raw, by_id = _raw(strong_refuted, weaker_supported)  # X ranked first
    fa = compose_final_epistemic_answer(raw, by_id)
    assert fa.primary_answer == "Y"  # must NOT be the refuted strongest claim
    assert strong_refuted.claim_id in _ids(fa.refuted_claims)
    assert weaker_supported.claim_id in _ids(fa.supported_claims)


def test_contested_appears_only_with_caveat():
    c = _mk("Z", [_ev(EvidenceStance.SUPPORTING, 0.7, "e1"),
                  _ev(EvidenceStance.CONTRADICTING, 0.6, "e2")])
    raw, by_id = _raw(c)
    fa = compose_final_epistemic_answer(raw, by_id)
    assert c.claim_id in _ids(fa.contested_claims)
    assert fa.primary_answer == NO_SUPPORTED_ANSWER  # contested is never primary


def test_missing_appears_only_as_missing_evidence():
    c = _mk("W", [])
    raw, by_id = _raw(c)
    fa = compose_final_epistemic_answer(raw, by_id)
    assert c.claim_id in _ids(fa.missing_evidence)
    assert fa.primary_answer == NO_SUPPORTED_ANSWER


def test_weak_appears_only_as_speculative():
    c = _mk("V", [_ev(EvidenceStance.WEAK, 0.5, "e1")])
    raw, by_id = _raw(c)
    fa = compose_final_epistemic_answer(raw, by_id)
    assert c.claim_id in _ids(fa.speculative_claims)
    assert fa.primary_answer == NO_SUPPORTED_ANSWER


def test_no_well_supported_returns_humble_answer():
    a = _mk("A", [_ev(EvidenceStance.WEAK, 0.4, "e1")])
    b = _mk("B", [])
    raw, by_id = _raw(a, b)
    fa = compose_final_epistemic_answer(raw, by_id)
    assert fa.primary_answer == NO_SUPPORTED_ANSWER
    assert fa.confidence_label == "insufficient_evidence"


def test_audit_and_composer_do_not_mutate_claim():
    c = _mk("X", [_ev(EvidenceStance.SUPPORTING, 0.85, "e1")])
    state_before, eq_before, n_before = c.state, c.evidence_quality, len(c.evidence)
    raw, by_id = _raw(c)
    evidence_status(c)
    evidence_summary(c)
    compose_final_epistemic_answer(raw, by_id)
    assert c.state == state_before
    assert c.evidence_quality == eq_before
    assert len(c.evidence) == n_before


# --------------------------------------------------------------------------- #
# 8. benchmark + harness
# --------------------------------------------------------------------------- #
def test_benchmark_loads_with_correct_schema():
    from backend.evaluation.evidence_harness import (
        load_evidence_benchmark, EVIDENCE_SCHEMA_VERSION,
    )
    assert EVIDENCE_SCHEMA_VERSION == "ced_evidence_eval_v0.1"
    cases = load_evidence_benchmark()
    ids = {c.id for c in cases}
    assert {"evidence_supported", "evidence_contradicted",
            "evidence_weak", "evidence_missing"} <= ids


def test_benchmark_wrong_schema_raises(tmp_path):
    from backend.evaluation.evidence_harness import load_evidence_benchmark
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": "wrong_v9", "cases": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_evidence_benchmark(str(p))


def test_harness_detects_status_and_passes():
    from backend.evaluation.evidence_harness import run_evidence_benchmark
    report = run_evidence_benchmark()
    by_id = {c["case_id"]: c for c in report.cases}
    assert by_id["evidence_supported"]["actual_status"] == "WELL_SUPPORTED"
    assert by_id["evidence_contradicted"]["actual_status"] == "REFUTED"
    assert by_id["evidence_weak"]["actual_status"] == "WEAKLY_SUPPORTED"
    assert by_id["evidence_missing"]["actual_status"] == "MISSING"
    assert all(c["status_correct"] for c in report.cases)
    assert report.aggregate["status_correct_rate"] == 1.0
    assert report.aggregate["passed_rate"] == 1.0


def test_harness_makes_no_live_calls(monkeypatch):
    import socrates_ai

    def boom(*args, **kwargs):
        raise AssertionError("Live model call attempted in evidence harness!")

    for name in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, name):
            monkeypatch.setattr(socrates_ai.DialogManager, name, boom, raising=False)

    from backend.evaluation.evidence_harness import run_evidence_benchmark
    report = run_evidence_benchmark()
    assert report.case_count == 4


# --------------------------------------------------------------------------- #
# 9. KnowledgeEmergenceEngine behavior is unchanged by the evidence layer
# --------------------------------------------------------------------------- #
def test_knowledge_emergence_engine_behavior_unchanged():
    c = Claim(text="Well-supported claim.", author_model="alpha", confidence=0.9)
    c.transition(EpistemicState.CHALLENGED, actor="e", reason="c")
    c.transition(EpistemicState.SUPPORTED, actor="e", reason="survived")
    c.add_evidence(Evidence("e1", "Peer-reviewed meta-analysis", quality=0.9))
    c.add_evidence(Evidence("e2", "Independent replication", quality=0.85))
    assert c.evidence_quality == 0.875  # legacy mean preserved
    c.independent_reviews = 3
    engine = KnowledgeEmergenceEngine(EmergenceThresholds())
    decision = engine.evaluate(c)
    assert decision.promoted is True
    assert c.state == EpistemicState.KNOWLEDGE
