"""Fail-closed tests for Shadow Apprentice evidence integrity."""

import asyncio

from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode, TaskKind
from backend.dialogues.provider_registry import ScriptedMockProvider
from backend.dialogues.openclaw_memory import load_stable_lessons
from backend.dialogues.openclaw_shadow import ShadowApprentice


class InvalidScoreJudge(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SECTION_SCORE:
            return "not valid json"
        return await super()._produce_raw_text(task, agent_state)


def test_shadow_fails_when_council_ledger_ids_are_missing_from_apprentice_pool():
    lessons = load_stable_lessons()
    council, _ = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        openclaw_lessons=lessons,
    )
    runner = ShadowApprentice(
        ScriptedMockProvider("shadow_apprentice"),
        [ScriptedMockProvider("external_judge")],
        lessons=[],
    )

    final, record = asyncio.run(runner.shadow_session(
        council,
        "xyzzy plugh",
        session_id="shadow_pool_mismatch",
    ))

    expected = []
    for injection in final.audit_summary["openclaw_lessons"]["injections"]:
        if injection["phase"] == "synthesis":
            for lesson_id in injection["lesson_ids"]:
                if lesson_id not in expected:
                    expected.append(lesson_id)

    assert expected
    assert record["ok"] is False
    assert record["reason"] == "lesson_pool_mismatch"
    assert record["missing_lesson_ids"] == expected
    assert record["shadow_comparison"] == []
    assert record["shadow_wins"] == 0
    assert final is not None                     # council result remains intact


def test_shadow_fails_when_no_complete_matched_score_pair_exists():
    council, _ = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
    )
    runner = ShadowApprentice(
        ScriptedMockProvider("shadow_apprentice"),
        [InvalidScoreJudge("broken_judge")],
    )

    final, record = asyncio.run(runner.shadow_session(
        council,
        "matched pair failure",
        session_id="shadow_no_matched_pair",
    ))

    assert record["ok"] is False
    assert record["reason"] == "no_eligible_matched_comparisons"
    assert record["shadow_comparison"] == []
    assert record["shadow_wins"] == 0
    assert final is not None
