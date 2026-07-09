"""
Promotion Arena — generation gating for the Teacher Loop
(docs/deliberation_tree/ARCHITECTURE.md §6.2: AlphaGo's 55% gate, adapted).

AlphaGo promoted a new network only when it beat the incumbent in evaluation
games. Here: a candidate seat (e.g. the LoRA student from Phase 22) is run
head-to-head against the incumbent seat on a fixed benchmark of questions.
Both produce full five-section drafts; a panel of judge seats (never the
contenders themselves) scores every draft through the SAME anonymous
section-scoring contract the council uses. The verdict is mechanical:

    promote  ⇔  decided_questions >= min_decided
                AND wins / decided_questions >= gate      (default 0.55)

Honesty properties:
  - Judges never see WHO authored a draft. The scoring task carries only the
    section text and a neutral rotating label ("arena_draft_a"/"_b", swapped
    every question so no label systematically means "candidate") — the same
    anti brand-bias anonymity the council's blind judging uses.
  - The contenders never judge (no self-scoring, no rival-scoring).
  - Nothing is fabricated: a failed draft or an unscorable side makes that
    question INVALID (not a loss — a provider outage is not a defeat) and
    invalid questions are excluded from the gate.
  - Insufficient evidence keeps the INCUMBENT (promote=False,
    reason="insufficient_evidence") — the burden of proof is on the candidate,
    exactly like AlphaGo's gate.
  - The arena only REPORTS. It never swaps a seat. Promotion is a human act —
    the same never-auto-promote symmetry as the OpenClaw lesson lifecycle.

Pure orchestration over the existing provider registry. No torch, no network
beyond the adapters it is given, no keys.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ScoreBreakdown,
    SectionName,
    SECTION_ORDER,
    TaskKind,
)

ARENA_SCHEMA_VERSION = "arena_v0"
DEFAULT_PROMOTION_GATE = 0.55     # AlphaGo's evaluation gate
DEFAULT_MIN_DECIDED = 3           # minimum decided (non-tie, valid) questions

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


class PromotionArena:
    """Head-to-head evaluation of a candidate seat against the incumbent."""

    def __init__(
        self,
        registry,
        candidate_id: str,
        incumbent_id: str,
        judge_ids: Optional[Sequence[str]] = None,
        *,
        gate: float = DEFAULT_PROMOTION_GATE,
        min_decided: int = DEFAULT_MIN_DECIDED,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        if candidate_id == incumbent_id:
            raise ValueError("candidate and incumbent must be different seats")
        if not (0.0 < gate <= 1.0):
            raise ValueError(f"gate must be in (0, 1], got {gate!r}")
        if min_decided < 1:
            raise ValueError(f"min_decided must be >= 1, got {min_decided!r}")
        by_id = {a.provider_id: a for a in registry.all_adapters()}
        for pid in (candidate_id, incumbent_id):
            if pid not in by_id:
                raise ValueError(f"unknown adapter {pid!r}")
        self.registry = registry
        self.candidate = by_id[candidate_id]
        self.incumbent = by_id[incumbent_id]
        wanted = (list(judge_ids) if judge_ids is not None
                  else [pid for pid in by_id if pid not in (candidate_id, incumbent_id)])
        if candidate_id in wanted or incumbent_id in wanted:
            raise ValueError("a contender can never judge the arena")
        missing = [pid for pid in wanted if pid not in by_id]
        if missing:
            raise ValueError(f"unknown judge adapters {missing!r}")
        if not wanted:
            raise ValueError("the arena needs at least one judge seat")
        self.judges = [by_id[pid] for pid in sorted(wanted)]
        self.gate = float(gate)
        self.min_decided = int(min_decided)
        self.timeout_seconds = timeout_seconds

    # ── One contender drafts one answer ───────────────────────────────────────

    async def _draft(self, adapter, question: str, qi: int,
                     agent_id: str) -> Optional[Dict[str, str]]:
        task = AgentTask(
            session_id=f"arena_q{qi}", agent_id=agent_id,
            role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
            question=question, context={},
            output_schema={"_role": AgentRole.SYNTHESIZER.value,
                           "_question": question, "_sections": True},
            task_kind=TaskKind.SYNTHESIS_DRAFT, slot_index=qi,
        )
        astate = AgentState(agent_id=agent_id,
                            primary_role=AgentRole.SYNTHESIZER,
                            assigned_role=AgentRole.SYNTHESIZER)
        resp = await self.registry.run_adapter(adapter, task, astate,
                                               self.timeout_seconds)
        if not resp.ok or resp.parsed_move is None:
            return None
        c = resp.parsed_move.content
        if not isinstance(c, dict):
            return None
        sections = {f: str(c.get(f, "")) for f in _SECTION_FIELDS}
        if not any(v.strip() for v in sections.values()):
            return None
        return sections

    # ── The judge panel scores one draft (anonymous) ──────────────────────────

    async def _panel_score(self, question: str, sections: Dict[str, str],
                           label: str, qi: int) -> Optional[float]:
        """Mean weighted-overall across judges and non-empty sections; None when
        no judge produced a single valid score (unscorable ≠ zero)."""
        scores: List[float] = []
        for jslot, judge in enumerate(self.judges):
            astate = AgentState(agent_id=judge.provider_id,
                                primary_role=AgentRole.FINAL_EVALUATOR,
                                assigned_role=AgentRole.FINAL_EVALUATOR)
            for section in SECTION_ORDER:
                content = sections.get(section.value, "")
                if not content.strip():
                    continue
                # Judge-visible payload: section text + neutral label ONLY —
                # no provider ids, no model names, no candidate/incumbent hint.
                task = AgentTask(
                    session_id=f"arena_q{qi}", agent_id=judge.provider_id,
                    role=AgentRole.FINAL_EVALUATOR, phase=DialogPhase.SYNTHESIS,
                    question=question,
                    context={"output_to_score": content,
                             "section": section.value},
                    output_schema={"_role": "__section_score__",
                                   "_target": label,
                                   "_section": section.value,
                                   "_question": question},
                    task_kind=TaskKind.SECTION_SCORE, slot_index=jslot,
                )
                resp = await self.registry.run_adapter(judge, task, astate,
                                                       self.timeout_seconds)
                if not resp.ok or resp.parsed_move is None:
                    continue
                c = resp.parsed_move.content
                overall = _parse_overall(c) if isinstance(c, dict) else None
                if overall is not None:
                    scores.append(float(overall))
        return (sum(scores) / len(scores)) if scores else None

    # ── The match ─────────────────────────────────────────────────────────────

    async def run(self, questions: Sequence[str]) -> Dict[str, Any]:
        """Run the benchmark and return the mechanical promotion report."""
        rows: List[Dict[str, Any]] = []
        wins = losses = ties = 0
        for qi, question in enumerate(questions):
            cand_secs = await self._draft(self.candidate, question, qi,
                                          "arena_candidate")
            inc_secs = await self._draft(self.incumbent, question, qi,
                                         "arena_incumbent")
            if cand_secs is None or inc_secs is None:
                rows.append({"question": question, "valid": False,
                             "reason": "draft_failed"})
                continue
            # Neutral labels rotate every question so neither label ever
            # systematically means "the candidate" (anti label-bias).
            cand_label = "arena_draft_a" if qi % 2 == 0 else "arena_draft_b"
            inc_label = "arena_draft_b" if qi % 2 == 0 else "arena_draft_a"
            cand_score = await self._panel_score(question, cand_secs, cand_label, qi)
            inc_score = await self._panel_score(question, inc_secs, inc_label, qi)
            if cand_score is None or inc_score is None:
                rows.append({"question": question, "valid": False,
                             "reason": "unscorable"})
                continue
            margin = cand_score - inc_score
            winner = ("candidate" if margin > 0
                      else "incumbent" if margin < 0 else "tie")
            if winner == "candidate":
                wins += 1
            elif winner == "incumbent":
                losses += 1
            else:
                ties += 1
            rows.append({"question": question, "valid": True,
                         "candidate_score": round(cand_score, 4),
                         "incumbent_score": round(inc_score, 4),
                         "margin": round(margin, 4), "winner": winner})

        decided = wins + losses
        win_rate = (wins / decided) if decided else 0.0
        if decided < self.min_decided:
            promote, reason = False, "insufficient_evidence"
        elif win_rate >= self.gate:
            promote, reason = True, "gate_passed"
        else:
            promote, reason = False, "gate_failed"
        return {
            "schema_version": ARENA_SCHEMA_VERSION,
            "candidate": self.candidate.provider_id,
            "incumbent": self.incumbent.provider_id,
            "judges": [j.provider_id for j in self.judges],
            "gate": self.gate,
            "min_decided": self.min_decided,
            "questions": rows,
            "wins": wins, "losses": losses, "ties": ties,
            "decided": decided,
            "invalid": sum(1 for r in rows if not r["valid"]),
            "win_rate": round(win_rate, 4),
            "promote": promote,
            "reason": reason,
            "note": "The arena reports; a human promotes. The seat swap is "
                    "never automatic.",
        }
