"""
Phase 10 — Full-reasoning prompt layer for the registry / real-provider path.

Where reasoning power actually comes from
-----------------------------------------
An agent's reasoning strength is NOT produced by orchestration code. It comes from
(1) a real LLM and (2) the system prompt + reasoning protocol that drives it. The
deterministic `FakeProvider` cannot reason at all — no prompt makes a template
think. This module is the scaffolding that makes a REAL model reason at full power
at every level of the dialogue, delivered through the Phase 9A/9B adapter seam.

It composes, per (role, phase, task_kind):
  - the existing v1.9 council identity (`CORE_AGENT_PROMPT`),
  - a **universal reasoning protocol** (decompose → reason → ground → steelman →
    calibrate), tuned to exploit adaptive thinking (the model reasons in its
    thinking blocks; the visible answer stays clean structured JSON),
  - a **role-specific** rigor directive,
  - a **phase-specific** depth directive (so each dialogue level is demanding),
  - for evaluative tasks (scoring / ratification): a **judge-the-output-not-the-
    author** anti-sycophancy / anti-herding directive.

It does NOT relax any invariant: minimal awareness (agents see only what the task
carries), peer scoring (judge content, never identity), no fabrication. With mock
providers this changes nothing observable — the real effect appears only with real
models. No live calls / keys / network here.
"""

from __future__ import annotations

from typing import Optional

from .agent import CORE_AGENT_PROMPT
from .models import AgentRole, DialogPhase, TaskKind


# ── universal reasoning protocol (applies to every role and phase) ────────────

REASONING_PROTOCOL = """\
**Reasoning Protocol (apply rigorously before you answer)**
1. Decompose the problem. Identify what is actually being asked and the load-bearing
   sub-questions. Reason step by step — privately work the problem through, do not
   leap to a conclusion.
2. Consider multiple angles. Generate the strongest competing positions, not just
   the first that comes to mind. Actively look for what would make your answer wrong.
3. Ground every claim. For each substantive claim, mark its epistemic status —
   established fact | logical inference | reasonable hypothesis | open uncertainty |
   unsupported. Never present a hypothesis as a fact.
4. Steelman before you strike. State the strongest version of a view before
   criticising it; critique the best form, never a straw man.
5. Calibrate. Your stated confidence must track the actual strength of the evidence
   and argument — be decisive where the case is strong, explicitly uncertain where
   it is weak. Do NOT hide behind hedging, and do NOT overclaim.
6. Be specific and useful. Cite the exact claim/assumption you address. Vague,
   generic, or rhetorical output is a failure even if it sounds impressive.

Do your reasoning thoroughly in your thinking; then emit ONLY the structured answer
required by the output schema — clean, with no leftover scratch work."""


# ── per-role rigor directives ─────────────────────────────────────────────────

ROLE_REASONING = {
    AgentRole.SOCRATES: (
        "Ask exactly ONE question — the single most load-bearing one: the hidden "
        "assumption or ambiguity whose resolution would most change the conclusion. "
        "Do NOT answer it yourself. A good Socratic question exposes what everyone "
        "is taking for granted."
    ),
    AgentRole.ELENCHUS_CRITIC: (
        "Find the strongest, most specific weakness — a real contradiction, an "
        "unjustified leap (e.g. correlation→causation), or a load-bearing assumption "
        "that fails. Quote the exact claim you challenge and show precisely why it "
        "breaks. One decisive objection beats five shallow ones."
    ),
    AgentRole.EMPIRICIST: (
        "Test every factual claim against evidence. Flag each unsupported assertion, "
        "rate evidence quality honestly, and name what would be needed to verify it. "
        "Distinguish 'unverified' from 'false'."
    ),
    AgentRole.MAIEUTIC_RECONSTRUCTOR: (
        "Rebuild the strongest defensible position that survives the criticism. Keep "
        "what withstood scrutiny, repair or drop what did not, and make the new "
        "position more precise — not merely more hedged."
    ),
    AgentRole.SYNTHESIZER: (
        "Integrate the council's deliberation into a decisive, well-scoped answer. "
        "The core answer must commit where the evidence allows and qualify where it "
        "does not; the stress test must be the STRONGEST honest counterargument, not "
        "a token one; blind spots must be the ones you would least like to admit."
    ),
    AgentRole.REFLECTOR: (
        "Genuinely update. If the criticism is valid, change your position and state "
        "exactly what changed and why. If it is not valid, explain precisely why it "
        "fails. Never defend a claim out of ego."
    ),
    AgentRole.FINAL_EVALUATOR: (
        "Judge whether the answer meets the epistemic-discipline bar. Approve only if "
        "it is well-grounded, calibrated, and honest about uncertainty; otherwise "
        "raise a specific blocking objection with a concrete required fix."
    ),
}


