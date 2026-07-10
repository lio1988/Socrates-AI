"""
OpenClaw Shadow Apprentice Mode — Stage 1 runtime (Goal 11).

The council completes and fixes its final answer before the apprentice runs.
The apprentice then receives the same question and, when available, the exact
SYNTHESIS lesson IDs recorded by the council's injected-context ledger.
Apprentice and council-winning sections are re-scored as matched pairs by the
same eligible judges.

Evidence-honesty guarantees:
  - shadow output never mutates council SessionState
  - the apprentice cannot sit in the council or judge itself
  - the provider that authored a winning council section cannot judge that pair
  - incomplete score pairs are excluded, never fabricated
  - ties earn no win
  - ledger lesson IDs must all exist in the apprentice pool; mismatch fails closed
  - a run with no eligible matched comparison is not recorded as successful

No keys and no network beyond the adapters explicitly supplied by the caller.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

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
_SHADOW_LABEL = "shadow_draft_a"
_SECTION_FIELDS = tuple(section.value for section in SECTION_ORDER)


def _parse_overall(content: Dict[str, Any]) -> Optional[float]:
    """Return a real weighted score; malformed payloads remain missing."""
    breakdown = content.get("score_breakdown")
    dimensions = tuple(ScoreBreakdown.model_fields.keys())
    try:
        parsed = ScoreBreakdown(**{
            dimension: float(breakdown[dimension])
            for dimension in dimensions
        })
    except (TypeError, ValueError, KeyError):
        return None
    return parsed.weighted_overall()


def _synthesis_lesson_ids(final) -> Optional[List[str]]:
    """Return the unique SYNTHESIS lesson IDs from the real injection ledger.

    ``None`` means no OpenClaw audit exists, so a legacy question-only fallback
    may be used. ``[]`` means the ledger exists and proves no synthesis lesson
    entered the council.
    """
    audit = (getattr(final, "audit_summary", None) or {}).get(
        "openclaw_lessons")
    if audit is None:
        return None

    selected: List[str] = []
    for injection in audit.get("injections", []) or []:
        if str(injection.get("phase", "")) != DialogPhase.SYNTHESIS.value:
            continue
        for lesson_id in injection.get("lesson_ids", []) or []:
            normalized = str(lesson_id)
            if normalized and normalized not in selected:
                selected.append(normalized)
    return selected


class ShadowApprentice:
    """Observe, predict, and get judged after the council — affect nothing."""

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
        judge_ids = {judge.provider_id for judge in judges}
        if apprentice.provider_id in judge_ids:
            raise ValueError("the apprentice can never judge itself")

        self.apprentice = apprentice
        self.judges = sorted(judges, key=lambda judge: judge.provider_id)
        self.lessons = list(lessons) if lessons else []
        self.timeout_seconds = float(timeout_seconds)
        self.registry = CouncilProviderRegistry(
            provider_timeout_seconds=self.timeout_seconds)
        self.registry.register(apprentice)
        for judge in self.judges:
            self.registry.register(judge)
        self.shadow_records: List[Dict[str, Any]] = []

    def _resolve_lessons(
        self,
        question: str,
        council_lesson_ids: Optional[Sequence[str]],
    ) -> Tuple[List[Any], str, List[str]]:
        """Return ``(selected, source, missing_ids)``.

        A real council ledger is authoritative. Every ledger ID must be present
        in the pool supplied to the apprentice; silently dropping one would make
        the claim "same lessons" false. Only when no audit exists do we retain
        the legacy question-only retrieval path.
        """
        if council_lesson_ids is not None:
            by_id = {
                str(lesson.lesson_id): lesson
                for lesson in self.lessons
            }
            missing = [
                str(lesson_id)
                for lesson_id in council_lesson_ids
                if str(lesson_id) not in by_id
            ]
            selected = [
                by_id[str(lesson_id)]
                for lesson_id in council_lesson_ids
                if str(lesson_id) in by_id
            ]
            return selected, "council_injection_ledger", missing

        if not self.lessons:
            return [], "no_council_audit", []

        from backend.dialogues.openclaw_memory import retrieve_lessons

        retrieved = retrieve_lessons(self.lessons, task_text=question)
        return (
            [item.lesson for item in retrieved],
            "legacy_question_retrieval",
            [],
        )

    def _context_for_lessons(self, selected: Sequence[Any]) -> Dict[str, Any]:
        if not selected:
            return {}
        from backend.dialogues.openclaw_memory import render_memory_lessons_block
        return {
            "openclaw_memory_lessons": render_memory_lessons_block(selected),
        }

    async def _draft(
        self,
        question: str,
        session_id: str,
        *,
        selected_lessons: Sequence[Any],
        lesson_source: str,
    ) -> Optional[Dict[str, Any]]:
        task = AgentTask(
            session_id=session_id,
            agent_id=self.apprentice.provider_id,
            role=AgentRole.SYNTHESIZER,
            phase=DialogPhase.SYNTHESIS,
            question=question,
            context=self._context_for_lessons(selected_lessons),
            output_schema={
                "_role": AgentRole.SYNTHESIZER.value,
                "_question": question,
                "_sections": True,
            },
            task_kind=TaskKind.SYNTHESIS_DRAFT,
            slot_index=0,
        )
        agent_state = AgentState(
            agent_id=self.apprentice.provider_id,
            primary_role=AgentRole.SYNTHESIZER,
            assigned_role=AgentRole.SYNTHESIZER,
        )
        response = await self.registry.run_adapter(
            self.apprentice,
            task,
            agent_state,
            self.timeout_seconds,
        )
        if not response.ok or response.parsed_move is None:
            return None
        content = response.parsed_move.content
        if not isinstance(content, dict):
            return None

        sections = {
            field: str(content.get(field, ""))
            for field in _SECTION_FIELDS
        }
        if not any(text.strip() for text in sections.values()):
            return None

        lesson_ids = [str(lesson.lesson_id) for lesson in selected_lessons]
        return {
            "sections": sections,
            "confidence": float(response.parsed_move.confidence or 0.0),
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
        task = AgentTask(
            session_id=session_id,
            agent_id=judge.provider_id,
            role=AgentRole.FINAL_EVALUATOR,
            phase=DialogPhase.SYNTHESIS,
            question=question,
            context={"output_to_score": content, "section": section_name},
            output_schema={
                "_role": "__section_score__",
                "_target": _SHADOW_LABEL,
                "_section": section_name,
                "_question": question,
            },
            task_kind=TaskKind.SECTION_SCORE,
            slot_index=slot_index,
        )
        agent_state = AgentState(
            agent_id=judge.provider_id,
            primary_role=AgentRole.FINAL_EVALUATOR,
            assigned_role=AgentRole.FINAL_EVALUATOR,
        )
        response = await self.registry.run_adapter(
            judge,
            task,
            agent_state,
            self.timeout_seconds,
        )
        if not response.ok or response.parsed_move is None:
            return None
        payload = response.parsed_move.content
        return _parse_overall(payload) if isinstance(payload, dict) else None

    async def _judge_matched_pairs(
        self,
        question: str,
        apprentice_sections: Dict[str, str],
        state,
        session_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        assembled = state.assembled_answer
        if assembled is None:
            return {}

        provider_by_draft = {
            draft.draft_id: draft.provider_id
            for draft in state.section_drafts
        }
        outcomes: Dict[str, Dict[str, Any]] = {}

        for section_index, section in enumerate(assembled.sections):
            if section.unresolved or not section.selected_draft_id:
                continue
            name = section.section_name.value
            apprentice_text = apprentice_sections.get(name, "")
            council_text = str(section.content or "")
            if not apprentice_text.strip() or not council_text.strip():
                continue

            apprentice_scores: List[float] = []
            council_scores: List[float] = []
            winning_provider = provider_by_draft.get(section.selected_draft_id)

            for judge_index, judge in enumerate(self.judges):
                if judge.provider_id == winning_provider:
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
                if (
                    pair.get("apprentice") is None
                    or pair.get("council") is None
                ):
                    continue
                apprentice_scores.append(float(pair["apprentice"]))
                council_scores.append(float(pair["council"]))

            if apprentice_scores:
                outcomes[name] = {
                    "apprentice_score": (
                        sum(apprentice_scores) / len(apprentice_scores)),
                    "council_score": sum(council_scores) / len(council_scores),
                    "matched_judges": len(apprentice_scores),
                    "original_council_score": float(section.average_score),
                }
        return outcomes

    @staticmethod
    def _failure_record(
        base: Dict[str, Any],
        *,
        reason: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        record = dict(base)
        record.update({
            "ok": False,
            "reason": reason,
            "moves": [],
            "assembly": None,
            "shadow_comparison": [],
            "shadow_wins": 0,
        })
        record.update(extra)
        return record

    async def shadow_session(
        self,
        ced,
        question: str,
        *,
        session_id: str,
        timeout_seconds: Optional[float] = None,
    ):
        """Run the fixed council first, then produce one auditable shadow record."""
        council_ids = {
            adapter.provider_id
            for adapter in ced.registry.all_adapters()
        }
        if self.apprentice.provider_id in council_ids:
            raise ValueError(
                "the apprentice sits in the council it is supposed to shadow — "
                "that is participation, not shadowing")

        final = await ced.run_registry_session(
            question,
            session_id=session_id,
            timeout_seconds=timeout_seconds,
        )
        state = ced.get_session(session_id)
        council_lesson_ids = _synthesis_lesson_ids(final)

        base_record: Dict[str, Any] = {
            "trace_version": SHADOW_SCHEMA_VERSION,
            "shadow_run": True,
            "session_id": session_id,
            "question": question,
            "apprentice_id": self.apprentice.provider_id,
            "judges": [judge.provider_id for judge in self.judges],
            "ratification": {
                "ratified": bool(final.ratified),
                "ratification_status": final.ratification_status,
            },
            "council_synthesis_lesson_ids": (
                list(council_lesson_ids)
                if council_lesson_ids is not None else None),
        }

        selected, lesson_source, missing = self._resolve_lessons(
            question, council_lesson_ids)
        if missing:
            record = self._failure_record(
                base_record,
                reason="lesson_pool_mismatch",
                lesson_source=lesson_source,
                lesson_ids=[str(lesson.lesson_id) for lesson in selected],
                lessons_selected=len(selected),
                missing_lesson_ids=missing,
            )
            self.shadow_records.append(record)
            return final, record

        draft = await self._draft(
            question,
            session_id,
            selected_lessons=selected,
            lesson_source=lesson_source,
        )
        if draft is None:
            record = self._failure_record(
                base_record,
                reason="apprentice_draft_failed",
                lesson_source=lesson_source,
                lesson_ids=[str(lesson.lesson_id) for lesson in selected],
                lessons_selected=len(selected),
            )
            self.shadow_records.append(record)
            return final, record

        matched = await self._judge_matched_pairs(
            question,
            draft["sections"],
            state,
            session_id,
        )
        if not matched:
            record = self._failure_record(
                base_record,
                reason="no_eligible_matched_comparisons",
                lesson_source=draft["lesson_source"],
                lesson_ids=list(draft["lesson_ids"]),
                lessons_selected=draft["lessons_selected"],
            )
            self.shadow_records.append(record)
            return final, record

        move_id = f"shadow_{session_id}"
        draft_id = f"draft_{move_id}"
        comparison: List[Dict[str, Any]] = []
        assembly_sections: List[Dict[str, Any]] = []

        for section in state.assembled_answer.sections:
            name = section.section_name.value
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
                    draft_id if win else section.selected_draft_id),
            })

        record = dict(base_record)
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
            "shadow_wins": sum(
                1 for row in comparison if row["shadow_win"]),
        })
        self.shadow_records.append(record)
        return final, record
