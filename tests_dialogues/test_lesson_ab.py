"""
Lesson effectiveness A/B harness tests (Goal 6.1 — closes lesson poisoning).

Rigged providers make the effect controllable end-to-end THROUGH the real CED
wiring: a drafter that produces STRONG content only when lessons actually
reached its deliberation context, and a scorer that rewards STRONG content.
So a "helped" verdict proves the whole pipeline (injection -> behavioral
effect -> blind scoring -> measurement), and an inverted rig proves the
harness DETECTS a poisonous lesson pool.

No network, no keys — mock adapters only.
"""

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import ScoreBreakdown, ShadowScoringMode, TaskKind
from backend.dialogues.providers import FakeProvider
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.openclaw_memory import (
    AB_SCHEMA_VERSION,
    load_stable_lessons,
    run_lesson_ab,
)

STRONG = "STRONGCONTENT"
WEAK = "WEAKCONTENT"
_SECTIONS = ("core_answer", "crucial_stress_test", "blind_spots",
             "nuance", "final_verdict")

#: matches stable-pool keyword triggers -> retrieval selects lessons
MATCHING_QUESTION = "deliberation scoring assembly"


def _draft_json(marker):
    return json.dumps({"content": {f: f"{marker} {f}" for f in _SECTIONS},
                       "confidence": 0.8})


def _score_json(value):
    breakdown = {k: value for k in ScoreBreakdown.model_fields}
    return json.dumps({"content": {"score_breakdown": breakdown,
                                   "confidence": 0.8, "justification": "rig",
                                   "penalty_flags": [],
                                   "provider_status": "ok"},
                       "confidence": 0.8})


class LessonSensitiveProvider(ScriptedMockProvider):
    """Drafts STRONG sections only when lessons reached its context (via the
    REAL injection key), and scores STRONG content higher when judging."""

    def __init__(self, provider_id, invert=False):
        super().__init__(provider_id)
        self.invert = invert

    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            has_lessons = "openclaw_memory_lessons" in (task.context or {})
            strong = has_lessons != self.invert
            return _draft_json(STRONG if strong else WEAK)
        if task.task_kind == TaskKind.SECTION_SCORE:
            text = str(task.context.get("output_to_score", ""))
            return _score_json(9.0 if STRONG in text else 5.0)
        return await super()._produce_raw_text(task, agent_state)


def _rigged_factory(invert=False):
    def factory(openclaw_lessons):
        reg = CouncilProviderRegistry(provider_timeout_seconds=10.0)
        reg.register(LessonSensitiveProvider("seat0", invert))
        reg.register(LessonSensitiveProvider("seat1", invert))
        provider = FakeProvider()
        agents = [SocraticAgent(f"agent_{i}", provider) for i in range(2)]
        ced = CEDOrchestrator(agents, provider, registry=reg,
                              assembly_fallback=True,
                              shadow_scoring_mode=ShadowScoringMode.OFF,
                              openclaw_lessons=openclaw_lessons)
        return ced, "mock"
    return factory


@pytest.fixture(scope="module")
def stable_pool():
    return load_stable_lessons()


def _run(questions, lessons, **kw):
    return asyncio.run(run_lesson_ab(questions, lessons, **kw))


# --------------------------------------------------------------------------- #
# The full pipeline: injection -> effect -> measurement
# --------------------------------------------------------------------------- #

def test_helpful_lessons_measured_as_helped(stable_pool):
    report = _run([MATCHING_QUESTION], stable_pool,
                  council_factory=_rigged_factory())
    assert report["schema_version"] == AB_SCHEMA_VERSION
    assert report["tested"] == 1
    assert report["mean_score_delta"] > 0
    assert report["improved"] == 1
    assert report["helped"] is True and report["verdict"] == "helped"
    row = report["questions"][0]
    assert row["valid"] is True
    assert row["treatment"]["lessons_selected"] > 0    # real injection happened
    assert row["treatment"]["mean_section_score"] > row["control"]["mean_section_score"]


def test_poisonous_lessons_detected_as_harmed(stable_pool):
    # Inverted rig: the drafter gets WORSE when lessons are present.
    report = _run([MATCHING_QUESTION], stable_pool,
                  council_factory=_rigged_factory(invert=True))
    assert report["tested"] == 1
    assert report["mean_score_delta"] < 0
    assert report["worsened"] == 1
    assert report["helped"] is False and report["verdict"] == "harmed"


def test_no_selection_means_untested():
    # A pool whose only lesson type matches NO deliberation phase and no
    # keyword of the question: nothing is ever injected, the arms are
    # trivially identical — honest "untested", never a verdict. (A pool of
    # stable lessons does NOT qualify: runtime retrieval is phase-aware and
    # injects phase-matched lessons even for keyword-less questions — the
    # injected-context ledger made the audit report that reality.)
    from backend.dialogues.openclaw_memory import MemoryLesson
    unmatched_pool = [MemoryLesson(
        lesson_id="LESSON-0999", name="Ratification-only lesson",
        status="stable", lesson_type="ratification_quality",
        source="test", use_when=(), problem_pattern="p",
        bad_pattern="b", good_pattern="g",
        lesson="Verify the verdict follows the stress test.", risk="r")]
    report = _run(["xyzzy plugh"], unmatched_pool,
                  council_factory=_rigged_factory())
    assert report["tested"] == 0 and report["untested"] == 1
    assert report["questions"][0]["reason"] == "no_lessons_selected"
    assert report["helped"] is False and report["verdict"] == "untested"


# --------------------------------------------------------------------------- #
# Default mock council: mechanics only (context-insensitive mocks tie)
# --------------------------------------------------------------------------- #

def test_default_council_mechanics(stable_pool):
    report = _run([MATCHING_QUESTION], stable_pool)
    for key in ("schema_version", "lesson_ids", "questions", "tested",
                "untested", "invalid", "mean_score_delta", "improved",
                "worsened", "unchanged", "ratification_gains",
                "ratification_regressions", "helped", "verdict", "note"):
        assert key in report, f"missing report field {key}"
    assert report["tested"] == 1
    # Deterministic mocks ignore context -> the arms tie exactly.
    assert report["mean_score_delta"] == 0.0
    assert report["verdict"] == "no_effect" and report["helped"] is False


# --------------------------------------------------------------------------- #
# Honesty rules
# --------------------------------------------------------------------------- #

def test_requires_lessons():
    with pytest.raises(ValueError):
        _run([MATCHING_QUESTION], [])


def test_min_delta_threshold(stable_pool):
    report = _run([MATCHING_QUESTION], stable_pool,
                  council_factory=_rigged_factory(), min_delta=100.0)
    assert report["mean_score_delta"] > 0          # effect exists...
    assert report["helped"] is False               # ...but below the bar
    assert report["verdict"] == "no_effect"


def test_harness_reports_human_promotes(stable_pool):
    report = _run([MATCHING_QUESTION], stable_pool,
                  council_factory=_rigged_factory())
    assert "human" in report["note"]
    # The lessons themselves are untouched (frozen records, no status flip).
    assert all(lesson.status in ("stable", "verified") for lesson in stable_pool)
