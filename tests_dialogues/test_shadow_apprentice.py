"""
Shadow Apprentice Mode tests (Goal 11, Stage 1).

Verifies the acceptance criteria mechanically:
  - shadow output is recorded separately from the council output
  - the final council answer is byte-identical with and without shadowing
  - the apprentice never sits in (or judges) the council it shadows
  - a shadow win requires STRICTLY beating the council winner (ties earn
    nothing); a failed apprentice draft is honest, never fabricated
  - the same selected memory lessons reach the apprentice (same context key
    the CED wiring uses)
  - judges see only section text + a neutral label (no apprentice identity)
  - shadow records feed the EXISTING 13.2 evidence path end-to-end:
    3 shadow wins -> identity gate v0.3 -> v0.4 passes
  - runtime isolation: the CED core never imports openclaw_shadow

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
from backend.dialogues.live_providers import build_council
from backend.dialogues.openclaw_identity import (
    evaluate_gate,
    evidence_from_shadow_traces,
    next_gate_for,
)
from backend.dialogues.openclaw_memory import load_stable_lessons
from backend.dialogues.openclaw_shadow import (
    SHADOW_SCHEMA_VERSION,
    ShadowApprentice,
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
                                   "confidence": 0.8, "justification": "rig",
                                   "penalty_flags": [],
                                   "provider_status": "ok"},
                       "confidence": 0.8})


class MarkerProvider(ScriptedMockProvider):
    """Drafts fixed-marker sections; scores 9.0 for STRONG text else 5.0.
    Records every task it receives (for spying in tests)."""

    def __init__(self, provider_id, marker=WEAK):
        super().__init__(provider_id)
        self.marker = marker
        self.seen = []

    async def _produce_raw_text(self, task, agent_state):
        self.seen.append({"task_kind": task.task_kind.value,
                          "context": dict(task.context),
                          "schema": dict(task.output_schema)})
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            return _draft_json(self.marker)
        if task.task_kind == TaskKind.SECTION_SCORE:
            text = str(task.context.get("output_to_score", ""))
            return _score_json(9.0 if STRONG in text else 5.0)
        return await super()._produce_raw_text(task, agent_state)


class BrokenApprentice(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            return "not json"
        return await super()._produce_raw_text(task, agent_state)


def _weak_council():
    """A 2-seat council whose drafts are WEAK and whose peers score by
    marker — assembled sections land at 5.0."""
    reg = CouncilProviderRegistry(provider_timeout_seconds=10.0)
    reg.register(MarkerProvider("council_seat0", WEAK))
    reg.register(MarkerProvider("council_seat1", WEAK))
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(2)]
    return CEDOrchestrator(agents, provider, registry=reg,
                           assembly_fallback=True,
                           shadow_scoring_mode=ShadowScoringMode.OFF)


def _runner(marker=STRONG, apprentice=None, lessons=None):
    return ShadowApprentice(
        apprentice or MarkerProvider("shadow_appr", marker),
        [MarkerProvider("shadow_judge0")],
        lessons=lessons)


def _shadow(runner, ced, question="q", sid="sh_1"):
    return asyncio.run(runner.shadow_session(ced, question, session_id=sid))


# --------------------------------------------------------------------------- #
# Record shape + separation
# --------------------------------------------------------------------------- #

def test_shadow_record_shape_and_marker():
    final, record = _shadow(_runner(), _weak_council())
    assert record["trace_version"] == SHADOW_SCHEMA_VERSION
    assert record["shadow_run"] is True                 # 13.2 marker
    assert record["ok"] is True
    assert record["apprentice_id"] == "shadow_appr"
    assert record["shadow_comparison"]                  # per-section rows
    assert final.ratified is True                       # council unaffected


def test_final_answer_identical_with_and_without_shadow():
    # Same question + session id on two separate weak councils: one plain,
    # one shadowed. Deterministic mocks -> byte-identical assembled answers.
    ced_plain = _weak_council()
    plain = asyncio.run(ced_plain.run_registry_session("q", session_id="cmp"))
    ced_shadowed = _weak_council()
    shadowed, _ = _shadow(_runner(), ced_shadowed, question="q", sid="cmp")
    plain_secs = {s.section_name: (s.content, s.average_score)
                  for s in ced_plain.get_session("cmp").assembled_answer.sections}
    shadow_secs = {s.section_name: (s.content, s.average_score)
                   for s in ced_shadowed.get_session("cmp").assembled_answer.sections}
    assert plain_secs == shadow_secs
    assert plain.ratified == shadowed.ratified
    # And the apprentice never appears in the council's own moves.
    council_providers = {m.provider_id
                         for m in ced_shadowed.get_session("cmp").moves}
    assert "shadow_appr" not in council_providers


def test_apprentice_inside_council_is_refused():
    ced = _weak_council()
    impostor = ShadowApprentice(MarkerProvider("council_seat0", STRONG),
                                [MarkerProvider("shadow_judge0")])
    with pytest.raises(ValueError, match="shadow"):
        asyncio.run(impostor.shadow_session(ced, "q", session_id="x"))


def test_apprentice_can_never_judge_itself():
    appr = MarkerProvider("shadow_appr", STRONG)
    with pytest.raises(ValueError, match="judge"):
        ShadowApprentice(appr, [appr])
    with pytest.raises(ValueError, match="judge"):
        ShadowApprentice(appr, [])


# --------------------------------------------------------------------------- #
# Win semantics: strictly beat the council, or earn nothing
# --------------------------------------------------------------------------- #

def test_strong_apprentice_wins_all_resolved_sections():
    final, record = _shadow(_runner(STRONG), _weak_council())
    assert record["shadow_wins"] == len(record["shadow_comparison"])
    for row in record["shadow_comparison"]:
        assert row["apprentice_score"] > row["council_score"]
    for sec in record["assembly"]["sections"]:
        assert sec["source_draft_id"].startswith("draft_shadow_")


def test_equal_apprentice_wins_nothing():
    # Apprentice drafts WEAK like the council -> judged 5.0 vs council 5.0:
    # a tie is not a win (burden of proof on the apprentice).
    final, record = _shadow(_runner(WEAK), _weak_council())
    assert record["shadow_wins"] == 0
    for sec in record["assembly"]["sections"]:
        assert not sec["source_draft_id"].startswith("draft_shadow_")


def test_failed_apprentice_draft_is_honest():
    final, record = _shadow(_runner(apprentice=BrokenApprentice("shadow_appr")),
                            _weak_council())
    assert record["ok"] is False
    assert record["reason"] == "apprentice_draft_failed"
    assert record["assembly"] is None and record["shadow_comparison"] == []
    assert final.ratified is True                       # council still fine


# --------------------------------------------------------------------------- #
# Lessons reach the apprentice (same key as the CED wiring)
# --------------------------------------------------------------------------- #

def test_lessons_reach_apprentice_context():
    appr = MarkerProvider("shadow_appr", STRONG)
    runner = _runner(apprentice=appr, lessons=load_stable_lessons())
    _, record = _shadow(runner, _weak_council(),
                        question="deliberation scoring assembly")
    assert record["lessons_selected"] > 0
    draft_tasks = [t for t in appr.seen
                   if t["task_kind"] == "synthesis_draft"]
    assert draft_tasks
    assert "openclaw_memory_lessons" in draft_tasks[0]["context"]


def test_no_matching_lessons_means_plain_context():
    appr = MarkerProvider("shadow_appr", STRONG)
    runner = _runner(apprentice=appr, lessons=load_stable_lessons())
    _, record = _shadow(runner, _weak_council(), question="xyzzy plugh")
    assert record["lessons_selected"] == 0
    draft_tasks = [t for t in appr.seen
                   if t["task_kind"] == "synthesis_draft"]
    assert "openclaw_memory_lessons" not in draft_tasks[0]["context"]


# --------------------------------------------------------------------------- #
# Judge anonymity
# --------------------------------------------------------------------------- #

def test_judges_see_neutral_label_only():
    judge = MarkerProvider("shadow_judge0")
    runner = ShadowApprentice(MarkerProvider("shadow_appr", STRONG), [judge])
    _shadow(runner, _weak_council())
    score_tasks = [t for t in judge.seen
                   if t["task_kind"] == "section_score"]
    assert score_tasks
    for t in score_tasks:
        assert set(t["context"]) == {"output_to_score", "section"}
        assert t["schema"]["_target"] == "shadow_draft_a"
        blob = json.dumps(t["context"]) + json.dumps(t["schema"])
        assert "shadow_appr" not in blob


# --------------------------------------------------------------------------- #
# End-to-end into the identity gate (the whole Stage-1 story)
# --------------------------------------------------------------------------- #

def test_shadow_wins_feed_identity_gate_v0_3():
    runner = _runner(STRONG)
    for i in range(3):
        _shadow(runner, _weak_council(), question=f"q{i}", sid=f"gate_{i}")
    evidence = evidence_from_shadow_traces("shadow_appr",
                                           runner.shadow_records)
    assert evidence["shadow_blind_spots_wins"] == 3
    assert evidence["shadow_sessions_analyzed"] == 3
    assert evidence["shadow_session_ids"] == ["gate_0", "gate_1", "gate_2"]
    gate = next_gate_for("v0.3")
    assert evaluate_gate(gate, evidence).passed is True
    # And the same wins by an apprentice that never won pass nothing.
    weak_runner = _runner(WEAK)
    for i in range(3):
        _shadow(weak_runner, _weak_council(), question=f"q{i}", sid=f"w_{i}")
    weak_evidence = evidence_from_shadow_traces("shadow_appr",
                                                weak_runner.shadow_records)
    assert evaluate_gate(gate, weak_evidence).passed is False


# --------------------------------------------------------------------------- #
# Runtime isolation
# --------------------------------------------------------------------------- #

def test_ced_core_never_imports_shadow_package():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "backend" / "dialogues"
    for name in ("ced.py", "live_providers.py", "provider_registry.py",
                 "models.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "openclaw_shadow" not in source, (
            f"{name} must not import the shadow package — Stage 1 shadows "
            "never touch the council")


def test_works_with_default_mock_council_too():
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF)
    runner = _runner(STRONG)
    final, record = _shadow(runner, ced, question="test", sid="dflt_1")
    assert record["ok"] is True and final is not None
    assert isinstance(record["shadow_wins"], int)
