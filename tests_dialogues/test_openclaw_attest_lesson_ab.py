"""Tests for single-agent Lesson A/B -> governed Memory evidence."""

import importlib.util
import json
from pathlib import Path

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    RevisionEvidenceRegistry,
)

_ROOT = Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"
LESSON = "LESSON-0007"


@pytest.fixture(scope="module")
def script():
    path = _ROOT / "scripts" / "openclaw_attest_lesson_ab.py"
    spec = importlib.util.spec_from_file_location(
        "openclaw_attest_lesson_ab_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _lesson_text(status="stable"):
    return f"""
### {LESSON} — Evidence discipline
**Status:** {status}
**Lesson type:** behavioral
**Source:** test
**Use when:** evidence, review
**Problem pattern:** overclaiming
**Bad pattern:** assert without evidence
**Good pattern:** cite verified evidence
**Lesson:** State the evidence before the conclusion.
**Risk:** May become overly cautious.
---
"""


def _report(**updates):
    report = {
        "schema_version": "openclaw_single_agent_lesson_ab_result_v1",
        "target_agent_id": AGENT,
        "lesson_id": LESSON,
        "treatment_scope": "single_agent",
        "tested": 4,
        "min_tested": 3,
        "verdict": "helped",
        "helped": True,
        "mean_score_delta": 0.25,
        "harm_rate": 0.0,
        "max_harm_rate": 0.0,
        "ratification_regressions": 0,
        "unresolved_regressions": 0,
        "catastrophic_regressions": 0,
        "configuration_mismatches": 0,
        "source": "AgentLessonAB/report-1",
        "observed_on": "2026-07-10",
    }
    report.update(updates)
    return report


def _write_report(tmp_path, report=None):
    path = tmp_path / "agent_ab.json"
    path.write_text(json.dumps(report or _report()), encoding="utf-8")
    return path


def _env(tmp_path, *, lesson_status="stable"):
    lessons = tmp_path / "MEMORY_LESSONS.md"
    lessons.write_text(_lesson_text(lesson_status), encoding="utf-8")
    return {
        "CED_MEMORY_LESSONS_PATH": str(lessons),
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
        "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
        "CED_ATTEST_DATE": "2026-07-10",
    }


def _argv(report_path, action="link", verifier="Operator"):
    return [
        "prog", AGENT,
        "--report", str(report_path),
        "--action", action,
        "--verified-by", verifier,
        "--verification-reference", "review/agent-ab-1",
    ]


def test_helped_single_agent_report_builds_link_evidence(script, tmp_path):
    env = _env(tmp_path)
    path = _write_report(tmp_path)
    assert script.main(_argv(path), env=env) == 0
    records = RevisionEvidenceRegistry(
        env["CED_SELF_REVISION_EVIDENCE_DIR"]).all_records()
    assert len(records) == 1
    evidence = records[0]
    assert evidence.agent_id == AGENT
    assert evidence.value == LESSON
    assert evidence.supports == ("memory:link_stable_lesson",)
    assert evidence.outcomes == ("confirmed",)


def test_link_requires_curated_stable_or_verified_lesson(
        script, tmp_path, capsys):
    env = _env(tmp_path, lesson_status="tested")
    path = _write_report(tmp_path)
    assert script.main(_argv(path), env=env) == 1
    assert "already stable/verified" in capsys.readouterr().out


def test_wrong_agent_self_attestation_and_whole_council_are_refused(
        script, tmp_path, capsys):
    env = _env(tmp_path)
    wrong = _write_report(tmp_path, _report(target_agent_id="agent_beta"))
    assert script.main(_argv(wrong), env=env) == 1
    assert "belongs to another agent" in capsys.readouterr().out

    own = _write_report(tmp_path, _report())
    assert script.main(_argv(own, verifier=AGENT.upper()), env=env) == 1
    assert "cannot attest its own" in capsys.readouterr().out

    council = _write_report(tmp_path, _report(treatment_scope="whole_council"))
    assert script.main(_argv(council), env=env) == 1
    assert "single_agent" in capsys.readouterr().out


def test_harm_or_no_effect_cannot_create_link_evidence(
        script, tmp_path, capsys):
    env = _env(tmp_path)
    harmed = _write_report(tmp_path, _report(
        verdict="harmed", helped=False, mean_score_delta=-0.2,
        harm_rate=0.5, ratification_regressions=1))
    assert script.main(_argv(harmed, action="link"), env=env) == 1
    assert "link evidence requires" in capsys.readouterr().out

    no_effect = _write_report(tmp_path, _report(
        verdict="no_effect", helped=False, mean_score_delta=0.0))
    assert script.main(_argv(no_effect, action="link"), env=env) == 1
    assert "link evidence requires" in capsys.readouterr().out


def test_harmed_report_builds_unlink_only_for_currently_linked_lesson(
        script, tmp_path, capsys):
    env = _env(tmp_path)
    path = _write_report(tmp_path, _report(
        verdict="harmed", helped=False, mean_score_delta=-0.2,
        harm_rate=0.5, ratification_regressions=1))
    assert script.main(_argv(path, action="unlink"), env=env) == 1
    assert "existing identity profile" in capsys.readouterr().out

    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(
        AgentIdentityProfile(
            agent_id=AGENT,
            identity_version="v0.3",
            promotion_status="shadow_apprentice",
            stable_lessons=(LESSON,),
        )
    )
    assert script.main(_argv(path, action="unlink"), env=env) == 0
    evidence = RevisionEvidenceRegistry(
        env["CED_SELF_REVISION_EVIDENCE_DIR"]).all_records()[0]
    assert evidence.supports == (
        "memory:link_stable_lesson", "memory:unlink_stable_lesson")
    assert evidence.outcomes == ("reverted",)


def test_unlink_refuses_unlinked_lesson(script, tmp_path, capsys):
    env = _env(tmp_path)
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(
        AgentIdentityProfile(
            agent_id=AGENT,
            identity_version="v0.3",
            promotion_status="shadow_apprentice",
        )
    )
    path = _write_report(tmp_path, _report(
        verdict="harmed", helped=False, mean_score_delta=-0.2,
        harm_rate=0.5, ratification_regressions=1))
    assert script.main(_argv(path, action="unlink"), env=env) == 1
    assert "currently linked" in capsys.readouterr().out


def test_exact_rerun_is_idempotent_and_changed_result_appends(script, tmp_path):
    env = _env(tmp_path)
    path = _write_report(tmp_path)
    argv = _argv(path)
    assert script.main(argv, env=env) == 0
    assert script.main(argv, env=env) == 0
    registry = RevisionEvidenceRegistry(
        env["CED_SELF_REVISION_EVIDENCE_DIR"])
    assert len(registry.all_records()) == 1

    path.write_text(json.dumps(_report(
        tested=5, mean_score_delta=0.30,
        source="AgentLessonAB/report-2")), encoding="utf-8")
    assert script.main(argv, env=env) == 0
    assert len(registry.all_records()) == 2


def test_schema_corrupt_json_and_secret_shaped_source_fail_closed(
        script, tmp_path, capsys):
    env = _env(tmp_path)
    path = _write_report(tmp_path, _report(authority="grant"))
    assert script.main(_argv(path), env=env) == 1
    assert "missing or unknown fields" in capsys.readouterr().out

    path.write_text("{not-json", encoding="utf-8")
    assert script.main(_argv(path), env=env) == 1
    assert "unreadable or corrupt" in capsys.readouterr().out

    fake_secret = "api" + "_key=" + "abcdefgh12345678"
    path.write_text(json.dumps(_report(source=fake_secret)), encoding="utf-8")
    assert script.main(_argv(path), env=env) == 1
    assert "secret-shaped" in capsys.readouterr().out
