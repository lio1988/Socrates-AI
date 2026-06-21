"""
Tests for Argumentation Framework v0.1 (Abstract Dung + grounded labeling).

Covers: the five canonical grounded cases, attack directionality (FALSIFIES
directed / CONTRADICTS symmetric), the claim-only scope lock (evidence nodes and
SUPPORTS edges ignored, REJECTED claims excluded), determinism, non-mutation,
benchmark loading, harness metrics, and the no-live-call guard.
"""

import json

import pytest

from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.epistemic_graph import EpistemicGraph, NodeType, EdgeType
from backend.epistemic.argumentation_framework import (
    ArgLabel,
    argument_ids,
    build_af_from_graph,
    grounded_labeling,
    label_graph,
)


def _graph(names):
    """Build a graph with one claim per symbolic name; return (graph, name->cid)."""
    g = EpistemicGraph()
    cid = {}
    for n in names:
        c = Claim(text=f"Claim {n}", author_model="t")
        g.add_claim(c)
        cid[n] = c.claim_id
    return g, cid


# --------------------------------------------------------------------------- #
# Canonical grounded cases
# --------------------------------------------------------------------------- #
def test_unattacked_is_in():
    g, cid = _graph(["A"])
    lab = label_graph(g)
    assert lab.labels[cid["A"]] == ArgLabel.IN
    assert lab.grounded_extension == [cid["A"]]


def test_single_attack_gives_in_out():
    g, cid = _graph(["A", "B"])
    g.link(cid["A"], cid["B"], EdgeType.FALSIFIES)
    lab = label_graph(g)
    assert lab.labels[cid["A"]] == ArgLabel.IN
    assert lab.labels[cid["B"]] == ArgLabel.OUT


def test_mutual_attack_gives_both_undec():
    g, cid = _graph(["A", "B"])
    g.link(cid["A"], cid["B"], EdgeType.CONTRADICTS)
    lab = label_graph(g)
    assert lab.labels[cid["A"]] == ArgLabel.UNDEC
    assert lab.labels[cid["B"]] == ArgLabel.UNDEC
    assert lab.grounded_extension == []


def test_chain_gives_in_out_in():
    g, cid = _graph(["A", "B", "C"])
    g.link(cid["A"], cid["B"], EdgeType.FALSIFIES)
    g.link(cid["B"], cid["C"], EdgeType.FALSIFIES)
    lab = label_graph(g)
    assert lab.labels[cid["A"]] == ArgLabel.IN
    assert lab.labels[cid["B"]] == ArgLabel.OUT
    assert lab.labels[cid["C"]] == ArgLabel.IN


def test_self_attack_gives_undec():
    g, cid = _graph(["A"])
    g.link(cid["A"], cid["A"], EdgeType.FALSIFIES)
    lab = label_graph(g)
    assert lab.labels[cid["A"]] == ArgLabel.UNDEC
    assert lab.grounded_extension == []


# --------------------------------------------------------------------------- #
# Attack directionality
# --------------------------------------------------------------------------- #
def test_falsifies_is_directed():
    g, cid = _graph(["A", "B"])
    g.link(cid["A"], cid["B"], EdgeType.FALSIFIES)
    af = build_af_from_graph(g)
    assert (cid["A"], cid["B"]) in af.attacks
    assert (cid["B"], cid["A"]) not in af.attacks
    assert af.attacked_by[cid["A"]] == [cid["B"]]
    assert af.attackers_by[cid["A"]] == []


def test_contradicts_is_symmetric():
    g, cid = _graph(["A", "B"])
    g.link(cid["A"], cid["B"], EdgeType.CONTRADICTS)
    af = build_af_from_graph(g)
    assert (cid["A"], cid["B"]) in af.attacks
    assert (cid["B"], cid["A"]) in af.attacks
    assert af.attackers_by[cid["A"]] == [cid["B"]]
    assert af.attackers_by[cid["B"]] == [cid["A"]]


# --------------------------------------------------------------------------- #
# Claim-only scope lock
# --------------------------------------------------------------------------- #
def test_evidence_nodes_are_not_arguments():
    g, cid = _graph(["A"])
    ev = g.add_node(NodeType.EVIDENCE, "some evidence", payload={"claim_id": cid["A"]})
    af = build_af_from_graph(g)
    assert af.arguments == [cid["A"]]
    assert ev not in af.arguments
    assert argument_ids(g) == [cid["A"]]


