"""
Tests for CED Integration Report v0.1.

Covers: the deterministic final_handling rule table, per-claim inclusion of
evidence_status / evidence_balance / argumentation_label, the WELL_SUPPORTED+IN
primary path and all the "never clean primary" guards (OUT / MISSING / REFUTED),
the humble no-clean-answer, read-only/non-mutation, that raw CBE / Evidence Layer
/ Argumentation Framework behavior is unchanged, benchmark loading, harness
metrics, JSON-only CLI, and the no-live-call guard.
"""

import copy
import json

import pytest

from backend.epistemic.claim import Claim, Evidence
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.epistemic_graph import EpistemicGraph, EdgeType
from backend.epistemic.evidence_scoring import evidence_status, EvidenceStatus
from backend.epistemic.argumentation_framework import label_graph, ArgLabel
from backend.reasoning.ced_integration_report import (
    NO_CLEAN_ANSWER,
    build_integration_report,
    compute_final_handling,
)
from backend.orchestrator.live_epistemics import produce_current_best_explanation
from backend.evaluation.integration_harness import IntegrationCase, build_case_graph


def _report(claims, attacks=None, focus=None):
    """Build session+graph for a spec, produce raw CBE, return the report bundle."""
    case = IntegrationCase(id="t", focus=focus, claims=claims, attacks=attacks or [], gold={})
    session, graph, n2c = build_case_graph(case)
    raw = produce_current_best_explanation(session).to_dict()
    report = build_integration_report(raw, graph)
    return report, graph, n2c, raw


def _view(report, cid):
    return next((v for v in report.claims if v.claim_id == cid), None)


_WS = [
    {"stance": "supporting", "strength": 0.9, "summary": "meta"},
    {"stance": "supporting", "strength": 0.85, "summary": "rep"},
]


# --------------------------------------------------------------------------- #
# 1. Deterministic final_handling rule table (pure function)
# --------------------------------------------------------------------------- #
def test_final_handling_rule_table():
    S, L = EvidenceStatus, ArgLabel
    assert compute_final_handling(S.WELL_SUPPORTED, L.IN) == "primary_candidate"
    assert compute_final_handling(S.WELL_SUPPORTED, L.OUT) == "well_supported_but_defeated"
    assert compute_final_handling(S.WELL_SUPPORTED, L.UNDEC) == "well_supported_but_unresolved"
    assert compute_final_handling(S.WEAKLY_SUPPORTED, L.IN) == "tentative_candidate"
    assert compute_final_handling(S.WEAKLY_SUPPORTED, L.OUT) == "weak_and_defeated"
    assert compute_final_handling(S.MISSING, L.IN) == "structurally_acceptable_but_unsupported"
    assert compute_final_handling(S.MISSING, L.OUT) == "unsupported_and_defeated"
    assert compute_final_handling(S.CONTESTED, L.UNDEC) == "contested"
    # REFUTED dominates regardless of structural label -> never primary
    assert compute_final_handling(S.REFUTED, L.IN) == "refuted"
    assert compute_final_handling(S.REFUTED, L.OUT) == "refuted"


# --------------------------------------------------------------------------- #
# 2. Per-claim inclusion of evidence + argumentation
# --------------------------------------------------------------------------- #
def test_each_claim_view_includes_evidence_and_label():
    report, graph, n2c, raw = _report([{"name": "A", "evidence": list(_WS)}], focus="A")
    assert len(report.claims) >= 1
    for v in report.claims:
        assert v.evidence_status in {s.value for s in EvidenceStatus}
        assert isinstance(v.evidence_balance, dict) and "counts" in v.evidence_balance
        assert v.argumentation_label in {"IN", "OUT", "UNDEC", "UNLABELED"}
        assert v.final_handling  # non-empty


