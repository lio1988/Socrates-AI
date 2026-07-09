"""
OpenClaw lesson proposer tests (Goal 6).

Verifies the failure->proposal flow and its safety properties:
  - mechanical detection of protocol failures from session traces
  - "repeated" gating (min_occurrences): one-off noise never becomes a proposal
  - every proposal is status="proposed" with source/problem/lesson/risk filled
  - proposals round-trip through the loader's parser
  - proposals can NEVER enter the stable pool (load_stable_lessons excludes)
  - the curated MEMORY_LESSONS.md is never written automatically (guard)
  - lesson types stay inside the retriever's taxonomy (retrievable on promote)

No provider calls, no network, no keys.
"""

import pytest

from backend.dialogues.openclaw_memory import (
    DEFAULT_MIN_OCCURRENCES,
    PROPOSAL_ID_START,
    default_lessons_path,
    detect_trace_failures,
    load_memory_lessons,
    load_stable_lessons,
    parse_memory_lessons,
    propose_from_capturer,
    propose_lessons,
    render_proposed_lessons,
    write_proposed_lessons,
    TraceCapturer,
)
from backend.dialogues.openclaw_memory.lesson_retriever import LESSON_TYPE_TRIGGERS


# --------------------------------------------------------------------------- #
# Trace builders (shape matches trace_capture.build_session_trace)
# --------------------------------------------------------------------------- #

def _ok_trace(sid="s_ok"):
    return {
        "session_id": sid,
        "question": "q",
        "moves": [{"phase": p, "role": "r", "confidence": 0.7}
                  for p in ("opening", "initial_response", "elenchus",
                            "reflection", "reconstruction", "synthesis")],
        "assembly": {"sections": [
            {"section_name": "core_answer", "source_draft_id": "draft_1"},
            {"section_name": "final_verdict", "source_draft_id": "draft_2"},
        ]},
        "ratification": {"ratified": True, "ratification_status": "ratified"},
    }


def _failed_ratification_trace(sid):
    t = _ok_trace(sid)
    t["ratification"] = {"ratified": False,
                         "ratification_status": "repair_required"}
    return t


def _unresolved_section_trace(sid, section="blind_spots"):
    t = _ok_trace(sid)
    t["assembly"]["sections"].append(
        {"section_name": section, "source_draft_id": ""})
    return t


def _blocked_trace(sid):
    return {
        "session_id": sid,
        "question": "q",
        "moves": [{"phase": "opening", "role": "r", "confidence": 0.5}],
        "assembly": None,
        "ratification": {"ratified": False,
                         "ratification_status": "not_ratified"},
    }


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

def test_clean_session_yields_no_observations():
    assert detect_trace_failures(_ok_trace()) == []


def test_detects_ratification_failure():
    obs = detect_trace_failures(_failed_ratification_trace("s1"))
    keys = {o["pattern_key"] for o in obs}
    assert "ratification_failed" in keys
    rat = next(o for o in obs if o["pattern_key"] == "ratification_failed")
    assert rat["lesson_type"] == "ratification_quality"
    assert rat["session_id"] == "s1"


def test_detects_unresolved_section():
    obs = detect_trace_failures(_unresolved_section_trace("s2"))
    keys = {o["pattern_key"] for o in obs}
    assert "unresolved_section:blind_spots" in keys


def test_detects_missing_assembly_and_phases():
    obs = detect_trace_failures(_blocked_trace("s3"))
    keys = {o["pattern_key"] for o in obs}
    assert "assembly_missing" in keys
    assert "phase_missing:synthesis" in keys
    assert "phase_missing:elenchus" in keys
    assert "phase_missing:opening" not in keys   # opening DID run


# --------------------------------------------------------------------------- #
# Repeated gating + proposal construction
# --------------------------------------------------------------------------- #

def test_single_occurrence_is_not_a_proposal():
    traces = [_failed_ratification_trace("s1"), _ok_trace("s2")]
    assert propose_lessons(traces) == []


