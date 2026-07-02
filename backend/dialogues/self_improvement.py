"""
Phase 13 — Self-Improvement Layer (the system gets better the more it is used).

Three mechanical, invariant-safe subsystems. CED GOVERNS here — it never judges
content. Every adaptation below is either (a) mechanical aggregation of its own
operational telemetry, (b) reuse of already-PUBLIC epistemic artifacts, or
(c) a recommendation surfaced to the operator — never a silent semantic choice.

A. SeatHealthTracker — operational self-improvement.
   Learns, from the CED-owned task_log, how reliable each provider seat actually
   is (schema failures, timeouts, rate limits, repairs). Mechanically ranks
   seats, quarantines chronically failing ones (with an honest audit trail), and
   emits config recommendations (e.g. "raise timeout") derived from observed
   failure modes. It never looks at content or scores — protocol only.

B. EpistemicLessonStore — knowledge self-improvement.
   After a RATIFIED session, distills the PUBLIC outcome (final verdict, caveats,
   decisive objections, key claims — the same material the Phase 8D chat brief
   already exposes) into a Lesson. Future dialogues on related questions receive
   the top-k relevant lessons as `lessons_from_prior_dialogues` in deliberation
   context, so the council builds on its own past work instead of restarting.
   Lessons carry NO scores, NO provider identities, NO hidden internals.

C. (See backend/evaluation/protocol_evolution.py) — protocol self-improvement:
   variants are promoted ONLY when they beat the incumbent on EXTERNAL metrics.

Persistence is plain local JSON (schema-versioned); everything is deterministic
and offline. No live calls, no keys, no `.env`.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .models import FinalResponse, ProviderStatus, SessionState

HEALTH_SCHEMA = "seat_health_v0"
LESSON_SCHEMA = "epistemic_lessons_v0"


# ══════════════════════════════════════════════════════════════════════════════
# A. SeatHealthTracker — operational self-improvement (mechanical, content-blind)
# ══════════════════════════════════════════════════════════════════════════════

_FAILURE_STATUSES = {
    ProviderStatus.ERROR, ProviderStatus.TIMEOUT, ProviderStatus.RATE_LIMITED,
    ProviderStatus.INVALID_JSON, ProviderStatus.SCHEMA_ERROR, ProviderStatus.MISSING_KEY,
}

# Quarantine policy (deterministic): enough evidence + mostly failing.
QUARANTINE_MIN_TASKS = 6
QUARANTINE_FAILURE_RATE = 0.5


@dataclass
class SeatStats:
    seat: str
    tasks: int = 0
    ok: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)

    @property
    def failure_rate(self) -> float:
        return round(1.0 - (self.ok / self.tasks), 4) if self.tasks else 0.0


class SeatHealthTracker:
    """CED-owned reliability ledger per provider seat. Purely mechanical."""

    def __init__(self, stats: Optional[Dict[str, SeatStats]] = None) -> None:
        self._stats: Dict[str, SeatStats] = stats or {}

    # -- ingest (from the CED-owned task_log; content is never read) --
    def ingest_session(self, state: SessionState) -> None:
        for entry in state.task_log:
            if not entry.provider_id or entry.provider_status is None:
                continue
            s = self._stats.setdefault(entry.provider_id, SeatStats(seat=entry.provider_id))
            s.tasks += 1
            status = entry.provider_status
            if entry.move_id is not None and status == ProviderStatus.OK:
                s.ok += 1
            s.by_status[status.value] = s.by_status.get(status.value, 0) + 1

    # -- mechanical judgements about PROTOCOL health (never about content) --
    def stats(self) -> Dict[str, SeatStats]:
        return dict(self._stats)

    def quarantined(self) -> List[str]:
        """Seats with enough evidence and a chronic failure rate — deterministic."""
        return sorted(
            s.seat for s in self._stats.values()
            if s.tasks >= QUARANTINE_MIN_TASKS and s.failure_rate >= QUARANTINE_FAILURE_RATE
        )

    def rank_seats(self, seat_ids: Sequence[str]) -> List[str]:
        """Order candidate seats by observed reliability (unknown seats first —
        they deserve a chance; then lowest failure rate; stable tie-break by id)."""
        def key(seat: str):
            s = self._stats.get(seat)
            if s is None or not s.tasks:
                return (0, 0.0, seat)          # unknown → try it
            return (1, s.failure_rate, seat)
        return sorted(seat_ids, key=key)

    def recommendations(self) -> List[str]:
        """Config advice derived mechanically from observed failure modes."""
        recs: List[str] = []
        for s in sorted(self._stats.values(), key=lambda x: x.seat):
            if not s.tasks:
                continue
            timeouts = s.by_status.get("timeout", 0)
            schema = s.by_status.get("schema_error", 0) + s.by_status.get("invalid_json", 0)
            limited = s.by_status.get("rate_limited", 0)
            if timeouts / s.tasks >= 0.25:
                recs.append(f"{s.seat}: frequent timeouts — raise CED_LIVE_TIMEOUT or use a faster model")
            if schema / s.tasks >= 0.25:
                recs.append(f"{s.seat}: frequent structure failures — prefer a stronger model for structured output")
            if limited / s.tasks >= 0.25:
                recs.append(f"{s.seat}: frequent rate limits — raise CED_LIVE_RETRIES or reduce council size")
            if s.seat in self.quarantined():
                recs.append(f"{s.seat}: QUARANTINE recommended (failure rate {s.failure_rate:.0%} over {s.tasks} tasks)")
        return recs

    def report(self) -> Dict[str, Any]:
        return {
            "schema_version": HEALTH_SCHEMA,
            "seats": {k: asdict(v) for k, v in sorted(self._stats.items())},
            "quarantined": self.quarantined(),
            "recommendations": self.recommendations(),
        }

    # -- persistence (local JSON; operational telemetry only, no secrets) --
    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.report(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "SeatHealthTracker":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != HEALTH_SCHEMA:
            raise ValueError(f"schema_version mismatch: expected {HEALTH_SCHEMA!r}")
        stats = {k: SeatStats(seat=v["seat"], tasks=v["tasks"], ok=v["ok"],
                              by_status=dict(v.get("by_status", {})))
                 for k, v in doc.get("seats", {}).items()}
        return cls(stats)


# ══════════════════════════════════════════════════════════════════════════════
# B. EpistemicLessonStore — knowledge self-improvement (public artifacts only)
# ══════════════════════════════════════════════════════════════════════════════

_WORD_RE = re.compile(r"[a-zA-Zα-ωΑ-Ωάέήίόύώϊϋΐΰ]{3,}", re.UNICODE)

# Common words that carry no topical signal (tiny, bilingual, deliberately short).
_STOP = {"the", "and", "for", "are", "was", "that", "this", "with", "από", "και",
         "της", "του", "των", "στο", "στη", "για", "είναι", "ότι", "μια", "ένα"}


def _keywords(text: str) -> set:
    return {w.lower() for w in _WORD_RE.findall(text or "") if w.lower() not in _STOP}


def _clip(text: str, n: int = 300) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


@dataclass(frozen=True)
class Lesson:
    """A PUBLIC distillation of one ratified dialogue. No scores, no identities.
    `distilled_by` records WHO wrote it: "mechanical" (CED clipping) or "council"
    (an AI agent authored insight/principle/pitfalls — Phase 13D)."""
    question: str
    final_verdict: str
    core_answer: str
    caveats: List[str] = field(default_factory=list)
    decisive_objections: List[str] = field(default_factory=list)
    session_id: str = ""
    insight: str = ""
    transferable_principle: str = ""
    pitfalls: List[str] = field(default_factory=list)
    distilled_by: str = "mechanical"

    def public_dict(self) -> Dict[str, Any]:
        out = {
            "question": self.question,
            "final_verdict": self.final_verdict,
            "core_answer": self.core_answer,
            "caveats": list(self.caveats),
            "decisive_objections": list(self.decisive_objections),
        }
        if self.insight:
            out["insight"] = self.insight
        if self.transferable_principle:
            out["transferable_principle"] = self.transferable_principle
        if self.pitfalls:
            out["pitfalls"] = list(self.pitfalls)
        return out


@dataclass(frozen=True)
class ProcessLesson:
    """AI meta-reflection on the council's OWN process (not the topic) — what the
    next dialogue should do differently. PUBLIC; no scores, no identities."""
    what_worked: str
    what_failed: str
    advice_for_next_dialogue: str
    session_id: str = ""

    def public_dict(self) -> Dict[str, Any]:
        return {
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "advice_for_next_dialogue": self.advice_for_next_dialogue,
        }


def extract_lesson(state: SessionState, final: FinalResponse) -> Optional[Lesson]:
    """Distill the PUBLIC outcome of a RATIFIED session. Returns None for
    non-ratified sessions — the store never learns from unratified answers."""
    if not final.ratified or not final.synthesis:
        return None
    sections = {s.section_name.value: s.content for s in final.synthesis.sections
                if not s.unresolved and s.content.strip()}
    cr = (final.audit_summary or {}).get("council_ratification", {}) or {}
    caveats = [_clip(c.get("caveat", "")) for c in cr.get("caveats", [])
               if isinstance(c, dict) and c.get("caveat")]
    objections = []
    if sections.get("crucial_stress_test"):
        objections.append(_clip(sections["crucial_stress_test"]))
    return Lesson(
        question=state.question,
        final_verdict=_clip(sections.get("final_verdict", "")),
        core_answer=_clip(sections.get("core_answer", "")),
        caveats=caveats[:3],
        decisive_objections=objections[:3],
        session_id=state.session_id,
    )


class EpistemicLessonStore:
    """Cross-session public memory: the council builds on its own past dialogues."""

    def __init__(self, lessons: Optional[List[Lesson]] = None,
                 process_lessons: Optional[List[ProcessLesson]] = None) -> None:
        self._lessons: List[Lesson] = list(lessons or [])
        self._process: List[ProcessLesson] = list(process_lessons or [])

    def __len__(self) -> int:
        return len(self._lessons)

    def add(self, lesson: Lesson) -> None:
        self._lessons.append(lesson)

    def lessons(self) -> List[Lesson]:
        return list(self._lessons)

    def replace_many(self, indices: List[int], replacement: Lesson) -> None:
        """Phase 15 consolidation: replace the lessons at `indices` with ONE
        consolidated lesson (deterministic; preserves the order of the rest)."""
        drop = set(indices)
        self._lessons = [l for i, l in enumerate(self._lessons) if i not in drop]
        self._lessons.append(replacement)

    def add_process(self, lesson: ProcessLesson) -> None:
        self._process.append(lesson)

    def process_guidance(self, k: int = 2) -> List[Dict[str, Any]]:
        """The latest k process lessons — the council's advice to its future self."""
        return [pl.public_dict() for pl in self._process[-k:]]

    def ingest(self, state: SessionState, final: FinalResponse) -> Optional[Lesson]:
        lesson = extract_lesson(state, final)
        if lesson is not None:
            self._lessons.append(lesson)
        return lesson

    def relevant(self, question: str, k: int = 3) -> List[Dict[str, Any]]:
        """Top-k lessons by deterministic keyword overlap with the new question
        (score desc, then most recent first). Returns PUBLIC dicts only."""
        q = _keywords(question)
        if not q:
            return []
        scored = []
        for idx, lesson in enumerate(self._lessons):
            overlap = len(q & _keywords(lesson.question + " " + lesson.core_answer))
            if overlap > 0:
                scored.append((overlap, idx, lesson))
        scored.sort(key=lambda t: (-t[0], -t[1]))
        return [lesson.public_dict() for _, _, lesson in scored[:k]]

    # -- persistence (local JSON; public artifacts only) --
    def save(self, path: str) -> None:
        doc = {"schema_version": LESSON_SCHEMA,
               "lessons": [asdict(l) for l in self._lessons],
               "process_lessons": [asdict(p) for p in self._process]}
        Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "EpistemicLessonStore":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != LESSON_SCHEMA:
            raise ValueError(f"schema_version mismatch: expected {LESSON_SCHEMA!r}")
        return cls([Lesson(**l) for l in doc.get("lessons", [])],
                   [ProcessLesson(**p) for p in doc.get("process_lessons", [])])