# --------------------------------------------------------------------------- #
# 3. WELL_SUPPORTED + IN -> primary_candidate
# --------------------------------------------------------------------------- #
def test_well_supported_in_is_primary_candidate():
    report, graph, n2c, raw = _report([{"name": "A", "evidence": list(_WS)}], focus="A")
    v = _view(report, n2c["A"])
    assert v.evidence_status == "WELL_SUPPORTED"
    assert v.argumentation_label == "IN"
    assert v.final_handling == "primary_candidate"
    assert report.summary["has_clean_primary"] is True
    assert report.summary["primary_claim_id"] == n2c["A"]
    assert report.summary["no_clean_answer"] is None


# --------------------------------------------------------------------------- #
# 4. WELL_SUPPORTED + OUT -> defeated, not clean primary
# --------------------------------------------------------------------------- #
def test_well_supported_out_is_not_clean_primary():
    report, graph, n2c, raw = _report(
        [{"name": "A", "evidence": list(_WS)}, {"name": "B", "evidence": []}],
        attacks=[{"type": "falsifies", "src": "B", "dst": "A"}],
        focus="A",
    )
    v = _view(report, n2c["A"])
    assert v.evidence_status == "WELL_SUPPORTED"
    assert v.argumentation_label == "OUT"
    assert v.final_handling == "well_supported_but_defeated"
    assert report.summary["has_clean_primary"] is False
    assert report.summary["primary_claim_id"] is None
    assert report.summary["no_clean_answer"] == NO_CLEAN_ANSWER


# --------------------------------------------------------------------------- #
# 5. REFUTED never primary (even when structurally IN)
# --------------------------------------------------------------------------- #
def test_refuted_never_primary():
    report, graph, n2c, raw = _report(
        [{"name": "A", "evidence": [{"stance": "contradicting", "strength": 0.85, "summary": "refute"}]}],
        focus="A",
    )
    v = _view(report, n2c["A"])
    assert v.evidence_status == "REFUTED"
    assert v.final_handling == "refuted"
    assert report.summary["has_clean_primary"] is False


# --------------------------------------------------------------------------- #
# 6. MISSING never clean primary
# --------------------------------------------------------------------------- #
def test_missing_never_clean_primary():
    report, graph, n2c, raw = _report([{"name": "A", "evidence": []}], focus="A")
    v = _view(report, n2c["A"])
    assert v.evidence_status == "MISSING"
    assert v.final_handling == "structurally_acceptable_but_unsupported"
    assert report.summary["has_clean_primary"] is False


# --------------------------------------------------------------------------- #
# 7. WEAKLY_SUPPORTED + IN is tentative only
# --------------------------------------------------------------------------- #
def test_weakly_supported_in_is_tentative_only():
    report, graph, n2c, raw = _report(
        [{"name": "A", "evidence": [{"stance": "weak", "strength": 0.5, "summary": "survey"}]}],
        focus="A",
    )
    v = _view(report, n2c["A"])
    assert v.evidence_status == "WEAKLY_SUPPORTED"
    assert v.argumentation_label == "IN"
    assert v.final_handling == "tentative_candidate"
    assert report.summary["has_clean_primary"] is False


# --------------------------------------------------------------------------- #
# 8. No WELL_SUPPORTED + IN -> humble no-clean-answer
# --------------------------------------------------------------------------- #
def test_no_well_supported_in_returns_humble_answer():
    report, graph, n2c, raw = _report(
        [
            {"name": "A", "evidence": [{"stance": "weak", "strength": 0.5, "summary": "w"}]},
            {"name": "B", "evidence": []},
        ],
        focus="A",
    )
    assert report.summary["has_clean_primary"] is False
    assert report.summary["primary_claim_id"] is None
    assert report.summary["no_clean_answer"] == NO_CLEAN_ANSWER


