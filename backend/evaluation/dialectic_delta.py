"""
Research R3a — the Dialectic Delta instrument.

THE question this project must answer is not "is the council accurate?" but
**"does the Socratic dialectic itself make the models better?"** — i.e. does the
final synthesized answer beat the agents' own INITIAL answers on external truth?

This module measures exactly that, per task:

    initial responses (phase INITIAL_RESPONSE)  vs  final synthesis (core_answer)
                    both verified against EXTERNAL gold (no LLM judge)

and reports the error-correction dynamics from RESEARCH.md §8:

    corrected  — initial wrong  → final right   (the dialectic HELPED)
    degraded   — initial right  → final wrong   (herding/HARM — must be visible)
    net_gain   — corrected − degraded

Honesty rules:
  - `initial_correct` uses the ANY-correct convention (if any single agent's
    initial answer was right, the initial state counts as right). This makes the
    delta CONSERVATIVE: a positive net_gain can't be explained by "the council
    just picked the best initial answer" — the dialectic added something beyond it.
    The majority-initial accuracy is also reported for completeness.
  - With mock providers both sides score ~chance; NO capability claim from mock.
    A real result requires a live/recorded council run (gated).

No live calls here — the caller passes whatever council it has (mock by default).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, List, Sequence

from .baseline_harness import EvalTask, extract_final_answer, verify

DISCLAIMER = (
    "Dialectic delta over external-truth tasks. ANY-correct initial convention "
    "(conservative). No capability claim from mock runs; a real result needs a "
    "live or recorded council (gated)."
)


# ── pure core (unit-testable without any council) ─────────────────────────────

def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(content)


@dataclass(frozen=True)
class DialecticOutcome:
    task_id: str
    initial_any_correct: bool      # was ANY initial answer right?
    initial_majority_correct: bool  # was the majority of initial answers right?
    final_correct: bool
    corrected: bool                # wrong (any) → right
    degraded: bool                 # right (any) → wrong


def flip_outcome(initial_texts: Sequence[str], final_text: str, task: EvalTask) -> DialecticOutcome:
    """Pure: verify initial answers and the final answer against external gold."""
    initial_flags = [verify(task, extract_final_answer(t)) for t in initial_texts]
    any_ok = any(initial_flags)
    majority_ok = bool(initial_flags) and sum(initial_flags) * 2 > len(initial_flags)
    final_ok = verify(task, extract_final_answer(final_text))
    return DialecticOutcome(
        task_id=task.task_id,
        initial_any_correct=any_ok,
        initial_majority_correct=majority_ok,
        final_correct=final_ok,
        corrected=(not any_ok) and final_ok,
        degraded=any_ok and (not final_ok),
    )


@dataclass(frozen=True)
class DialecticReport:
    n: int
    initial_any_accuracy: float
    initial_majority_accuracy: float
    final_accuracy: float
    corrected: int                 # dialectic fixed a wrong initial state
    degraded: int                  # dialectic broke a right initial state
    net_gain: int                  # corrected − degraded (the headline number)
    outcomes: List[DialecticOutcome] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def summarize(outcomes: Sequence[DialecticOutcome]) -> DialecticReport:
    n = len(outcomes)
    if not n:
        return DialecticReport(0, 0.0, 0.0, 0.0, 0, 0, 0, [])
    corrected = sum(1 for o in outcomes if o.corrected)
    degraded = sum(1 for o in outcomes if o.degraded)
    return DialecticReport(
        n=n,
        initial_any_accuracy=round(sum(o.initial_any_correct for o in outcomes) / n, 4),
        initial_majority_accuracy=round(sum(o.initial_majority_correct for o in outcomes) / n, 4),
        final_accuracy=round(sum(o.final_correct for o in outcomes) / n, 4),
        corrected=corrected, degraded=degraded, net_gain=corrected - degraded,
        outcomes=list(outcomes),
    )


# ── council extraction + runner ───────────────────────────────────────────────

def extract_initial_texts(state) -> List[str]:
    """The agents' own INITIAL positions, as text (from CED-owned state)."""
    from backend.dialogues.models import DialogPhase
    return [_text_of(m.content) for m in state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)]


def extract_final_text(final) -> str:
    """The council's released answer: prefer core_answer, then final_verdict, then full text."""
    if final.synthesis:
        for name in ("core_answer", "final_verdict"):
            blk = next((s for s in final.synthesis.sections
                        if s.section_name.value == name and not s.unresolved and s.content.strip()),
                       None)
            if blk:
                return blk.content
    return final.answer or ""


def measure_dialectic_delta(ced, tasks: Sequence[EvalTask],
                            session_prefix: str = "delta") -> DialecticReport:
    """Run one full council session per task and measure initial→final flips.
    Uses whatever council `ced` wraps (mock by default; live only if the caller
    built a gated live council themselves)."""
    outcomes: List[DialecticOutcome] = []
    for t in tasks:
        sid = f"{session_prefix}_{t.task_id}"
        final = asyncio.run(ced.run_registry_session(t.question, session_id=sid))
        state = ced.get_session(sid)
        outcomes.append(flip_outcome(extract_initial_texts(state), extract_final_text(final), t))
    return summarize(outcomes)
