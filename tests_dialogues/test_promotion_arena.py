"""
Promotion Arena tests — generation gating (ARCHITECTURE.md §6.2).

Rigged mock providers give fully controlled outcomes:
  - a drafter whose sections carry a strength marker
  - a judge that scores 9.0 for strong content, 5.0 otherwise

Verifies the AlphaGo-gate mechanics: clear winner promotes, clear loser fails,
ties decide nothing, failures are invalid (never counted as defeats),
insufficient evidence keeps the incumbent, the gate boundary is >=, contenders
can never judge, and the judge-visible payload stays anonymous with rotating
neutral labels.

No network, no keys — everything runs on local mock adapters.
"""

import asyncio
import json

import pytest

from backend.dialogues.models import ScoreBreakdown, TaskKind
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.training import (
    ARENA_SCHEMA_VERSION,
    DEFAULT_PROMOTION_GATE,
    PromotionArena,
)

STRONG = "STRONGCONTENT"
WEAK = "WEAKCONTENT"
_SECTIONS = ("core_answer", "crucial_stress_test", "blind_spots",
             "nuance", "final_verdict")


def _draft_json(marker):
    content = {f: f"{marker} {f}" for f in _SECTIONS}
    content["epistemic_marker"] = "reasonable_hypothesis"
    return json.dumps({"content": content,
                       "confidence": 0.8})


def _score_json(value):
    breakdown = {k: value for k in ScoreBreakdown.model_fields}
    return json.dumps({"content": {"score_breakdown": breakdown,
                                   "confidence": 0.8,
                                   "justification": "rigged",
                                   "penalty_flags": [],
                                   "provider_status": "ok"},
                       "confidence": 0.8})


class RiggedDrafter(ScriptedMockProvider):
    """Drafts sections carrying a fixed strength marker."""

    def __init__(self, provider_id, marker):
        super().__init__(provider_id)
        self.marker = marker

    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            return _draft_json(self.marker)
        return await super()._produce_raw_text(task, agent_state)


class QuestionSensitiveDrafter(ScriptedMockProvider):
    """Strong on ordinary questions, weak when the question contains 'hard'."""

    def __init__(self, provider_id, invert=False):
        super().__init__(provider_id)
        self.invert = invert

    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            weak_here = ("hard" in task.question) != self.invert
            return _draft_json(WEAK if weak_here else STRONG)
        return await super()._produce_raw_text(task, agent_state)


class BrokenDrafter(ScriptedMockProvider):
    """Every draft is unparseable (provider failure path)."""

    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            return "not json at all"
        return await super()._produce_raw_text(task, agent_state)


class RiggedJudge(ScriptedMockProvider):
    """Scores 9.0 when the judged text carries STRONG, else 5.0. Records every
    scoring task it receives (for the anonymity assertions)."""

    def __init__(self, provider_id):
        super().__init__(provider_id)
        self.seen = []

    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SECTION_SCORE:
            self.seen.append({
                "session_id": task.session_id,
                "context": dict(task.context),
                "schema": dict(task.output_schema),
            })
            text = str(task.context.get("output_to_score", ""))
            return _score_json(9.0 if STRONG in text else 5.0)
        return await super()._produce_raw_text(task, agent_state)


def _registry(*adapters):
    reg = CouncilProviderRegistry(provider_timeout_seconds=10.0)
    for a in adapters:
        reg.register(a)
    return reg


def _run(arena, questions):
    return asyncio.run(arena.run(questions))


QUESTIONS_4 = ["q one", "q two", "q three", "q four"]


# --------------------------------------------------------------------------- #
# Gate mechanics
# --------------------------------------------------------------------------- #

def test_clearly_better_candidate_promotes():
    judge = RiggedJudge("judge0")
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", WEAK), judge)
    report = _run(PromotionArena(reg, "cand", "inc"), QUESTIONS_4)
    assert report["wins"] == 4 and report["losses"] == 0
    assert report["win_rate"] == 1.0
    assert report["promote"] is True and report["reason"] == "gate_passed"
    assert report["schema_version"] == ARENA_SCHEMA_VERSION


def test_worse_candidate_fails_gate():
    reg = _registry(RiggedDrafter("cand", WEAK),
                    RiggedDrafter("inc", STRONG), RiggedJudge("judge0"))
    report = _run(PromotionArena(reg, "cand", "inc"), QUESTIONS_4)
    assert report["losses"] == 4 and report["wins"] == 0
    assert report["promote"] is False and report["reason"] == "gate_failed"


def test_ties_decide_nothing():
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", STRONG), RiggedJudge("judge0"))
    report = _run(PromotionArena(reg, "cand", "inc"), QUESTIONS_4)
    assert report["ties"] == 4 and report["decided"] == 0
    assert report["promote"] is False
    assert report["reason"] == "insufficient_evidence"


def test_insufficient_questions_keeps_incumbent():
    # Candidate wins everything, but 2 decided < min_decided=3.
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", WEAK), RiggedJudge("judge0"))
    report = _run(PromotionArena(reg, "cand", "inc"), ["q1", "q2"])
    assert report["wins"] == 2
    assert report["promote"] is False
    assert report["reason"] == "insufficient_evidence"