def test_repeated_failure_becomes_proposal():
    traces = [_failed_ratification_trace("s1"),
              _failed_ratification_trace("s2"),
              _ok_trace("s3")]
    proposals = propose_lessons(traces)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.status == "proposed"
    assert p.lesson_type == "ratification_quality"
    assert p.lesson_id == f"LESSON-{PROPOSAL_ID_START}"
    # Spec: every proposal includes source, problem pattern, lesson, risk.
    assert "s1" in p.source and "s2" in p.source
    assert "2 of 3" in p.problem_pattern
    assert p.lesson.strip() and p.risk.strip()


def test_min_occurrences_override():
    traces = [_failed_ratification_trace("s1")]
    assert propose_lessons(traces, min_occurrences=1)[0].status == "proposed"
    with pytest.raises(ValueError):
        propose_lessons(traces, min_occurrences=0)


def test_proposals_deterministic_ids_sorted_by_pattern():
    traces = [
        _failed_ratification_trace("s1"),
        _failed_ratification_trace("s2"),
        _unresolved_section_trace("s3"),
        _unresolved_section_trace("s4"),
    ]
    a = propose_lessons(traces)
    b = propose_lessons(traces)
    assert [p.lesson_id for p in a] == [p.lesson_id for p in b]
    keys = [p.name for p in a]
    assert keys == sorted(keys, key=lambda n: [p.name for p in a].index(n))
    assert a[0].lesson_id == f"LESSON-{PROPOSAL_ID_START}"
    assert a[1].lesson_id == f"LESSON-{PROPOSAL_ID_START + 1}"


def test_lesson_types_stay_in_retriever_taxonomy():
    traces = [
        _failed_ratification_trace("s1"), _failed_ratification_trace("s2"),
        _unresolved_section_trace("s3"), _unresolved_section_trace("s4"),
        _blocked_trace("s5"), _blocked_trace("s6"),
    ]
    for p in propose_lessons(traces):
        assert p.lesson_type in LESSON_TYPE_TRIGGERS, (
            f"{p.lesson_id} has unretrievable type {p.lesson_type!r}")


# --------------------------------------------------------------------------- #
# Round-trip + never-auto-promote (the two mechanical safety proofs)
# --------------------------------------------------------------------------- #

def _sample_proposals():
    return propose_lessons([
        _failed_ratification_trace("s1"), _failed_ratification_trace("s2"),
        _unresolved_section_trace("s3"), _unresolved_section_trace("s4"),
    ])


def test_render_round_trips_through_loader_parser():
    proposals = _sample_proposals()
    parsed = parse_memory_lessons(render_proposed_lessons(proposals))
    assert parsed == proposals


def test_proposals_never_enter_stable_pool(tmp_path):
    path = tmp_path / "PROPOSED_LESSONS.md"
    write_proposed_lessons(_sample_proposals(), path)
    # The core Goal 6 guarantee, mechanically: the stable loader returns NOTHING
    # from a proposals file — promotion requires a human edit.
    assert load_stable_lessons(path) == []
    # But the default loader (curator view) sees them as proposed.
    seen = load_memory_lessons(path)
    assert seen and all(lesson.status == "proposed" for lesson in seen)


def test_write_refuses_curated_lessons_file():
    with pytest.raises(ValueError):
        write_proposed_lessons(_sample_proposals(), default_lessons_path())


def test_written_file_parses(tmp_path):
    path = write_proposed_lessons(_sample_proposals(), tmp_path / "p.md")
    text = path.read_text(encoding="utf-8")
    assert "pending human review" in text
    assert parse_memory_lessons(text) == _sample_proposals()


# --------------------------------------------------------------------------- #
# Capturer convenience (composes with Goal 5)
# --------------------------------------------------------------------------- #

def test_propose_from_capturer():
    capturer = TraceCapturer()
    capturer.traces.extend([
        _failed_ratification_trace("s1"),
        _failed_ratification_trace("s2"),
    ])
    proposals = propose_from_capturer(capturer)
    assert len(proposals) == 1
    assert proposals[0].status == "proposed"


def test_empty_traces_no_proposals():
    assert propose_lessons([]) == []
    assert propose_from_capturer(TraceCapturer()) == []
