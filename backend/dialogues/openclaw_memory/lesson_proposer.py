"""
OpenClaw Memory Lessons — lesson proposer (Goal 6).

Converts REPEATED failures observed in session traces (Goal 5 output) into
PROPOSED lessons for human review. The flow from FUTURE_GOALS.md:

    failure pattern -> proposed lesson -> human/test review -> verified lesson

Safety properties (each mechanically guaranteed, not aspirational):

  - Every proposal has ``status="proposed"``. The existing, test-locked loader
    (:func:`load_stable_lessons`) excludes non-stable/verified statuses, so a
    proposal can NEVER be auto-injected into agent contexts. Promotion is a
    human act (editing the status in the curated file).
  - :func:`write_proposed_lessons` REFUSES to write to the curated
    ``MEMORY_LESSONS.md`` — stable lessons are never overwritten automatically.
  - Detection is mechanical (protocol facts from traces: ratification failed,
    assembly missing, section unresolved, phase produced no valid moves).
    No LLM authorship, no semantic judgement, no scores shown to anyone.
  - A pattern must repeat (``min_occurrences``, default 2) before it becomes a
    proposal — one-off noise is not a lesson.
  - Proposal ids live in a reserved provisional range (LESSON-9001+) and are
    deterministic (sorted pattern order). The curator re-numbers on promotion.

Every proposal carries the four fields the spec requires: source (which
sessions exhibited the pattern), problem pattern, lesson, and risk.

No provider calls, no network, no API keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .lesson_loader import MemoryLesson, default_lessons_path

#: Reserved provisional id range for machine-proposed lessons. Curated lessons
#: use low ids; the curator assigns a real id when promoting a proposal.
PROPOSAL_ID_START = 9001

#: A failure pattern must appear in at least this many sessions to become a
#: proposal ("repeated failures", per Goal 6 — single occurrences are noise).
DEFAULT_MIN_OCCURRENCES = 2

#: The deliberation phases a completed registry session is expected to run.
EXPECTED_PHASES: tuple[str, ...] = (
    "opening", "initial_response", "elenchus",
    "reflection", "reconstruction", "synthesis",
)

#: phase -> lesson_type for the phase_missing detector. A phase with zero
#: validated moves is almost always a broken output contract (schema/quorum),
#: which is exact_output territory regardless of which phase starved.
_PHASE_MISSING_LESSON_TYPE = "exact_output"


# --------------------------------------------------------------------------- #
# Detection (mechanical protocol facts from one trace)
# --------------------------------------------------------------------------- #

def detect_trace_failures(trace: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return mechanical failure observations from ONE session trace.

    Each observation: {"pattern_key", "lesson_type", "session_id", "detail"}.
    Only protocol facts are read — never scores, identities, or content.
    """
    out: List[Dict[str, str]] = []
    sid = str(trace.get("session_id", ""))

    def _obs(pattern_key: str, lesson_type: str, detail: str) -> None:
        out.append({"pattern_key": pattern_key, "lesson_type": lesson_type,
                    "session_id": sid, "detail": detail})

    ratification = trace.get("ratification") or {}
    if ratification.get("ratified") is False:
        _obs("ratification_failed", "ratification_quality",
             f"status={ratification.get('ratification_status')}")

    assembly = trace.get("assembly")
    if assembly is None:
        _obs("assembly_missing", "synthesis_quality",
             "session produced no assembled answer")
    else:
        for section in assembly.get("sections", []):
            if not str(section.get("source_draft_id", "")).strip():
                name = str(section.get("section_name", "unknown"))
                _obs(f"unresolved_section:{name}", "synthesis_quality",
                     f"section {name} had no valid peer-scored source draft")

    phases_seen = {str(m.get("phase", "")) for m in trace.get("moves", [])}
    for phase in EXPECTED_PHASES:
        if phase not in phases_seen:
            _obs(f"phase_missing:{phase}", _PHASE_MISSING_LESSON_TYPE,
                 f"phase {phase} contributed zero validated moves")

    return out


