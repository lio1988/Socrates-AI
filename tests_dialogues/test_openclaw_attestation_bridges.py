"""Tests for resolution and Soul attestation bridges.

All tests are offline and write only to temporary registries. The bridges never
propose, approve, apply, promote, call providers, or read credentials.
"""

import importlib.util
import json
import pathlib

import pytest

from backend.dialogues.openclaw_identity import (
    RevisionEvidenceRecord,
    RevisionEvidenceRegistry,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"
SECTION = "blind_spots"
PRINCIPLE = "State uncertainty before asserting a final verdict."


def _load_script():
    path = _ROOT / "scripts" / "openclaw_attest_evidence.py"
    spec = importlib.util.spec_from_file_location("openclaw_attest_bridge", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def attest_script():
    return _load_script()


def _record(session_id, won, *, agent_id=AGENT, section=SECTION):
    return {
        "trace_version": "openclaw_shadow_trace_v0",
        "shadow_run": True,
        "ok": True,
        "session_id": session_id,
        "apprentice_id": agent_id,
        "shadow_comparison": [{
            "section_name": section,
            "apprentice_score": 8.0 if won else 5.0,
            "council_score": 6.0 if won else 7.0,
            "shadow_win": won,
        }],
        "shadow_wins": 1 if won else 0,
    }


def _write_records(tmp_path, records):
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    path = shadow_dir / "shadow_records.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path


def _env(tmp_path):
    return {
        "CED_SHADOW_DIR": str(tmp_path / "shadow"),
        "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
        "CED_ATTEST_DATE": "2026-07-10",
    }


def _failure_args(agent_id=AGENT):
    return ["prog", agent_id, "--verified-by", "Operator"]


def _resolution_args(agent_id=AGENT, *, section=SECTION, window=2):
    return [
        "prog", agent_id,
        "--mode", "resolution",
        "--section", section,
        "--window", str(window),
        "--verified-by", "Operator",
    ]


def _soul_args(reference, *, agent_id=AGENT, action="add_principle",
               principle=PRINCIPLE, include_constitution=True,
               include_risk=True):
    args = [
        "prog", agent_id,
        "--mode", "soul",
        "--action", action,
        "--principle", principle,
        "--evidence-ref", reference,
        "--rationale", "Repeated verified evidence warrants this principle.",
        "--review-reference", "review/soul-001",
        "--verified-by", "Operator",
    ]
    if include_constitution:
        args.append("--constitutional-review")
    if include_risk:
        args.append("--risk-reviewed")
    return args


def _prepare_failure(attest_script, tmp_path, capsys):
    _write_records(tmp_path, [
        _record("s1", False),
        _record("s2", False),
        _record("s3", True),
        _record("s4", True),
    ])
    assert attest_script.main(_failure_args(), env=_env(tmp_path)) == 0
    capsys.readouterr()
    registry = RevisionEvidenceRegistry(tmp_path / "evidence")
    failures = [
        record for record in registry.all_records(AGENT)
        if record.supports == ("identity:add_known_failure",)
    ]
    assert len(failures) == 1
    return registry, failures[0]


# --------------------------------------------------------------------------- #
# Resolution bridge: existing weakness + matched adjacent failure/win windows
# --------------------------------------------------------------------------- #


def test_resolution_requires_existing_attested_failure(
        attest_script, tmp_path, capsys):
    _write_records(tmp_path, [
        _record("s1", False), _record("s2", False),
        _record("s3", True), _record("s4", True),
    ])

    assert attest_script.main(
        _resolution_args(), env=_env(tmp_path)) == 1
    out = capsys.readouterr().out
    assert "existing attested failure" in out
    assert RevisionEvidenceRegistry(tmp_path / "evidence").all_records() == []


def test_matched_resolution_window_becomes_inverse_evidence(
        attest_script, tmp_path, capsys):
    registry, failure = _prepare_failure(attest_script, tmp_path, capsys)

    assert attest_script.main(
        _resolution_args(), env=_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "mode           : resolution" in out
    assert "evidence written (1)" in out

    records = registry.all_records(AGENT)
    assert len(records) == 2
    resolution = next(record for record in records
                      if "identity:resolve_known_failure" in record.supports)
    assert resolution.value == failure.value
    assert resolution.supports == (
        "identity:add_known_failure",
        "identity:resolve_known_failure",
    )
    assert resolution.outcomes == ("reverted",)
    assert "matched-" in resolution.source


def test_resolution_refuses_non_clean_after_window(
        attest_script, tmp_path, capsys):
    _write_records(tmp_path, [
        _record("s1", False), _record("s2", False),
        _record("s3", True), _record("s4", False),
    ])
    assert attest_script.main(_failure_args(), env=_env(tmp_path)) == 0
    capsys.readouterr()

    assert attest_script.main(
        _resolution_args(), env=_env(tmp_path)) == 1
    assert "after-window must contain only verified wins" in \
        capsys.readouterr().out
    records = RevisionEvidenceRegistry(tmp_path / "evidence").all_records()
    assert not any("identity:resolve_known_failure" in row.supports
                   for row in records)


def test_resolution_replay_does_not_create_a_second_record(
        attest_script, tmp_path, capsys):
    registry, _ = _prepare_failure(attest_script, tmp_path, capsys)
    args = _resolution_args()
    assert attest_script.main(args, env=_env(tmp_path)) == 0
    capsys.readouterr()
    assert attest_script.main(args, env=_env(tmp_path)) == 0
    capsys.readouterr()
    assert len(registry.all_records(AGENT)) == 2


# --------------------------------------------------------------------------- #
# Soul bridge: explicit constitutional+risk review over existing agent evidence
# --------------------------------------------------------------------------- #


def test_soul_requires_both_explicit_reviews(attest_script, tmp_path, capsys):
    _, failure = _prepare_failure(attest_script, tmp_path, capsys)

    assert attest_script.main(
        _soul_args(failure.reference, include_risk=False),
        env=_env(tmp_path),
    ) == 1
    assert "requires --risk-reviewed" in capsys.readouterr().out

    assert attest_script.main(
        _soul_args(failure.reference, include_constitution=False),
        env=_env(tmp_path),
    ) == 1
    assert "requires --constitutional-review" in capsys.readouterr().out


def test_soul_add_principle_is_named_non_self_evidence(
        attest_script, tmp_path, capsys):
    registry, failure = _prepare_failure(attest_script, tmp_path, capsys)

    args = _soul_args(failure.reference)
    assert attest_script.main(args, env=_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "mode           : soul" in out
    assert "evidence written (1)" in out

    soul = next(record for record in registry.all_records(AGENT)
                if "soul:add_principle" in record.supports)
    assert soul.value == PRINCIPLE
    assert soul.supports == ("soul:add_principle",)
    assert soul.verified_by == "Operator"
    assert soul.source.startswith("SoulConstitutionalReview/")

    assert attest_script.main(args, env=_env(tmp_path)) == 0
    capsys.readouterr()
    assert len([row for row in registry.all_records(AGENT)
                if "soul:add_principle" in row.supports]) == 1


def test_soul_refuses_cross_agent_evidence(attest_script, tmp_path, capsys):
    registry = RevisionEvidenceRegistry(tmp_path / "evidence")
    foreign = RevisionEvidenceRecord(
        reference="trace/foreign",
        agent_id="other_agent",
        source="trace-harness",
        supports=("identity:add_known_failure",),
        value="foreign weakness",
        verified_by="Operator",
        verification_reference="review/foreign",
    )
    registry.register(foreign)

    assert attest_script.main(
        _soul_args(foreign.reference), env=_env(tmp_path)) == 1
    assert "belongs to another agent" in capsys.readouterr().out


def test_soul_retirement_and_secret_principles_are_strict(
        attest_script, tmp_path, capsys):
    registry, failure = _prepare_failure(attest_script, tmp_path, capsys)

    assert attest_script.main(
        _soul_args(failure.reference, action="retire_principle"),
        env=_env(tmp_path),
    ) == 0
    capsys.readouterr()
    retirement = next(
        record for record in registry.all_records(AGENT)
        if "soul:retire_principle" in record.supports
    )
    assert retirement.supports == (
        "soul:add_principle", "soul:retire_principle")
    assert retirement.outcomes == ("reverted",)

    assert attest_script.main(
        _soul_args(
            failure.reference,
            principle="api_key=abcdefgh12345678",
        ),
        env=_env(tmp_path),
    ) == 1
    assert "secret-shaped" in capsys.readouterr().out