# ══════════════════════════════════════════════════════════════════════════════
# D. AI-in-the-loop learning — agents AUTHOR the lessons; CED governs & verifies
# ══════════════════════════════════════════════════════════════════════════════
#
# The mechanical extractor clips text; an AI distiller UNDERSTANDS the dialogue.
# Both paths obey the same rules: distillation runs through the SAME registry
# adapters (mock = deterministic, live = real model), CED validates the schema,
# and on ANY failure it falls back honestly to the mechanical lesson — never a
# fabricated one. Inputs are PUBLIC artifacts only.

def _public_final_sections(final: FinalResponse) -> Dict[str, str]:
    if not final.synthesis:
        return {}
    return {s.section_name.value: s.content for s in final.synthesis.sections
            if not s.unresolved and s.content.strip()}


async def distill_lesson_with_council(ced, state: SessionState,
                                      final: FinalResponse) -> Optional[Lesson]:
    """Ask ONE council seat (via the registry) to author the lesson. Returns None
    on any failure — the caller falls back to the mechanical extractor."""
    from .models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
    if ced.registry is None or not final.ratified:
        return None
    adapters = ced.registry.available_adapters()
    if not adapters:
        return None
    if ced.seat_health is not None:
        order = ced.seat_health.rank_seats([a.provider_id for a in adapters])
        adapters = sorted(adapters, key=lambda a: order.index(a.provider_id))
    task = AgentTask(
        session_id=state.session_id, agent_id="lesson_distiller",
        role=AgentRole.SYNTHESIZER, phase=DialogPhase.COMPLETE,
        question=state.question,
        context={"final_answer_sections": _public_final_sections(final)},
        output_schema={"_role": "synthesizer", "_question": state.question},
        task_kind=TaskKind.LESSON_DISTILLATION,
    )
    astate = AgentState(agent_id="lesson_distiller",
                        primary_role=AgentRole.SYNTHESIZER,
                        assigned_role=AgentRole.SYNTHESIZER)
    resp = await ced.registry.run_adapter(adapters[0], task, astate, None)
    if not resp.ok:
        return None
    c = resp.parsed_move.content
    insight = str(c.get("insight", "")).strip()
    principle = str(c.get("transferable_principle", "")).strip()
    if not insight and not principle:
        return None                      # AI gave nothing usable → mechanical fallback
    base = extract_lesson(state, final)  # mechanical public facts stay the backbone
    if base is None:
        return None
    pitfalls = c.get("pitfalls", [])
    return Lesson(
        question=base.question, final_verdict=base.final_verdict,
        core_answer=base.core_answer, caveats=base.caveats,
        decisive_objections=base.decisive_objections, session_id=base.session_id,
        insight=_clip(insight), transferable_principle=_clip(principle),
        pitfalls=[_clip(str(p)) for p in pitfalls][:3] if isinstance(pitfalls, list) else [],
        distilled_by="council",
    )