def aggregate_failures(
    traces: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, str]]]:
    """Group observations across traces by pattern_key (deterministic order)."""
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for trace in traces:
        for obs in detect_trace_failures(trace):
            grouped.setdefault(obs["pattern_key"], []).append(obs)
    return {key: grouped[key] for key in sorted(grouped)}


# --------------------------------------------------------------------------- #
# Proposal templates (mechanical text, filled with observed counts)
# --------------------------------------------------------------------------- #

def _template_for(pattern_key: str) -> Dict[str, str]:
    if pattern_key == "ratification_failed":
        return {
            "name": "Synthesis repeatedly failed ratification",
            "use_when": "ratification, synthesis, final verdict, objection",
            "bad_pattern": "Submit the synthesis unchanged and hope the "
                           "ratifier accepts it.",
            "good_pattern": "Ground the crucial stress test in the strongest "
                            "objection actually raised, and let the final "
                            "verdict answer it directly.",
            "lesson": "When ratification keeps failing, the synthesis is not "
                      "absorbing the dialectic's objections. Engage the "
                      "strongest standing objection inside the draft itself — "
                      "a synthesis that ignores the elenchus invites a block.",
            "risk": "Over-fitting the synthesis to please the ratifier can "
                    "suppress honest disagreement; ratification must remain a "
                    "real check, not a formality to be gamed.",
        }
    if pattern_key == "assembly_missing":
        return {
            "name": "Sessions repeatedly ended with no assembled answer",
            "use_when": "synthesis, sections, draft, assembly",
            "bad_pattern": "Let a blocked phase end the session with no "
                           "usable synthesis drafts.",
            "good_pattern": "Produce a schema-valid five-section draft every "
                            "synthesis round so assembly has real candidates.",
            "lesson": "An unassembled session wastes the whole deliberation. "
                      "Every synthesis draft must be complete and schema-valid "
                      "so at least one candidate reaches blind assembly.",
            "risk": "Producing a rushed draft merely to have output can lower "
                    "answer quality; the fix is contract compliance, not "
                    "haste.",
        }
    if pattern_key.startswith("unresolved_section:"):
        section = pattern_key.split(":", 1)[1]
        return {
            "name": f"Section '{section}' repeatedly unresolved at assembly",
            "use_when": f"synthesis, sections, draft, {section.replace('_', ' ')}",
            "bad_pattern": f"Leave '{section}' empty or so thin that no peer "
                           "score validates it.",
            "good_pattern": f"Write substantive standalone content for "
                            f"'{section}' in every synthesis draft.",
            "lesson": f"The assembled answer repeatedly shipped without a "
                      f"resolved '{section}'. Every draft must give that "
                      "section real content — a missing section leaves the "
                      "final answer incomplete even when other sections win.",
            "risk": "Padding the section with filler to avoid 'unresolved' is "
                    "worse than honest thinness; the fix is substance.",
        }
    if pattern_key.startswith("phase_missing:"):
        phase = pattern_key.split(":", 1)[1]
        return {
            "name": f"Phase '{phase}' repeatedly produced no valid moves",
            "use_when": f"format, exact, schema, {phase.replace('_', ' ')}",
            "bad_pattern": "Return output that does not match the phase's "
                           "required JSON contract.",
            "good_pattern": "Return exactly the required JSON contract so the "
                            "move validates.",
            "lesson": f"Phase '{phase}' repeatedly contributed zero validated "
                      "moves, starving every downstream phase. The output "
                      "contract is a hard gate: match it exactly.",
            "risk": "This pattern can also stem from provider outages rather "
                    "than agent behavior; verify the task log before treating "
                    "it as a behavioral lesson.",
        }
    # Unknown pattern — honest generic template (still fully specified).
    return {
        "name": f"Repeated failure pattern: {pattern_key}",
        "use_when": "process, protocol",
        "bad_pattern": "Repeat the observed failure pattern.",
        "good_pattern": "Avoid the observed failure pattern.",
        "lesson": f"The pattern '{pattern_key}' repeated across sessions and "
                  "should be reviewed by a human.",
        "risk": "Auto-detected pattern without a curated template; review "
                "carefully before promotion.",
    }


# --------------------------------------------------------------------------- #
# Proposal construction
# --------------------------------------------------------------------------- #

