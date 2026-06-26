"""
Phase 10 — full-reasoning prompt layer (registry / real-provider path).

Proves the rigorous reasoning scaffolding is built per role/phase/task-kind and is
delivered through the adapter, without relaxing any invariant. (Mock providers
ignore the system prompt; the real effect appears only with real models.)
"""

from backend.dialogues.models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, REASONING_PROTOCOL, EVALUATION_DIRECTIVE,
    ROLE_REASONING, PHASE_REASONING,
)
from backend.dialogues.agent import CORE_AGENT_PROMPT
from backend.dialogues.offline_provider_adapter import offline_scripted_adapter


def test_prompt_includes_identity_and_reasoning_protocol():
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS)
    assert CORE_AGENT_PROMPT[:40] in p                 # council identity carried
    assert REASONING_PROTOCOL.splitlines()[0] in p     # reasoning protocol header
    for cue in ("Decompose", "Steelman", "Calibrate", "Ground every claim"):
        assert cue in p


def test_role_directive_is_role_specific():
    for role in (AgentRole.SOCRATES, AgentRole.ELENCHUS_CRITIC, AgentRole.SYNTHESIZER,
                 AgentRole.MAIEUTIC_RECONSTRUCTOR, AgentRole.REFLECTOR,
                 AgentRole.EMPIRICIST, AgentRole.FINAL_EVALUATOR):
        p = build_reasoning_system_prompt(role, DialogPhase.INITIAL_RESPONSE)
        assert ROLE_REASONING[role] in p
        assert role.value.upper().replace("_", " ") in p


def test_phase_directive_present():
    p = build_reasoning_system_prompt(AgentRole.ELENCHUS_CRITIC, DialogPhase.ELENCHUS)
    assert PHASE_REASONING[DialogPhase.ELENCHUS] in p


def test_evaluative_tasks_get_judge_not_author_directive():
    for kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE, TaskKind.COUNCIL_RATIFICATION):
        p = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION, kind)
        assert EVALUATION_DIRECTIVE.splitlines()[0] in p
        assert "must not consider — which agent or provider" in p   # anti-identity
        assert "Do not herd" in p                                    # anti-herding


def test_non_evaluative_tasks_have_no_evaluation_directive():
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                      TaskKind.SYNTHESIS_DRAFT)
    assert EVALUATION_DIRECTIVE.splitlines()[0] not in p   # a synthesizer is not judging


def test_response_contract_preserved():
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS)
    assert "EXACTLY one JSON object" in p                  # structured-output contract kept


def test_prompt_carries_no_hidden_internals():
    # the reasoning prompt is static role/phase guidance — no scores/leaderboard/task_log
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                      TaskKind.SYNTHESIS_DRAFT).lower()
    for forbidden in ("leaderboard", "task_log", "micro_score", "provider_id", "audit_summary"):
        assert forbidden not in p


def test_adapter_now_sends_full_reasoning_prompt():
    adapter = offline_scripted_adapter("p")
    task = AgentTask(session_id="s", agent_id="agent_0", role=AgentRole.ELENCHUS_CRITIC,
                     phase=DialogPhase.ELENCHUS, question="Is knowledge JTB?",
                     task_kind=TaskKind.ELENCHUS_OBJECTION)
    state = AgentState(agent_id="agent_0", primary_role=AgentRole.ELENCHUS_CRITIC,
                       assigned_role=AgentRole.ELENCHUS_CRITIC)
    req = adapter._build_request(task, state)
    assert REASONING_PROTOCOL.splitlines()[0] in req.system
    assert ROLE_REASONING[AgentRole.ELENCHUS_CRITIC] in req.system
    assert PHASE_REASONING[DialogPhase.ELENCHUS] in req.system
    # request still shaped for a live Messages call (unchanged contract)
    kw = req.to_messages_kwargs()
    assert set(kw) == {"model", "max_tokens", "system", "messages", "thinking"}
