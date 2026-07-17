"""Tests for bound single-agent Lesson A/B -> governed Memory evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from backend.dialogues.openclaw_identity import (
    AGENT_LESSON_AB_REPORT_VERSION,
    AgentIdentityProfile,
    IdentityRegistry,
    RevisionEvidenceRegistry,
    governed_profile_fingerprint,
)
from backend.dialogues.openclaw_memory import (
    load_memory_lessons,
    memory_lesson_fingerprint,
)

_ROOT = Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"
LESSON = "LESSON-0007"
ATTESTATION_VERSION = "openclaw_agent_lesson_ab_attestation_v1"
EXPERIMENT_VERSION = "openclaw_agent_lesson_ab_experiment_v1"


@pytest.fixture(scope="module")
def attest_script():
    path = _ROOT / "scripts" / "openclaw_attest_lesson_ab.py"
    spec = importlib.util.spec_from_file_location(
        "openclaw_attest_lesson_ab_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _digest(value):
    return hashlib.sha256(json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _lesson_markdown(status="stable", lesson_text=None):
    lesson_text = lesson_text or \
        "Verify every exact-output constraint before finalizing."
    return f"""# Test catalogue

### {LESSON} — Exact-output discipline

**Status:** {status}
**Lesson type:** behavioral
**Source:** test harness
**Use when:** synthesis, exact output
**Problem pattern:** Agent rushes exact-output tasks.
**Bad pattern:** Ignore exact constraints.
**Good pattern:** Check every exact constraint.
**Lesson:** {lesson_text}
**Risk:** May over-constrain open-ended tasks.

