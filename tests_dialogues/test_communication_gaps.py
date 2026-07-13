"""
Binding/communication gap tests — the disk is the message bus.

Three gaps closed and locked:
  1. traces written by TraceCapturer can be READ BACK (load_traces /
     load_jsonl) — cross-session learning is possible
  2. shadow_dialogue accumulates evidence ACROSS runs and persists identity
     to the registry (earned fields survive rebuilds)
  3. openclaw_review reads the accumulated history and writes the curator's
     proposal files — the system reports, the human decides

All offline, deterministic, no network, no keys.
"""

import asyncio
import importlib.util
import json
import pathlib

import pytest

from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode
from backend.dialogues.openclaw_memory import (
    TraceCapturer,
    load_jsonl,
    load_traces,
    parse_memory_lessons,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(
        f"{name}_script", _ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def shadow_script():
    return _script("shadow_dialogue")


@pytest.fixture(scope="module")
def review_script():
    return _script("openclaw_review")


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    monkeypatch.delenv("CED_ENABLE_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("CED_ENABLE_LOCAL_APPRENTICE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _blocked_trace(sid):
    return {"session_id": sid, "question": "q",
            "moves": [{"move_id": f"m_{sid}", "phase": "opening", "role": "r",
                       "confidence": 0.5, "provider_id": "seat_a"}],
            "assembly": None,
            "ratification": {"ratified": False,
                             "ratification_status": "not_ratified"}}


# --------------------------------------------------------------------------- #
# Gap 1: traces round-trip through disk
# --------------------------------------------------------------------------- #

def test_captured_traces_can_be_loaded_back(tmp_path):
    capturer = TraceCapturer(output_dir=tmp_path / "traces")
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           trace_capturer=capturer)
    asyncio.run(ced.run_registry_session("q1", session_id="rt_1"))
    asyncio.run(ced.run_registry_session("q2", session_id="rt_2"))
    loaded = load_traces(tmp_path / "traces")
    assert len(loaded) == 2
    assert {t["session_id"] for t in loaded} == {"rt_1", "rt_2"}
    assert all(t["trace_version"] == "openclaw_trace_v0" for t in loaded)


def test_load_jsonl_skips_corrupt_lines_honestly(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text('{"a": 1}\nNOT JSON\n\n{"b": 2}\n["not a dict"]\n',
                    encoding="utf-8")
    assert load_jsonl(path) == [{"a": 1}, {"b": 2}]


def test_missing_paths_are_empty_history_not_errors(tmp_path):
    assert load_jsonl(tmp_path / "nope.jsonl") == []
    assert load_traces(tmp_path / "nowhere") == []


# --------------------------------------------------------------------------- #
# Gap 2: shadow evidence accumulates across runs; identity persists
# --------------------------------------------------------------------------- #

def test_shadow_runs_accumulate_across_invocations(shadow_script, tmp_path,
                                                   capsys):
    env = {"CED_SHADOW_SESSIONS": "2",
           "CED_SHADOW_DIR": str(tmp_path / "shadow"),
           "CED_IDENTITY_DIR": str(tmp_path / "identity")}
    assert shadow_script.main(["prog"], env=env) == 0
    first = capsys.readouterr().out
    assert "2 shadow record(s) across all runs" in first
    assert shadow_script.main(["prog"], env=env) == 0
    second = capsys.readouterr().out
    # The second run's evidence covers BOTH runs (4 records, 4 sessions).
    assert "4 shadow record(s) across all runs" in second
    assert "Sessions analyzed: 4" in second
    # And the identity registry file exists and matches the accumulation.
    record = json.loads((tmp_path / "identity" /
                         "local_apprentice_001.json").read_text("utf-8"))
    assert record["sessions_analyzed"] == 4


def test_earned_identity_survives_rebuild(shadow_script, tmp_path, capsys):
    from backend.dialogues.openclaw_identity import (
        AgentIdentityProfile, IdentityRegistry, evaluate_gate, next_gate_for,
        record_promotion)
    registry = IdentityRegistry(tmp_path / "identity")
    # Governed seeding: bootstrap first (curated fields, no history), then a
    # REAL evidence-backed promotion — a profile born already promoted is a
    # forgery vector the registry rightly refuses.
    base = AgentIdentityProfile(
        agent_id="local_apprentice_001",
        identity_version="v0.3",
        promotion_status="self_learning",
        known_failures=("over-explains exact-output tasks",))
    registry.save_profile(base)
    gate = next_gate_for("v0.3")
    result = evaluate_gate(gate, {"shadow_blind_spots_wins": 3})
    registry.save_profile(record_promotion(
        base, result, approved_by="operator", approved_on="2026-07-10"))
    env = {"CED_SHADOW_SESSIONS": "1",
           "CED_SHADOW_DIR": str(tmp_path / "shadow"),
           "CED_IDENTITY_DIR": str(tmp_path / "identity")}
    assert shadow_script.main(["prog"], env=env) == 0
    out = capsys.readouterr().out
    # Earned fields preserved; evidence recomputed from actual records.
    assert "Identity version: v0.4" in out
    assert "self_learning" in out
    assert "over-explains exact-output tasks" in out
    assert "Promotions recorded: 1" in out
    assert "gate gate_v0_4_to_v0_5" in out          # next gate follows v0.4


# --------------------------------------------------------------------------- #
# Gap 3: the curator review loop
# --------------------------------------------------------------------------- #

def _review_env(tmp_path):
    # Full isolation: every directory the review reads must point at tmp,
    # including the governed self-revision surfaces - otherwise the test
    # silently reads the repo's real runs/ artifacts.
    return {"CED_TRACE_DIR": str(tmp_path / "traces"),
            "CED_SHADOW_DIR": str(tmp_path / "shadow"),
            "CED_PROPOSALS_DIR": str(tmp_path / "proposals"),
            "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
            "CED_SELF_REVISION_DIR": str(tmp_path / "revisions")}


def test_review_with_empty_history_is_a_clean_message(review_script, tmp_path,
                                                      capsys):
    assert review_script.main(env=_review_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "Nothing to review yet" in out


def test_review_proposes_from_accumulated_failures(review_script, tmp_path,
                                                   capsys):
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir(parents=True)
    with (traces_dir / "failing.jsonl").open("w", encoding="utf-8") as f:
        for sid in ("f1", "f2"):
            f.write(json.dumps(_blocked_trace(sid)) + "\n")
    assert review_script.main(env=_review_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "FAILURE PATTERNS" in out
    assert "human decides" in out
    # Lesson proposals: loader-parseable, all proposed.
    lessons_path = tmp_path / "proposals" / "PROPOSED_LESSONS.md"
    lessons = parse_memory_lessons(lessons_path.read_text("utf-8"))
    assert lessons and all(l.status == "proposed" for l in lessons)
    # Patch proposals: policy audit fields present in the report.
    patches_text = (tmp_path / "proposals" /
                    "PROPOSED_PROMPT_PATCHES.md").read_text("utf-8")
    assert "PATCH-9001" in patches_text
    assert "**Risk:**" in patches_text
    assert "pending human review" in patches_text


def test_review_reports_shadow_evidence(review_script, shadow_script,
                                        tmp_path, capsys):
    env = {"CED_SHADOW_SESSIONS": "2",
           "CED_SHADOW_DIR": str(tmp_path / "shadow"),
           "CED_IDENTITY_DIR": str(tmp_path / "identity")}
    shadow_script.main(["prog"], env=env)
    capsys.readouterr()
    assert review_script.main(env=_review_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "SHADOW APPRENTICE EVIDENCE" in out
    assert "local_apprentice_001" in out
