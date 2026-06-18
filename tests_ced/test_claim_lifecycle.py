"""Proves: claims cannot skip challenge; no HYPOTHESIS->KNOWLEDGE shortcut;
transitions are logged."""

import pytest

from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_state import EpistemicState, IllegalTransition


def make_claim():
    return Claim(text="The sky appears blue due to Rayleigh scattering.",
                 author_model="alpha")


def test_default_state_is_hypothesis():
    assert make_claim().state == EpistemicState.HYPOTHESIS


def test_cannot_jump_hypothesis_to_knowledge():
    c = make_claim()
    with pytest.raises(IllegalTransition):
        c.transition(EpistemicState.KNOWLEDGE, actor="rogue", reason="shortcut")


def test_cannot_reach_knowledge_without_challenge_flag():
    c = make_claim()
    # Walk a legal path but never set has_been_challenged via CHALLENGED.
    c.transition(EpistemicState.SUPPORTED, actor="t", reason="support")
    c.transition(EpistemicState.VERIFIED, actor="t", reason="verify")
    with pytest.raises(IllegalTransition):
        c.transition(EpistemicState.KNOWLEDGE, actor="t", reason="no challenge")


def test_minimum_valid_path_to_knowledge():
    c = make_claim()
    c.transition(EpistemicState.CHALLENGED, actor="elenchus", reason="challenge")
    c.transition(EpistemicState.REVISED, actor="revision", reason="revise")
    c.transition(EpistemicState.VERIFIED, actor="verifier", reason="verify")
    c.transition(EpistemicState.KNOWLEDGE, actor="emergence", reason="promote")
    assert c.state == EpistemicState.KNOWLEDGE
    assert c.has_been_challenged is True


def test_every_transition_is_logged():
    c = make_claim()
    c.transition(EpistemicState.CHALLENGED, actor="e", reason="r1")
    c.transition(EpistemicState.REVISED, actor="e", reason="r2")
    assert len(c.revision_history) == 2
    assert c.revision_history[0].to_state == EpistemicState.CHALLENGED


def test_knowledge_is_reversible():
    c = make_claim()
    for to, why in [(EpistemicState.CHALLENGED, "c"),
                    (EpistemicState.REVISED, "r"),
                    (EpistemicState.VERIFIED, "v"),
                    (EpistemicState.KNOWLEDGE, "k"),
                    (EpistemicState.DISPUTED, "new evidence")]:
        c.transition(to, actor="t", reason=why)
    assert c.state == EpistemicState.DISPUTED
