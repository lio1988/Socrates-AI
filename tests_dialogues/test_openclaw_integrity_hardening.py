"""
Adversarial regression tests for the OpenClaw integrity hardening pass.

These tests target failure modes that happy-path tests can miss:
- shadow evidence must use council-ledger lesson ids and matched-pair judging
- lesson A/B cannot hide coverage regressions behind a higher mean
- a forged GateResult cannot promote an identity
- trace secret checks must run before memory/disk mutation
- prompt lineage distinguishes composition from exact rendering and versions
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
from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    GateResult,
    record_promotion,
)
from backend.dialogues.openclaw_memory import (
    TraceCapturer,
    load_stable_lessons,
    run_lesson_ab,
)
from backend.dialogues.openclaw_prompts import (
    PromptRegistry,
    PromptSpec,
    prompt_fingerprint,
    render_prompt_with_metadata,
)
from backend.dialogues.openclaw_shadow import ShadowApprentice


_SECTIONS = (
    "core_answer",
    "crucial_stress_test",
    "blind_spots",
    "nuance",
    "final_verdict",
)


def _draft_json(marker):
    return json.dumps({
        "content": {name: f"{marker} {name}" for name in _SECTIONS},
        "confidence": 0.8,
    })


def _score_json(value):
    breakdown = {key: value for key in ScoreBreakdown.model_fields}
    return json.dumps({
        "content": {
            "score_breakdown": breakdown,
            "confidence": 0.8,
            "justification": "integrity-rig",
            "penalty_flags": [],
            "provider_status": "ok",
        },
        "confidence": 0.8,
    })


class _MarkerProvider(ScriptedMockProvider):
    def __init__(self, provider_id, marker="WEAK"):
        super().__init__(provider_id)
        self.marker = marker

    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            return _draft_json(self.marker)
        if task.task_kind == TaskKind.SECTION_SCORE:
            text = str(task.context.get("output_to_score", ""))
            return _score_json(9.0 if "STRONG" in text else 5.0)
        return await super()._produce_raw_text(task, agent_state)


def _lesson_council(lessons):
    registry = CouncilProviderRegistry(provider_timeout_seconds=10.0)
    registry.register(_MarkerProvider("council_seat0", "WEAK"))
    registry.register(_MarkerProvider("council_seat1", "WEAK"))
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{index}", provider) for index in range(2)]
    return CEDOrchestrator(
        agents,
        provider,
        registry=registry,
        assembly_fallback=True,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        openclaw_lessons=lessons,
    )


def test_shadow_uses_exact_council_synthesis_ledger_and_matched_scores():
    lessons = load_stable_lessons()
    council = _lesson_council(lessons)
    runner = ShadowApprentice(
        _MarkerProvider("shadow_apprentice", "STRONG"),
        [_MarkerProvider("shadow_judge")],
        lessons=lessons,
    )

    final, record = asyncio.run(runner.shadow_session(
        council,
        "xyzzy plugh — no keyword match",
        session_id="integrity_shadow",
    ))

    audit = final.audit_summary["openclaw_lessons"]
    expected = []
    for injection in audit["injections"]:
        if injection["phase"] == "synthesis":
            for lesson_id in injection["lesson_ids"]:
                if lesson_id not in expected:
                    expected.append(lesson_id)

    assert expected
    assert record["lesson_source"] == "council_injection_ledger"
    assert record["lesson_ids"] == expected
    assert record["lessons_selected"] == len(expected)
    assert record["shadow_comparison"]
    assert all(row["matched_judges"] == 1
               for row in record["shadow_comparison"])
    assert all("original_council_score" in row
               for row in record["shadow_comparison"])


def test_lesson_ab_unresolved_regression_vetoes_higher_mean(monkeypatch):
    import backend.dialogues.openclaw_memory.lesson_ab as module

    class FakeCED:
        def __init__(self, arm):
            self.arm = arm

        async def run_registry_session(self, question, session_id):
            return object()

    def factory(openclaw_lessons):
        return FakeCED("treatment" if openclaw_lessons is not None else "control"), "fake"

    def outcome(ced, session_id, final):
        if ced.arm == "control":
            return {
                "ratified": True,
                "mean_section_score": 8.0,
                "resolved_sections": 5,
                "unresolved_sections": 0,
                "lessons_selected": 0,
                "lesson_ids": [],
            }
        return {
            "ratified": True,
            "mean_section_score": 9.0,
            "resolved_sections": 4,
            "unresolved_sections": 1,
            "lessons_selected": 1,
            "lesson_ids": ["LESSON-X"],
        }

    monkeypatch.setattr(module, "_arm_outcome", outcome)
    report = asyncio.run(run_lesson_ab(
        ["q"],
        [object()],
        council_factory=factory,
    ))

    assert report["mean_score_delta"] == 1.0
    assert report["unresolved_regressions"] == 1
    assert report["helped"] is False
    assert report["verdict"] == "harmed"


def test_forged_gate_result_cannot_promote():
    profile = AgentIdentityProfile(agent_id="agent_a")
    forged = GateResult(
        gate_id="gate_v0_1_to_v0_2",
        passed=True,
        reasons=("trust me",),
        evidence_used={},
    )
    with pytest.raises(ValueError, match="independently re-evaluated"):
        record_promotion(
            profile,
            forged,
            approved_by="operator",
        )


def test_trace_secret_guard_runs_before_capture_mutation():
    capturer = TraceCapturer(metadata={"api_key": "must-not-persist"})
    from backend.dialogues.live_providers import build_council

    ced, _ = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        trace_capturer=capturer,
    )
    final = asyncio.run(ced.run_registry_session(
        "trace secret test",
        session_id="trace_secret_guard",
    ))

    assert capturer.traces == []
    assert final.audit_summary["trace_capture_error"] is True


def test_prompt_registry_versions_and_exact_render_hash():
    spec_v1 = PromptSpec(
        prompt_id="synthesis",
        version_label="v0.1",
        description="v1",
        base_text="Question: {{question}}\n\n{{memory_lessons}}",
        required_variables=("question",),
    )
    spec_v2 = PromptSpec(
        prompt_id="synthesis",
        version_label="v0.2",
        description="v2",
        base_text="Answer carefully.\nQuestion: {{question}}\n\n{{memory_lessons}}",
        required_variables=("question",),
    )
    registry = PromptRegistry()
    registry.register(spec_v1)
    registry.register(spec_v2)

    assert registry.get("synthesis", "v0.1") is spec_v1
    assert registry.get("synthesis", "v0.2") is spec_v2
    with pytest.raises(ValueError, match="multiple versions"):
        registry.get("synthesis")

    rendered_a, metadata_a = render_prompt_with_metadata(
        spec_v1,
        {"question": "What is knowledge?", "memory_lessons": "LESSON-1"},
    )
    rendered_b, metadata_b = render_prompt_with_metadata(
        spec_v1,
        {"question": "What is knowledge?", "memory_lessons": "LESSON-2"},
    )

    assert rendered_a != rendered_b
    assert prompt_fingerprint(spec_v1) == metadata_a["composition_fingerprint"]
    assert metadata_a["composition_fingerprint"] == \
        metadata_b["composition_fingerprint"]
    assert metadata_a["rendered_prompt_fingerprint"] != \
        metadata_b["rendered_prompt_fingerprint"]
