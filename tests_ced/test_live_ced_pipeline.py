"""Live CED pipeline tests.

These prove the production dialog path is no longer only post-hoc replay:
responses become live EpistemicGraph claims during the round, Elenchus targets a
specific claim_id, and synthesis is a CurrentBestExplanation-derived result.
"""

import asyncio

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.epistemic.epistemic_graph import NodeType
from backend.orchestrator.session import EnhancedDialogSession, session_manager
from backend.orchestrator import dialog_pipeline_ced


class _FakeManager:
    async def _call_model(self, model_id, prompt):
        if "CLAIM_ID:" in prompt or "challenge this exact claim" in prompt.lower():
            return (
                '{"challenged_assumptions":["assumes the premise holds"],'
                '"logic_gaps":["inference is incomplete"],'
                '"evidence_issues":[],"conclusion_issues":[],'
                '"falsification_successful":false}'
            )
        return "INITIAL: a\nCRITICISM: b\nREVISION: c\nFINAL: Knowledge requires justified claims and surviving critique."


def _make_session(sid, rounds=2):
    cfg = DialogConfig(
        topic="Is knowledge justified true belief?",
        rounds=rounds,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    s = EnhancedDialogSession(sid, cfg, {"claude": "x", "chatgpt": "y"})
    s.manager = _FakeManager()
    s.enforced_rounds = rounds
    session_manager._sessions[sid] = s
    return s


def test_live_pipeline_creates_epistemic_graph_claims():
    s = _make_session("test_live_ced_1")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))

    assert hasattr(s, "epistemic_graph")
    assert len(s.epistemic_graph.claims) > 0
    assert len(s.epistemic_graph.active_claims()) > 0


def test_socratic_questions_are_question_nodes_not_claims():
    s = _make_session("test_live_ced_2")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))

    question_nodes = [n for n in s.epistemic_graph.nodes.values()
                      if n.node_type == NodeType.QUESTION]
    assert question_nodes, "Socratic/root questions must be represented as Question nodes"


def test_elenchus_targets_specific_claim_id():
    s = _make_session("test_live_ced_3")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))

    assert s.elenchus_history
    assert all(getattr(e, "target_claim_id", None) for e in s.elenchus_history)
    assert all(getattr(e, "target_claim_id") in s.epistemic_graph.claims
               for e in s.elenchus_history)


def test_synthesis_uses_current_best_explanation():
    s = _make_session("test_live_ced_4")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))

    assert s.current_best_explanation is not None
    assert s.current_best_explanation.to_dict()["label"] == "Current Best Explanation"
    assert s.synthesis_result is not None
    assert s.synthesis_result.emerged_from_dialogue is True


def test_history_is_trace_not_source_of_truth():
    s = _make_session("test_live_ced_5")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))

    assert s.history, "dialogue history remains available as trace"
    assert s.epistemic_graph.claims, "EpistemicGraph is the live source of truth"
    assert s.current_best_explanation.reasoning_trace