---
"""


def _report(**updates):
    report = {
        "schema_version": AGENT_LESSON_AB_REPORT_VERSION,
        "reference": "agent-ab/local-apprentice-001/lesson-0007/helped-1",
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
        "verified_by": "Operator",
        "verification_reference": "review/agent-ab-1",
        "observed_on": "2026-07-10",
    }
    report.update(updates)
    return report


def _env(tmp_path):
    lessons_path = tmp_path / "MEMORY_LESSONS.md"
    if not lessons_path.exists():
        lessons_path.write_text(_lesson_markdown(), encoding="utf-8")
    return {
        "CED_MEMORY_LESSONS_PATH": str(lessons_path),
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
        "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
    }


def _save_profile(tmp_path, *, linked=()):
    env = _env(tmp_path)
    profile = AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
        stable_lessons=tuple(linked),
    )
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(profile)
    return env, profile


def _manifest(lesson_fingerprint, **updates):
    manifest = {
        "schema_version": EXPERIMENT_VERSION,
        "target_agent_id": AGENT,
        "lesson_id": LESSON,
        "treatment_scope": "single_agent",
        "question_hashes": [
            "1" * 64,
            "2" * 64,
            "3" * 64,
            "4" * 64,
        ],
        "control_configuration": {
            "base_configuration_fingerprint": "a" * 64,
            "injected_lesson_fingerprints": [],
            "injection_target_agent_id": "",
        },
        "treatment_configuration": {
            "base_configuration_fingerprint": "a" * 64,
            "injected_lesson_fingerprints": [lesson_fingerprint],
            "injection_target_agent_id": AGENT,
        },
        "execution_mode": "deterministic-mock",
        "provider_ids": ["mock-a", "mock-b"],
        "judge_configuration": {
            "judge_set_fingerprint": "b" * 64,
            "self_judging_allowed": False,
        },
        "random_seeds": [101, 102, 103, 104],
        "arm_orders": [
            ["control", "treatment"],
            ["treatment", "control"],
            ["control", "treatment"],
            ["treatment", "control"],
        ],
        "counterbalanced": True,
        "compute_budget": {
            "token_limit": 1000,
            "timeout_seconds": 30.0,
            "retry_limit": 0,
        },
        "producer_version": "test-producer-v1",
    }
    manifest.update(updates)
    return manifest


def _envelope(tmp_path, report=None, *, envelope_updates=None,
              manifest_updates=None):
    env = _env(tmp_path)
    lessons = load_memory_lessons(
        env["CED_MEMORY_LESSONS_PATH"], include_deprecated=True)
    lesson = next(item for item in lessons if item.lesson_id == LESSON)
    profile = IdentityRegistry(env["CED_IDENTITY_DIR"]).load_profile(AGENT)
    envelope_updates = dict(envelope_updates or {})
    lesson_fingerprint = envelope_updates.pop(
        "lesson_fingerprint", memory_lesson_fingerprint(lesson))
    manifest = _manifest(
        lesson_fingerprint,
        **dict(manifest_updates or {}),
    )
    envelope = {
        "schema_version": ATTESTATION_VERSION,
        "lesson_fingerprint": lesson_fingerprint,
        "target_identity_fingerprint": (
            governed_profile_fingerprint(profile) if profile is not None
            else "d" * 64
        ),
        "experiment_fingerprint": _digest(manifest),
        "experiment_manifest": manifest,
        "instrument_report": report or _report(),
    }
    envelope.update(envelope_updates)
    return envelope


def _write_envelope(tmp_path, report=None, *, envelope_updates=None,
                    manifest_updates=None):
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(_envelope(
        tmp_path,
        report,
        envelope_updates=envelope_updates,
        manifest_updates=manifest_updates,
    )), encoding="utf-8")
    return path


def _run(attest_script, tmp_path, *, action="link", report=None,
         verifier="Operator", envelope_updates=None, manifest_updates=None):
    env = _env(tmp_path)
    report_path = _write_envelope(
        tmp_path,
        report,
        envelope_updates=envelope_updates,
        manifest_updates=manifest_updates,
    )
    argv = [
        "prog", AGENT,
        "--report", str(report_path),
        "--action", action,
        "--verified-by", verifier,
    ]
    return attest_script.main(argv, env=env)


def test_helped_single_agent_report_builds_memory_link_evidence(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)

    assert _run(attest_script, tmp_path) == 0
    out = capsys.readouterr().out
    assert "action         : link_stable_lesson" in out
    assert "lesson bind" in out
    assert "identity bind" in out
    assert "experiment bind" in out
    assert "Nothing was linked or unlinked" in out

    records = RevisionEvidenceRegistry(tmp_path / "evidence").all_records(AGENT)
    assert len(records) == 1
    evidence = records[0]
    assert evidence.value == LESSON
    assert evidence.supports == ("memory:link_stable_lesson",)
    assert evidence.outcomes == ("confirmed",)
    assert evidence.verified_by == "Operator"
    assert "bindings-" in evidence.source


def test_unbound_or_generic_council_report_cannot_become_personal_memory(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)
    env = _env(tmp_path)
    path = tmp_path / "unbound.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")
    argv = ["prog", AGENT, "--report", str(path), "--action", "link",
            "--verified-by", "Operator"]
    assert attest_script.main(argv, env=env) == 1
    assert "attestation contains missing or unknown fields" in \
        capsys.readouterr().out

    report = _report(schema_version="lesson_ab_v2")
    assert _run(attest_script, tmp_path, report=report) == 1
    assert "only openclaw_agent_lesson_ab_v1" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_report_target_and_named_verifier_are_bound(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)

    assert _run(
        attest_script,
        tmp_path,
        report=_report(target_agent_id="agent_beta"),
    ) == 1
    assert "targets another agent" in capsys.readouterr().out

    assert _run(attest_script, tmp_path, verifier="Different Reviewer") == 1
    assert "must match the named verifier" in capsys.readouterr().out

    assert _run(attest_script, tmp_path, verifier=AGENT) == 1
    assert "never attest its own" in capsys.readouterr().out


def test_link_requires_existing_stable_or_verified_catalogue_lesson(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)
    lessons_path = tmp_path / "MEMORY_LESSONS.md"
    lessons_path.write_text(_lesson_markdown(status="tested"), encoding="utf-8")

    assert _run(attest_script, tmp_path) == 1
    assert "only stable or verified lessons may be linked" in \
        capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_missing_identity_profile_fails_before_registration(
        attest_script, tmp_path, capsys):
    _env(tmp_path)

    assert _run(attest_script, tmp_path) == 1
    assert "no governed identity profile exists" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_lesson_and_identity_fingerprints_must_match_current_state(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)

    assert _run(
        attest_script,
        tmp_path,
        envelope_updates={"lesson_fingerprint": "e" * 64},
    ) == 1
    assert "lesson_fingerprint does not match" in capsys.readouterr().out

    assert _run(
        attest_script,
        tmp_path,
        envelope_updates={"target_identity_fingerprint": "f" * 64},
    ) == 1
    assert "target_identity_fingerprint does not match" in \
        capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_same_lesson_id_with_changed_content_cannot_reuse_old_result(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)
    old_envelope = _envelope(tmp_path)
    (tmp_path / "MEMORY_LESSONS.md").write_text(
        _lesson_markdown(
            lesson_text="A materially changed rule under the same identifier."),
        encoding="utf-8",
    )
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(old_envelope), encoding="utf-8")
    argv = ["prog", AGENT, "--report", str(path), "--action", "link",
            "--verified-by", "Operator"]

    assert attest_script.main(argv, env=_env(tmp_path)) == 1
    assert "lesson_fingerprint does not match" in capsys.readouterr().out


def test_harmful_report_builds_dual_unlink_and_revert_evidence(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path, linked=(LESSON,))
    report = _report(
        reference="agent-ab/local-apprentice-001/lesson-0007/harmed-1",
        verdict="harmed",
        helped=False,
        mean_score_delta=-0.2,
        harm_rate=0.5,
        ratification_regressions=1,
    )

    assert _run(attest_script, tmp_path, action="unlink", report=report) == 0
    capsys.readouterr()
    evidence = RevisionEvidenceRegistry(
        tmp_path / "evidence").all_records(AGENT)[0]
    assert evidence.supports == (
        "memory:link_stable_lesson",
        "memory:unlink_stable_lesson",
    )
    assert evidence.outcomes == ("reverted",)


def test_unlink_requires_lesson_to_be_currently_linked(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)
    report = _report(
        reference="agent-ab/local-apprentice-001/lesson-0007/harmed-1",
        verdict="harmed",
        helped=False,
        mean_score_delta=-0.2,
        harm_rate=0.5,
        ratification_regressions=1,
    )

    assert _run(attest_script, tmp_path, action="unlink", report=report) == 1
    assert "is not currently linked" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_helped_report_cannot_attest_unlink_and_harmed_cannot_attest_link(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path, linked=(LESSON,))

    assert _run(attest_script, tmp_path, action="unlink") == 1
    assert "concrete harmed verdict" in capsys.readouterr().out

    harmed = _report(
        reference="agent-ab/local-apprentice-001/lesson-0007/harmed-1",
        verdict="harmed",
        helped=False,
        mean_score_delta=-0.2,
        harm_rate=0.5,
        ratification_regressions=1,
    )
    assert _run(attest_script, tmp_path, action="link", report=harmed) == 1
    assert "verdict='helped'" in capsys.readouterr().out


def test_exact_rerun_is_idempotent_and_changed_binding_conflicts(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)
    assert _run(attest_script, tmp_path) == 0
    capsys.readouterr()
    assert _run(attest_script, tmp_path) == 0
    capsys.readouterr()
    registry = RevisionEvidenceRegistry(tmp_path / "evidence")
    assert len(registry.all_records(AGENT)) == 1

    conflict = _report(mean_score_delta=0.5)
    assert _run(attest_script, tmp_path, report=conflict) == 1
    assert "conflicting content" in capsys.readouterr().out

    assert _run(
        attest_script,
        tmp_path,
        manifest_updates={"producer_version": "test-producer-v2"},
    ) == 1
    assert "conflicting content" in capsys.readouterr().out
    assert len(registry.all_records(AGENT)) == 1


def test_invalid_envelope_json_url_and_digest_fail_closed(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)
    env = _env(tmp_path)

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    argv = ["prog", AGENT, "--report", str(bad), "--action", "link",
            "--verified-by", "Operator"]
    assert attest_script.main(argv, env=env) == 1
    assert "invalid JSON" in capsys.readouterr().out

    bad.write_text("[]", encoding="utf-8")
    assert attest_script.main(argv, env=env) == 1
    assert "one JSON object" in capsys.readouterr().out

    argv[3] = "https://example.test/report.json"
    assert attest_script.main(argv, env=env) == 1
    assert "local file, not a URL" in capsys.readouterr().out

    assert _run(
        attest_script,
        tmp_path,
        envelope_updates={"experiment_fingerprint": "not-a-digest"},
    ) == 1
    assert "lowercase SHA-256" in capsys.readouterr().out


def test_secret_or_non_finite_values_are_refused(
        attest_script, tmp_path, capsys):
    _save_profile(tmp_path)

    secret = _report(source="api_key=abcdefgh12345678")
    assert _run(attest_script, tmp_path, report=secret) == 1
    assert "secret-shaped" in capsys.readouterr().out

    non_finite = _report(mean_score_delta=float("nan"))
    assert _run(attest_script, tmp_path, report=non_finite) == 1
    assert "must be finite" in capsys.readouterr().out

    assert _run(
        attest_script,
        tmp_path,
        manifest_updates={"producer_version": "api_key=abcdefgh12345678"},
    ) == 1
    assert "experiment_manifest.producer_version contains secret-shaped" in \
        capsys.readouterr().out
