"""
Tests for the CED demo report service v0.1.

Covers: build without live calls, demo schema, required top-level keys, the three
demo scenarios (clean primary / supported-but-defeated / humble), per-claim
evidence_status + argumentation_label + final_handling, raw CBE left unchanged,
determinism per case_id, unknown case_id -> ValueError, JSON-only CLI, benchmark
loading, harness metrics, and that the underlying layers are unchanged.
"""

import json

import pytest

from backend.epistemic.claim import Claim, Evidence
from backend.epistemic.epistemic_graph import EpistemicGraph, EdgeType
from backend.epistemic.evidence_scoring import evidence_status, EvidenceStatus
from backend.epistemic.argumentation_framework import label_graph, ArgLabel
from backend.demo.ced_demo_report import (
    DEMO_REPORT_SCHEMA,
    build_demo_report,
    list_demo_cases,
)


def _epistemic_view(out: dict) -> dict:
    """Deterministic projection (no timestamps) for equality checks."""
    return {
        "summary": out["summary"],
        "focus": out["focus"],
        "claims": {
            c["claim_id"]: (c["evidence_status"], c["argumentation_label"], c["final_handling"])
            for c in out["integration_report"]["claims"]
        },
    }


# --------------------------------------------------------------------------- #
# Shape / schema
# --------------------------------------------------------------------------- #
def test_demo_report_schema_and_keys():
    out = build_demo_report("default")
    assert out["schema_version"] == DEMO_REPORT_SCHEMA == "ced_demo_report_v0.1"
    for key in ("question", "raw_cbe", "integration_report", "summary", "note"):
        assert key in out
    assert out["note"] == "Demo uses scripted local fixtures; not a live answer."


def test_default_case_id_is_available():
    assert "default" in list_demo_cases()


# --------------------------------------------------------------------------- #
# The three demo scenarios
# --------------------------------------------------------------------------- #
def test_clean_supported_case_has_clean_primary():
    out = build_demo_report("default")
    assert out["summary"]["has_clean_primary"] is True
    assert out["focus"]["evidence_status"] == "WELL_SUPPORTED"
    assert out["focus"]["argumentation_label"] == "IN"
    assert out["focus"]["final_handling"] == "primary_candidate"


def test_supported_but_defeated_has_no_clean_primary():
    out = build_demo_report("supported_but_defeated")
    assert out["focus"]["evidence_status"] == "WELL_SUPPORTED"
    assert out["focus"]["argumentation_label"] == "OUT"
    assert out["focus"]["final_handling"] == "well_supported_but_defeated"
    assert out["summary"]["has_clean_primary"] is False
    assert out["summary"]["primary_claim_id"] is None


def test_uncertain_case_returns_humble_answer():
    out = build_demo_report("uncertain")
    assert out["summary"]["has_clean_primary"] is False
    assert out["summary"]["no_clean_answer"]  # humble message present
    assert out["focus"]["final_handling"] == "tentative_candidate"


# --------------------------------------------------------------------------- #
# Per-claim content + raw CBE integrity
# --------------------------------------------------------------------------- #
def test_integration_report_includes_per_claim_fields():
    out = build_demo_report("supported_but_defeated")
    claims = out["integration_report"]["claims"]
    assert len(claims) >= 2
    for c in claims:
        assert c["evidence_status"] in {s.value for s in EvidenceStatus}
        assert c["argumentation_label"] in {"IN", "OUT", "UNDEC", "UNLABELED"}
        assert c["final_handling"]
        assert isinstance(c["evidence_balance"], dict) and "counts" in c["evidence_balance"]


def test_raw_cbe_has_no_integration_keys_injected():
    out = build_demo_report("default")
    raw = out["raw_cbe"]
    assert "final_handling" not in raw
    assert "argumentation_label" not in raw
    assert "evidence_status" not in raw


# --------------------------------------------------------------------------- #
# Determinism + error handling
# --------------------------------------------------------------------------- #
def test_service_is_deterministic_for_same_case_id():
    a = build_demo_report("supported_but_defeated")
    b = build_demo_report("supported_but_defeated")
    assert _epistemic_view(a) == _epistemic_view(b)


def test_unknown_case_id_raises_value_error():
    with pytest.raises(ValueError):
        build_demo_report("does_not_exist")


# --------------------------------------------------------------------------- #
# CLI + benchmark + harness + no-live-calls
# --------------------------------------------------------------------------- #
def test_cli_prints_only_json(capsys):
    from backend.evaluation.run_demo_report_eval import main

    main()
    out = capsys.readouterr().out
    data = json.loads(out)  # must parse cleanly
    assert data["schema_version"] == "ced_demo_report_eval_v0.1"
    assert data["aggregate"]["passed_rate"] == 1.0


def test_benchmark_loads_schema():
    from backend.evaluation.demo_report_harness import (
        load_demo_benchmark,
        DEMO_EVAL_SCHEMA_VERSION,
    )

    assert DEMO_EVAL_SCHEMA_VERSION == "ced_demo_report_eval_v0.1"
    cases = load_demo_benchmark()
    ids = {c.case_id for c in cases}
    assert {"default", "supported_but_defeated", "uncertain"} <= ids


def test_benchmark_wrong_schema_raises(tmp_path):
    from backend.evaluation.demo_report_harness import load_demo_benchmark

    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": "nope", "cases": []}))
    with pytest.raises(ValueError):
        load_demo_benchmark(str(p))


def test_harness_metrics_all_pass():
    from backend.evaluation.demo_report_harness import run_demo_benchmark

    report = run_demo_benchmark()
    assert report.aggregate["passed_rate"] == 1.0
    assert all(c.passed for c in report.cases)


def test_demo_makes_no_live_calls(monkeypatch):
    import socrates_ai

    def boom(*a, **k):
        raise AssertionError("live model call in demo report")

    for m in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, m):
            monkeypatch.setattr(socrates_ai.DialogManager, m, boom, raising=False)

    out = build_demo_report("default")
    assert out["schema_version"] == "ced_demo_report_v0.1"


# --------------------------------------------------------------------------- #
# Underlying layers unchanged
# --------------------------------------------------------------------------- #
def test_evidence_layer_behavior_unchanged():
    c = Claim(text="x", author_model="m")
    c.add_evidence(Evidence("e1", "x", quality=0.9))
    c.add_evidence(Evidence("e2", "y", quality=0.85))
    assert c.evidence_quality == 0.875
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
