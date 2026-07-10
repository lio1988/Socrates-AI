"""
OpenClaw Shadow Apprentice Mode — Stage 1 runtime (Goal 11).

    The local agent should learn beside the council before it influences
    the council.

The runner executes a NORMAL council session first (CED untouched — the
final answer is already produced and ratified before the apprentice moves),
then gives the apprentice the SAME question plus the same selected memory
lessons, judges its five-section draft blind, and compares it per section
against the council's actual assembled winners.

Every shadow session emits a marked shadow record (``shadow_run=True``, the
Goal 13.2 capture-time marker) shaped like a session trace, so the EXISTING
instruments consume it unchanged:

  - ``evidence_from_shadow_traces`` counts verified shadow wins
    (identity gate v0.3 -> v0.4: useful blind_spots in shadow mode)
  - ``build_identity_profile`` derives the apprentice's role strengths
  - the comparison detail is the raw material for future lesson extraction

Non-interference, mechanically guaranteed (not aspirational):

  - the apprentice runs AFTER the council final exists; nothing it produces
    is written into the council session state
  - an apprentice whose provider id sits in the council it shadows is
    refused outright (it would not be a shadow)
  - the apprentice never judges itself; the judge panel must exclude it
  - a failed apprentice draft is an honest ``ok=False`` record — never a
    fabricated comparison
  - a shadow WIN requires strictly beating the council winner's peer score
    (ties earn nothing: the burden of proof is on the apprentice)

No keys, no network beyond the adapters it is given. Fully offline with
mock adapters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ScoreBreakdown,
    SECTION_ORDER,
    TaskKind,
)
from backend.dialogues.provider_registry import CouncilProviderRegistry

SHADOW_SCHEMA_VERSION = "openclaw_shadow_trace_v0"

#: Neutral label the judges see — never the apprentice's identity.
_SHADOW_LABEL = "shadow_draft_a"

_SECTION_FIELDS = [s.value for s in SECTION_ORDER]


def _parse_overall(content: Dict[str, Any]) -> Optional[float]:
    """Weighted overall from a score payload; None when malformed (a missing
    score stays missing — never fabricated as zero)."""
    bd = content.get("score_breakdown")
    dims = list(ScoreBreakdown.model_fields.keys())
    try:
        return ScoreBreakdown(**{k: float(bd[k]) for k in dims}).weighted_overall()
    except (TypeError, ValueError, KeyError):
        return None


class ShadowApprentice:
    """Stage 1 shadow runner: observe, predict, get judged — affect nothing."""

    def __init__(
        self,
        apprentice,
        judges: Sequence[Any],
        *,
        lessons: Optional[Sequence[Any]] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not judges:
            raise ValueError("the shadow apprentice needs at least one judge")
        judge_ids = {j.provider_id for j in judges}
        if apprentice.provider_id in judge_ids:
            raise ValueError("the apprentice can never judge itself")
        self.apprentice = apprentice
        self.judges = sorted(judges, key=lambda j: j.provider_id)
        self.lessons = list(lessons) if lessons else None
        self.timeout_seconds = timeout_seconds
        # Own executor — completely separate from any council registry.
        self.registry = CouncilProviderRegistry(
            provider_timeout_seconds=timeout_seconds)
        self.registry.register(apprentice)
        for judge in self.judges:
            self.registry.register(judge)
        self.shadow_records: List[Dict[str, Any]] = []

    # ── The apprentice drafts (same task, same selected lessons) ─────────────

    def _apprentice_context(self, question: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        if self.lessons:
            from backend.dialogues.openclaw_memory import (
                render_memory_lessons_block,
                retrieve_lessons,
            )
            retrieved = retrieve_lessons(self.lessons, task_text=question)
            if retrieved:
                # The SAME context key the CED wiring uses for real seats.
                context["openclaw_memory_lessons"] = \
                    render_memory_lessons_block(retrieved)
                context["_shadow_lessons_selected"] = len(retrieved)
        return context

    async def _draft(self, question: str,
                     session_id: str) -> Optional[Dict[str, Any]]:
        context = self._apprentice_context(question)
        lessons_selected = int(context.pop("_shadow_lessons_selected", 0))
        task = AgentTask(
            session_id=session_id, agent_id=self.apprentice.provider_id,
            role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
            question=question, context=context,
            output_schema={"_role": AgentRole.SYNTHESIZER.value,
                           "_question": question, "_sections": True},
            task_kind=TaskKind.SYNTHESIS_DRAFT, slot_index=0,
        )
        astate = AgentState(agent_id=self.apprentice.provider_id,
                            primary_role=AgentRole.SYNTHESIZER,
                            assigned_role=AgentRole.SYNTHESIZER)
        resp = await self.registry.run_adapter(
            self.apprentice, task, astate, self.timeout_seconds)
        if not resp.ok or resp.parsed_move is None:
            return None
        c = resp.parsed_move.content
        if not isinstance(c, dict):
            return None
        sections = {f: str(c.get(f, "")) for f in _SECTION_FIELDS}
        if not any(v.strip() for v in sections.values()):
            return None
        return {"sections": sections,
                "confidence": float(resp.parsed_move.confidence or 0.0),
                "lessons_selected": lessons_selected}

    # ── The judges score (blind: section text + neutral label only) ──────────

    async def _judge_section_scores(
        self, question: str, sections: Dict[str, str], session_id: str,
    ) -> Dict[str, float]:
        scores: Dict[str, List[float]] = {}
        for jslot, judge in enumerate(self.judges):
            astate = AgentState(agent_id=judge.provider_id,
                                primary_role=AgentRole.FINAL_EVALUATOR,
                                assigned_role=AgentRole.FINAL_EVALUATOR)
            for section in SECTION_ORDER:
                content = sections.get(section.value, "")
                if not content.strip():
                    continue
                task = AgentTask(
                    session_id=session_id, agent_id=judge.provider_id,
                    role=AgentRole.FINAL_EVALUATOR,
                    phase=DialogPhase.SYNTHESIS, question=question,
                    context={"output_to_score": content,
                             "section": section.value},
                    output_schema={"_role": "__section_score__",
                                   "_target": _SHADOW_LABEL,
                                   "_section": section.value,
                                   "_question": question},
                    task_kind=TaskKind.SECTION_SCORE, slot_index=jslot,
                )
                resp = await self.registry.run_adapter(
                    judge, task, astate, self.timeout_seconds)
                if not resp.ok or resp.parsed_move is None:
                    continue
                c = resp.parsed_move.content
                overall = _parse_overall(c) if isinstance(c, dict) else None
                if overall is not None:
                    scores.setdefault(section.value, []).append(float(overall))
        return {name: sum(vals) / len(vals) for name, vals in scores.items()}

    # ── One shadow session ────────────────────────────────────────────────────

    async def shadow_session(
        self, ced, question: str, *, session_id: str,
        timeout_seconds: Optional[float] = None,
    ):
        """Run the council normally, then shadow it. Returns
        ``(final, shadow_record)`` — the council final is EXACTLY what the
        council alone would have produced."""
        council_ids = {a.provider_id for a in ced.registry.all_adapters()}
        if self.apprentice.provider_id in council_ids:
            raise ValueError(
                "the apprentice sits in the council it is supposed to "
                "shadow — that is participation, not shadowing")

        # 1. The council runs normally. The final answer exists BEFORE the
        #    apprentice moves; nothing below writes into this session.
        final = await ced.run_registry_session(
            question, session_id=session_id,
            timeout_seconds=timeout_seconds)
        state = ced.get_session(session_id)

        record: Dict[str, Any] = {
            "trace_version": SHADOW_SCHEMA_VERSION,
            "shadow_run": True,                      # Goal 13.2 marker
            "session_id": session_id,
            "question": question,
            "apprentice_id": self.apprentice.provider_id,
            "judges": [j.provider_id for j in self.judges],
            "ratification": {"ratified": bool(final.ratified),
                             "ratification_status": final.ratification_status},
        }

        # 2. The apprentice drafts the same task (+ same selected lessons).
        draft = await self._draft(question, session_id)
        if draft is None:
            record.update({"ok": False, "reason": "apprentice_draft_failed",
                           "moves": [], "assembly": None,
                           "shadow_comparison": []})
            self.shadow_records.append(record)
            return final, record

        # 3. Blind judging, then per-section comparison against the
        #    council's ACTUAL assembled winners.
        apprentice_scores = await self._judge_section_scores(
            question, draft["sections"], session_id)
        move_id = f"shadow_{session_id}"
        draft_id = f"draft_{move_id}"
        assembled = state.assembled_answer
        comparison: List[Dict[str, Any]] = []
        assembly_sections: List[Dict[str, Any]] = []
        if assembled is not None:
            for sec in assembled.sections:
                if sec.unresolved or not sec.selected_draft_id:
                    continue                        # no contest — honest skip
                name = sec.section_name.value
                a_score = apprentice_scores.get(name)
                council_score = float(sec.average_score)
                win = a_score is not None and a_score > council_score
                comparison.append({
                    "section_name": name,
                    "apprentice_score": (round(a_score, 4)
                                         if a_score is not None else None),
                    "council_score": round(council_score, 4),
                    "shadow_win": win,
                })
                assembly_sections.append({
                    "section_name": name,
                    "source_draft_id": (draft_id if win
                                        else sec.selected_draft_id),
                })

        record.update({
            "ok": True,
            "lessons_selected": draft["lessons_selected"],
            "moves": [{
                "move_id": move_id, "phase": "synthesis",
                "role": "synthesizer",
                "confidence": draft["confidence"],
                "provider_id": self.apprentice.provider_id,
            }],
            "assembly": {"sections": assembly_sections},
            "shadow_comparison": comparison,
            "shadow_wins": sum(1 for c in comparison if c["shadow_win"]),
        })
        self.shadow_records.append(record)
        return final, record