async def review_process_with_council(ced, state: SessionState) -> Optional[ProcessLesson]:
    """Ask ONE council seat to critique the council's OWN process this session.
    Returns None on any failure (no fabricated self-praise)."""
    from .models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
    if ced.registry is None:
        return None
    adapters = ced.registry.available_adapters()
    if not adapters:
        return None
    task = AgentTask(
        session_id=state.session_id, agent_id="process_reviewer",
        role=AgentRole.REFLECTOR, phase=DialogPhase.COMPLETE,
        question=state.question,
        context={"dialogue_so_far": ced._dialogue_transcript(state)},
        output_schema={"_role": "reflector", "_question": state.question},
        task_kind=TaskKind.PROCESS_REVIEW,
    )
    astate = AgentState(agent_id="process_reviewer",
                        primary_role=AgentRole.REFLECTOR,
                        assigned_role=AgentRole.REFLECTOR)
    resp = await ced.registry.run_adapter(adapters[-1], task, astate, None)
    if not resp.ok:
        return None
    c = resp.parsed_move.content
    advice = str(c.get("advice_for_next_dialogue", "")).strip()
    if not advice:
        return None
    return ProcessLesson(
        what_worked=_clip(str(c.get("what_worked", ""))),
        what_failed=_clip(str(c.get("what_failed", ""))),
        advice_for_next_dialogue=_clip(advice),
        session_id=state.session_id,
    )


