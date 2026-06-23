"""
PART 1 + PART 6 — deterministic task identity / async latency reproducibility.

move_id must derive from task identity (session_id, phase, agent_id, role,
task_kind, slot, attempt), NEVER from async completion order. Same session +
same question + same mock config → identical move_ids / winners / leaderboard /
audit counters / task_log context_hashes, regardless of provider latency.
"""

import asyncio
from unittest.mock import patch

import pytest

from backend.dialogues.models import DialogPhase, TaskKind, ShadowScoringMode
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)

Q = "Is knowledge merely justified true belief?"


def _ced(adapters):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    reg = CouncilProviderRegistry()
    for a in adapters:
        reg.register(a)
    return CEDOrchestrator(agents, provider, registry=reg)


def _registry_run(delays, sid):
    adapters = [ScriptedMockProvider(f"mock_{i}", delay_seconds=d) for i, d in enumerate(delays)]
    ced = _ced(adapters)
    final = asyncio.run(ced.run_registry_session(Q, session_id=sid, timeout_seconds=5.0))
    state = ced.get_session(sid)
    return final, state


def _signature(final, state):
    return {
        "move_ids": [m.move_id for m in state.moves],
        "winners": {s.section_name.value: s.selected_author_agent_id
                    for s in final.synthesis.sections},
        "leaderboard": final.socratic_leaderboard.average_scores_by_agent,
        "context_hashes": [e.context_hash for e in state.task_log],
        "scores_expected": final.audit_summary["score_coverage"]["scores_expected"],
    }


# ── Latency must not affect identity ─────────────────────────────────────────

def test_move_ids_independent_of_completion_order():
    # Run with varied latencies (completion order != submission order) vs no delay.
    f1, s1 = _registry_run([0.06, 0.0, 0.0], "lat-a")
    f2, s2 = _registry_run([0.0, 0.0, 0.0], "lat-a")
    assert [m.move_id for m in s1.moves] == [m.move_id for m in s2.moves]
    assert _signature(f1, s1)["winners"] == _signature(f2, s2)["winners"]


def test_same_session_fully_reproducible():
    f1, s1 = _registry_run([0.04, 0.02, 0.0], "lat-b")
    f2, s2 = _registry_run([0.04, 0.02, 0.0], "lat-b")
    assert _signature(f1, s1) == _signature(f2, s2)


def test_move_ids_unique_within_session():
    _f, s = _registry_run([0.0, 0.0], "lat-uniq")
    ids = [m.move_id for m in s.moves]
    assert len(set(ids)) == len(ids)


def test_different_provider_order_same_move_ids():
    # Provider order changes which adapter answers a slot, but content depends on
    # agent identity and move_id depends on task identity → identical either way.
    f1, s1 = _registry_run([0.0, 0.05, 0.0], "lat-ord")
    f2, s2 = _registry_run([0.05, 0.0, 0.0], "lat-ord")
    assert [m.move_id for m in s1.moves] == [m.move_id for m in s2.moves]


# ── Deterministic move_id in the standard pipeline too ───────────────────────

def test_standard_pipeline_move_ids_reproducible():
    def run(sid):
        p = FakeProvider()
        ced = CEDOrchestrator([SocraticAgent(f"agent_{i}", p) for i in range(4)], p)
        ced.run_session(Q, session_id=sid)
        return [m.move_id for m in ced.get_session(sid).moves]
    assert run("std-rep") == run("std-rep")


# ── Ratification: repeated evaluator gets distinct deterministic task_kind ────

def test_ratification_rounds_have_distinct_task_kind():
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"agent_{i}", p) for i in range(4)], p)
    sid = "rat-kinds"
    ced.create_session(Q, session_id=sid)
    for fn in [ced.run_opening_phase, ced.run_initial_response_phase,
               ced.run_elenchus_phase, ced.run_reflection_phase,
               ced.run_reconstruction_phase, ced.run_synthesis_phase]:
        fn(sid)
    ced.compute_shadow_scores(sid)
    ced.score_section_drafts(sid)
    ced.assemble_sections(sid)

    # Force two evaluator rounds: critical sectional objection, then approve.
    votes = [
        {"decision": "blocking_objection", "severity": "critical",
         "target_section": "core_answer", "reason": "overclaim"},
        {"decision": "approve", "severity": "none", "reason": "ok"},
    ]
    with patch.object(FakeProvider, "complete", side_effect=votes):
        ced.run_ratification_phase(sid)

    state = ced.get_session(sid)
    rat_moves = [m for m in state.moves if m.phase == DialogPhase.RATIFICATION]
    assert len(rat_moves) == 2
    kinds = [m.task_kind for m in rat_moves]
    assert kinds == [TaskKind.RATIFICATION_INITIAL, TaskKind.RATIFICATION_REVISION]
    assert rat_moves[0].move_id != rat_moves[1].move_id   # distinct, deterministic
