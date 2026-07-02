"""
Phase 15 — The Living System: curiosity, memory consolidation, homeostasis.

What makes a system ALIVE rather than merely reactive:

  1. It knows what it does NOT know, and wants to find out.
     `OpenQuestionLedger` — every gap a dialogue exposes (blind spots, quorum
     failures, uniform uncertainty) becomes an OPEN QUESTION. The ledger is the
     system's self-generated research agenda (`propose_inquiries`), and it
     notices when a later ratified dialogue RESOLVES an open question.

  2. It consolidates memory instead of hoarding it ("sleep").
     `consolidate_lessons` — clusters of related lessons are merged into ONE
     deeper, more general lesson (a council seat authors the generalization when
     ai_learning; deterministic mechanical merge otherwise). The store shrinks
     while the knowledge deepens.

  3. It monitors its own vital signs (homeostasis).
     `compute_vitals` — ratification rate, quorum-failure rate, confidence
     trend, memory growth, seat quarantines → one honest health status
     (thriving | stable | degrading) with mechanical recommendations.

Same discipline as everything else: mechanical triggers, PUBLIC artifacts only,
honest fallbacks, CED governs (never judges content), no live calls here.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .models import FinalResponse, SessionState
from .self_improvement import Lesson, _clip, _keywords

LEDGER_SCHEMA = "open_questions_v0"

# Deterministic priority: a failed dialogue is a louder gap than a blind spot.
_SOURCE_PRIORITY = {"quorum_failure": 0, "uncertainty": 1, "blind_spot": 2, "caveat": 3}


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Curiosity — the OpenQuestionLedger (the system's own research agenda)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OpenQuestion:
    question: str
    source: str                      # quorum_failure | uncertainty | blind_spot | caveat
    born_session: str = ""
    status: str = "open"             # open | resolved
    resolved_by_session: str = ""


class OpenQuestionLedger:
    """CED-owned registry of what the system does not yet know. PUBLIC text only."""

    def __init__(self, questions: Optional[List[OpenQuestion]] = None) -> None:
        self._questions: List[OpenQuestion] = list(questions or [])

    def __len__(self) -> int:
        return len(self._questions)

    # -- accumulation --
    def add(self, question: str, source: str, session_id: str = "") -> bool:
        q = _clip(question, 300)
        if not q.strip():
            return False
        key = _norm(q)
        if any(_norm(existing.question) == key for existing in self._questions):
            return False                          # dedupe — a gap is recorded once
        self._questions.append(OpenQuestion(question=q, source=source,
                                            born_session=session_id))
        return True

    def ingest_session(self, state: SessionState, final: FinalResponse) -> None:
        """Harvest this session's gaps; mark resolved what this session answered."""
        au = final.audit_summary or {}
        adaptive = au.get("adaptive_dialectic", {}) or {}
        if not final.ratified:
            # The question itself remains open — the loudest kind of gap.
            self.add(state.question, "quorum_failure", state.session_id)
            return
        # A ratified answer to a question we had marked open → resolved.
        self._mark_resolved(state.question, state.session_id)
        if adaptive.get("uncertainty_mode_triggered"):
            self.add(state.question, "uncertainty", state.session_id)
        if final.synthesis:
            blind = next((s.content for s in final.synthesis.sections
                          if s.section_name.value == "blind_spots"
                          and not s.unresolved and s.content.strip()), "")
            if blind:
                self.add(f"Blind spot left open by «{_clip(state.question, 80)}»: "
                         f"{_clip(blind, 180)}", "blind_spot", state.session_id)
        cr = au.get("council_ratification", {}) or {}
        for c in cr.get("caveats", []):
            if isinstance(c, dict) and c.get("caveat"):
                self.add(f"Caveat to revisit from «{_clip(state.question, 80)}»: "
                         f"{_clip(str(c['caveat']), 180)}", "caveat", state.session_id)

    def _mark_resolved(self, question: str, session_id: str) -> None:
        key = _norm(question)
        for oq in self._questions:
            if oq.status == "open" and _norm(oq.question) == key:
                oq.status = "resolved"
                oq.resolved_by_session = session_id

    # -- the agenda --
    def open_questions(self) -> List[OpenQuestion]:
        return [q for q in self._questions if q.status == "open"]

    def propose_inquiries(self, k: int = 3) -> List[Dict[str, str]]:
        """The k most pressing open questions (deterministic: source priority,
        then oldest first) — the system's suggestion for what to ask next."""
        ranked = sorted(
            (q for q in self._questions if q.status == "open"),
            key=lambda q: (_SOURCE_PRIORITY.get(q.source, 9),
                           self._questions.index(q)))
        return [{"question": q.question, "source": q.source,
                 "born_session": q.born_session} for q in ranked[:k]]

    def report(self) -> Dict[str, Any]:
        resolved = [q for q in self._questions if q.status == "resolved"]
        return {
            "schema_version": LEDGER_SCHEMA,
            "open": len(self.open_questions()),
            "resolved": len(resolved),
            "questions": [asdict(q) for q in self._questions],
        }

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.report(), ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "OpenQuestionLedger":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != LEDGER_SCHEMA:
            raise ValueError(f"schema_version mismatch: expected {LEDGER_SCHEMA!r}")
        return cls([OpenQuestion(**{k: v for k, v in q.items()})
                    for q in doc.get("questions", [])])