async def rank_lessons_with_council(ced, question: str, k: int = 3):
    """
    Phase 14 — semantic lesson retrieval: keyword prefilter proposes candidates,
    then a council seat SELECTS which lessons genuinely TRANSFER to the new
    question (surface overlap is not transfer). Returns (lessons, mode) where
    mode is "council" or "keyword" (honest fallback on any failure).
    """
    from .models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
    store = ced.lesson_store
    if store is None:
        return [], "keyword"
    candidates = store.relevant(question, k=8)          # deterministic prefilter
    if not candidates or ced.registry is None:
        return candidates[:k], "keyword"
    adapters = ced.registry.available_adapters()
    if not adapters:
        return candidates[:k], "keyword"
    task = AgentTask(
        session_id="lesson_retrieval", agent_id="lesson_ranker",
        role=AgentRole.EMPIRICIST, phase=DialogPhase.OPENING,
        question=question,
        context={"candidate_lessons": candidates},
        output_schema={"_role": "empiricist", "_question": question},
        task_kind=TaskKind.LESSON_RELEVANCE,
    )
    astate = AgentState(agent_id="lesson_ranker",
                        primary_role=AgentRole.EMPIRICIST,
                        assigned_role=AgentRole.EMPIRICIST)
    resp = await ced.registry.run_adapter(adapters[0], task, astate, None)
    if not resp.ok:
        return candidates[:k], "keyword"
    idx = resp.parsed_move.content.get("relevant_indices", None)
    if not isinstance(idx, list):
        return candidates[:k], "keyword"
    picked = [candidates[i] for i in idx
              if isinstance(i, int) and 0 <= i < len(candidates)][:k]
    return picked, "council"


