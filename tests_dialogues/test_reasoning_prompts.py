"""
Phase 10 — full-reasoning prompt layer (registry / real-provider path).

Proves the rigorous reasoning scaffolding is built per role/phase/task-kind and is
delivered through the adapter, without relaxing any invariant. (Mock providers
ignore the system prompt; the real effect appears only with real models.)
"""

from backend.dialogues.models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, REASONING_PROTOCOL, EVALUATION_DIRECTIVE,
    ROLE_REASONING, PHASE_REASONING, SYNTHESIS_CONTENT_DIRECTIVE,
    SCORE_CONTENT_DIRECTIVE, BAYESIAN_UPDATE_DIRECTIVE,
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


def test_elenchus_searches_hard_but_may_report_no_material_objection():
    directive = ROLE_REASONING[AgentRole.ELENCHUS_CRITIC]
    assert "Search aggressively" in directive
    assert "NO MATERIAL OBJECTION" in directive
    assert "Never manufacture disagreement" in directive
    assert "not to win" in directive


def test_reflection_may_retain_a_defensible_position():
    directive = ROLE_REASONING[AgentRole.REFLECTOR]
    assert "evidence_force is none" in directive
    assert "retain the defensible position" in directive
    assert "do not manufacture an update" in directive
    assert 'evidence_force is "none"' in BAYESIAN_UPDATE_DIRECTIVE
    assert "what_changed" in BAYESIAN_UPDATE_DIRECTIVE
    assert '"NONE"' in BAYESIAN_UPDATE_DIRECTIVE


def test_synthesis_uses_real_objections_or_honest_sentinels():
    directive = ROLE_REASONING[AgentRole.SYNTHESIZER]
    assert "strongest REAL material objection actually raised" in directive
    for sentinel in ("NONE", "NO MATERIAL REMAINING OBJECTION", "NOT_APPLICABLE"):
        assert sentinel in SYNTHESIS_CONTENT_DIRECTIVE
    assert "`critiques_raised`" in SYNTHESIS_CONTENT_DIRECTIVE
    assert "never\n                          invent" in SYNTHESIS_CONTENT_DIRECTIVE


def test_numeric_score_prompt_matches_the_seven_field_contract():
    for kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE):
        prompt = build_reasoning_system_prompt(
            AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION, kind,
        )
        assert "EXACTLY these seven numeric fields" in prompt
        assert "do not add prose justification" in prompt.lower()
        assert "Justify each judgement" not in prompt
        assert '"rationale"' not in prompt
    assert "seven numeric fields" in SCORE_CONTENT_DIRECTIVE


def test_ratification_keeps_schema_supported_textual_reasoning():
    prompt = build_reasoning_system_prompt(
        AgentRole.FINAL_EVALUATOR,
        DialogPhase.RATIFICATION,
        TaskKind.COUNCIL_RATIFICATION,
    )
    assert '"rationale" string' in prompt
    assert "task-specific schema" in prompt