def propose_lessons(
    traces: Sequence[Dict[str, Any]],
    *,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
) -> List[MemoryLesson]:
    """Convert repeated failure patterns across traces into PROPOSED lessons.

    Deterministic: patterns sorted by key; ids assigned from
    ``PROPOSAL_ID_START`` in that order. Every proposal has
    ``status="proposed"`` and therefore can never enter the stable pool
    without explicit human promotion.
    """
    if min_occurrences < 1:
        raise ValueError(f"min_occurrences must be >= 1, got {min_occurrences!r}")
    grouped = aggregate_failures(traces)
    total = len(traces)
    proposals: List[MemoryLesson] = []
    next_id = PROPOSAL_ID_START
    for pattern_key, observations in grouped.items():
        sessions = sorted({o["session_id"] for o in observations})
        if len(sessions) < min_occurrences:
            continue
        t = _template_for(pattern_key)
        source = (f"openclaw trace analysis: {len(sessions)}/{total} sessions "
                  f"({', '.join(sessions)})")
        problem = (f"Observed in {len(sessions)} of {total} analyzed sessions: "
                   f"{observations[0]['detail']}.")
        proposals.append(MemoryLesson(
            lesson_id=f"LESSON-{next_id}",
            name=t["name"],
            status="proposed",
            lesson_type=observations[0]["lesson_type"],
            source=source,
            use_when=tuple(p.strip() for p in t["use_when"].split(",") if p.strip()),
            problem_pattern=problem,
            bad_pattern=t["bad_pattern"],
            good_pattern=t["good_pattern"],
            lesson=t["lesson"],
            risk=t["risk"],
        ))
        next_id += 1
    return proposals


def propose_from_capturer(
    capturer: Any,
    *,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
) -> List[MemoryLesson]:
    """Convenience: propose lessons from a TraceCapturer's collected traces."""
    return propose_lessons(list(getattr(capturer, "traces", [])),
                           min_occurrences=min_occurrences)


# --------------------------------------------------------------------------- #
# Rendering (loader-parseable Markdown) + guarded file output
# --------------------------------------------------------------------------- #

def render_proposed_lessons(lessons: Sequence[MemoryLesson]) -> str:
    """Render proposals in the exact Markdown format ``parse_memory_lessons``
    reads, so a curator can review and (manually) merge them. Round-trips:
    ``parse_memory_lessons(render_proposed_lessons(x)) == x``."""
    parts: List[str] = [
        "# PROPOSED memory lessons — pending human review",
        "",
        "Machine-proposed from repeated failure patterns in session traces.",
        "Nothing here is active: status `proposed` is excluded from the stable",
        "pool by the loader. Promote by curating into MEMORY_LESSONS.md.",
        "",
    ]
    for lesson in lessons:
        parts.extend([
            f"### {lesson.lesson_id} — {lesson.name}",
            "",
            f"**Status:** {lesson.status}",
            f"**Lesson type:** {lesson.lesson_type}",
            f"**Source:** {lesson.source}",
            f"**Use when:** {', '.join(lesson.use_when)}",
            "",
            f"**Problem pattern:** {lesson.problem_pattern}",
            "",
            f"**Bad pattern:** `{lesson.bad_pattern}`",
            "",
            f"**Good pattern:** `{lesson.good_pattern}`",
            "",
            f"**Lesson:** {lesson.lesson}",
            "",
            f"**Risk:** {lesson.risk}",
            "",
            "---",
            "",
        ])
    return "\n".join(parts)


def write_proposed_lessons(
    lessons: Sequence[MemoryLesson],
    path: Path | str,
) -> Path:
    """Write rendered proposals to ``path`` — NEVER the curated lessons file.

    Refuses ``default_lessons_path()`` outright: stable lessons are not
    overwritten automatically (Goal 6 acceptance criterion).
    """
    target = Path(path).resolve()
    if target == default_lessons_path().resolve():
        raise ValueError(
            "write_proposed_lessons refuses to write to the curated "
            "MEMORY_LESSONS.md — proposals go to a separate file and are "
            "promoted only by a human."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_proposed_lessons(lessons), encoding="utf-8")
    return target