# ══════════════════════════════════════════════════════════════════════════════
# F. CalibrationLedger — Brier-scored confidence calibration per seat (CED-owned)
# ══════════════════════════════════════════════════════════════════════════════
#
# Confidence must MEAN something. A proper scoring rule (Brier) makes honest
# confidence the optimal report: for each SYNTHESIS draft, the seat's stated
# confidence is scored against the mechanical outcome "share of the 5 sections
# its draft actually won at blind assembly". From this we get, per seat:
#   brier  = mean (confidence − outcome)²   (lower is better-calibrated)
#   bias   = mean confidence − mean outcome (>0 overconfident, <0 underconfident)
# CED-owned, HIDDEN from agents (like the leaderboard) — used for operator
# reports and seat selection, never in a prompt.

CALIBRATION_SCHEMA = "calibration_v0"
CALIBRATION_BIAS_THRESHOLD = 0.20   # |bias| beyond this (with evidence) → recalibrate
CALIBRATION_MIN_SAMPLES = 3


@dataclass
class CalibrationStats:
    seat: str
    n: int = 0
    conf_sum: float = 0.0
    outcome_sum: float = 0.0
    brier_sum: float = 0.0

    @property
    def mean_confidence(self) -> float:
        return round(self.conf_sum / self.n, 4) if self.n else 0.0

    @property
    def mean_outcome(self) -> float:
        return round(self.outcome_sum / self.n, 4) if self.n else 0.0

    @property
    def brier(self) -> float:
        return round(self.brier_sum / self.n, 4) if self.n else 0.0

    @property
    def bias(self) -> float:
        return round(self.mean_confidence - self.mean_outcome, 4) if self.n else 0.0


class CalibrationLedger:
    """Per-seat confidence calibration from mechanical assembly outcomes."""

    def __init__(self, stats: Optional[Dict[str, CalibrationStats]] = None) -> None:
        self._stats: Dict[str, CalibrationStats] = stats or {}

    def ingest_session(self, state: SessionState) -> None:
        assembled = state.assembled_answer
        if assembled is None or not assembled.sections or not state.section_drafts:
            return
        total = len(assembled.sections)
        wins: Dict[str, int] = {}
        for s in assembled.sections:
            if s.selected_draft_id:
                wins[s.selected_draft_id] = wins.get(s.selected_draft_id, 0) + 1
        move_conf = {m.move_id: m.confidence for m in state.moves}
        for draft in state.section_drafts:
            seat = draft.provider_id
            conf = move_conf.get(draft.move_id)
            if seat is None or conf is None:
                continue
            outcome = wins.get(draft.draft_id, 0) / total
            st = self._stats.setdefault(seat, CalibrationStats(seat=seat))
            st.n += 1
            st.conf_sum += float(conf)
            st.outcome_sum += outcome
            st.brier_sum += (float(conf) - outcome) ** 2

    def stats(self) -> Dict[str, CalibrationStats]:
        return dict(self._stats)

    def recommendations(self) -> List[str]:
        recs: List[str] = []
        for st in sorted(self._stats.values(), key=lambda s: s.seat):
            if st.n < CALIBRATION_MIN_SAMPLES:
                continue
            if st.bias >= CALIBRATION_BIAS_THRESHOLD:
                recs.append(f"{st.seat}: OVERCONFIDENT by {st.bias:+.2f} "
                            f"(brier {st.brier}, n={st.n}) — discount its confidence")
            elif st.bias <= -CALIBRATION_BIAS_THRESHOLD:
                recs.append(f"{st.seat}: UNDERCONFIDENT by {st.bias:+.2f} "
                            f"(brier {st.brier}, n={st.n}) — its hedged claims tend to win")
        return recs

    def report(self) -> Dict[str, Any]:
        return {
            "schema_version": CALIBRATION_SCHEMA,
            "seats": {k: {"seat": v.seat, "n": v.n,
                          "mean_confidence": v.mean_confidence,
                          "mean_outcome": v.mean_outcome,
                          "brier": v.brier, "bias": v.bias}
                      for k, v in sorted(self._stats.items())},
            "recommendations": self.recommendations(),
            "interpretation_warning": SKILL_INTERPRETATION_WARNING,
        }

    def save(self, path: str) -> None:
        doc = {"schema_version": CALIBRATION_SCHEMA,
               "stats": {k: asdict(v) for k, v in sorted(self._stats.items())}}
        Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "CalibrationLedger":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != CALIBRATION_SCHEMA:
            raise ValueError(f"schema_version mismatch: expected {CALIBRATION_SCHEMA!r}")
        return cls({k: CalibrationStats(**v) for k, v in doc.get("stats", {}).items()})


