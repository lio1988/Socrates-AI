"""Governance tests for agent-authored memory/identity/soul revisions."""

import dataclasses

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    RevisionEvaluation,
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    evaluate_self_revision,
    from_record,
    proposal_from_record,
    render_soul_card,
)


AGENT = "local_apprentice_001"
EVIDENCE = ("trace/session-1", "report/ab-1")


def _proposal(*, target="identity", action="add_known_failure", value="rushes exact-output tasks", proposal_id="REV-001"):
    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=AGENT,
        proposed_by=AGENT,
        target=target,
        action=action,
        value=value,
        reason="The cited evidence shows a repeated pattern.",
        evidence_references=EVIDENCE,
        risk="The agent may overfit to a small evidence window.",
    )


def _evaluate(proposal, *, stable=()):
    return evaluate_self_revision(
        proposal,
        available_evidence_references=EVIDENCE,
        stable_lesson_ids=stable,
    )


def _apply(profile, proposal, *, stable=(), approver="operator"):
    evaluation = _evaluate(proposal, stable=stable)
    return approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        available_evidence_references=EVIDENCE,
        stable_lesson_ids=stable,
        approved_by=approver,
        approved_on="2026-07-10",
        approval_reference="review/self-revision-1",
    )


def test_agent_output_parser_is_strict_and_seat_bound():
    record = _proposal().to_record()
    assert proposal_from_record(record, expected_agent_id=AGENT) == _proposal()

    with pytest.raises(ValueError, match="unknown fields"):
        proposal_from_record({**record, "authority": "grant"})
    with pytest.raises(ValueError, match="reviewed seat"):
        proposal_from_record(record, expected_agent_id="different_agent")


def test_self_revision_must_be_authored_by_the_same_agent():
    with pytest.raises(ValueError, match="same agent"):
        dataclasses.replace(_proposal(), proposed_by="operator")


def test_target_action_pairs_and_memory_ids_are_validated():
    with pytest.raises(ValueError, match="not valid"):
        dataclasses.replace(_proposal(), target="soul", action="add_known_failure")
    with pytest.raises(ValueError, match="LESSON"):
        _proposal(target="memory", action="link_stable_lesson", value="not-a-lesson")


def test_missing_evidence_fails_closed():
    result = evaluate_self_revision(
        _proposal(), available_evidence_references=(EVIDENCE[0],))
    assert result.passed is False
    assert "missing evidence" in result.reasons[0]


def test_memory_link_requires_already_stable_lesson():
    proposal = _proposal(
        target="memory", action="link_stable_lesson", value="LESSON-0007")
    denied = _evaluate(proposal)
    allowed = _evaluate(proposal, stable=("LESSON-0007",))
    assert denied.passed is False
    assert allowed.passed is True


def test_forged_passing_evaluation_is_recomputed():
    proposal = _proposal()
    forged = RevisionEvaluation(
        proposal_id=proposal.proposal_id,
        passed=True,
        reasons=("trust me",),
        evidence_used=EVIDENCE,
    )
    with pytest.raises(ValueError, match="independent re-evaluation"):
        approve_and_apply_self_revision(
            AgentIdentityProfile(agent_id=AGENT),
            proposal,
            forged,
            available_evidence_references=(),
            approved_by="operator",
            approval_reference="review/forged",
        )


def test_agent_can_never_approve_its_own_revision():
    with pytest.raises(ValueError, match="own self-revision"):
        _apply(AgentIdentityProfile(agent_id=AGENT), _proposal(), approver=AGENT)


def test_approved_identity_revision_updates_profile_and_history():
    updated = _apply(AgentIdentityProfile(agent_id=AGENT), _proposal())
    assert updated.known_failures == ("rushes exact-output tasks",)
    assert len(updated.revision_history) == 1
    entry = updated.revision_history[0]
    assert entry["entry_type"] == "self_revision"
    assert entry["proposed_by"] == AGENT
    assert entry["approved_by"] == "operator"
    assert entry["evidence_references"] == list(EVIDENCE)


