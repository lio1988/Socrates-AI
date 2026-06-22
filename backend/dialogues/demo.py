"""
End-to-End Demo — Socratic Dialogues Orchestration System (V1)

Runs a complete Council session on the deterministic FakeProvider and pretty-prints
the full trajectory: role assignment, every phase, every agent move, the shadow
scorecard (which agents never see), the blindly-assembled answer, and the final
ratification verdict.

Run it with:

    python -m backend.dialogues.demo

Optionally pass your own question:

    python -m backend.dialogues.demo "Is mathematics discovered or invented?"
"""

from __future__ import annotations

import sys
from typing import List

from .models import AgentRole, DialogPhase, SessionState
from .providers import FakeProvider
from .agent import SocraticAgent
from .ced import CEDOrchestrator


# ── Pretty-printing helpers ───────────────────────────────────────────────────

_WIDTH = 78


def _rule(char: str = "─") -> str:
    return char * _WIDTH


def _banner(title: str) -> None:
    print()
    print("╔" + "═" * (_WIDTH - 2) + "╗")
    print("║" + title.center(_WIDTH - 2) + "║")
    print("╚" + "═" * (_WIDTH - 2) + "╝")


def _section(title: str) -> None:
    print()
    print(_rule())
    print(f"  {title}")
    print(_rule())


def _kv(key: str, value: object, indent: int = 2) -> None:
    print(f"{' ' * indent}{key + ':':<22}{value}")


def _wrap(text: str, indent: int = 4) -> str:
    """Soft-wrap a paragraph to the demo width with a hanging indent."""
    words = str(text).split()
    lines: List[str] = []
    current = ""
    limit = _WIDTH - indent
    for word in words:
        if len(current) + len(word) + 1 > limit:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    pad = " " * indent
    return "\n".join(pad + ln for ln in lines)


def _role_label(role: AgentRole) -> str:
    return role.value.upper().replace("_", " ")


# ── Per-phase rendering ───────────────────────────────────────────────────────

# Phases shown with "all agents …" rather than a per-agent list.
_COLLECTIVE_PHASES = {
    DialogPhase.SYNTHESIS.value:  "all agents -> Synthesizer draft generation",
    DialogPhase.REFLECTION.value: "all responders -> Reflector revision",
}


def _print_role_rotation(state: SessionState) -> None:
    """
    Show the actual per-phase role rotation recorded during the run.

    Roles are assigned by the CED per phase (not fixed for the session); the
    same agent does not monopolize high-impact roles when enough agents exist.
    """
    _section("DETERMINISTIC ROLE ROTATION")
    print("  CED assigns roles per phase. Deterministic from session_id + phase")
    print("  + round_index. Agents never choose their own role; providers never")
    print("  influence it.")
    print()

    # Group role_history records by phase, preserving first-seen phase order.
    phase_order: List[str] = []
    by_phase: dict = {}
    for rec in state.role_history:
        ph = rec["phase"]
        if ph not in by_phase:
            by_phase[ph] = []
            phase_order.append(ph)
        by_phase[ph].append(rec)

    for ph in phase_order:
        print(f"  Phase: {ph}")
        collective = _COLLECTIVE_PHASES.get(ph)
        if collective:
            print(f"    {collective}")
        else:
            for rec in by_phase[ph]:
                role = AgentRole(rec["role"])
                print(f"    {rec['agent_id']} -> {_role_label(role)}")
        print()


def _print_phase_moves(state: SessionState, phase: DialogPhase, heading: str) -> None:
    _section(heading)
    moves = state.moves_for_phase(phase)
    if not moves:
        print("  (no moves in this phase)")
        return
    for move in moves:
        print(f"  ▸ {move.agent_id}  [{_role_label(move.role)}]  "
              f"confidence={move.confidence:.2f}")
        if move.epistemic_markers:
            markers = ", ".join(m.value for m in move.epistemic_markers)
            _kv("epistemic markers", markers, indent=6)
        # Render the structured content compactly, one key per line.
        for key, val in move.content.items():
            if isinstance(val, list):
                _kv(key, "", indent=6)
                for item in val:
                    print(_wrap(f"- {item}", indent=10))
            else:
                print(_wrap(f"{key}: {val}", indent=6))
        print()


_DIM_ORDER = [
    "epistemic_value", "logical_rigor", "factual_grounding",
    "constructive_impact", "intellectual_honesty", "clarity_precision",
    "grounded_creativity",
]


