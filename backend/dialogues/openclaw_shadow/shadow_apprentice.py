"""
OpenClaw Shadow Apprentice Mode — Stage 1 runtime (Goal 11).

The local agent learns beside the council before it influences the council.

The runner executes a normal council session first (CED untouched — the final
answer already exists), then gives the apprentice the same question and, when
available, the exact synthesis lessons recorded by the council's injected-
context ledger. Its draft is judged in a matched pair against the council's
assembled winner using the same judges and rubric.

Non-interference and evidence-honesty guarantees:
  - the apprentice runs only after the council final exists
  - nothing it produces is written into the council SessionState
  - an apprentice sitting in the council is refused
  - the apprentice never judges itself
  - council and apprentice sections are re-scored by the same eligible judges
  - a judge who authored the council-winning section is excluded for that pair
  - incomplete score pairs are missing, never fabricated
  - ties earn no shadow win
  - exact lesson ids used by the apprentice are recorded

No keys, no network beyond the adapters supplied by the caller.
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

# Neutral target label. Both candidates use the same anonymous label and rubric;
# their identity is retained only in CED-owned bookkeeping.
_SHADOW_LABEL = "shadow_draft_a"
_SECTION_FIELDS = [s.value for s in SECTION_ORDER]


def _parse_overall(content: Dict[str, Any]) -> Optional[float]:
    """Weighted overall from a score payload; malformed stays missing."""
    bd = content.get("score_breakdown")
    dims = list(ScoreBreakdown.model_fields.keys())
    try:
        return ScoreBreakdown(**{k: float(bd[k]) for k in dims}).weighted_overall()
    except (TypeError, ValueError, KeyError):
        return None


def _synthesis_lesson_ids(final) -> Optional[List[str]]:
    """Exact lesson ids recorded by the council ledger for SYNTHESIS.

    ``None`` means the council had no OpenClaw audit block at all (legacy or a
    council built without lessons), allowing the backwards-compatible fallback.
    An empty list means the ledger existed and proves no synthesis lesson entered.
    """
    audit = (getattr(final, "audit_summary", None) or {}).get("openclaw_lessons")
    if audit is None:
        return None
    selected: List[str] = []
    seen = set()
    for injection in audit.get("injections", []) or []:
        if str(injection.get("phase", "")) != DialogPhase.SYNTHESIS.value:
            continue
        for lesson_id in injection.get("lesson_ids", []) or []:
            lid = str(lesson_id)
            if lid and lid not in seen:
                seen.add(lid)
                selected.append(lid)
    return selected


class ShadowApprentice:
    """Stage-1 shadow runner: observe, predict, get judged — affect nothing."""

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
        self.registry = CouncilProviderRegistry(
            provider_timeout_seconds=timeout_seconds)
        self.registry.register(apprentice)
        for judge in self.judges:
            self.registry.register(judge)
        self.shadow_records: List[Dict[str, Any]] = []

    def _apprentice_context(
        self,
        question: str,
        council_lesson_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Build apprentice memory context.

        Preferred path: replay the exact synthesis lesson ids from the council's
        injection ledger. Legacy fallback (no audit block) retains question-only
        retrieval for callers that shadow a council built without OpenClaw.
        """
        context: Dict[str, Any] = {}
        if not self.lessons:
            return context

        from backend.dialogues.openclaw_memory import (
            render_memory_lessons_block,
            retrieve_lessons,
        )

        if council_lesson_ids is not None:
            by_id = {str(l.lesson_id): l for l in self.lessons}
            selected = [by_id[lid] for lid in council_lesson_ids if lid in by_id]
            source = "council_injection_ledger"
        else:
            retrieved = retrieve_lessons(self.lessons, task_text=question)
            selected = [r.lesson for r in retrieved]
            source = "legacy_question_retrieval"

        if selected:
            context["openclaw_memory_lessons"] = \
                render_memory_lessons_block(selected)
            context["_shadow_lesson_ids"] = [str(l.lesson_id) for l in selected]
        else:
            context["_shadow_lesson_ids"] = []
        context["_shadow_lesson_source"] = source
        return context

    async def _draft(
        self,
        question: str,
        session_id: str,
        *,
        council_lesson_ids: Optional[Sequence[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        context = self._apprentice_context(
            question, council_lesson_ids=council_lesson_ids)
        lesson_ids = list(context.pop("_shadow_lesson_ids", []))
        lesson_source = str(context.pop("_shadow_lesson_source", "none"))
        task = AgentTask(
            session_id=session_id,
            agent_id=self.apprentice.provider_id,
            role=AgentRole.SYNTHESIZER,
            phase=DialogPhase.SYNTHESIS,
            question=question,
            context=context,
            output_schema={"_role": AgentRole.SYNTHESIZER.value,
                           "_question": question, "_sections": True},
            task_kind=TaskKind.SYNTHESIS_DRAFT,
            slot_index=0,
        )
        astate = AgentState(
            agent_id=self.apprentice.provider_id,
            primary_role=AgentRole.SYNTHESIZER,
            assigned_role=AgentRole.SYNTHESIZER,
        )
        resp = await self.registry.run_adapter(
            self.apprentice, task, astate, self.timeout_seconds)
        if not resp.ok or resp.parsed_move is None:
            return None
        content = resp.parsed_move.content
        if not isinstance(content, dict):
            return None
        sections = {field: str(content.get(field, ""))
                    for field in _SECTION_FIELDS}
        if not any(value.strip() for value in sections.values()):
            return None
        return {
            "sections": sections,
            "confidence": float(resp.parsed_move.confidence or 0.0),
            "lesson_ids": lesson_ids,
            "lessons_selected": len(lesson_ids),
            "lesson_source": lesson_source,
        }

    async def _score_one(
        self,
        judge,
        *,
        question: str,
        section_name: str,
        content: str,
        session_id: str,
        slot_index: int,
    ) -> Optional[float]:
        astate = AgentState(
            agent_id=judge.provider_id,
            primary_role=AgentRole.FINAL_EVALUATOR,
            assigned_role=AgentRole.FINAL_EVALUATOR,
        )
        task = AgentTask(
            session_id=session_id,
            agent_id=judge.provider_id,
            role=AgentRole.FINAL_EVALUATOR,
            phase=DialogPhase.SYNTHESIS,
            question=question,
            context={"output_to_score": content, "section": section_name},
            output_schema={"_role": "__section_score__",
                           "_target": _SHADOW_LABEL,
                           "_section": section_name,
                           "_question": question},
            task_kind=TaskKind.SECTION_SCORE,
            slot_index=slot_index,
        )
        resp = await self.registry.run_adapter(
            judge, task, astate, self.timeout_seconds)
        if not resp.ok or resp.parsed_move is None:
            return None
        payload = resp.parsed_move.content
        return _parse_overall(payload) if isinstance(payload, dict) else None

    async def _judge_matched_pairs(
        self,
        question: str,
        apprentice_sections: Dict[str, str],
        assembled,
        session_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Re-score apprentice and council winner with the same eligible judges.

        Candidate order alternates by judge/section. If either score in a judge's
        pair is missing, that pair contributes nothing. This prevents comparing
        two unrelated score distributions.
        """
        if assembled is None:
            return {}
        outcomes: Dict[str, Dict[str, Any]] = {}
        for section_index, sec in enumerate(assembled.sections):
            if sec.unresolved or not sec.selected_draft_id:
                continue
            name = sec.section_name.value
            apprentice_text = apprentice_sections.get(name, "")
            council_text = str(sec.content or "")
            if not apprentice_text.strip() or not council_text.strip():
                continue

            apprentice_scores: List[float] = []
            council_scores: List[float] = []
            for judge_index, judge in enumerate(self.judges):
                # A provider must not score its own winning council section.
                if judge.provider_id == sec.selected_author_agent_id:
                    continue
                candidates = [
                    ("apprentice", apprentice_text),
                    ("council", council_text),
                ]
                if (judge_index + section_index) % 2:
                    candidates.reverse()

                pair: Dict[str, Optional[float]] = {}
                for position, (candidate, text) in enumerate(candidates):
                    pair[candidate] = await self._score_one(
                        judge,
                        question=question,
                        section_name=name,
                        content=text,
                        session_id=session_id,
                        slot_index=judge_index * 2 + position,
                    )
                if pair.get("apprentice") is None or pair.get("council") is None:
                    continue
                apprentice_scores.append(float(pair["apprentice"]))
                council_scores.append(float(pair["council"]))

            if not apprentice_scores:
                continue
            outcomes[name] = {
                "apprentice_score": sum(apprentice_scores) / len(apprentice_scores),
                "council_score": sum(council_scores) / len(council_scores),
                "matched_judges": len(apprentice_scores),
                "original_council_score": float(sec.average_score),
            }
        return outcomes

    async def shadow_session(
        self,
        ced,
        question: str,
        *,
        session_id: str,
        timeout_seconds: Optional[float] = None,
    ):
        """Run the council normally, then shadow it.

        Returns ``(final, shadow_record)``. The council final is already fixed
        before the apprentice runs and is never mutated by this method.
        """
        council_ids = {a.provider_id for a in ced.registry.all_adapters()}
        if self.apprentice.provider_id in council_ids:
            raise ValueError(
                "the apprentice sits in the council it is supposed to "
                "shadow — that is participation, not shadowing")

        final = await ced.run_registry_session(
            question, session_id=session_id,
            timeout_seconds=timeout_seconds)
        state = ced.get_session(session_id)
        council_lesson_ids = _synthesis_lesson_ids(final)

        record: Dict[str, Any] = {
            "trace_version": SHADOW_SCHEMA_VERSION,
            "shadow_run": True,
            "session_id": session_id,
            "question": question,
            "apprentice_id": self.apprentice.provider_id,
            "judges": [j.provider_id for j in self.judges],
            "ratification": {
                "ratified": bool(final.ratified),
                "ratification_status": final.ratification_status,
            },
        }

        draft = await self._draft(
            question, session_id, council_lesson_ids=council_lesson_ids)
        if draft is None:
            record.update({
                "ok": False,
                "reason": "apprentice_draft_failed",
                "moves": [],
                "assembly": None,
                "shadow_comparison": [],
            })
            self.shadow_records.append(record)
            return final, record

        matched = await self._judge_matched_pairs(
            question, draft["sections"], state.assembled_answer, session_id)
        move_id = f"shadow_{session_id}"
        draft_id = f"draft_{move_id}"
        comparison: List[Dict[str, Any]] = []
        assembly_sections: List[Dict[str, Any]] = []

        assembled = state.assembled_answer
        if assembled is not None:
            for sec in assembled.sections:
                name = sec.section_name.value
                pair = matched.get(name)
                if pair is None:
                    continue
                apprentice_score = float(pair["apprentice_score"])
                council_score = float(pair["council_score"])
                win = apprentice_score > council_score
                comparison.append({
                    "section_name": name,
                    "apprentice_score": round(apprentice_score, 4),
                    "council_score": round(council_score, 4),
                    "original_council_score": round(
                        float(pair["original_council_score"]), 4),
                    "matched_judges": int(pair["matched_judges"]),
                    "shadow_win": win,
                })
                assembly_sections.append({
                    "section_name": name,
                    "source_draft_id": (
                        draft_id if win else sec.selected_draft_id),
                })

        record.update({
            "ok": True,
            "lesson_ids": list(draft["lesson_ids"]),
            "lessons_selected": draft["lessons_selected"],
            "lesson_source": draft["lesson_source"],
            "moves": [{
                "move_id": move_id,
                "phase": "synthesis",
                "role": "synthesizer",
                "confidence": draft["confidence"],
                "provider_id": self.apprentice.provider_id,
            }],
            "assembly": {"sections": assembly_sections},
            "shadow_comparison": comparison,
            "shadow_wins": sum(1 for row in comparison if row["shadow_win"]),
        })
        self.shadow_records.append(record)
        return final, record