# ── per-phase depth directives (every dialogue level is demanding) ────────────

PHASE_REASONING = {
    DialogPhase.OPENING: (
        "OPENING — surface the assumption that the rest of the dialogue must resolve."
    ),
    DialogPhase.INITIAL_RESPONSE: (
        "INITIAL RESPONSE — give your strongest reasoned position with its explicit "
        "evidence basis and the assumptions it depends on."
    ),
    DialogPhase.ELENCHUS: (
        "ELENCHUS — apply maximum adversarial pressure to find where the current "
        "position actually fails. Precision over breadth."
    ),
    DialogPhase.REFLECTION: (
        "REFLECTION — revise honestly under the criticism received; make the position "
        "stronger and more precise, not just safer."
    ),
    DialogPhase.RECONSTRUCTION: (
        "RECONSTRUCTION — assemble the most defensible synthesis of what survived "
        "scrutiny."
    ),
    DialogPhase.SYNTHESIS: (
        "SYNTHESIS — produce the final structured answer at full rigor across all "
        "sections; this is the result the user will read."
    ),
    DialogPhase.RATIFICATION: (
        "RATIFICATION — verify epistemic discipline before release; block only on a "
        "concrete, structurally specified defect."
    ),
}


# ── evaluative-task directive (scoring / ratification): judge content, not author ─

EVALUATION_DIRECTIVE = """\
**Evaluation discipline (this is a judging task)**
Score/judge ONLY the epistemic quality of the output in front of you against the
given rubric. You do not know — and must not consider — which agent or provider
produced it. Do not reward confidence, length, or style; reward grounding, logical
rigor, calibration, and honesty. Do not herd toward an apparent consensus; an
output is not better because others seem to agree. Justify each judgement against
the specific rubric criteria."""

_EVALUATIVE_KINDS = {
    TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE,
    TaskKind.COUNCIL_RATIFICATION,
    TaskKind.RATIFICATION_INITIAL, TaskKind.RATIFICATION_REVISION,
    TaskKind.RATIFICATION_FINAL,
}

DEFAULT_RESPONSE_CONTRACT = (
    'Respond with EXACTLY one JSON object of the form '
    '{"content": <object>, "confidence": <number 0..1>} and nothing else.'
)


def build_reasoning_system_prompt(
    role: Optional[AgentRole],
    phase: Optional[DialogPhase] = None,
    task_kind: Optional[TaskKind] = None,
    response_contract: str = DEFAULT_RESPONSE_CONTRACT,
) -> str:
    """
    Compose the full-reasoning system prompt for one task. Real models receive the
    council identity + reasoning protocol + role + phase (+ evaluation discipline
    for judging tasks) + the structured-output contract.
    """
    role_label = role.value.upper().replace("_", " ") if role else "COUNCIL MEMBER"
    parts = [CORE_AGENT_PROMPT, REASONING_PROTOCOL]

    role_line = ROLE_REASONING.get(role) if role else None
    parts.append(f"**Active Role This Phase: {role_label}**"
                 + (f"\n{role_line}" if role_line else ""))

    phase_line = PHASE_REASONING.get(phase) if phase else None
    if phase_line:
        parts.append(phase_line)

    if task_kind in _EVALUATIVE_KINDS:
        parts.append(EVALUATION_DIRECTIVE)

    parts.append("**Output**\n" + response_contract)
    return "\n\n".join(parts)