# ══════════════════════════════════════════════════════════════════════════════
# 2. Memory consolidation ("sleep") — clusters of lessons → one deeper lesson
# ══════════════════════════════════════════════════════════════════════════════

MIN_CLUSTER = 3          # consolidate only with enough evidence of a theme
_SHARED_KEYWORDS = 3     # lessons sharing >= this many keywords cluster together


def _lesson_keywords(lesson: Lesson) -> set:
    return _keywords(lesson.question + " " + lesson.core_answer)


def find_clusters(lessons: Sequence[Lesson], min_cluster: int = MIN_CLUSTER) -> List[List[int]]:
    """Greedy deterministic clustering by shared keywords. Returns index groups."""
    seeds: List[Dict[str, Any]] = []
    for i, lesson in enumerate(lessons):
        kw = _lesson_keywords(lesson)
        placed = False
        for seed in seeds:
            if len(kw & seed["kw"]) >= _SHARED_KEYWORDS:
                seed["members"].append(i)
                seed["kw"] |= kw
                placed = True
                break
        if not placed:
            seeds.append({"kw": set(kw), "members": [i]})
    return [s["members"] for s in seeds if len(s["members"]) >= min_cluster]


def _mechanical_merge(members: List[Lesson]) -> Lesson:
    """No-AI merge: the newest lesson survives, tagged with the cluster size.
    Nothing is invented — only provenance is recorded."""
    newest = members[-1]
    return Lesson(
        question=f"[consolidated ×{len(members)}] {newest.question}",
        final_verdict=newest.final_verdict, core_answer=newest.core_answer,
        caveats=newest.caveats, decisive_objections=newest.decisive_objections,
        session_id=newest.session_id, insight=newest.insight,
        transferable_principle=newest.transferable_principle,
        pitfalls=newest.pitfalls, distilled_by="consolidation_mechanical",
    )


async def consolidate_lessons(ced, min_cluster: int = MIN_CLUSTER) -> Dict[str, Any]:
    """
    The sleep cycle. Clusters related lessons; each cluster becomes ONE deeper
    lesson — authored by a council seat when ai_learning (honest mechanical merge
    otherwise / on failure). Returns an honest report; never fabricates.
    """
    from .models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
    store = ced.lesson_store
    if store is None:
        return {"clusters_found": 0, "lessons_before": 0, "lessons_after": 0, "mode": "none"}
    before = store.lessons()
    clusters = find_clusters(before, min_cluster=min_cluster)
    mode = "mechanical"
    merged = 0
    # Replace from the last cluster backwards so earlier indices stay valid.
    for members_idx in sorted(clusters, key=lambda c: -min(c)):
        current = store.lessons()
        members = [current[i] for i in members_idx if i < len(current)]
        if len(members) < min_cluster:
            continue
        consolidated: Optional[Lesson] = None
        if ced.ai_learning and ced.registry is not None:
            adapters = ced.registry.available_adapters()
            if adapters:
                task = AgentTask(
                    session_id="consolidation", agent_id="memory_consolidator",
                    role=AgentRole.SYNTHESIZER, phase=DialogPhase.COMPLETE,
                    question=f"Consolidate {len(members)} related lessons",
                    context={"lessons_to_consolidate": [m.public_dict() for m in members]},
                    output_schema={"_role": "synthesizer"},
                    task_kind=TaskKind.LESSON_CONSOLIDATION,
                )
                astate = AgentState(agent_id="memory_consolidator",
                                    primary_role=AgentRole.SYNTHESIZER,
                                    assigned_role=AgentRole.SYNTHESIZER)
                resp = await ced.registry.run_adapter(adapters[0], task, astate, None)
                if resp.ok:
                    c = resp.parsed_move.content
                    insight = str(c.get("consolidated_insight", "")).strip()
                    if insight:
                        newest = members[-1]
                        pitfalls = c.get("pitfalls", [])
                        consolidated = Lesson(
                            question=f"[consolidated ×{len(members)}] {newest.question}",
                            final_verdict=newest.final_verdict,
                            core_answer=_clip(insight),
                            caveats=newest.caveats,
                            decisive_objections=newest.decisive_objections,
                            session_id=newest.session_id,
                            insight=_clip(insight),
                            transferable_principle=_clip(str(c.get("transferable_principle", ""))),
                            pitfalls=[_clip(str(p)) for p in pitfalls][:3]
                                     if isinstance(pitfalls, list) else [],
                            distilled_by="consolidation_council",
                        )
                        mode = "council"
        if consolidated is None:
            consolidated = _mechanical_merge(members)
        store.replace_many(members_idx, consolidated)
        merged += 1
    return {"clusters_found": len(clusters), "clusters_merged": merged,
            "lessons_before": len(before), "lessons_after": len(store.lessons()),
            "mode": mode if merged else "none"}


