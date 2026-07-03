"""
Phase 21 — Analytics-informed seat routing (a real collaboration/cohesion gap).

Before this phase: TopicSkillTracker and CalibrationLedger were ingested every
session but NEVER READ by anything — the CED measured which seats were good at
what, then routed deliberation work with plain registration-order round-robin,
ignoring its own analytics entirely. This closes that loop: when a phase needs
fewer healthy seats than are available, CED prefers the seats its own
topic-skill + reliability data rate best for THIS question's topic.

Invariants:
- no trackers attached -> BYTE-FOR-BYTE the pre-Phase-21 order (registration
  order via Python's stable sort, not an arbitrary provider_id string sort);
- trackers attached but no data yet -> also unchanged order (same reason);
- unrated seats still get a fair first chance (exploration) over known-mediocre
  seats — same philosophy as SeatHealthTracker.rank_seats;
- among seats WITH data, higher topic skill / lower failure rate wins;
- role assignment (who plays which Socratic role) is completely untouched —
  only which PROVIDER executes an already-assigned agent's task changes;
- routing/skill values never reach agent-facing context (hidden, like the
  leaderboard) — audited only, in seat_routing.
Offline, mock only.
"""

import asyncio

import pytest

from backend.dialogues.models import DialogPhase
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider
from backend.dialogues.self_improvement import TopicSkillTracker, TopicSkill, SeatHealthTracker

Q = "Is knowledge merely justified true belief?"


