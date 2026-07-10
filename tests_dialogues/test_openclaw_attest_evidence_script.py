"""Tests for the evidence attestation bridge (instruments -> trusted registry).

The gap this closes, proven live before the fix: a shadow apprentice with
real marker-verified comparisons still showed `evidence: 0` in self-review,
because nothing fed the immutable RevisionEvidenceRegistry.

All offline: mock shadow records on disk, no providers, no network, no keys.
"""

import importlib.util
import json
import pathlib

import pytest

from backend.dialogues.openclaw_identity import RevisionEvidenceRegistry

_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"


def _script(name):
    spec = importlib.util.spec_from_file_location(
        f"{name}_script", _ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def attest_script():
    return _script("openclaw_attest_evidence")


@pytest.fixture(scope="module")
def self_review_script():
    return _script("openclaw_self_review")


def _shadow_record(session_id, *, wins=(), losses=("blind_spots",)):
    comparison = (
        [{"section_name": section, "apprentice_score": 8.0,
          "council_score": 6.0, "shadow_win": True} for section in wins]
        + [{"section_name": section, "apprentice_score": 5.0,
            "council_score": 7.0, "shadow_win": False} for section in losses]
    )
    return {"trace_version": "openclaw_shadow_trace_v0", "shadow_run": True,
            "ok": True, "session_id": session_id, "apprentice_id": AGENT,
            "shadow_comparison": comparison, "shadow_wins": len(wins)}


def _write_records(tmp_path, records):
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    path = shadow_dir / "shadow_records.jsonl"
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")
    return path


def _env(tmp_path):
    return {"CED_SHADOW_DIR": str(tmp_path / "shadow"),
            "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
            "CED_IDENTITY_DIR": str(tmp_path / "identity"),
            "CED_SELF_REVISION_DIR": str(tmp_path / "revisions"),
            "CED_SELF_REVIEW_DIR": str(tmp_path / "review"),
            "CED_ATTEST_DATE": "2026-07-10"}


def _run(attest_script, tmp_path, argv=None, capsys=None):
    argv = argv or ["prog", AGENT, "--verified-by", "Operator"]
    return attest_script.main(argv, env=_env(tmp_path))


# --------------------------------------------------------------------------- #
# The named-human constitution
# --------------------------------------------------------------------------- #

def test_refuses_unnamed_attestation(attest_script, tmp_path, capsys):
    _write_records(tmp_path, [_shadow_record("s1"), _shadow_record("s2")])
    assert attest_script.main(["prog", AGENT], env=_env(tmp_path)) == 1
    assert "requires a named attester" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_refuses_self_attestation(attest_script, tmp_path, capsys):
    _write_records(tmp_path, [_shadow_record("s1"), _shadow_record("s2")])
    rc = attest_script.main(["prog", AGENT, "--verified-by", AGENT],
                            env=_env(tmp_path))
    assert rc == 1
    assert "never attest its own" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Repeated-only, replay-proof, append-only
# --------------------------------------------------------------------------- #

def test_repeated_losses_become_verified_evidence(attest_script, tmp_path,
                                                  capsys):
    _write_records(tmp_path, [_shadow_record("s1"), _shadow_record("s2")])
    assert _run(attest_script, tmp_path) == 0
    out = capsys.readouterr().out
    assert "evidence written (1)" in out
    registry = RevisionEvidenceRegistry(tmp_path / "evidence")
    records = registry.all_records()
    assert len(records) == 1
    evidence = records[0]
    assert evidence.agent_id == AGENT
    assert evidence.supports == ("identity:add_known_failure",)
    assert "blind_spots" in evidence.value
    assert evidence.verified_by == "Operator"


def test_single_loss_is_not_evidence(attest_script, tmp_path, capsys):
    _write_records(tmp_path, [_shadow_record("s1"),
                              _shadow_record("s2", wins=("blind_spots",),
                                             losses=("nuance",))])
    assert _run(attest_script, tmp_path) == 0
    out = capsys.readouterr().out
    assert "evidence written: none" in out
    assert "needs 2 distinct sessions" in out


def test_replayed_session_never_double_counts(attest_script, tmp_path, capsys):
    record = _shadow_record("s1")
    _write_records(tmp_path, [record, dict(record), _shadow_record("s2",
                                                                   losses=())])
    assert _run(attest_script, tmp_path) == 0
    assert "evidence written: none" in capsys.readouterr().out


def test_exact_rerun_is_idempotent_and_new_window_appends(attest_script,
                                                          tmp_path, capsys):
    path = _write_records(tmp_path,
                          [_shadow_record("s1"), _shadow_record("s2")])
    assert _run(attest_script, tmp_path) == 0
    assert _run(attest_script, tmp_path) == 0      # exact rerun: no error
    registry = RevisionEvidenceRegistry(tmp_path / "evidence")
    assert len(registry.all_records()) == 1
    with path.open("a", encoding="utf-8") as file:  # window grows
        file.write(json.dumps(_shadow_record("s3")) + "\n")
    assert _run(attest_script, tmp_path) == 0
    assert len(registry.all_records()) == 2         # append-only history


# --------------------------------------------------------------------------- #
# End-to-end: the self-review chain finally has raw material
# --------------------------------------------------------------------------- #

def test_self_review_sees_attested_evidence(attest_script, self_review_script,
                                            tmp_path, capsys):
    from backend.dialogues.openclaw_identity import (
        AgentIdentityProfile, IdentityRegistry)
    IdentityRegistry(_env(tmp_path)["CED_IDENTITY_DIR"]).save_profile(
        AgentIdentityProfile(agent_id=AGENT, identity_version="v0.3",
                             promotion_status="shadow_apprentice"))
    _write_records(tmp_path, [_shadow_record("s1"), _shadow_record("s2")])
    assert _run(attest_script, tmp_path) == 0
    capsys.readouterr()
    assert self_review_script.main(["prog", AGENT], env=_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "evidence     : 1 verified record(s)" in out
    snapshot = json.loads(
        (tmp_path / "review" / f"{AGENT}.snapshot.json").read_text("utf-8"))
    blob = json.dumps(snapshot)
    assert "blind_spots" in blob                    # the weakness is visible
    assert "add_known_failure" in blob              # as proposable material
