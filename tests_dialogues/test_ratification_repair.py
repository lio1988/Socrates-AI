"""
Phase 19 — Ratification Repair Option B (runner-up swap + re-ratify, bounded).

The long-deferred capability: on a schema-valid critical block, CED mechanically
swaps each blocked section for its peer-scored RUNNER-UP draft and asks the
COUNCIL to ratify again (max MAX_RATIFICATION_ROUNDS). Invariants intact:
- the runner-up comes from peer scores (or deterministic draft order) — never
  a semantic CED choice;
- re-ratification is the council's judgment — CED never overrides a block;
- no runner-up / rounds exhausted → repair_required stands, answer withheld;
- Option A ("block") remains the default: existing behavior unchanged.
Offline, mock only.
"""

import asyncio

import pytest

from backend.dialogues.models import MAX_RATIFICATION_ROUNDS, SectionName
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, BlockingObjectionProvider,
)

Q = "Is knowledge merely justified true belief?"


class OneShotBlocker(BlockingObjectionProvider):
    """Critically blocks core_answer on the FIRST ratification round, accepts after."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._rat_calls = 0

    def _ratification_verdict(self, task):
        self._rat_calls += 1
        if self._rat_calls == 1:
            return super()._ratification_verdict(task)
        return {"verdict": "accept",
                "rationale": "The repaired section resolves the objection.",
                "confidence": 0.8}


def _council(repair="block", blocker_cls=None, extra_seats=("m_a",)):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pid in extra_seats:
        reg.register(ScriptedMockProvider(pid))
    if blocker_cls is not None:
        reg.register(blocker_cls("m_blk"))
    else:
        reg.register(ScriptedMockProvider("m_b"))
    return CEDOrchestrator(agents, p, registry=reg, ratification_repair=repair)


# ── Option A (default) unchanged ─────────────────────────────────────────────

def test_default_block_mode_unchanged():
    ced = _council("block", BlockingObjectionProvider)
    final = asyncio.run(ced.run_registry_session(Q, session_id="a1"))
    assert final.ratification_status == "repair_required"
    assert final.ratified is False and final.answer == ""
    ra = final.audit_summary["ratification_repair"]
    assert ra["mode"] == "block" and ra["rounds_used"] == 0 and ra["repairs"] == []


def test_default_param_is_block():
    ced = _council()
    assert ced.ratification_repair == "block"


def test_invalid_mode_raises():
    p = FakeProvider()
    agents = [SocraticAgent(f"a{i}", p) for i in range(2)]
    with pytest.raises(ValueError, match="ratification_repair"):
        CEDOrchestrator(agents, p, ratification_repair="magic")


# ── Option B: repair succeeds ─────────────────────────────────────────────────

def test_runner_up_repair_succeeds_and_ratifies():
    ced = _council("runner_up", OneShotBlocker)
    final = asyncio.run(ced.run_registry_session(Q, session_id="b1"))
    assert final.ratified is True
    ra = final.audit_summary["ratification_repair"]
    assert ra["outcome"] == "repaired_and_ratified" and ra["rounds_used"] == 1
    assert ra["round_statuses"] == ["repair_required", "ratified"]
    assert final.answer                                    # answer delivered


def test_repair_provenance_is_recorded_and_real():
    ced = _council("runner_up", OneShotBlocker)
    final = asyncio.run(ced.run_registry_session(Q, session_id="b2"))
    rep = final.audit_summary["ratification_repair"]["repairs"][0]
    assert rep["section"] == "core_answer"
    assert rep["from_draft"] != rep["to_draft"]            # actually swapped
    assert rep["via"] in ("peer_ranking", "deterministic_order")
    # the repaired section's content is a REAL runner-up draft's text (no fabrication)
    state = ced.get_session("b2")
    section = state.assembled_answer.section(SectionName.CORE_ANSWER)
    draft = next(d for d in state.section_drafts if d.draft_id == rep["to_draft"])
    assert section.content == draft.section_text(SectionName.CORE_ANSWER)
    assert section.selected_draft_id == rep["to_draft"]


# ── Option B: honest stops ────────────────────────────────────────────────────

def test_persistent_blocker_stops_honestly_within_bounds():
    ced = _council("runner_up", BlockingObjectionProvider)
    final = asyncio.run(ced.run_registry_session(Q, session_id="c1"))
    assert final.ratified is False and final.answer == ""   # never overridden
    ra = final.audit_summary["ratification_repair"]
    assert ra["rounds_used"] <= MAX_RATIFICATION_ROUNDS
    assert ra["outcome"] in ("repair_required", "unrepairable_no_runner_up")
    # every round's council status is audited
    assert ra["round_statuses"][0] == "repair_required"


def test_no_runner_up_available_stays_blocked():
    # blocker + only ONE scripted seat → synthesis drafts may exhaust quickly;
    # force exhaustion by pre-marking every draft as tried
    ced = _council("runner_up", BlockingObjectionProvider)
    final = asyncio.run(ced.run_registry_session(Q, session_id="c2"))
    state = ced.get_session("c2")
    tried = {SectionName.CORE_ANSWER: {d.draft_id for d in state.section_drafts}}
    from backend.dialogues.ced import CEDOrchestrator as _C
    repairs = ced._repair_blocked_sections(state, state.council_ratification, tried)
    assert repairs == []                                    # nothing left to try


# ── normal sessions unaffected ────────────────────────────────────────────────

def test_accepting_council_never_enters_repair():
    ced = _council("runner_up")                              # no blocker
    final = asyncio.run(ced.run_registry_session(Q, session_id="d1"))
    assert final.ratified is True
    ra = final.audit_summary["ratification_repair"]
    assert ra["rounds_used"] == 0 and ra["repairs"] == []
    assert ra["round_statuses"] == ["ratified"]


def test_build_council_enables_runner_up_by_default():
    from backend.dialogues.live_providers import build_council
    ced, mode = build_council(env={}, council_size=2)
    assert mode == "mock" and ced.ratification_repair == "runner_up"