# --------------------------------------------------------------------------- #
# 9. Read-only / non-mutating; raw CBE unchanged
# --------------------------------------------------------------------------- #
def test_report_is_read_only_and_raw_cbe_unchanged():
    case = IntegrationCase(
        id="ro",
        focus="A",
        claims=[{"name": "A", "evidence": list(_WS)}, {"name": "B", "evidence": []}],
        attacks=[{"type": "falsifies", "src": "B", "dst": "A"}],
        gold={},
    )
    session, graph, n2c = build_case_graph(case)
    raw = produce_current_best_explanation(session).to_dict()
    raw_snapshot = copy.deepcopy(raw)
    states_before = {c: graph.claims[c].state for c in graph.claims}
    quality_before = {c: graph.claims[c].evidence_quality for c in graph.claims}
    n_nodes, n_edges = len(graph.nodes), len(graph.edges)

    report = build_integration_report(raw, graph)
    report2 = build_integration_report(raw, graph)  # idempotent

    assert {c: graph.claims[c].state for c in graph.claims} == states_before
    assert {c: graph.claims[c].evidence_quality for c in graph.claims} == quality_before
    assert len(graph.nodes) == n_nodes and len(graph.edges) == n_edges
    assert raw == raw_snapshot                      # raw CBE not mutated
    assert report.raw_cbe is raw                    # embedded verbatim
    assert "final_handling" not in raw and "argumentation_label" not in raw
    assert report.to_dict() == report2.to_dict()


# --------------------------------------------------------------------------- #
# 10. Existing layers unchanged
# --------------------------------------------------------------------------- #
def test_evidence_layer_behavior_unchanged():
    c = Claim(text="x", author_model="m")
    c.add_evidence(Evidence("e1", "x", quality=0.9))
    c.add_evidence(Evidence("e2", "y", quality=0.85))
    assert c.evidence_quality == 0.875  # mandatory legacy compat still holds
    assert evidence_status(c) == EvidenceStatus.WELL_SUPPORTED


def test_argumentation_behavior_unchanged():
    g = EpistemicGraph()
    a = Claim(text="A", author_model="m")
    b = Claim(text="B", author_model="m")
    g.add_claim(a)
    g.add_claim(b)
    g.link(a.claim_id, b.claim_id, EdgeType.FALSIFIES)
    lab = label_graph(g)
    assert lab.labels[a.claim_id] == ArgLabel.IN
    assert lab.labels[b.claim_id] == ArgLabel.OUT


# --------------------------------------------------------------------------- #
# 11. Benchmark + harness + CLI + no-live-calls
# --------------------------------------------------------------------------- #
def test_benchmark_loads_schema():
    from backend.evaluation.integration_harness import (
        load_integration_benchmark,
        INTEGRATION_SCHEMA_VERSION,
    )

    assert INTEGRATION_SCHEMA_VERSION == "ced_integration_eval_v0.1"
    cases = load_integration_benchmark()
    ids = {c.id for c in cases}
    assert {
        "ws_in_primary",
        "ws_out_defeated",
        "weak_in_tentative",
        "missing_in_unsupported",
        "refuted_never_primary",
        "contested_undec",
        "no_clean_answer",
    } <= ids


def test_benchmark_wrong_schema_raises(tmp_path):
    from backend.evaluation.integration_harness import load_integration_benchmark

    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": "nope", "cases": []}))
    with pytest.raises(ValueError):
        load_integration_benchmark(str(p))


def test_harness_metrics_all_pass():
    from backend.evaluation.integration_harness import run_integration_benchmark

    report = run_integration_benchmark()
    assert report.aggregate["passed_rate"] == 1.0
    assert all(c.passed for c in report.cases)


def test_cli_prints_only_json(capsys):
    from backend.evaluation.run_integration_eval import main

    main()
    out = capsys.readouterr().out
    data = json.loads(out)  # must parse cleanly
    assert data["schema_version"] == "ced_integration_eval_v0.1"
    assert data["aggregate"]["passed_rate"] == 1.0


def test_harness_makes_no_live_calls(monkeypatch):
    import socrates_ai

    def boom(*a, **k):
        raise AssertionError("live model call in integration harness")

    for m in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, m):
            monkeypatch.setattr(socrates_ai.DialogManager, m, boom, raising=False)

    from backend.evaluation.integration_harness import run_integration_benchmark

    report = run_integration_benchmark()
    assert report.case_count >= 7
