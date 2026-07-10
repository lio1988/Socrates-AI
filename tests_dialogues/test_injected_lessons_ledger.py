"""
Injected-context ledger tests — the audit reports REALITY, not a re-run.

The gap this closes: runtime lesson retrieval is PHASE-AWARE, but the old
audit re-ran retrieval with the question only — so "what we think entered
the context" could disagree with "what actually entered the context". The
ledger records every injection at injection time; the audit (and therefore
every trace) reads the ledger.

No provider calls, no network, no keys.
"""

import asyncio

import pytest

from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode
from backend.dialogues.openclaw_memory import (
    TraceCapturer,
    load_stable_lessons,
    retrieve_lessons,
)


@pytest.fixture(scope="module")
def stable_pool():
    return load_stable_lessons()


def _run(question, sid, pool, capturer=None):
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           openclaw_lessons=pool,
                           trace_capturer=capturer)
    final = asyncio.run(ced.run_registry_session(question, session_id=sid))
    return ced, final


def test_audit_selected_equals_union_of_actual_injections(stable_pool):
    _, final = _run("deliberation scoring assembly", "ledger_1", stable_pool)
    audit = final.audit_summary["openclaw_lessons"]
    assert audit["injections"], "phase contexts should have received lessons"
    union = sorted({lid for inj in audit["injections"]
                    for lid in inj["lesson_ids"]})
    assert audit["selected"] == union
    assert audit["selected_count"] == len(union)
    for inj in audit["injections"]:
        assert set(inj) == {"phase", "agent_id", "lesson_ids"}
        assert inj["lesson_ids"]


def test_audit_now_sees_phase_matched_lessons(stable_pool):
    # A question with NO keyword matches: question-only retrieval selects
    # nothing (the OLD audit would report selected=[]) — but runtime phase
    # contexts DO inject phase-matched lessons, and the ledger proves it.
    question = "xyzzy plugh qwortle"
    assert retrieve_lessons(stable_pool, task_text=question) == []
    _, final = _run(question, "ledger_2", stable_pool)
    audit = final.audit_summary["openclaw_lessons"]
    assert audit["selected_count"] > 0, (
        "phase-aware injections happened; the audit must not hide them")
    phases = {inj["phase"] for inj in audit["injections"]}
    assert phases                        # real per-phase attribution


def test_traces_carry_the_real_injected_ids(stable_pool):
    capturer = TraceCapturer()
    _run("xyzzy plugh qwortle", "ledger_3", stable_pool, capturer=capturer)
    trace = capturer.latest_trace()
    audit_selected = trace["selected_openclaw_lessons"]
    assert audit_selected                # reality reaches the trace too


def test_no_pool_means_no_audit_block():
    _, final = _run("deliberation scoring assembly", "ledger_4", None)
    assert final.audit_summary["openclaw_lessons"] is None


def test_sessions_do_not_leak_into_each_other(stable_pool):
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           openclaw_lessons=stable_pool)
    f1 = asyncio.run(ced.run_registry_session("deliberation scoring assembly",
                                              session_id="ledger_a"))
    f2 = asyncio.run(ced.run_registry_session("xyzzy plugh qwortle",
                                              session_id="ledger_b"))
    a = f1.audit_summary["openclaw_lessons"]
    b = f2.audit_summary["openclaw_lessons"]
    assert {i["phase"] for i in a["injections"]} \
        and {i["phase"] for i in b["injections"]}
    # Different questions -> independent ledgers (keyword lessons only in a).
    assert a["selected"] != b["selected"] or a["injections"] != b["injections"]
