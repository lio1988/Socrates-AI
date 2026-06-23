"""
Phase 8C.1 — Socratic Council Ratification (council-level, registry-backed).

Council ratification is NOT majority voting. CED does not count ACCEPT votes to
decide truth: it checks quorum, validates verdict schemas, detects structurally
valid CRITICAL blocking objections, and applies deterministic protocol rules.
No single Final Evaluator monopoly; no fabricated ACCEPT.
"""

import asyncio
from unittest.mock import patch

import pytest

from backend.dialogues.models import (
    CouncilRatificationStatus, CouncilVerdict, FinalSynthesisMode,
    DialogPhase, TaskKind,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, CaveatRatifierProvider,
    BlockingObjectionProvider, TimeoutScriptedProvider,
)

Q = "Is knowledge merely justified true belief?"


def _build(provs, **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pr in provs:
        reg.register(pr)
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _run(provs, sid, **kw):
    ced = _build(provs, **kw)
    final = asyncio.run(ced.run_registry_session(Q, session_id=sid))
    return ced, ced.get_session(sid), final


class _InvalidVerdictProvider(ScriptedMockProvider):
    """Valid deliberation content, but an UNRECOGNISED verdict at ratification."""
    def __init__(self, provider_id, **kw):
        super().__init__(provider_id, **kw)

    def _ratification_verdict(self, task):
        return {"verdict": "not_a_real_verdict", "rationale": "x"}


# 1 — ratification tasks go to ALL valid participating providers ──────────────

def test_ratification_sent_to_all_valid_providers():
    ced, state, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"), ScriptedMockProvider("p_c")],
        "cr-all")
    cr = final.audit_summary["council_ratification"]
    assert {v["provider_id"] for v in cr["verdicts"]} == {"p_a", "p_b", "p_c"}
    # every ratification task is traced with task_kind=council_ratification
    rat_log = [e for e in state.task_log if e.task_kind == TaskKind.COUNCIL_RATIFICATION]
    assert {e.agent_id for e in rat_log} == {"p_a", "p_b", "p_c"}


# 2 — RATIFIED when quorum met and no caveats/blocks ─────────────────────────

def test_ratified_when_all_accept():
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b")], "cr-ok")
    assert final.ratification_status == CouncilRatificationStatus.RATIFIED.value
    assert final.ratified is True
    assert final.answer


# 3 — RATIFIED_WITH_CAVEATS when caveats exist, no critical block ─────────────

def test_ratified_with_caveats():
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"), CaveatRatifierProvider("p_cav")],
        "cr-cav")
    assert final.ratification_status == CouncilRatificationStatus.RATIFIED_WITH_CAVEATS.value
    assert final.ratified is True
    assert final.audit_summary["council_ratification"]["caveat_count"] >= 1


# 4 + 12 — a schema-valid CRITICAL block blocks; ACCEPT majority cannot override

def test_critical_block_blocks_even_against_accept_majority():
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"),
         ScriptedMockProvider("p_c"), BlockingObjectionProvider("p_block")], "cr-block")
    cr = final.audit_summary["council_ratification"]
    assert final.ratification_status == CouncilRatificationStatus.REPAIR_REQUIRED.value
    assert final.ratified is False
    assert cr["critical_block_count"] == 1
    # 3 ACCEPT did NOT override 1 critical block (not majority voting)
    accepts = sum(1 for v in cr["verdicts"] if v["verdict"] == "accept")
    assert accepts == 3
    assert final.answer == ""        # non-ratified answer is not released


# 9 — blocking objection attributed to the exact provider that raised it ─────

def test_blocking_objection_is_attributed():
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"),
         BlockingObjectionProvider("p_block", target_section="nuance")], "cr-attr")
    objs = final.audit_summary["council_ratification"]["attributed_critical_objections"]
    assert len(objs) == 1
    assert objs[0]["provider_id"] == "p_block"
    assert objs[0]["target_section"] == "nuance"
    assert objs[0]["required_fix"]


# 5 + 8 — quorum failure / invalid verdicts never fabricate ACCEPT ───────────

def test_quorum_failure_does_not_fabricate_acceptance():
    # deliberation succeeds (all produce content), but only 1 valid verdict < quorum 2
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"),
         _InvalidVerdictProvider("p_bad1"), _InvalidVerdictProvider("p_bad2")], "cr-quorum")
    assert final.ratification_status == CouncilRatificationStatus.RATIFICATION_QUORUM_FAILED.value
    assert final.ratified is False
    assert final.answer == ""


# 6 — no valid verdicts → RATIFICATION_FAILED ────────────────────────────────

def test_no_valid_verdicts_failed_status():
    _ced, _st, final = _run(
        [_InvalidVerdictProvider("p_bad1"), _InvalidVerdictProvider("p_bad2"),
         _InvalidVerdictProvider("p_bad3")], "cr-failed")
    assert final.ratification_status == CouncilRatificationStatus.RATIFICATION_FAILED.value
    assert final.ratified is False


