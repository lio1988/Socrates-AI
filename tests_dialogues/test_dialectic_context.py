"""
Dialectic context flow — the mechanism by which the dialogue improves answers.

If an agent never sees the other agents' actual moves, the "dialectic" is N
parallel monologues. These tests lock in that each phase receives the material
it must argue against — especially that the SYNTHESIS sees the actual critiques
(previously the elenchus work was discarded at the last mile) — while minimal
awareness holds (no scores/leaderboard/audit in any agent-facing context).
"""

import asyncio

from backend.dialogues.models import (
    AgentMove, AgentRole, DialogPhase, SessionState, TaskKind,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider

Q = "Is knowledge merely justified true belief?"


def _ced():
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    reg.register(ScriptedMockProvider("m_a"))
    reg.register(ScriptedMockProvider("m_b"))
    return CEDOrchestrator(agents, p, registry=reg)


def _state_with_dialogue(ced) -> SessionState:
    st = SessionState(session_id="ctx", question=Q)
    ced._sessions["ctx"] = st

    def mv(phase, agent, content, role=AgentRole.SYNTHESIZER):
        st.moves.append(AgentMove(task_id="t", agent_id=agent, role=role,
                                  phase=phase, content=content))
    # a Socrates opening that uses the LIVE key name (socratic_question)
    mv(DialogPhase.OPENING, "agent_3",
       {"socratic_question": "What do we assume by 'justified'?"}, AgentRole.SOCRATES)
    mv(DialogPhase.INITIAL_RESPONSE, "agent_0", {"thesis": "JTB suffices"})
    mv(DialogPhase.ELENCHUS, "agent_1",
       {"objection": "Gettier cases break sufficiency"}, AgentRole.ELENCHUS_CRITIC)
    mv(DialogPhase.REFLECTION, "agent_0", {"revised": "JTB necessary, not sufficient"},
       AgentRole.REFLECTOR)
    mv(DialogPhase.RECONSTRUCTION, "agent_2", {"stronger": "JTB + anti-luck"},
       AgentRole.MAIEUTIC_RECONSTRUCTOR)
    return st


def test_initial_response_gets_socratic_question_from_live_key_name():
    ced = _ced()
    st = _state_with_dialogue(ced)
    ctx = ced._registry_phase_context(st, DialogPhase.INITIAL_RESPONSE, "agent_0")
    # previously only content["question"] was read -> live moves using
    # "socratic_question" silently fell back to the raw question
    assert ctx["socratic_opening_question"] == "What do we assume by 'justified'?"


def test_elenchus_sees_opening_and_initial_responses():
    ced = _ced()
    st = _state_with_dialogue(ced)
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "agent_1")
    assert ctx["socratic_opening_question"] == "What do we assume by 'justified'?"
    assert any("JTB suffices" in str(r) for r in ctx["initial_responses"])


def test_synthesis_sees_the_actual_critiques():
    ced = _ced()
    st = _state_with_dialogue(ced)
    ctx = ced._registry_phase_context(st, DialogPhase.SYNTHESIS, "agent_0")
    # THE fix: the objections raised now reach the synthesis
    assert any("Gettier" in str(c) for c in ctx["critiques_raised"])
    assert ctx["socratic_opening_question"] == "What do we assume by 'justified'?"
    assert any("anti-luck" in str(r) for r in ctx["reconstructed_positions"])
    assert any("not sufficient" in str(r) for r in ctx["reflected_positions"])


def test_reflection_still_gets_own_position_plus_critiques():
    ced = _ced()
    st = _state_with_dialogue(ced)
    ctx = ced._registry_phase_context(st, DialogPhase.REFLECTION, "agent_0")
    assert ctx["my_initial_response"] == {"thesis": "JTB suffices"}
    assert any("Gettier" in str(c) for c in ctx["critiques_from_council"])


def test_no_hidden_internals_in_any_phase_context():
    ced = _ced()
    st = _state_with_dialogue(ced)
    forbidden = ("score", "leaderboard", "task_log", "audit", "provider", "micro")
    for phase in (DialogPhase.OPENING, DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS,
                  DialogPhase.REFLECTION, DialogPhase.RECONSTRUCTION, DialogPhase.SYNTHESIS):
        ctx = ced._registry_phase_context(st, phase, "agent_0")
        for key in ctx:
            assert not any(tok in key.lower() for tok in forbidden), (phase, key)


def test_full_registry_session_still_green_with_new_context():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="ctx_full"))
    assert final.ratified is True
    assert all(not s.unresolved for s in final.synthesis.sections)
