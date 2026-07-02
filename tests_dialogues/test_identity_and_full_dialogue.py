"""
Agent identity + whole-dialogue reasoning.

(1) Each agent knows WHO IT IS (model/company) and WHO IS IN THE ROOM
    (council_roster) while deliberating, and every deliberation move carries
    speaker attribution in the full `dialogue_so_far` transcript.
(2) Each agent is instructed to reason over the WHOLE dialogue before every move.
(3) The judging boundary holds: scoring/ratification tasks receive NO roster,
    NO transcript, NO attribution — judged outputs stay anonymous (the permanent
    peer-scoring invariant; identity there would enable brand/self-preference bias).
"""

import asyncio

from backend.dialogues.models import (
    AgentRole, DialogPhase, ShadowScoringMode, TaskKind,
)
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, model_company,
    DIALOGUE_REVIEW_DIRECTIVE, EVALUATION_DIRECTIVE,
)
from backend.dialogues.live_providers import LiveAnthropicAdapter, build_council
from backend.dialogues.models import AgentState, AgentTask

FAKE_KEY = "sk-ant-FAKE-not-a-real-key-000000"


# ── (1a) self-identity: model + company in the system prompt ─────────────────

def test_model_company_mapping():
    assert model_company("claude-opus-4-8") == "Anthropic"
    assert model_company("claude-haiku-4-5-20251001") == "Anthropic"
    assert model_company("gpt-5") == "OpenAI"
    assert model_company("gemini-2.5-pro") == "Google"
    assert model_company("grok-4") == "xAI"
    assert model_company("mock") == "Mock (offline)"
    assert model_company("mystery-model") == "Unknown"
    assert model_company(None) == "Unknown"


def test_prompt_carries_self_identity():
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                      TaskKind.SYNTHESIS_DRAFT, model="claude-opus-4-8")
    assert "`claude-opus-4-8`" in p and "built by Anthropic" in p
    assert "council_roster" in p                       # told where to find the panel
    assert "agreement between" in p.lower()            # anti-herding framing


def test_live_adapter_request_carries_identity():
    adapter = LiveAnthropicAdapter("seat0", FAKE_KEY, model="claude-haiku-4-5-20251001")
    task = AgentTask(session_id="s", agent_id="a", role=AgentRole.ELENCHUS_CRITIC,
                     phase=DialogPhase.ELENCHUS, question="q",
                     task_kind=TaskKind.ELENCHUS_OBJECTION)
    st = AgentState(agent_id="a", primary_role=AgentRole.ELENCHUS_CRITIC,
                    assigned_role=AgentRole.ELENCHUS_CRITIC)
    req = adapter._build_request(task, st)
    assert "claude-haiku-4-5-20251001" in req.system and "Anthropic" in req.system


# ── (1b) roster + attributed transcript in deliberation context ──────────────

def _session():
    ced, mode = build_council(env={}, council_size=2,
                              shadow_scoring_mode=ShadowScoringMode.OFF)
    asyncio.run(ced.run_registry_session("Is knowledge JTB?", session_id="idfd"))
    return ced, ced.get_session("idfd")


def test_deliberation_context_has_roster_and_attributed_transcript():
    ced, st = _session()
    for phase in (DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS,
                  DialogPhase.REFLECTION, DialogPhase.SYNTHESIS):
        ctx = ced._registry_phase_context(st, phase, "agent_0")
        roster = ctx["council_roster"]
        assert len(roster) == 2
        assert all({"seat", "model", "company"} <= set(r) for r in roster)
        transcript = ctx["dialogue_so_far"]
        assert len(transcript) == len(st.moves)         # the WHOLE dialogue
        assert all({"phase", "role", "by", "content"} <= set(e) for e in transcript)
        # chronological: first entry is the Socratic opening
        assert transcript[0]["phase"] == "opening"


def test_phase_specific_extracts_still_present():
    ced, st = _session()
    ctx = ced._registry_phase_context(st, DialogPhase.SYNTHESIS, "agent_0")
    for key in ("critiques_raised", "reconstructed_positions", "socratic_opening_question"):
        assert key in ctx                              # targeted material kept too


# ── (2) whole-dialogue review instruction, deliberation only ─────────────────

def test_dialogue_review_directive_for_deliberation_kinds():
    for kind in (TaskKind.SOCRATIC_QUESTION, TaskKind.INITIAL_RESPONSE,
                 TaskKind.ELENCHUS_OBJECTION, TaskKind.REFLECTION_REVISION,
                 TaskKind.RECONSTRUCTION_PROPOSAL, TaskKind.SYNTHESIS_DRAFT):
        p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                          kind, model="claude-opus-4-8")
        assert DIALOGUE_REVIEW_DIRECTIVE.splitlines()[0] in p, kind


def test_no_dialogue_review_for_judging_kinds():
    for kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE, TaskKind.COUNCIL_RATIFICATION):
        p = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION,
                                          kind, model="claude-opus-4-8")
        assert DIALOGUE_REVIEW_DIRECTIVE.splitlines()[0] not in p, kind
        assert EVALUATION_DIRECTIVE.splitlines()[0] in p          # blind judging kept


# ── (3) judging tasks stay identity-free (anti brand-bias boundary) ──────────

def test_scoring_and_ratification_context_has_no_identity():
    ced, st = _session()
    # move-level scoring task context
    move = st.moves[0]
    mtask = ced._build_move_score_task(st, move, "voter_x", move.phase, 0)
    for forbidden in ("council_roster", "dialogue_so_far", "company", "model", "by"):
        assert forbidden not in mtask.context, forbidden
    assert set(mtask.context) == {"output_to_score", "rubric_name", "rubric_focus"}


def test_backward_compatible_without_model():
    # callers that don't pass a model (legacy/tests) get no identity block, no crash
    p = build_reasoning_system_prompt(AgentRole.SOCRATES, DialogPhase.OPENING,
                                      TaskKind.SOCRATIC_QUESTION)
    assert "built by" not in p
    assert DIALOGUE_REVIEW_DIRECTIVE.splitlines()[0] in p
