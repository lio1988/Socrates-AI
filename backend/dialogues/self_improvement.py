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
    """A PUBLIC distillation of one ratified dialogue. No scores, no identities."""
    question: str
    final_verdict: str
    core_answer: str
    caveats: List[str] = field(default_factory=list)
    decisive_objections: List[str] = field(default_factory=list)
    session_id: str = ""

    def public_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "final_verdict": self.final_verdict,
            "core_answer": self.core_answer,
            "caveats": list(self.caveats),
            "decisive_objections": list(self.decisive_objections),
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

    def __init__(self, lessons: Optional[List[Lesson]] = None) -> None:
        self._lessons: List[Lesson] = list(lessons or [])

    def __len__(self) -> int:
        return len(self._lessons)

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
               "lessons": [asdict(l) for l in self._lessons]}
        Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "EpistemicLessonStore":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != LESSON_SCHEMA:
            raise ValueError(f"schema_version mismatch: expected {LESSON_SCHEMA!r}")
        return cls([Lesson(**l) for l in doc.get("lessons", [])])
