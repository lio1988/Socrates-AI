"""Two role slots must be two seats, and a retry must not undo that.

The role planner was never wrong. For session "live_dialogue" it gave ELENCHUS
to agent_0 and agent_3, and the frozen binding put those on seat0 and seat3 —
distinct, as promised. seat3 was the Mistral seat, which fails structurally on
the JSON contract, and the phase-retry re-asked the failed slot with a fixed
`offset=1`: order[(3 + 1) % 4] = seat0, already serving agent_0.

Both objections were then authored by one physical seat, and the peers left to
corroborate them dropped from three to two — which is why two live runs in a row
could not corroborate anything and the release stayed unresolved.

A fixed offset cannot see what the sibling slots are doing. These tests pin the
routing, not the trace: a duplicated seat reads as a full council and is not one.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import _PHASE_ROLE_SLOTS, CEDOrchestrator
from backend.dialogues.models import (
    AgentState, AgentTask, DialogPhase, ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider

SESSION = "live_dialogue"          # the session id that exposed the bug
Q = "Four researchers present once each. Anna presents before Ben."


class BreaksOnElenchus(ScriptedMockProvider):
    """What the Mistral seat actually does: valid everywhere but one contract."""

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.ELENCHUS_OBJECTION:
            return '{"content:{claims":["broken"'
        return await super()._produce_raw_text(task, agent_state)


#: Socrates rejoins the elenchus, so the phase now fills three slots.
ELENCHUS_SLOTS = len(_PHASE_ROLE_SLOTS[DialogPhase.ELENCHUS])


def _council(*, broken_seat=None, seats=4, retry=True, quorum=None):
    """`quorum` forces the rescue path: with three slots and the default quorum
    two survivors are enough, so a single failure would never trigger a retry and
    the reroute regression could not be exercised at all."""
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(seats):
        cls = BreaksOnElenchus if broken_seat == i else ScriptedMockProvider
        registry.register(cls(f"seat{i}"))
    if quorum is not None:
        registry.quorum_for_assembly = quorum
    return CEDOrchestrator(
        [SocraticAgent(f"agent_{i}", provider) for i in range(4)], provider,
        registry=registry, shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
        phase_retry=retry)


def _run(ced, session_id=SESSION):
    final = asyncio.run(ced.run_registry_session(Q, session_id=session_id))
    return final


def _elenchus(ced, session_id=SESSION):
    for entry in ced._phase_dispatch.get(session_id, []):
        if entry["phase"] == DialogPhase.ELENCHUS.value:
            return entry["slots"]
    return []


def _serving(slots):
    return [d["provider_id"] for d in slots if d["ok"]]


# ══ distinct logical agents, distinct seats ══════════════════════════════════

def test_every_elenchus_slot_resolves_to_a_distinct_logical_agent():
    ced = _council()
    _run(ced)
    slots = _elenchus(ced)
    agents = [d["logical_agent_id"] for d in slots]
    assert len(slots) == ELENCHUS_SLOTS
    assert len(set(agents)) == ELENCHUS_SLOTS, agents


def test_every_elenchus_slot_resolves_to_a_distinct_provider():
    ced = _council()
    _run(ced)
    serving = _serving(_elenchus(ced))
    assert len(serving) == ELENCHUS_SLOTS
    assert len(set(serving)) == ELENCHUS_SLOTS, serving


def test_every_slot_records_its_full_dispatch_identity():
    ced = _council()
    _run(ced)
    for entry in ced._phase_dispatch[SESSION]:
        for d in entry["slots"]:
            assert set(d) >= {"slot_index", "logical_agent_id", "assigned_role",
                              "provider_id", "model_id", "attempt_index", "retry"}
            assert isinstance(d["slot_index"], int)
            assert d["logical_agent_id"].startswith("agent_")
            assert d["provider_id"].startswith("seat")


# ══ the bug: a retry must not land on a busy sibling seat ════════════════════

def test_a_failed_slot_never_reroutes_onto_a_seat_serving_a_sibling():
    """THE regression. seat3 fails; offset=1 lands on seat0, which is busy."""
    ced = _council(broken_seat=3, quorum=ELENCHUS_SLOTS)
    _run(ced)
    slots = _elenchus(ced)
    serving = _serving(slots)
    assert serving, "the phase must still produce moves"
    assert len(set(serving)) == len(serving), f"a seat served twice: {serving}"
    assert "seat0" in serving
    assert "seat3" not in serving          # it failed; it did not serve


def test_only_the_failed_slot_is_retried():
    # Read from the orchestrator rather than the final audit summary: with the
    # handover gone a wholly dead seat can end the session before a summary
    # exists, and this test is about which slots were re-asked, not about
    # whether the council reached a verdict.
    ced = _council(broken_seat=3, quorum=ELENCHUS_SLOTS)
    _run(ced)
    retries = [r for r in ced._phase_retries.get(SESSION, [])
               if r["phase"] == DialogPhase.ELENCHUS.value]
    assert len(retries) == 1
    assert retries[0]["failed_slots"] == retries[0]["reasked_same_seat_slots"]
    assert len(retries[0]["reasked_same_seat_slots"]) == 1


def test_the_successful_sibling_slot_never_moves():
    ced = _council(broken_seat=3, quorum=ELENCHUS_SLOTS)
    _run(ced)
    slots = _elenchus(ced)
    primaries = [d for d in slots if d["attempt_index"] == 0 and d["ok"]]
    assert len(primaries) == ELENCHUS_SLOTS - 1
    assert primaries[0]["retry"] is False
    # It appears exactly once: nothing re-dispatched it.
    assert sum(1 for d in slots
               if d["logical_agent_id"] == primaries[0]["logical_agent_id"]) == 1


def test_the_retry_is_recorded_on_the_seat_that_failed():
    """The second ask goes back to the same seat, and the record shows it.

    This asserted the opposite until the cross-seat handover was removed: the
    retry used to land on a different provider, which is precisely the topology
    change a bound protocol refuses at dispatch.
    """
    ced = _council(broken_seat=3, quorum=ELENCHUS_SLOTS)
    _run(ced)
    slots = _elenchus(ced)
    retried = [d for d in slots if d["retry"]]
    assert len(retried) == 1
    assert retried[0]["attempt_index"] == 1
    failed_primary = [d for d in slots
                      if d["attempt_index"] == 0 and not d["ok"]][0]
    assert retried[0]["logical_agent_id"] == failed_primary["logical_agent_id"]
    assert retried[0]["provider_id"] == failed_primary["provider_id"]


# ══ determinism ══════════════════════════════════════════════════════════════

def test_the_same_session_id_yields_the_same_assignment():
    def shape():
        ced = _council()
        _run(ced)
        return [(d["slot_index"], d["logical_agent_id"], d["provider_id"])
                for d in _elenchus(ced)]

    assert shape() == shape()


def test_a_different_session_id_may_rotate_differently_and_stays_distinct():
    seen = set()
    for session_id in ("live_dialogue", "session_b", "session_c", "session_d"):
        ced = _council()
        _run(ced, session_id)
        slots = _elenchus(ced, session_id)
        agents = tuple(d["logical_agent_id"] for d in slots)
        assert len(set(agents)) == ELENCHUS_SLOTS, f"{session_id}: {agents}"
        seen.add(agents)
    assert len(seen) > 1, "rotation should vary across session ids"


# ══ untouched by design ══════════════════════════════════════════════════════

def test_synthesis_still_uses_every_agent():
    ced = _council()
    _run(ced)
    entry = next(e for e in ced._phase_dispatch[SESSION]
                 if e["phase"] == DialogPhase.SYNTHESIS.value)
    agents = {d["logical_agent_id"] for d in entry["slots"]}
    assert agents == {f"agent_{i}" for i in range(4)}


def test_ratification_still_calls_every_available_provider():
    ced = _council()
    final = _run(ced)
    council = final.audit_summary["council_ratification"]
    assert council["valid_verdicts"] >= council["quorum"]
    assert final.ratification_status


def test_role_history_matches_what_was_actually_dispatched():
    ced = _council()
    _run(ced)
    state = ced.get_session(SESSION)
    recorded = {(e["phase"], e["agent_id"], e["role"]) for e in state.role_history}
    for entry in ced._phase_dispatch[SESSION]:
        for d in entry["slots"]:
            if d["attempt_index"] != 0:
                continue          # a reroute changes the seat, never the agent
            assert (entry["phase"], d["logical_agent_id"],
                    d["assigned_role"]) in recorded, d


def test_the_dispatch_audit_is_observability_and_changes_no_verdict():
    with_audit = _run(_council())
    assert "phase_dispatch" in with_audit.audit_summary
    # Nothing epistemic reads it.
    governing = with_audit.audit_summary["governing_release"]
    assert "phase_dispatch" not in json.dumps(governing)


# ══ the objection observability the audit was missing ════════════════════════

def test_the_audit_shows_each_objections_target_scope_and_provenance():
    ced = _council()
    final = _run(ced)
    objections = final.audit_summary["governing_release"]["objections"]
    assert objections, "elenchus moves should project as objections"
    for row in objections:
        assert set(row) >= {"objection_id", "target_claim_id", "target_section",
                            "scope", "targeting_provenance", "state"}


def test_objection_observability_does_not_change_the_release():
    a = _run(_council())
    b = _run(_council())
    assert a.release_decision == b.release_decision
    assert a.governing_epistemic_status == b.governing_epistemic_status