def _council(seats=("m_a", "m_b", "m_c"), **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pid in seats:
        reg.register(ScriptedMockProvider(pid))
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _epistemology_skill(scores: dict) -> TopicSkillTracker:
    skill = TopicSkillTracker()
    for seat, total in scores.items():
        skill._skills[f"{seat}|epistemology"] = TopicSkill(
            seat=seat, topic="epistemology", score_sum=total, score_count=10)
    return skill


# ── no-op without trackers / without data ─────────────────────────────────────

def test_no_trackers_preserves_registration_order():
    ced = _council()
    st = ced.create_session(Q, session_id="s1")
    assert [a.provider_id for a in ced._ranked_adapters(st)] == ["m_a", "m_b", "m_c"]


def test_seat_health_attached_but_empty_preserves_registration_order():
    ced = _council(seat_health=SeatHealthTracker())
    st = ced.create_session(Q, session_id="s2")
    assert [a.provider_id for a in ced._ranked_adapters(st)] == ["m_a", "m_b", "m_c"]


def test_topic_skill_attached_but_empty_preserves_registration_order():
    ced = _council(topic_skill=TopicSkillTracker())
    st = ced.create_session(Q, session_id="s3")
    assert [a.provider_id for a in ced._ranked_adapters(st)] == ["m_a", "m_b", "m_c"]


# ── exploration: unrated seats get a fair first chance ────────────────────────

def test_unrated_seat_outranks_known_mediocre_seat():
    skill = _epistemology_skill({"m_a": 50.0})   # only m_a is rated; m_b, m_c unrated
    ced = _council(topic_skill=skill)
    st = ced.create_session(Q, session_id="s4")
    order = [a.provider_id for a in ced._ranked_adapters(st)]
    assert order[0] in ("m_b", "m_c")             # an unrated seat leads
    assert order[-1] == "m_a"                     # the only rated (mediocre) seat is last


# ── known seats: higher skill / lower failure rate wins ───────────────────────

def test_higher_topic_skill_wins_among_known_seats():
    skill = _epistemology_skill({"m_c": 95.0, "m_b": 60.0, "m_a": 50.0})
    ced = _council(topic_skill=skill)
    st = ced.create_session(Q, session_id="s5")
    assert [a.provider_id for a in ced._ranked_adapters(st)] == ["m_c", "m_b", "m_a"]


def test_top_ranked_seat_gets_the_single_slot_phase():
    skill = _epistemology_skill({"m_c": 95.0, "m_b": 60.0, "m_a": 50.0})
    ced = _council(topic_skill=skill)
    final = asyncio.run(ced.run_registry_session(Q, session_id="s6"))
    opening = final.audit_summary["registry_phase_rounds"][0]
    assert opening["phase"] == "opening" and opening["ok_providers"] == ["m_c"]
    assert final.ratified is True


def test_lower_failure_rate_wins_when_no_skill_data():
    from backend.dialogues.models import (
        AgentRole, DialogPhase as DP, ProviderStatus, SessionState, TaskLogEntry,
    )
    health = SeatHealthTracker()
    st_seed = SessionState(session_id="seed", question="q")
    for _ in range(6):
        st_seed.task_log.append(TaskLogEntry(
            task_id="t", move_id=None, session_id="seed", phase=DP.SYNTHESIS,
            agent_id="a", assigned_role=AgentRole.SYNTHESIZER,
            provider_id="m_flaky", provider_status=ProviderStatus.TIMEOUT))
    st_seed.task_log.append(TaskLogEntry(
        task_id="t2", move_id="m1", session_id="seed", phase=DP.SYNTHESIS,
        agent_id="a", assigned_role=AgentRole.SYNTHESIZER,
        provider_id="m_solid", provider_status=ProviderStatus.OK))
    health.ingest_session(st_seed)
    ced = _council(seats=("m_flaky", "m_solid"), seat_health=health)
    st = ced.create_session(Q, session_id="s7")
    order = [a.provider_id for a in ced._ranked_adapters(st)]
    assert order == ["m_solid", "m_flaky"]        # more reliable seat ranks first


# ── role assignment untouched; audit + hiding ─────────────────────────────────

def test_role_assignment_unaffected_by_routing():
    # SAME session_id in both (role assignment is a function of session_id via
    # stable_hash) — isolates the one variable under test: trackers on/off.
    skill = _epistemology_skill({"m_c": 95.0, "m_a": 50.0})
    ced_ranked = _council(topic_skill=skill)
    ced_plain = _council()
    st1 = ced_ranked.create_session(Q, session_id="same_id")
    st2 = ced_plain.create_session(Q, session_id="same_id")
    r1 = ced_ranked._registry_phase_assignment(st1, DialogPhase.INITIAL_RESPONSE)
    r2 = ced_plain._registry_phase_assignment(st2, DialogPhase.INITIAL_RESPONSE)
    assert r1 == r2                                # same agent->role plan regardless


def test_seat_routing_audited_and_hidden_from_agents():
    skill = _epistemology_skill({"m_c": 95.0, "m_b": 60.0, "m_a": 50.0})
    ced = _council(topic_skill=skill)
    final = asyncio.run(ced.run_registry_session(Q, session_id="s8"))
    sr = final.audit_summary["seat_routing"]
    assert sr["topic"] == "epistemology"
    assert sr["order"] == ["m_c", "m_b", "m_a"]
    assert sr["analytics_informed"] is True
    state = ced.get_session("s8")
    for phase in (DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS, DialogPhase.SYNTHESIS):
        blob = str(ced._registry_phase_context(state, phase, "agent_0")).lower()
        assert "seat_routing" not in blob and "topic_skill" not in blob


def test_analytics_informed_false_without_trackers():
    ced = _council()
    final = asyncio.run(ced.run_registry_session(Q, session_id="s9"))
    assert final.audit_summary["seat_routing"]["analytics_informed"] is False


def test_scoring_and_ratification_voters_remain_unbiased():
    """Scoring/ratification eligibility must NOT be skill-ranked — every voice
    counts equally in judging, regardless of topic skill."""
    skill = _epistemology_skill({"m_c": 95.0, "m_a": 50.0})
    ced = _council(topic_skill=skill)
    asyncio.run(ced.run_registry_session(Q, session_id="s10"))
    state = ced.get_session("s10")
    move = state.moves[0]
    voters = {a.provider_id for a in ced._eligible_score_voters(move)}
    assert voters == {a.provider_id for a in ced._healthy_adapters()} - {move.provider_id}


def test_build_council_full_session_still_works_with_new_trackers():
    from backend.dialogues.live_providers import build_council
    from backend.dialogues.self_improvement import TopicSkillTracker as TST, CalibrationLedger
    ced, mode = build_council(env={}, council_size=2, topic_skill=TST(),
                              calibration=CalibrationLedger())
    final = asyncio.run(ced.run_registry_session(Q, session_id="s11"))
    assert mode == "mock" and final.ratified is True