# ══════════════════════════════════════════════════════════════════════════════
# E. TopicSkillTracker — per-topic skill profile per seat (CED-owned analytics)
# ══════════════════════════════════════════════════════════════════════════════
#
# WHICH seat is actually good at WHAT. Mechanical: peer scores (already CED-owned
# analytics) aggregated by (seat, topic) using the existing classify_topic
# heuristic. Like the leaderboard, this is HIDDEN FROM AGENTS — it informs seat
# selection and operator decisions, never a prompt.

TOPIC_SKILL_SCHEMA = "topic_skill_v0"
SKILL_INTERPRETATION_WARNING = (
    "Peer-evaluation signals aggregated by topic — not proof of truth or ability.")


@dataclass
class TopicSkill:
    seat: str
    topic: str
    score_sum: float = 0.0
    score_count: int = 0

    @property
    def average(self) -> float:
        return round(self.score_sum / self.score_count, 4) if self.score_count else 0.0


class TopicSkillTracker:
    """CED-owned per-(seat, topic) skill profile from peer scores. Never shown
    to agents; used mechanically for seat selection and operator reports."""

    def __init__(self, skills: Optional[Dict[str, TopicSkill]] = None) -> None:
        self._skills: Dict[str, TopicSkill] = skills or {}   # key "seat|topic"

    def ingest_session(self, state: SessionState) -> None:
        from .topic import classify_topic
        topic = classify_topic(state.question).value
        seat_of_move = {m.move_id: m.provider_id for m in state.moves if m.provider_id}
        for ms in state.micro_scores:
            seat = seat_of_move.get(ms.output_id)
            if seat is None or ms.overall_score is None:
                continue
            key = f"{seat}|{topic}"
            ts = self._skills.setdefault(key, TopicSkill(seat=seat, topic=topic))
            ts.score_sum += float(ms.overall_score)
            ts.score_count += 1

    def best_seats(self, topic: str) -> List[str]:
        """Seats ranked by peer-scored average on this topic (desc; stable)."""
        rows = [s for s in self._skills.values() if s.topic == topic and s.score_count]
        rows.sort(key=lambda s: (-s.average, s.seat))
        return [s.seat for s in rows]

    def profile(self, seat: str) -> Dict[str, float]:
        """topic -> average for one seat (the seat's skill fingerprint)."""
        return {s.topic: s.average for s in self._skills.values()
                if s.seat == seat and s.score_count}

    def report(self) -> Dict[str, Any]:
        return {
            "schema_version": TOPIC_SKILL_SCHEMA,
            "skills": {k: asdict(v) for k, v in sorted(self._skills.items())},
            "interpretation_warning": SKILL_INTERPRETATION_WARNING,
        }

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.report(), ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TopicSkillTracker":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != TOPIC_SKILL_SCHEMA:
            raise ValueError(f"schema_version mismatch: expected {TOPIC_SKILL_SCHEMA!r}")
        return cls({k: TopicSkill(seat=v["seat"], topic=v["topic"],
                                  score_sum=v["score_sum"], score_count=v["score_count"])
                    for k, v in doc.get("skills", {}).items()})