def test_approved_memory_revision_links_only_curated_lesson():
    proposal = _proposal(
        target="memory", action="link_stable_lesson", value="LESSON-0007")
    updated = _apply(
        AgentIdentityProfile(agent_id=AGENT),
        proposal,
        stable=("LESSON-0007",),
    )
    assert updated.stable_lessons == ("LESSON-0007",)


def test_approved_soul_revision_is_descriptive_not_authority():
    principle = "State uncertainty before asserting a final verdict."
    proposal = _proposal(
        target="soul", action="add_principle", value=principle)
    updated = _apply(AgentIdentityProfile(agent_id=AGENT), proposal)
    assert updated.soul_principles == (principle,)
    assert "authority" not in updated.to_record()


def test_duplicate_and_missing_reverse_operations_are_refused():
    profile = AgentIdentityProfile(
        agent_id=AGENT,
        known_failures=("rushes exact-output tasks",),
        stable_lessons=("LESSON-0007",),
        soul_principles=("State uncertainty.",),
    )
    with pytest.raises(ValueError, match="already recorded"):
        _apply(profile, _proposal())
    with pytest.raises(ValueError, match="not recorded"):
        _apply(
            profile,
            _proposal(
                target="identity",
                action="resolve_known_failure",
                value="different failure",
            ),
        )


@pytest.mark.parametrize(
    "field,target,action,value",
    [
        ("known_failures", "identity", "resolve_known_failure", "failure-a"),
        ("stable_lessons", "memory", "unlink_stable_lesson", "LESSON-0007"),
        ("soul_principles", "soul", "retire_principle", "principle-a"),
    ],
)
def test_approved_reverse_operations_remove_existing_values(
        field, target, action, value):
    profile = AgentIdentityProfile(
        agent_id=AGENT,
        known_failures=("failure-a",),
        stable_lessons=("LESSON-0007",),
        soul_principles=("principle-a",),
    )
    updated = _apply(
        profile,
        _proposal(target=target, action=action, value=value),
    )
    assert value not in getattr(updated, field)


def test_registry_refuses_direct_mutation_without_revision(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = AgentIdentityProfile(agent_id=AGENT)
    registry.save_profile(original)

    for forged in (
        dataclasses.replace(original, known_failures=("failure",)),
        dataclasses.replace(original, stable_lessons=("LESSON-0007",)),
        dataclasses.replace(original, soul_principles=("principle",)),
    ):
        with pytest.raises(ValueError, match="matching approved self-revisions"):
            registry.save_profile(forged)


def test_registry_accepts_and_round_trips_approved_revision(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = AgentIdentityProfile(agent_id=AGENT)
    registry.save_profile(original)
    updated = _apply(original, _proposal())
    registry.save_profile(updated)
    assert registry.load_profile(AGENT) == updated


def test_registry_rejects_revision_history_truncation_and_self_approval(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = AgentIdentityProfile(agent_id=AGENT)
    updated = _apply(original, _proposal())
    registry.save_profile(updated)

    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(dataclasses.replace(updated, revision_history=()))

    entry = dict(updated.revision_history[0])
    entry["approved_by"] = AGENT
    forged = dataclasses.replace(updated, revision_history=(entry,))
    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(forged)


def test_old_identity_records_load_with_empty_revision_defaults():
    profile = from_record({"agent_id": AGENT, "known_failures": ["legacy"]})
    assert profile.known_failures == ("legacy",)
    assert profile.soul_principles == ()
    assert profile.revision_history == ()


def test_soul_card_shows_approved_principles_and_revision_count():
    updated = _apply(
        AgentIdentityProfile(agent_id=AGENT),
        _proposal(
            target="soul",
            action="add_principle",
            value="State uncertainty before asserting a final verdict.",
        ),
    )
    card = render_soul_card(updated)
    assert "Approved soul principles:" in card
    assert "State uncertainty" in card
    assert "Self-revisions recorded: 1" in card
