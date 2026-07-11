"""Retained Tree Evidence Operator Bridge tests.

The golden invariant: a RETAINED session must yield byte-identical
observations to the LIVE session it captured (same extractor, same digests),
so the report step and the attestation step can never disagree with runtime
reality.

All offline: mock council with tree expansions, no providers, no keys.
"""

import dataclasses
import importlib.util
import json
import pathlib

import pytest

from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode
from backend.dialogues.openclaw_identity import (
    RevisionEvidenceRegistry,
    TreeRevisionObservation,
    extract_tree_revision_observations,
    load_tree_session_artifact,
    retain_tree_session,
    save_tree_session_artifact,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(
        f"{name}_script", _ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report_script():
    return _script("openclaw_tree_evidence")


@pytest.fixture(scope="module")
def attest_script():
    return _script("openclaw_attest_tree_evidence")


@pytest.fixture(scope="module")
def live_session():
    import asyncio
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           tree_expansions=2)
    final = asyncio.run(ced.run_registry_session(
        "retained tree bridge", session_id="tree_bridge_1"))
    return ced.get_session("tree_bridge_1"), final


# --------------------------------------------------------------------------- #
# Retention round-trip: retained == live, tamper-evident
# --------------------------------------------------------------------------- #

def test_retained_session_yields_identical_observations(live_session,
                                                        tmp_path):
    state, final = live_session
    live = extract_tree_revision_observations(state, final)
    path = save_tree_session_artifact(state, final, tmp_path)
    retained = load_tree_session_artifact(path)
    replayed = extract_tree_revision_observations(
        retained.state, retained.final)
    assert [item.to_record() for item in replayed] == \
        [item.to_record() for item in live]
    assert [item.observation_digest for item in replayed] == \
        [item.observation_digest for item in live]


def test_tampered_artifact_is_refused(live_session, tmp_path):
    state, final = live_session
    path = save_tree_session_artifact(state, final, tmp_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["question"] = record["question"] + " (edited)"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_tree_session_artifact(path)


def test_unknown_artifact_fields_are_refused(live_session, tmp_path):
    state, final = live_session
    record = retain_tree_session(state, final)
    record["extra"] = True
    with pytest.raises(ValueError, match="missing or unknown"):
        load_tree_session_artifact(record)


# --------------------------------------------------------------------------- #
# Report script: read-only recomputation
# --------------------------------------------------------------------------- #

def test_report_script_writes_versioned_report_and_registers_nothing(
        live_session, tmp_path, capsys):
    state, final = live_session
    artifact = save_tree_session_artifact(state, final, tmp_path)
    script = _script("openclaw_tree_evidence")
    rc = script.main(["prog", str(artifact), "--out", str(tmp_path / "out")],
                     env={})
    assert rc == 0
    out = capsys.readouterr().out
    assert "Nothing was registered" in out
    report_path = tmp_path / "out" / \
        "TREE_EVIDENCE_REPORT_tree_bridge_1.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "openclaw_tree_evidence_report_v1"
    live = extract_tree_revision_observations(state, final)
    assert report["observations"] == [item.to_record() for item in live]
    # Read-only: no evidence registry anywhere under tmp.
    assert not list((tmp_path / "out").glob("*.evidence*"))


def test_report_script_refuses_tampered_artifact(live_session, tmp_path,
                                                 capsys):
    state, final = live_session
    artifact = save_tree_session_artifact(state, final, tmp_path)
    record = json.loads(artifact.read_text(encoding="utf-8"))
    record["session_id"] = "forged"
    artifact.write_text(json.dumps(record), encoding="utf-8")
    script = _script("openclaw_tree_evidence")
    assert script.main(["prog", str(artifact)], env={
        "CED_TREE_EVIDENCE_DIR": str(tmp_path / "out")}) == 1
    assert "REFUSED" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Attestation script: named human act over cited digests
# --------------------------------------------------------------------------- #

AGENT = "agent_tree"


def _observation(session, key, margin, *, outcome):
    parent, child = 6.0, 6.0 + margin
    return TreeRevisionObservation(
        session_id=session,
        comparison_key=key,
        question_hash="a" * 64,
        agent_id=AGENT,
        provider_id="prov_tree",
        parent_draft_id=f"draft_p_{session}",
        child_draft_id=f"draft_c_{session}",
        parent_score=parent,
        child_score=child,
        margin=margin,
        effect_margin=0.5,
        outcome=outcome,
        matched_score_count=2,
        judge_ids=("judge_a", "judge_b"),
        matched_sections=("blind_spots", "core_answer"),
        tree_exploration=0.5,
        tree_total_expansions=2,
        scorecard_digest="b" * 64,
        source_trace=f"ced-tree://{session}/draft_c_{session}#deadbeef",
    )


def _write_report(tmp_path, observations):
    from backend.dialogues.openclaw_identity.tree_revision_schema import digest
    report = {
        "schema_version": "openclaw_tree_evidence_report_v1",
        "session_id": "synthetic",
        "artifact": "synthetic",
        "parameters": {"agent_id": None, "effect_margin": 0.5,
                       "min_matched_scores": 1},
        "observations": [item.to_record() for item in observations],
        "summaries": {},
    }
    report["report_digest"] = digest(dict(report))
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _attest_argv(report_path, *, kind="failure", digests=(), before=(),
                 after=(), verified_by="Operator"):
    argv = ["prog", AGENT, "--report", str(report_path), "--kind", kind,
            "--pattern-key", "tree_regression:core",
            "--weakness", "revisions regress the core answer",
            "--verified-by", verified_by,
            "--verification-reference", "review/tree-001"]
    for value in digests:
        argv += ["--observation", value]
    for value in before:
        argv += ["--before", value]
    for value in after:
        argv += ["--after", value]
    return argv


def test_attest_failure_happy_path_idempotent_and_immutable(
        attest_script, tmp_path, capsys):
    regressions = [
        _observation("s1", "q1", -1.0, outcome="regressed"),
        _observation("s2", "q2", -0.8, outcome="regressed"),
    ]
    report = _write_report(tmp_path, regressions)
    env = {"CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
           "CED_ATTEST_DATE": "2026-07-10"}
    digests = [item.observation_digest for item in regressions]
    assert attest_script.main(
        _attest_argv(report, digests=digests), env=env) == 0
    out = capsys.readouterr().out
    assert "Nothing was proposed" in out
    registry = RevisionEvidenceRegistry(tmp_path / "evidence")
    records = registry.all_records()
    assert len(records) == 1
    assert records[0].agent_id == AGENT
    assert records[0].supports == ("identity:add_known_failure",)
    # Exact rerun: idempotent, still one record.
    assert attest_script.main(
        _attest_argv(report, digests=digests), env=env) == 0
    assert len(registry.all_records()) == 1


def test_attest_refuses_unknown_digest_self_verifier_and_tamper(
        attest_script, tmp_path, capsys):
    regressions = [
        _observation("s1", "q1", -1.0, outcome="regressed"),
        _observation("s2", "q2", -0.8, outcome="regressed"),
    ]
    report = _write_report(tmp_path, regressions)
    env = {"CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence")}
    good = [item.observation_digest for item in regressions]

    assert attest_script.main(_attest_argv(
        report, digests=["f" * 64, good[1]]), env=env) == 1
    assert "not in the report" in capsys.readouterr().out

    assert attest_script.main(_attest_argv(
        report, digests=good, verified_by=AGENT.upper()), env=env) == 1
    assert "cannot attest its own" in capsys.readouterr().out

    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["observations"][0]["margin"] = -2.0
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert attest_script.main(_attest_argv(report, digests=good), env=env) == 1
    assert "digest mismatch" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_attest_refuses_non_regressed_and_insufficient_observations(
        attest_script, tmp_path, capsys):
    mixed = [
        _observation("s1", "q1", -1.0, outcome="regressed"),
        _observation("s2", "q2", 1.0, outcome="improved"),
    ]
    report = _write_report(tmp_path, mixed)
    env = {"CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence")}
    digests = [item.observation_digest for item in mixed]
    assert attest_script.main(_attest_argv(report, digests=digests),
                              env=env) == 1
    assert "concrete regressions" in capsys.readouterr().out
    assert attest_script.main(_attest_argv(report, digests=digests[:1]),
                              env=env) == 1
    assert "repeated regressions" in capsys.readouterr().out


