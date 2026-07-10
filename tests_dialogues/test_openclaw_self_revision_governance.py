"""Governance tests for agent-authored Memory/Identity/Soul revisions."""

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


def _proposal(
    *,
    target="identity",
    action="add_known_failure",
    value="rushes exact-output tasks",
    proposal_id="REV-001",
):
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


def _manifest(
    proposal,
    *,
    agent_id=AGENT,
    verified=True,
    supports=None,
    source="test-instrument",
    value=None,
    verified_by="evidence-harness",
):
    support = supports or (f"{proposal.target}:{proposal.action}",)
    evidence_value = proposal.value if value is None else value
    return {
        reference: {
            "agent_id": agent_id,
            "verified": verified,
            "source": source,
            "supports": tuple(support),
            "value": evidence_value,
            "verified_by": verified_by,
            "verification_reference": f"verification/{reference}",
            "observed_on": "2026-07-10",
            "outcomes": (),
        }
        for reference in EVIDENCE
    }


def _evaluate(proposal, *, stable=(), manifest=None):
    return evaluate_self_revision(
        proposal,
        evidence_manifest=manifest or _manifest(proposal),
        stable_lesson_ids=stable,
    )


def _apply(profile, proposal, *, stable=(), approver="operator", manifest=None):
    evidence_manifest = manifest or _manifest(proposal)
    evaluation = _evaluate(
        proposal, stable=stable, manifest=evidence_manifest)
    return approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        evidence_manifest=evidence_manifest,
        stable_lesson_ids=stable,
        approved_by=approver,
        approved_on="2026-07-10",
        approval_reference="review/self-revision-1",
    )


def test_agent_output_parser_is_exact_strict_and_seat_bound():
    record = _proposal().to_record()
    assert proposal_from_record(record, expected_agent_id=AGENT) == _proposal()

    with pytest.raises(ValueError, match="must be a mapping"):
        proposal_from_record([])
    with pytest.raises(ValueError, match="missing or unknown"):
        proposal_from_record({**record, "authority": "grant"})
    missing = dict(record)
    missing.pop("risk")
    with pytest.raises(ValueError, match="missing or unknown"):
        proposal_from_record(missing)
    with pytest.raises(ValueError, match="reviewed seat"):
        proposal_from_record(record, expected_agent_id="different_agent")
    with pytest.raises(ValueError, match="sequence, not text"):
        proposal_from_record({**record, "evidence_references": "trace/1"})


def test_self_revision_must_be_same_safe_agent_and_valid_target_action():
    with pytest.raises(ValueError, match="same agent"):
        dataclasses.replace(_proposal(), proposed_by="operator")
    with pytest.raises(ValueError, match="filesystem-safe"):
        dataclasses.replace(_proposal(), agent_id="../agent", proposed_by="../agent")
    with pytest.raises(ValueError, match="not valid"):
        dataclasses.replace(
            _proposal(), target="soul", action="add_known_failure")
    with pytest.raises(ValueError, match="LESSON"):
        _proposal(
            target="memory",
            action="link_stable_lesson",
            value="not-a-lesson",
        )


def test_secret_shaped_or_oversized_proposal_text_is_rejected():
    with pytest.raises(ValueError, match="secret-shaped"):
        _proposal(value="Bearer abcdefghijklmnop")
    with pytest.raises(ValueError, match="secret-shaped"):
        dataclasses.replace(_proposal(), reason="api_key=abcdefghijklmnop")
    with pytest.raises(ValueError, match="exceeds 64 entries"):
        dataclasses.replace(
            _proposal(),
            evidence_references=tuple(f"trace/{index}" for index in range(65)),
        )


def test_malformed_or_missing_evidence_fails_closed():
    proposal = _proposal()
    with pytest.raises(ValueError, match="must be a mapping"):
        evaluate_self_revision(proposal, evidence_manifest=[])
    with pytest.raises(ValueError, match="sequence, not text"):
        evaluate_self_revision(
            proposal,
            evidence_manifest=_manifest(proposal),
            stable_lesson_ids="LESSON-0007",
        )

    manifest = _manifest(proposal)
    manifest.pop(EVIDENCE[1])
    result = _evaluate(proposal, manifest=manifest)
    assert result.passed is False
    assert "missing evidence" in result.reasons[0]


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ({"verified": False}, "not verified"),
        ({"agent_id": "other_agent"}, "another agent"),
        ({"source": ""}, "valid auditable source"),
        ({"verified_by": ""}, "no named verifier"),
        ({"verified_by": AGENT}, "self-verified"),
        ({"verification_reference": ""}, "invalid verification provenance"),
        ({"supports": ("soul:add_principle",)}, "does not support"),
        ({"supports": 7}, "supports field is invalid"),
        ({"value": "different value"}, "value does not match"),
    ],
)
def test_evidence_requires_named_non_self_action_specific_provenance(
        mutation, reason):
    proposal = _proposal()
    evidence = _manifest(proposal)
    for record in evidence.values():
        record.update(mutation)
    result = _evaluate(proposal, manifest=evidence)
    assert result.passed is False
    assert any(reason in item for item in result.reasons)