def _print_scorecard(state: SessionState) -> None:
    _section("SHADOW SCORECARD — CED-owned, hidden from agents")
    if not state.micro_scores:
        print("  (no scores computed)")
        return
    print("  No agent scores its own output. Scores are on a 0–10 scale and")
    print("  drive blind assembly only. Never shown to any agent.")
    print()

    # Aggregate move-level micro scores per move (one block per synthesis draft).
    moves = state.moves_for_phase(DialogPhase.SYNTHESIS)
    blocks = []
    for move in moves:
        scores = state.micro_scores_for_move(move.move_id)
        if not scores:
            continue
        avg_overall = sum(s.overall_score for s in scores) / len(scores)
        # Average each dimension across voters.
        dim_avg = {
            dim: sum(getattr(s.score_breakdown, dim) for s in scores) / len(scores)
            for dim in _DIM_ORDER
        }
        flags = sorted({f.value for s in scores for f in s.penalty_flags})
        blocks.append((move, avg_overall, dim_avg, flags))

    for move, avg_overall, dim_avg, flags in sorted(
        blocks, key=lambda b: b[1], reverse=True
    ):
        print(f"  ▸ {move.move_id} by {move.agent_id}")
        _kv("overall score", f"{avg_overall:.2f} / 10", indent=6)
        print("      dimensions:")
        for dim in _DIM_ORDER:
            print(f"        {dim}: {dim_avg[dim]:.1f}")
        _kv("penalty_flags", ", ".join(flags) if flags else "none", indent=6)
        print()


def _print_assembly(state: SessionState) -> None:
    _section("BLIND SECTION ASSEMBLY  (mechanical — highest average per section)")
    assembled = state.assembled_answer
    if assembled is None:
        print("  (nothing assembled)")
        return
    _kv("method", assembled.assembly_method)
    print()
    for section in assembled.sections:
        draft = section.selected_draft_id or "—"
        tag = "  [UNRESOLVED]" if section.unresolved else ""
        print(
            f"  {section.section_name.value} -> {draft} "
            f"(by {section.selected_author_agent_id or '—'}), "
            f"avg {section.average_score:.2f} / 10  "
            f"[n={section.score_count}, var={section.variance:.3f}]{tag}"
        )
    print()


def _print_final(state: SessionState) -> None:
    final = state.final_response
    _banner("FINAL RESPONSE")
    if final is None:
        print("  (no final response produced)")
        return

    verdict = "✓ RATIFIED" if final.ratified else "✗ NOT RATIFIED"
    _kv("Question", final.question)
    _kv("Ratified", verdict)
    _kv("Epistemic status", final.epistemic_status.value)
    if final.unresolved_sections:
        _kv("Unresolved sections",
            ", ".join(s.value for s in final.unresolved_sections))
    if final.blocking_objections:
        _kv("Objections", "")
        for obj in final.blocking_objections:
            print(_wrap(f"- {obj}", indent=6))
    print()
    print("  Answer (5-section assembled):")
    if final.answer:
        # Render line-by-line so the "## Section" headers keep their own line.
        for line in final.answer.split("\n"):
            if not line.strip():
                print()
            elif line.startswith("## "):
                print(f"    {line}")
            else:
                print(_wrap(line, indent=6))
    else:
        print("    (withheld — hard-blocked by a critical objection)")

    print()
    print("  Council summary:")
    for key, val in final.council_summary.items():
        if isinstance(val, list):
            _kv(key, ", ".join(str(v) for v in val), indent=4)
        else:
            _kv(key, val, indent=4)


# ── Orchestration ─────────────────────────────────────────────────────────────

def build_demo_orchestrator(num_agents: int = 4) -> CEDOrchestrator:
    """Build a Council of `num_agents` agents, all on the deterministic FakeProvider."""
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(num_agents)]
    return CEDOrchestrator(agents, provider)


def run_demo(question: str, session_id: str = "demo_session") -> SessionState:
    """Run a full session end-to-end and pretty-print every stage."""
    _banner("SOCRATES AI — SOCRATIC COUNCIL DEMO (V1, FakeProvider)")
    print(_wrap(f"Question: {question}", indent=2))

    ced = build_demo_orchestrator(num_agents=4)
    final = ced.run_session(question, session_id=session_id)
    state = ced.get_session(session_id)

    # Per-phase deterministic role rotation (the real executed assignment)
    _print_role_rotation(state)

    # Each phase, in pipeline order
    _print_phase_moves(state, DialogPhase.OPENING,
                       "PHASE 1 — OPENING  (Socrates asks one question)")
    _print_phase_moves(state, DialogPhase.INITIAL_RESPONSE,
                       "PHASE 2 — INITIAL RESPONSE")
    _print_phase_moves(state, DialogPhase.ELENCHUS,
                       "PHASE 3 — ELENCHUS  (critics expose gaps)")
    _print_phase_moves(state, DialogPhase.REFLECTION,
                       "PHASE 4 — REFLECTION  (authors revise their positions)")
    _print_phase_moves(state, DialogPhase.RECONSTRUCTION,
                       "PHASE 5 — RECONSTRUCTION  (Maieutic rebuild)")
    _print_phase_moves(state, DialogPhase.SYNTHESIS,
                       "PHASE 6 — SYNTHESIS  (competing drafts)")

    # Scoring → assembly → ratification
    _print_scorecard(state)
    _print_assembly(state)
    _print_phase_moves(state, DialogPhase.RATIFICATION,
                       "PHASE 7 — RATIFICATION  (Final Evaluator verdict)")
    _print_final(state)

    print()
    print(_rule("═"))
    print(f"  Done. Final ratified = {final.ratified}. "
          f"Total moves = {len(state.moves)}.")
    print(_rule("═"))
    return state


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    question = (
        argv[0] if argv
        else "Is knowledge merely justified true belief?"
    )
    run_demo(question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