def test_attest_resolution_happy_path(attest_script, tmp_path, capsys):
    before = [
        _observation("s1", "q1", -1.0, outcome="regressed"),
        _observation("s2", "q2", -0.8, outcome="regressed"),
    ]
    after = [
        _observation("s3", "q1", 1.0, outcome="improved"),
        _observation("s4", "q2", 0.9, outcome="improved"),
    ]
    report = _write_report(tmp_path, before + after)
    env = {"CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence")}
    argv = _attest_argv(
        report, kind="resolution",
        before=[item.observation_digest for item in before],
        after=[item.observation_digest for item in after])
    assert attest_script.main(argv, env=env) == 0
    records = RevisionEvidenceRegistry(tmp_path / "evidence").all_records()
    assert len(records) == 1
    assert records[0].supports == ("identity:add_known_failure",
                                   "identity:resolve_known_failure")
    assert records[0].outcomes == ("reverted",)


def test_attest_resolution_refuses_unmatched_windows(attest_script, tmp_path,
                                                     capsys):
    before = [
        _observation("s1", "q1", -1.0, outcome="regressed"),
        _observation("s2", "q2", -0.8, outcome="regressed"),
    ]
    after = [
        _observation("s3", "q1", 1.0, outcome="improved"),
        _observation("s4", "qX", 0.9, outcome="improved"),   # key mismatch
    ]
    report = _write_report(tmp_path, before + after)
    env = {"CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence")}
    argv = _attest_argv(
        report, kind="resolution",
        before=[item.observation_digest for item in before],
        after=[item.observation_digest for item in after])
    assert attest_script.main(argv, env=env) == 1
    assert "matched comparison keys" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()