# 7 — provider timeout at ratification is audited, no fake ACCEPT ─────────────

class _RatTimeoutProvider(ScriptedMockProvider):
    """Valid deliberation, but times out specifically at ratification."""
    async def generate_agent_move(self, task, agent_state):
        if task.task_kind == TaskKind.COUNCIL_RATIFICATION:
            from backend.dialogues.models import ProviderResponse, ProviderStatus
            return ProviderResponse(provider_id=self.provider_id, agent_id=task.agent_id,
                                    status=ProviderStatus.TIMEOUT, error_message="rat timeout")
        return await super().generate_agent_move(task, agent_state)


def test_ratification_timeout_audited_no_fake_accept():
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"),
         _RatTimeoutProvider("p_to")], "cr-timeout")
    cr = final.audit_summary["council_ratification"]
    assert "p_to" in cr["timed_out_providers"]
    assert all(v["provider_id"] != "p_to" for v in cr["verdicts"])   # no fabricated verdict
    # the two real ACCEPTs still meet quorum
    assert final.ratification_status == CouncilRatificationStatus.RATIFIED.value


# 10 — no single Final Evaluator monopoly in registry mode ───────────────────

def test_no_single_evaluator_monopoly():
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"), ScriptedMockProvider("p_c")],
        "cr-mono")
    verdicts = final.audit_summary["council_ratification"]["verdicts"]
    assert len(verdicts) >= 3          # every provider votes; not one authority


# 13 — CED applies structural rules only (no semantic judgement) ─────────────

def test_ced_uses_structural_not_semantic_rules():
    # A blocking objection MISSING required_fix is NOT a schema-valid critical
    # block → it does not block (CED checks structure, not philosophical strength).
    class _IncompleteBlocker(ScriptedMockProvider):
        def _ratification_verdict(self, task):
            return {"verdict": "blocking_objection", "severity": "critical",
                    "target_section": "core_answer", "rationale": "vague concern"}
            # no required_fix → structurally invalid critical block
    _ced, _st, final = _run(
        [ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b"), _IncompleteBlocker("p_inc")],
        "cr-struct")
    # treated as a (non-critical) caveat, not a block
    assert final.ratification_status == CouncilRatificationStatus.RATIFIED_WITH_CAVEATS.value
    assert final.audit_summary["council_ratification"]["critical_block_count"] == 0


# 11 — explicitly NOT majority voting ────────────────────────────────────────

def test_not_majority_voting_single_block_wins():
    # 5 ACCEPT vs 1 CRITICAL block → blocked. Majority would have accepted.
    provs = [ScriptedMockProvider(f"p_{i}") for i in range(5)] + [BlockingObjectionProvider("p_block")]
    _ced, _st, final = _run(provs, "cr-nomaj")
    assert final.ratification_status == CouncilRatificationStatus.REPAIR_REQUIRED.value
    assert final.ratified is False


# 14 — minimal awareness: ratification task carries no hidden internals ───────

def test_ratification_task_minimal_awareness():
    ced = _build([ScriptedMockProvider("p_a"), ScriptedMockProvider("p_b")])
    captured = {}
    reg = ced.registry
    orig = reg.run_adapter

    async def cap(adapter, task, agent_state, timeout_seconds=None):
        if task.task_kind == TaskKind.COUNCIL_RATIFICATION:
            captured[task.agent_id] = task
        return await orig(adapter, task, agent_state, timeout_seconds)

    with patch.object(reg, "run_adapter", cap):
        asyncio.run(ced.run_registry_session(Q, session_id="cr-ma"))

    assert captured
    for task in captured.values():
        blob = (str(task.context) + " " + str(task.output_schema)).lower()
        for kw in ("leaderboard", "score_breakdown", "overall_score", "coverage_ratio",
                   "task_log", "provider_status_summary", "micro_score", "api_key"):
            assert kw not in blob
    # AgentState carries no ratification internals either
    state = ced.get_session("cr-ma")
    for ast in state.agent_states.values():
        assert "council_ratification" not in ast.model_dump()


# 15 — run_session remains backward-compatible (single-evaluator path) ───────

def test_run_session_backward_compatible():
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"agent_{i}", p) for i in range(4)], p)
    final = ced.run_session(Q, session_id="cr-bc")
    assert final.ratified is True
    assert "council_ratification" not in final.audit_summary   # not a council session


# reserved modes raise (tournament/hybrid kept for V2/V3, no logic added) ─────

def test_reserved_modes_not_implemented():
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    for mode in (FinalSynthesisMode.CANDIDATE_TOURNAMENT, FinalSynthesisMode.HYBRID):
        with pytest.raises(NotImplementedError):
            CEDOrchestrator(agents, p, final_synthesis_mode=mode)
