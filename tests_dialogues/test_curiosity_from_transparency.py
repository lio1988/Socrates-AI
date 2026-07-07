"""
Phase 28 — transparency becomes curiosity (closing the observe→act loop).

The gap: Phases 26/27 made thin corroboration and shipped penalty flags VISIBLE
(audit), but the signals were themselves inert — nothing acted on them. Now the
OpenQuestionLedger harvests them into the system's own research agenda:
  - serious flags on shipped content  → "flagged_section" open question (pri 2)
  - thinly corroborated sections      → "thin_corroboration" question (pri 4)
One aggregated question per signal (informed, not spammed); deduped; runnable by
the autonomous inquiry cycle. Mechanical reads of CED's own audit. Offline.
"""

import asyncio

import pytest

from backend.dialogues.models import FinalResponse, SessionState
from backend.dialogues.living_system import (
    OpenQuestionLedger, _SOURCE_PRIORITY, run_inquiry_cycle,
)
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"


def _final(ratified=True, flags=None, reliability=None):
    au = {}
    if flags is not None:
        au["assembly_flags"] = flags
    if reliability is not None:
        au["assembly_reliability"] = reliability
    return FinalResponse(session_id="s", question=Q, ratified=ratified,
                         ratification_status="ratified" if ratified else "quorum_failed",
                         answer="a" if ratified else "", audit_summary=au)


def _state():
    return SessionState(session_id="s", question=Q)


# ── harvesting the transparency signals ───────────────────────────────────────

def test_serious_flags_become_an_open_question():
    ledger = OpenQuestionLedger()
    ledger.ingest_session(_state(), _final(flags={
        "serious_flag_count": 2, "clean": False,
        "flags_by_section": {"core_answer": {"unsupported_claim": 2}},
        "flagged_sections": ["core_answer"]}))
    qs = ledger.open_questions()
    assert len(qs) == 1 and qs[0].source == "flagged_section"
    assert "unsupported_claim×2" in qs[0].question
    assert "core_answer" in qs[0].question


def test_thin_sections_become_an_open_question():
    ledger = OpenQuestionLedger()
    ledger.ingest_session(_state(), _final(reliability={
        "thinly_corroborated_sections": 2, "thin_sections": ["nuance", "blind_spots"],
        "well_corroborated": False}))
    qs = ledger.open_questions()
    assert len(qs) == 1 and qs[0].source == "thin_corroboration"
    assert "nuance" in qs[0].question and "more reviewers" in qs[0].question


def test_clean_and_well_corroborated_add_nothing():
    ledger = OpenQuestionLedger()
    ledger.ingest_session(_state(), _final(
        flags={"serious_flag_count": 0, "clean": True, "flags_by_section": {},
               "flagged_sections": []},
        reliability={"thinly_corroborated_sections": 0, "thin_sections": [],
                     "well_corroborated": True}))
    assert ledger.open_questions() == []


def test_stylistic_only_flags_add_nothing():
    # serious_flag_count already excludes stylistic flags (Phase 27) — a session
    # flagged only for style must not enter the research agenda
    ledger = OpenQuestionLedger()
    ledger.ingest_session(_state(), _final(flags={
        "serious_flag_count": 0, "clean": True,
        "flags_by_section": {"nuance": {"vague": 3}}, "flagged_sections": ["nuance"]}))
    assert ledger.open_questions() == []


def test_unratified_sessions_do_not_harvest_transparency():
    # quorum failure already records the loudest question; flags/thin from a
    # failed session never shipped, so they add nothing extra
    ledger = OpenQuestionLedger()
    ledger.ingest_session(_state(), _final(ratified=False, flags={
        "serious_flag_count": 5, "clean": False,
        "flags_by_section": {"core_answer": {"logical_gap": 5}},
        "flagged_sections": ["core_answer"]}))
    assert [q.source for q in ledger.open_questions()] == ["quorum_failure"]


# ── priority + dedupe + the loop actually closes ─────────────────────────────

def test_priorities_are_ordered_and_complete():
    assert (_SOURCE_PRIORITY["quorum_failure"] < _SOURCE_PRIORITY["uncertainty"]
            < _SOURCE_PRIORITY["flagged_section"] < _SOURCE_PRIORITY["blind_spot"]
            < _SOURCE_PRIORITY["thin_corroboration"] < _SOURCE_PRIORITY["caveat"])


def test_real_session_feeds_agenda_with_correct_order_and_dedupe():
    ledger = OpenQuestionLedger()
    ced, _ = build_council(env={}, council_size=2, open_questions=ledger)
    asyncio.run(ced.run_registry_session(Q, session_id="s1"))
    sources = {q.source for q in ledger.open_questions()}
    # 2-seat mock: every section is single-scored → thin; mock raises
    # missed_uncertainty flags → flagged_section
    assert "thin_corroboration" in sources and "flagged_section" in sources
    agenda = ledger.propose_inquiries(6)
    prios = [_SOURCE_PRIORITY[a["source"]] for a in agenda]
    assert prios == sorted(prios)                       # priority-ordered
    n = len(ledger.open_questions())
    asyncio.run(ced.run_registry_session(Q, session_id="s2"))   # identical question
    assert len(ledger.open_questions()) == n            # deduped, no spam


def test_flagged_question_is_runnable_by_the_inquiry_cycle():
    ledger = OpenQuestionLedger()
    ced, _ = build_council(env={}, council_size=2, open_questions=ledger)
    asyncio.run(ced.run_registry_session(Q, session_id="s1"))
    rep = asyncio.run(run_inquiry_cycle(ced, max_inquiries=1))
    assert rep["inquiries_run"] == 1
    assert rep["results"][0]["ratified"] is True        # observe → act, closed loop
