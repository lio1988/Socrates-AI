"""CED Graph v7 — Epistemic Replay / Audit Trail Export tests."""

from types import SimpleNamespace

from backend.orchestrator.epistemic_replay import (
    REPLAY_VERSION,
    canonical_replay_json,
    export_audit_trail,
    export_epistemic_replay,
)
from backend.orchestrator.live_epistemics import (
    apply_elenchus_to_claim,
    apply_revision_to_claim,
    produce_current_best_explanation,
    record_epistemic_claim,
    record_epistemic_question,
)


def _session(topic="Is knowledge a process or a final answer?"):
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
        challenged_assumptions=["assumes certainty is stable"],
        logic_gaps=["unsupported universal conclusion"] if falsified else [],
        evidence_issues=[],
        conclusion_issues=[],
    )


def _rich_session():
    s = _session()
    record_epistemic_question(s, "socrates", "What would make this claim false?", 1)
    c1 = record_epistemic_claim(
        s,
        "claude",
        "Knowledge is a revisable process because evidence can change what is justified.",
        1,
    )
    record_epistemic_claim(
        s,
        "chatgpt",
        "A final answer can still be provisional when stronger evidence appears.",
        1,
    )
    apply_elenchus_to_claim(s, _elenchus(c1, falsified=True))
    apply_revision_to_claim(
        s,
        c1,
        "Knowledge is a revisable process, but the reliability of revision also matters.",
        actor="claude",
    )
    produce_current_best_explanation(s)
    return s


def test_replay_export_returns_full_structure():
    replay = export_epistemic_replay(_rich_session())
    assert replay["replay_version"] == REPLAY_VERSION
    for key in (
        "metadata",
        "graph",
        "claim_timeline",
        "epistemic_trace",
        "current_best_explanation",
        "process_evaluation",
        "audit_checks",
    ):
        assert key in replay
    assert replay["metadata"]["claim_count"] >= 2
    assert replay["graph"]["nodes"]
    assert replay["graph"]["edges"]
    assert replay["claim_timeline"]


def test_replay_export_includes_v5_lineage():
    replay = export_epistemic_replay(_rich_session())
    assert replay["metadata"]["lineage_event_count"] > 0
    lineage_rows = [row["lineage"] for row in replay["claim_timeline"] if row["lineage"]]
    assert lineage_rows
    event_types = set()
    for lineage in lineage_rows:
        event_types.update(lineage.get("event_types", []))
    assert "created" in event_types
    assert "challenged" in event_types
    assert "revised" in event_types
    assert "used_in_current_best_explanation" in event_types


def test_replay_export_includes_v6_process_evaluation():
    replay = export_epistemic_replay(_rich_session())
    process = replay["process_evaluation"]
    assert process is not None
    assert "process_score" in process
    assert "process_level" in process
    assert "metrics" in process
    assert 0.0 <= process["process_score"] <= 1.0


def test_audit_checks_confirm_cbe_does_not_invent_claim_ids():
    replay = export_epistemic_replay(_rich_session())
    checks = replay["audit_checks"]
    assert checks["cbe_claim_ids_exist"] is True
    assert checks["cbe_invents_no_new_claims"] is True
    assert checks["all_lineage_claim_ids_exist"] is True
    assert checks["exported_claim_count_matches_graph"] is True
    assert checks["deterministic_ordering"] is True


def test_canonical_replay_json_is_deterministic():
    s = _rich_session()
    a = canonical_replay_json(s)
    b = canonical_replay_json(s)
    assert a == b
    assert '"replay_version":"v7"' in a


def test_empty_session_exports_safely():
    replay = export_epistemic_replay(_session("Empty topic"))
    assert replay["metadata"]["claim_count"] == 0
    assert replay["metadata"]["lineage_event_count"] == 0
    assert replay["graph"]["nodes"] == []
    assert replay["graph"]["edges"] == []
    assert replay["claim_timeline"] == []
    assert replay["current_best_explanation"] is None
    assert replay["process_evaluation"] is None
    assert replay["audit_checks"]["cbe_invents_no_new_claims"] is True


def test_export_audit_trail_is_compact_view():
    audit = export_audit_trail(_rich_session())
    assert audit["replay_version"] == REPLAY_VERSION
    assert "metadata" in audit
    assert "audit_checks" in audit
    assert "claim_timeline" in audit
    assert audit["current_best_explanation"] is not None
    assert audit["process_evaluation"] is not None