def test_failed_draft_is_invalid_never_a_loss():
    reg = _registry(BrokenDrafter("cand"),
                    RiggedDrafter("inc", STRONG), RiggedJudge("judge0"))
    report = _run(PromotionArena(reg, "cand", "inc"), QUESTIONS_4)
    assert report["invalid"] == 4
    assert report["losses"] == 0 and report["wins"] == 0
    assert report["promote"] is False
    assert report["reason"] == "insufficient_evidence"
    assert all(r["reason"] == "draft_failed"
               for r in report["questions"] if not r["valid"])


def test_gate_boundary_is_inclusive():
    # 2 easy + 2 hard: candidate strong on easy, incumbent strong on hard →
    # wins=2, losses=2, win_rate=0.5. gate=0.5 → promote (>= semantics).
    reg = _registry(QuestionSensitiveDrafter("cand"),
                    QuestionSensitiveDrafter("inc", invert=True),
                    RiggedJudge("judge0"))
    questions = ["easy a", "easy b", "hard a", "hard b"]
    report = _run(PromotionArena(reg, "cand", "inc", gate=0.5, min_decided=3),
                  questions)
    assert report["wins"] == 2 and report["losses"] == 2
    assert report["win_rate"] == 0.5
    assert report["promote"] is True and report["reason"] == "gate_passed"
    # And the default AlphaGo gate (0.55) would refuse the same record.
    report_default = _run(PromotionArena(reg, "cand", "inc", min_decided=3),
                          questions)
    assert report_default["promote"] is False
    assert report_default["reason"] == "gate_failed"


# --------------------------------------------------------------------------- #
# Constitution: who may fight, who may judge
# --------------------------------------------------------------------------- #

def test_contenders_can_never_judge():
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", WEAK), RiggedJudge("judge0"))
    with pytest.raises(ValueError):
        PromotionArena(reg, "cand", "inc", judge_ids=["cand"])
    with pytest.raises(ValueError):
        PromotionArena(reg, "cand", "inc", judge_ids=["judge0", "inc"])


def test_needs_at_least_one_judge():
    reg = _registry(RiggedDrafter("cand", STRONG), RiggedDrafter("inc", WEAK))
    with pytest.raises(ValueError):
        PromotionArena(reg, "cand", "inc")


def test_config_validation():
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", WEAK), RiggedJudge("judge0"))
    with pytest.raises(ValueError):
        PromotionArena(reg, "cand", "cand")
    with pytest.raises(ValueError):
        PromotionArena(reg, "cand", "inc", gate=0.0)
    with pytest.raises(ValueError):
        PromotionArena(reg, "cand", "inc", min_decided=0)
    with pytest.raises(ValueError):
        PromotionArena(reg, "nope", "inc")


# --------------------------------------------------------------------------- #
# Anonymity of the judged payload
# --------------------------------------------------------------------------- #

def test_judge_sees_no_identities_and_labels_rotate():
    judge = RiggedJudge("judge0")
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", WEAK), judge)
    _run(PromotionArena(reg, "cand", "inc"), QUESTIONS_4)
    assert judge.seen
    for rec in judge.seen:
        assert set(rec["context"]) == {"output_to_score", "section"}
        blob = json.dumps(rec["context"]) + json.dumps(rec["schema"])
        for forbidden in ("cand", "inc", "candidate", "incumbent",
                          "provider_id", "model"):
            assert forbidden not in blob, f"judge payload leaked {forbidden!r}"
        assert rec["schema"]["_target"] in ("arena_draft_a", "arena_draft_b")
    # Rotation: the STRONG (candidate) draft is labelled a on even questions
    # and b on odd questions — no label systematically means "candidate".
    cand_labels = {rec["session_id"]: rec["schema"]["_target"]
                   for rec in judge.seen
                   if STRONG in rec["context"]["output_to_score"]}
    assert cand_labels["arena_q0"] == "arena_draft_a"
    assert cand_labels["arena_q1"] == "arena_draft_b"


# --------------------------------------------------------------------------- #
# Report shape + the human-promotes principle
# --------------------------------------------------------------------------- #

def test_report_shape_and_human_promotion_note():
    reg = _registry(RiggedDrafter("cand", STRONG),
                    RiggedDrafter("inc", WEAK), RiggedJudge("judge0"))
    report = _run(PromotionArena(reg, "cand", "inc"), QUESTIONS_4)
    for key in ("schema_version", "candidate", "incumbent", "judges", "gate",
                "min_decided", "questions", "wins", "losses", "ties",
                "decided", "invalid", "win_rate", "promote", "reason", "note"):
        assert key in report, f"missing report field {key}"
    assert report["gate"] == DEFAULT_PROMOTION_GATE
    assert report["judges"] == ["judge0"]
    assert "human" in report["note"]           # the arena reports; a human promotes
    valid_rows = [r for r in report["questions"] if r["valid"]]
    for r in valid_rows:
        assert {"candidate_score", "incumbent_score", "margin", "winner"} <= set(r)