def test_evidence_contradicts_claim_creates_no_claim_attack():
    g, cid = _graph(["A"])
    ev = g.add_node(NodeType.EVIDENCE, "contradicting evidence")
    g.link(ev, cid["A"], EdgeType.CONTRADICTS)  # evidence-node -> claim
    af = build_af_from_graph(g)
    assert af.attacks == set()                  # no claim-to-claim attack
    lab = grounded_labeling(af)
    assert lab.labels[cid["A"]] == ArgLabel.IN  # claim unattacked at claim level


def test_supports_edges_are_ignored():
    g, cid = _graph(["A", "B"])
    g.link(cid["A"], cid["B"], EdgeType.SUPPORTS)
    af = build_af_from_graph(g)
    assert af.attacks == set()
    lab = grounded_labeling(af)
    assert lab.labels[cid["A"]] == ArgLabel.IN
    assert lab.labels[cid["B"]] == ArgLabel.IN


def test_rejected_claims_excluded_from_args():
    g, cid = _graph(["A", "B"])
    g.claims[cid["A"]].transition(EpistemicState.REJECTED, actor="t", reason="r")
    g.link(cid["A"], cid["B"], EdgeType.FALSIFIES)  # rejected A "attacks" B
    af = build_af_from_graph(g)
    assert af.arguments == [cid["B"]]               # A is not an argument
    assert af.attacks == set()                      # attack from non-arg dropped
    lab = grounded_labeling(af)
    assert lab.labels[cid["B"]] == ArgLabel.IN
    assert cid["A"] not in lab.labels


# --------------------------------------------------------------------------- #
# Determinism and non-mutation
# --------------------------------------------------------------------------- #
def test_output_is_deterministic_and_sorted():
    g, cid = _graph(["A", "B", "C"])
    g.link(cid["A"], cid["B"], EdgeType.CONTRADICTS)
    g.link(cid["C"], cid["B"], EdgeType.FALSIFIES)
    assert label_graph(g).to_dict() == label_graph(g).to_dict()
    af = build_af_from_graph(g)
    assert af.arguments == sorted(af.arguments)
    for a in af.arguments:
        assert af.attackers_by[a] == sorted(af.attackers_by[a])
        assert af.attacked_by[a] == sorted(af.attacked_by[a])


def test_labeling_does_not_mutate_graph_or_claims():
    g, cid = _graph(["A", "B"])
    g.link(cid["A"], cid["B"], EdgeType.FALSIFIES)
    states_before = {c: g.claims[c].state for c in g.claims}
    n_nodes, n_edges = len(g.nodes), len(g.edges)
    _ = label_graph(g)
    assert {c: g.claims[c].state for c in g.claims} == states_before
    assert len(g.nodes) == n_nodes and len(g.edges) == n_edges


# --------------------------------------------------------------------------- #
# Benchmark + harness
# --------------------------------------------------------------------------- #
def test_benchmark_loads_schema():
    from backend.evaluation.argumentation_harness import (
        load_arg_benchmark,
        ARG_SCHEMA_VERSION,
    )

    assert ARG_SCHEMA_VERSION == "ced_argumentation_eval_v0.1"
    cases = load_arg_benchmark()
    ids = {c.id for c in cases}
    assert {
        "unattacked",
        "single_attack_falsifies",
        "mutual_attack_contradicts",
        "chain",
        "self_attack",
    } <= ids


def test_benchmark_wrong_schema_raises(tmp_path):
    from backend.evaluation.argumentation_harness import load_arg_benchmark

    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": "nope", "cases": []}))
    with pytest.raises(ValueError):
        load_arg_benchmark(str(p))


def test_harness_metrics_all_pass():
    from backend.evaluation.argumentation_harness import run_arg_benchmark

    report = run_arg_benchmark()
    assert report.aggregate["passed_rate"] == 1.0
    assert report.aggregate["labels_correct_rate"] == 1.0
    assert report.aggregate["extension_correct_rate"] == 1.0
    assert all(c.passed for c in report.cases)


def test_harness_makes_no_live_calls(monkeypatch):
    import socrates_ai

    def boom(*a, **k):
        raise AssertionError("live model call in argumentation harness")

    for m in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, m):
            monkeypatch.setattr(socrates_ai.DialogManager, m, boom, raising=False)

    from backend.evaluation.argumentation_harness import run_arg_benchmark

    report = run_arg_benchmark()
    assert report.case_count >= 5
