"""
Agent alignment — the agents serve the SYSTEM's purpose and philosophy.

(1) TELOS: deliberating agents are told what the system is FOR (the measured
    dialectic delta; honest unresolved > fabricated consensus; mind-changing is
    a contribution). (2) CONTEXT PROTOCOL: every system artifact an agent's
    context may carry is explained with its obligation — including a drift lock:
    any context key the CED injects must be documented or explicitly exempt.
Judging tasks get NEITHER (blind, anonymous evaluation preserved). Offline.
"""

import asyncio

import pytest

from backend.dialogues.models import AgentRole, DialogPhase, ShadowScoringMode, TaskKind
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, TELOS_DIRECTIVE, CONTEXT_PROTOCOL,
    EVALUATION_DIRECTIVE, ROLE_REASONING,
)
from backend.dialogues.self_improvement import EpistemicLessonStore, ProcessLesson
from backend.dialogues.living_system import OpenQuestionLedger
from backend.dialogues.live_providers import build_council

DELIBERATION_KINDS = (
    TaskKind.SOCRATIC_QUESTION, TaskKind.INITIAL_RESPONSE, TaskKind.ELENCHUS_OBJECTION,
    TaskKind.REFLECTION_REVISION, TaskKind.RECONSTRUCTION_PROPOSAL, TaskKind.SYNTHESIS_DRAFT,
)
JUDGING_KINDS = (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE, TaskKind.COUNCIL_RATIFICATION)

# Phase-specific keys that are self-explanatory move material (not system
# artifacts) and therefore exempt from the CONTEXT_PROTOCOL documentation lock.
EXEMPT_KEYS = {"original_question", "initial_responses", "my_initial_response",
               "reflected_positions", "reconstructed_positions"}


# ── telos + protocol reach deliberating agents only ──────────────────────────

def test_telos_and_protocol_for_deliberation():
    for kind in DELIBERATION_KINDS:
        p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                          kind, model="claude-opus-4-8")
        assert TELOS_DIRECTIVE.splitlines()[0] in p, kind
        assert CONTEXT_PROTOCOL.splitlines()[0] in p, kind


def test_judging_gets_neither_but_keeps_blind_evaluation():
    for kind in JUDGING_KINDS:
        p = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION,
                                          kind, model="claude-opus-4-8")
        assert TELOS_DIRECTIVE.splitlines()[0] not in p, kind
        assert CONTEXT_PROTOCOL.splitlines()[0] not in p, kind
        assert EVALUATION_DIRECTIVE.splitlines()[0] in p, kind


# ── the telos carries the philosophy ──────────────────────────────────────────

def test_telos_aligns_agents_to_the_measured_delta():
    assert "beats the best initial answer" in TELOS_DIRECTIVE
    assert "changing your mind" in TELOS_DIRECTIVE.lower() or \
           "Changing your mind" in TELOS_DIRECTIVE
    assert "fabricated consensus" in TELOS_DIRECTIVE
    assert "Serve the dialogue, not your position." in TELOS_DIRECTIVE


def test_roles_carry_telos_aligned_clauses():
    assert "beat the best initial response" in ROLE_REASONING[AgentRole.SYNTHESIZER]
    assert "not to win" in ROLE_REASONING[AgentRole.ELENCHUS_CRITIC]
    assert "diplomatic average" in ROLE_REASONING[AgentRole.MAIEUTIC_RECONSTRUCTOR]
    assert "improves" in ROLE_REASONING[AgentRole.REFLECTOR]
    assert "prior lessons" in ROLE_REASONING[AgentRole.SOCRATES]
    assert "open questions" in ROLE_REASONING[AgentRole.EMPIRICIST]
    assert "Blocking a bad answer" in ROLE_REASONING[AgentRole.FINAL_EVALUATOR]


# ── drift lock: every injected artifact key is documented ────────────────────

def test_every_injected_context_key_is_documented_or_exempt():
    store, ledger = EpistemicLessonStore(), OpenQuestionLedger()
    store.add_process(ProcessLesson(what_worked="w", what_failed="f",
                                    advice_for_next_dialogue="a"))
    ced, _ = build_council(env={}, council_size=2, lesson_store=store,
                           open_questions=ledger,
                           shadow_scoring_mode=ShadowScoringMode.OFF)
    asyncio.run(ced.run_registry_session(
        "Is knowledge merely justified true belief?", session_id="lock1"))
    asyncio.run(ced.run_registry_session(
        "Is justified true belief enough for knowledge?", session_id="lock2"))
    st = ced.get_session("lock2")
    seen = set()
    for phase in (DialogPhase.OPENING, DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS,
                  DialogPhase.REFLECTION, DialogPhase.RECONSTRUCTION, DialogPhase.SYNTHESIS):
        seen |= set(ced._registry_phase_context(st, phase, "agent_0"))
    undocumented = {k for k in seen
                    if k not in EXEMPT_KEYS and f"`{k}`" not in CONTEXT_PROTOCOL}
    assert not undocumented, f"context keys missing from CONTEXT_PROTOCOL: {undocumented}"


def test_protocol_documents_the_mandates_and_memory():
    for key in ("dialogue_so_far", "council_roster", "lessons_from_prior_dialogues",
                "process_lessons_from_past_dialogues", "devils_advocate_mandate",
                "uncertainty_mapping_mandate", "low_diversity_alert",
                "socratic_opening_question", "critiques_raised"):
        assert f"`{key}`" in CONTEXT_PROTOCOL, key
    # obligations, not just names
    assert "BUILD on them" in CONTEXT_PROTOCOL
    assert "never fabricate to satisfy it" in CONTEXT_PROTOCOL


# ── full pipeline still green with the enriched prompts ──────────────────────

def test_full_session_and_output_contract_unchanged():
    ced, _ = build_council(env={}, council_size=2)
    final = asyncio.run(ced.run_registry_session("test q", session_id="align_ok"))
    assert final.ratified is True
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                      TaskKind.SYNTHESIS_DRAFT, model="claude-opus-4-8")
    assert p.rstrip().endswith("and nothing else.")        # output contract stays last