# ══════════════════════════════════════════════════════════════════════════════
# 2b. Autonomous inquiry — the system studies its own open questions
# ══════════════════════════════════════════════════════════════════════════════

async def run_inquiry_cycle(ced, max_inquiries: int = 2,
                            session_prefix: str = "inquiry") -> Dict[str, Any]:
    """
    The self-study loop: take the TOP open questions from the system's own
    ledger and run a full council dialogue on each. Resolution marking happens
    automatically inside the session ingest (a ratified answer to an open
    question closes it), new gaps become new open questions, lessons accumulate
    — curiosity feeding inquiry feeding memory.

    Runs on whatever council `ced` wraps (mock by default; live only if the
    caller built a gated live council — each inquiry costs a full session).
    Session ids are made collision-safe with a rolling counter.
    """
    ledger = ced.open_questions
    if ledger is None:
        return {"inquiries_run": 0, "results": [],
                "note": "no OpenQuestionLedger attached"}
    agenda = ledger.propose_inquiries(max_inquiries)
    results: List[Dict[str, Any]] = []
    for item in agenda:
        sid = f"{session_prefix}_{len(ced._session_outcomes)}_{len(results)}"
        final = await ced.run_registry_session(item["question"], session_id=sid)
        results.append({
            "question": item["question"], "source": item["source"],
            "session_id": sid, "ratified": bool(final.ratified),
            "ratification_status": final.ratification_status,
        })
    return {
        "inquiries_run": len(results),
        "results": results,
        "open_questions_after": len(ledger.open_questions()),
        "resolved_total": sum(1 for q in ledger._questions if q.status == "resolved"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. Homeostasis — the system's vital signs
# ══════════════════════════════════════════════════════════════════════════════

THRIVING_RATIFICATION_RATE = 0.8
DEGRADING_QUORUM_RATE = 0.3


def compute_vitals(session_outcomes: Sequence[Dict[str, Any]],
                   seat_health=None, lesson_store=None, ledger=None) -> Dict[str, Any]:
    """One honest snapshot of how alive the system is. Purely mechanical."""
    n = len(session_outcomes)
    ratified = sum(1 for o in session_outcomes if o.get("ratified"))
    quorum_failed = sum(1 for o in session_outcomes if o.get("quorum_failed"))
    confidences = [o["initial_mean_confidence"] for o in session_outcomes
                   if isinstance(o.get("initial_mean_confidence"), (int, float))]
    quarantined = list(seat_health.quarantined()) if seat_health is not None else []

    ratification_rate = round(ratified / n, 4) if n else None
    quorum_rate = round(quorum_failed / n, 4) if n else None
    status = "unknown"
    recommendations: List[str] = []
    if n:
        if quarantined or (quorum_rate is not None and quorum_rate >= DEGRADING_QUORUM_RATE):
            status = "degrading"
            if quarantined:
                recommendations.append(f"replace quarantined seats: {quarantined}")
            if quorum_rate and quorum_rate >= DEGRADING_QUORUM_RATE:
                recommendations.append("quorum failures are frequent — check seat availability/timeouts")
        elif ratification_rate is not None and ratification_rate >= THRIVING_RATIFICATION_RATE:
            status = "thriving"
        else:
            status = "stable"
    open_qs = len(ledger.open_questions()) if ledger is not None else None
    if open_qs:
        recommendations.append(f"{open_qs} open questions await inquiry — run propose_inquiries()")
    return {
        "sessions_observed": n,
        "ratification_rate": ratification_rate,
        "quorum_failure_rate": quorum_rate,
        "mean_initial_confidence": round(sum(confidences) / len(confidences), 4)
                                   if confidences else None,
        "lessons_total": len(lesson_store.lessons()) if lesson_store is not None else None,
        "open_questions": open_qs,
        "quarantined_seats": quarantined,
        "health_status": status,
        "recommendations": recommendations,
    }
