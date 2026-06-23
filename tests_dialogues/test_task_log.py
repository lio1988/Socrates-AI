"""
PART 4 — CED-owned task_log (traceability, hidden from agents).
"""

import asyncio
from unittest.mock import patch

import pytest

from backend.dialogues.models import DialogPhase
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, TimeoutScriptedProvider,
)

Q = "Is knowledge merely justified true belief?"


def _std_run(sid):
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"agent_{i}", p) for i in range(4)], p)
    ced.run_session(Q, session_id=sid)
    return ced.get_session(sid)


# ── Every move has a task trace ──────────────────────────────────────────────

def test_every_move_has_a_task_log_entry():
    st = _std_run("tl-trace")
    logged_move_ids = {e.move_id for e in st.task_log if e.move_id is not None}
    for m in st.moves:
        assert m.move_id in logged_move_ids
    # entries carry identity, never a raw key
    e = st.task_log[0]
    assert e.task_id and e.context_hash and e.schema_name
    assert e.task_kind is not None


def test_context_hash_stable_across_runs():
    s1 = _std_run("tl-hash")
    s2 = _std_run("tl-hash")
    assert [e.context_hash for e in s1.task_log] == [e.context_hash for e in s2.task_log]


def test_debug_context_off_by_default():
    st = _std_run("tl-debug")
    assert all(e.debug_context is None for e in st.task_log)


def test_debug_context_can_be_enabled():
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"agent_{i}", p) for i in range(4)], p)
    ced.debug_task_log = True
    ced.run_session(Q, session_id="tl-on")
    st = ced.get_session("tl-on")
    assert any(e.debug_context is not None for e in st.task_log)


# ── Hidden from agents ───────────────────────────────────────────────────────

def test_task_log_not_in_agentstate():
    st = _std_run("tl-ma")
    for ast in st.agent_states.values():
        assert "task_log" not in ast.model_dump()


def test_task_log_not_in_agent_task_context():
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"agent_{i}", p) for i in range(4)], p)
    captured = []
    original = SocraticAgent.execute

    def cap(self, task):
        captured.append(task)
        return original(self, task)

    with patch.object(SocraticAgent, "execute", cap):
        ced.run_session(Q, session_id="tl-ctx")

    for task in captured:
        blob = str(task.context).lower()
        for kw in ("task_log", "context_hash", "provider_status", "api_key"):
            assert kw not in blob


# ── Failed providers get a trace with no move ────────────────────────────────

def test_failed_provider_logged_without_move():
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    reg.register(ScriptedMockProvider("mock_a"))
    reg.register(ScriptedMockProvider("mock_b"))
    reg.register(TimeoutScriptedProvider())
    ced = CEDOrchestrator(agents, p, registry=reg)
    asyncio.run(ced.run_registry_session(Q, session_id="tl-fail"))
    st = ced.get_session("tl-fail")
    no_move = [e for e in st.task_log if e.move_id is None]
    assert no_move, "failed-provider tasks must still be traced"
    assert all(e.provider_status is not None for e in no_move)


# ── task_log appears in CED-owned audit ──────────────────────────────────────

def test_task_log_count_in_registry_audit():
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    reg.register(ScriptedMockProvider("mock_a"))
    reg.register(ScriptedMockProvider("mock_b"))
    ced = CEDOrchestrator(agents, p, registry=reg)
    final = asyncio.run(ced.run_registry_session(Q, session_id="tl-audit"))
    assert final.audit_summary["task_log_count"] > 0
    assert "task_log_summary" in final.audit_summary
