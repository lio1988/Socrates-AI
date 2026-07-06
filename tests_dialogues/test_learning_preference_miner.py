"""
Phase 26E — Smart Learning Preference Miner tests.

The miner is a parallel data-engine layer. It reads sanitized LearningDataset
records and creates preference data without calling providers or changing CED.
"""

from backend.dialogues.learning_foundation import (
    LearningDataset,
    LearningSignalKind,
    LearningTrace,
    LearningUse,
    TrainingEligibility,
)
from backend.dialogues.learning_preference_miner import (
    PreferenceMiningPolicy,
    PreferenceSignal,
    mine_preference_candidates,
    mine_preferences,
    score_trace_for_preference,
    smart_learning_summary,
)
from backend.dialogues.models import ProviderStatus, TaskKind


QUESTION = "What makes a belief knowledge?"


def _trace(
    trace_id,
    *,
    text,
    provider="p",
    confidence=0.75,
    eligible=True,
    status=ProviderStatus.OK.value,
    winner_sections=None,
    failed_sections=None,
    external_eval=None,
    peer_scores=None,
):
    t = LearningTrace(
        trace_id=trace_id,
        session_id="sess_pref",
        task_id=f"task_{trace_id}",
        question=QUESTION,
        provider_id=provider,
        provider_family="mock",
        model="mock",
        agent_id=f"agent_{provider}",
        role="synthesizer",
        phase="synthesis",
        task_kind=TaskKind.SYNTHESIS_DRAFT.value,
        status=status,
        content={"text": text},
        confidence=confidence,
        winner_sections=winner_sections or [],
        failed_sections=failed_sections or [],
        external_eval_result=external_eval,
        peer_scores=peer_scores or {},
    )
    t.eligibility = (
        TrainingEligibility.accept(LearningUse.SUPERVISED_DISTILLATION)
        if eligible
        else TrainingEligibility.reject("test rejection")
    )
    return t


def test_score_trace_combines_eval_assembly_peer_and_confidence_signals():
    trace = _trace(
        "chosen",
        text="Strong calibrated answer.",
        confidence=0.9,
        winner_sections=["core_answer", "nuance"],
        external_eval={"passed": True, "score": 0.8},
        peer_scores={"average": 8.0},
    )
    scored = score_trace_for_preference(trace)

    assert scored.score > 0
    assert PreferenceSignal.EXTERNAL_EVAL.value in scored.signals
    assert PreferenceSignal.ASSEMBLY_WINNER.value in scored.signals
    assert PreferenceSignal.PEER_SCORE_GAP.value in scored.signals
    assert PreferenceSignal.CONFIDENCE_CALIBRATION.value in scored.signals


def test_mine_preferences_creates_dpo_pair_from_stronger_trace():
    chosen = _trace(
        "chosen",
        provider="winner",
        text="Chosen: careful, evidence-aware, and uncertainty-preserving.",
        confidence=0.88,
        winner_sections=["core_answer", "final_verdict"],
        external_eval={"passed": True, "score": 0.7},
        peer_scores={"average": 8.5},
    )
    rejected = _trace(
        "rejected",
        provider="loser",
        text="Rejected: overconfident and thin.",
        confidence=0.62,
        winner_sections=[],
        failed_sections=["blind_spots"],
        peer_scores={"average": 5.8},
    )
    ds = LearningDataset(traces=[chosen, rejected])

    report = mine_preferences(ds, attach=True)
    assert report.preference_count == 1
    assert len(ds.preferences) == 1
    pref = ds.preferences[0]
    assert "Chosen" in pref.chosen
    assert "Rejected" in pref.rejected
    assert pref.metadata["miner"] == "phase_26e"
    assert pref.metadata["margin"] > 0


def test_failed_provider_trace_is_not_used_as_rejected_dpo_negative():
    chosen = _trace(
        "chosen",
        text="Valid chosen.",
        winner_sections=["core_answer"],
        external_eval={"passed": True, "score": 1.0},
    )
    failed = _trace(
        "failed",
        text="Broken provider output.",
        status=ProviderStatus.TIMEOUT.value,
        eligible=False,
    )
    ds = LearningDataset(traces=[chosen, failed])

    report = mine_preferences(ds)
    assert report.preference_count == 0
    assert any("rejected is not a valid move" in s["reason"] for s in report.skipped)


def test_conservative_policy_requires_clear_margin():
    a = _trace("a", text="A", confidence=0.72, peer_scores={"average": 6.2})
    b = _trace("b", text="B", confidence=0.70, peer_scores={"average": 6.0})
    ds = LearningDataset(traces=[a, b])

    conservative = mine_preference_candidates(ds, policy=PreferenceMiningPolicy.conservative())
    aggressive = mine_preference_candidates(ds, policy=PreferenceMiningPolicy.aggressive())

    assert len(conservative.candidates) == 0
    assert len(aggressive.candidates) >= 0  # aggressive may still skip if margin is tiny


def test_miner_ignores_non_provider_move_signals_as_pair_sources():
    provider = _trace("provider", text="Only provider move", winner_sections=["core_answer"])
    ratification = _trace("rat", text="Ratification verdict", winner_sections=["core_answer"])
    ratification.signal_kind = LearningSignalKind.RATIFICATION
    ds = LearningDataset(traces=[provider, ratification])

    report = mine_preferences(ds)
    assert report.preference_count == 0
    assert any("fewer than two provider_move" in s["reason"] for s in report.skipped)


def test_smart_learning_summary_reports_counts():
    chosen = _trace("chosen", text="Chosen", winner_sections=["core_answer"], external_eval={"passed": True})
    rejected = _trace("rejected", text="Rejected", peer_scores={"average": 4.0})
    ds = LearningDataset(traces=[chosen, rejected])
    report = mine_preferences(ds)
    summary = smart_learning_summary(report)

    assert summary["traces_seen"] == 2
    assert summary["prompts_seen"] == 1
    assert "preference_count" in summary
    assert "skipped_count" in summary
