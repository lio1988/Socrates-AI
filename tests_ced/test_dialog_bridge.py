"""Proves the dialog→CED bridge maps a completed dialogue onto the epistemic
state machine and produces a Current Best Explanation. Fully offline."""

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.storage.models import DialogTurnResponse, ElenchusResult
from backend.orchestrator.session import EnhancedDialogSession
from backend.epistemic.dialog_bridge import build_epistemic_graph
from backend.epistemic.epistemic_state import EpistemicState


def _session_with_dialogue():
    cfg = DialogConfig(topic="Is knowledge justified true belief?", rounds=4,
                       mode=DialogMode.SOCRATIC, speed=DialogSpeed.NORMAL,
                       summary_mode=SummaryMode.NONE)
    s = EnhancedDialogSession("bridge_test", cfg, {"claude": "x", "chatgpt": "y"})

    # Two Socratic positions.
    s.history.append(DialogTurnResponse(
        round=1, model_id="claude",
        content="Justification is internal access to good reasons for a belief.",
        is_socratic=True, is_elenchus=False, is_reflection=False, timestamp="t1"))
    s.history.append(DialogTurnResponse(
        round=2, model_id="claude",
        content="Knowledge requires a non-accidental connection to truth.",
        is_socratic=True, is_elenchus=False, is_reflection=False, timestamp="t2"))

    # Round 1 claim: challenged, falsified, and revised (survives, improved).
    s.elenchus_history.append(ElenchusResult(
        round=1, target_claim_summary="justification is internal access",
        challenger_model="chatgpt", challenged_assumptions=["conflates internalism"],
        falsification_successful=True, revision_required=True, revision_submitted=True))

    # Round 2 claim: challenged but survives intact.
    s.elenchus_history.append(ElenchusResult(
        round=2, target_claim_summary="non-accidental connection",
        challenger_model="claude", falsification_successful=False,
        revision_required=False, revision_submitted=False))
    return s


def test_bridge_creates_claims_for_positions():
    graph, _ = build_epistemic_graph(_session_with_dialogue())
    assert len(graph.claims) == 2


def test_every_claim_was_challenged():
    graph, _ = build_epistemic_graph(_session_with_dialogue())
    for c in graph.claims.values():
        assert c.has_been_challenged is True


def test_revised_claim_ends_supported():
    graph, _ = build_epistemic_graph(_session_with_dialogue())
    # The round-1 claim was falsified then revised -> should be SUPPORTED.
    revised = [c for c in graph.claims.values()
               if "internal access" in c.text]
    assert revised and revised[0].state == EpistemicState.SUPPORTED


def test_no_claim_reaches_knowledge_without_evidence():
    # Dialogue alone (no external evidence) must NOT yield KNOWLEDGE.
    graph, _ = build_epistemic_graph(_session_with_dialogue())
    assert all(c.state != EpistemicState.KNOWLEDGE for c in graph.claims.values())


def test_current_best_explanation_shape():
    _, cbe = build_epistemic_graph(_session_with_dialogue())
    d = cbe.to_dict()
    assert d["label"] == "Current Best Explanation"
    assert d["question"] == "Is knowledge justified true belief?"
    assert "strongest_claims" in d and "why_preferred" in d
    assert "not final truth" in d["note"]