def test_memory_link_requires_already_stable_lesson():
    proposal = _proposal(
        target="memory", action="link_stable_lesson", value="LESSON-0007")
    assert _evaluate(proposal).passed is False
    assert _evaluate(proposal, stable=("LESSON-0007",)).passed is True


def test_forged_passing_evaluation_is_recomputed_and_compared():
    proposal = _proposal()
    forged = RevisionEvaluation(
        proposal_id=proposal.proposal_id,
        passed=True,
        reasons=("trust me",),
        evidence_used=(EVIDENCE[0],),
    )
    with pytest.raises(ValueError, match="does not match independently"):
        approve_and_apply_self_revision(
            AgentIdentityProfile(agent_id=AGENT),
            proposal,
            forged,
            evidence_manifest=_manifest(proposal),
            approved_by="operator",
            approval_reference="review/forged",
        )

    forged_valid_refs = dataclasses.replace(
        forged, evidence_used=EVIDENCE)
    broken_manifest = _manifest(proposal, verified=False)
    with pytest.raises(ValueError, match="independent re-evaluation"):
        approve_and_apply_self_revision(
            AgentIdentityProfile(agent_id=AGENT),
            proposal,
            forged_valid_refs,
            evidence_manifest=broken_manifest,
            approved_by="operator",
            approval_reference="review/forged",
        )


def test_agent_can_never_approve_or_verify_its_own_revision():
    with pytest.raises(ValueError, match="own self-revision"):
        _apply(
            AgentIdentityProfile(agent_id=AGENT),
            _proposal(),
            approver=AGENT,
        )
    proposal = _proposal()
    manifest = _manifest(proposal, verified_by=AGENT)
    assert _evaluate(proposal, manifest=manifest).passed is False


def test_approved_revision_records_complete_evidence_provenance():
    proposal = _proposal()
    manifest = _manifest(proposal)
    updated = _apply(
        AgentIdentityProfile(agent_id=AGENT), proposal, manifest=manifest)
    assert updated.known_failures == ("rushes exact-output tasks",)
    entry = updated.revision_history[0]
    assert entry["entry_type"] == "self_revision"
    assert entry["proposed_by"] == AGENT
    assert entry["approved_by"] == "operator"
    assert entry["evidence_support"] == "identity:add_known_failure"
    assert entry["evidence_references"] == list(EVIDENCE)
    assert entry["evidence_verifiers"] == [
        "evidence-harness", "evidence-harness"]
    assert entry["verification_references"] == [
        "verification/trace/session-1", "verification/report/ab-1"]
    assert len(entry["evidence_manifest_digest"]) == 64


def test_approved_memory_and_soul_revisions_are_descriptive_only():
    memory = _proposal(
        target="memory", action="link_stable_lesson", value="LESSON-0007")
    memory_updated = _apply(
        AgentIdentityProfile(agent_id=AGENT),
        memory,
        stable=("LESSON-0007",),
    )
    assert memory_updated.stable_lessons == ("LESSON-0007",)

    principle = "State uncertainty before asserting a final verdict."
    soul = _proposal(
        target="soul", action="add_principle", value=principle)
    soul_updated = _apply(AgentIdentityProfile(agent_id=AGENT), soul)
    assert soul_updated.soul_principles == (principle,)
    assert "authority" not in soul_updated.to_record()


def test_duplicate_and_missing_reverse_operations_are_refused():
    first = _apply(AgentIdentityProfile(agent_id=AGENT), _proposal())
    duplicate_id = _proposal(
        target="soul",
        action="add_principle",
        value="State uncertainty.",
    )
    with pytest.raises(ValueError, match="already been applied"):
        _apply(first, duplicate_id)

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


def test_registry_refuses_direct_mutation_and_accepts_approved_revision(tmp_path):
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

    updated = _apply(original, _proposal())
    registry.save_profile(updated)
    assert registry.load_profile(AGENT) == updated


def test_registry_rejects_revision_history_rewrite_self_approval_and_first_save(
        tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = AgentIdentityProfile(agent_id=AGENT)
    registry.save_profile(original)
    updated = _apply(original, _proposal())
    registry.save_profile(updated)

    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(dataclasses.replace(updated, revision_history=()))

    entry = dict(updated.revision_history[0])
    entry["approved_by"] = AGENT
    forged = dataclasses.replace(updated, revision_history=(entry,))
    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(forged)

    fresh_registry = IdentityRegistry(tmp_path / "fresh")
    with pytest.raises(ValueError, match="must be saved before"):
        fresh_registry.save_profile(updated)


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
