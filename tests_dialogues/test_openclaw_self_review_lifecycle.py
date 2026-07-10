"""Tests for bounded self-review, evidence-bound lifecycle, and rollback."""

import dataclasses
import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    approve_and_apply_self_revision,
    build_reversal_proposal,
    build_self_review_snapshot,
    build_self_revision_instruction,
    evaluate_self_revision,
    is_canonical_reversal,
    profile_fingerprint,
    render_self_review_summary,
)

AGENT = "agent_alpha"
VALUE = "rushes exact-output tasks"
REFERENCE = "trace/session-1"
OUTCOME_REFERENCE = "post-window/report-1"
REVERSAL_REFERENCE = "post-window/reversal-1"


def _profile(**updates):
    base = AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
        role_strengths={"blind_spots": 0.75, "core_answer": 0.5},
        section_wins={"blind_spots": 3, "core_answer": 2},
        section_opportunities={"blind_spots": 4, "core_answer": 4},
        sessions_analyzed=4,
        ratified_sessions=3,
        stable_lessons=("LESSON-0001",),
        soul_principles=("State uncertainty honestly.",),
    )
    return dataclasses.replace(base, **updates)


def _proposal(
    *,
    proposal_id="REV-100",
    target="identity",
    action="add_known_failure",
    value=VALUE,
    agent_id=AGENT,
    references=(REFERENCE,),
):
    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=agent_id,
        proposed_by=agent_id,
        target=target,
        action=action,
        value=value,
        reason="Repeated verified evidence shows this behavior.",
        evidence_references=tuple(references),
        risk="The evidence window may be too small.",
    )


def _evidence(
    proposal=None,
    *,
    reference=REFERENCE,
    verified=True,
    agent_id=AGENT,
    outcomes=(),
    source="trace-harness",
    verified_by="evidence-harness",
):
    proposal = proposal or _proposal()
    return {
        reference: {
            "verified": verified,
            "agent_id": agent_id,
            "source": source,
            "supports": (f"{proposal.target}:{proposal.action}",),
            "value": proposal.value,
            "verified_by": verified_by,
            "verification_reference": f"verification/{reference}",
            "observed_on": "2026-07-10",
            "outcomes": tuple(outcomes),
        }
    }


def _manifest(proposal=None, **kwargs):
    proposal = proposal or _proposal()
    manifest = _evidence(proposal, **kwargs)
    manifest.update({
        "trace/other-agent": {
            "verified": True,
            "agent_id": "agent_beta",
            "source": "trace-harness",
            "supports": ("identity:add_known_failure",),
            "value": "other agent failure",
            "verified_by": "evidence-harness",
            "verification_reference": "verification/other",
            "observed_on": "2026-07-10",
            "outcomes": (),
        },
        "trace/unverified": {
            "verified": False,
            "agent_id": AGENT,
            "source": "trace-harness",
            "supports": ("identity:add_known_failure",),
            "value": "unverified value",
            "verified_by": "evidence-harness",
            "verification_reference": "verification/unverified",
            "observed_on": "2026-07-10",
            "outcomes": (),
        },
    })
    return manifest


def _snapshot(profile=None, proposal=None, manifest=None, pending=()):
    profile = profile or _profile()
    proposal = proposal or _proposal()
    manifest = manifest or _manifest(proposal)
    return build_self_review_snapshot(
        profile,
        evidence_manifest=manifest,
        pending_proposals=pending,
    )


def _evaluation(proposal=None, manifest=None):
    proposal = proposal or _proposal()
    manifest = manifest or _manifest(proposal)
    return evaluate_self_revision(
        proposal,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
    )


def _applied_profile(profile=None, proposal=None, manifest=None):
    profile = profile or _profile()
    proposal = proposal or _proposal()
    manifest = manifest or _manifest(proposal)
    return approve_and_apply_self_revision(
        profile,
        proposal,
        _evaluation(proposal, manifest),
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        approved_by="operator",
        approval_reference="review/approved",
        approved_on="2026-07-10",
    )


def _submit(registry, profile=None, proposal=None, manifest=None):
    profile = profile or _profile()
    proposal = proposal or _proposal()
    manifest = manifest or _manifest(proposal)
    snapshot = _snapshot(profile, proposal, manifest)
    registry.submit(
        proposal,
        snapshot=snapshot,
        submitted_on="2026-07-10",
    )
    return profile, proposal, manifest, snapshot


def _evaluate_and_approve(registry, profile, proposal, manifest):
    result = registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        evaluated_by="evidence-harness",
        evaluated_on="2026-07-10",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        decision="approved",
        decided_by="operator",
        decision_reference="review/approved",
        decided_on="2026-07-10",
    )
    return result


def _apply(registry, profile, proposal, manifest):
    updated = _applied_profile(profile, proposal, manifest)
    registry.record_application(
        AGENT,
        proposal.proposal_id,
        previous_profile=profile,
        updated_profile=updated,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        applied_by="operator",
        application_reference="identity/revision/0",
        applied_on="2026-07-10",
    )
    return updated


# --------------------------------------------------------------------------- #
# Bounded self-review
# --------------------------------------------------------------------------- #


def test_snapshot_contains_only_verified_evidence_for_same_agent():
    snapshot = _snapshot()
    assert [row.reference for row in snapshot.verified_evidence] == [REFERENCE]
    assert snapshot.verified_evidence[0].value == VALUE
    assert "agent_beta" not in json.dumps(snapshot.to_record())
    assert "unverified value" not in json.dumps(snapshot.to_record())


def test_snapshot_exposes_public_counts_not_hidden_scorecards():
    snapshot = _snapshot()
    assert snapshot.role_strengths["blind_spots"] == {
        "win_rate": 0.75,
        "wins": 3,
        "opportunities": 4,
    }
    raw = json.dumps(snapshot.to_record())
    for forbidden in ("scorecard", "score_breakdown", "leaderboard"):
        assert forbidden not in raw


def test_snapshot_fingerprints_are_deterministic_and_state_bound():
    first = _snapshot()
    second = _snapshot()
    changed = _snapshot(_profile(known_failures=("new failure",)))
    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.profile_fingerprint == profile_fingerprint(_profile())
    assert changed.profile_fingerprint != first.profile_fingerprint
    assert changed.snapshot_fingerprint != first.snapshot_fingerprint


def test_pending_proposals_are_seat_bound_deduplicated_and_bounded():
    proposal = _proposal()
    snapshot = _snapshot(pending=(proposal, proposal))
    assert snapshot.pending_proposal_ids == (proposal.proposal_id,)
    with pytest.raises(ValueError, match="another agent"):
        _snapshot(pending=(_proposal(agent_id="agent_beta"),))
    pending = tuple(
        _proposal(proposal_id=f"REV-{index}") for index in range(33)
    )
    with pytest.raises(ValueError, match="bounded snapshot limit"):
        _snapshot(pending=pending)


def test_snapshot_limits_refuse_memory_and_prompt_flooding():
    with pytest.raises(ValueError, match="known_failures contains 33"):
        _snapshot(_profile(
            known_failures=tuple(f"failure-{index}" for index in range(33))))

    proposal = _proposal()
    manifest = {}
    for index in range(65):
        manifest[f"trace/{index}"] = {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-harness",
            "supports": ("identity:add_known_failure",),
            "value": proposal.value,
            "verified_by": "evidence-harness",
            "verification_reference": f"verification/{index}",
            "observed_on": "2026-07-10",
            "outcomes": (),
        }
    with pytest.raises(ValueError, match="bounded snapshot limit"):
        _snapshot(manifest=manifest)

    large_manifest = {}
    for index in range(64):
        large_manifest[f"trace/{index}-" + "r" * 180] = {
            "verified": True,
            "agent_id": AGENT,
            "source": "s" * 500,
            "supports": ("identity:add_known_failure",),
            "value": "v" * 490,
            "verified_by": "evidence-harness",
            "verification_reference": f"verification/{index}",
            "observed_on": "2026-07-10",
            "outcomes": (),
        }
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=large_manifest)
    with pytest.raises(ValueError, match="instruction is .* bytes"):
        build_self_revision_instruction(snapshot)


def test_malformed_or_secret_evidence_fails_closed():
    manifest = _manifest()
    manifest[REFERENCE]["supports"] = "identity:add_known_failure"
    with pytest.raises(ValueError, match="must be a sequence"):
        _snapshot(manifest=manifest)

    manifest = _manifest()
    manifest[REFERENCE]["source"] = ""
    with pytest.raises(ValueError, match="source must be non-empty"):
        _snapshot(manifest=manifest)

    manifest = _manifest()
    manifest[REFERENCE]["value"] = "api_key=abcdefgh12345678"
    with pytest.raises(ValueError, match="secret-shaped"):
        _snapshot(manifest=manifest)


def test_instruction_is_proposal_only_and_exact_json_contract():
    snapshot = _snapshot()
    instruction = build_self_revision_instruction(snapshot)
    summary = render_self_review_summary(snapshot)
    assert "Return exactly one JSON object and nothing else" in instruction
    assert "proposal only; no authority" in instruction
    assert REFERENCE in instruction
    assert "trace/other-agent" not in instruction
    assert "Snapshot fingerprint" in summary
    assert "grants no runtime authority" in summary


# --------------------------------------------------------------------------- #
# Snapshot-bound, evidence-recomputed lifecycle
# --------------------------------------------------------------------------- #


def test_submit_binds_proposal_snapshot_profile_and_evidence_metadata(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, _, snapshot = _submit(registry)
    loaded = registry.load(AGENT, proposal.proposal_id)

    assert loaded["status"] == "submitted"
    assert loaded["snapshot_version"] == snapshot.snapshot_version
    assert loaded["snapshot_fingerprint"] == snapshot.snapshot_fingerprint
    assert loaded["profile_fingerprint"] == profile_fingerprint(profile)
    assert loaded["snapshot_evidence_references"] == [REFERENCE]
    assert loaded["proposal"] == proposal.to_record()
    submitted = loaded["events"][0]
    assert submitted["actor"] == AGENT
    for field in (
        "proposal_digest", "snapshot_fingerprint", "profile_fingerprint",
        "snapshot_evidence_digest",
    ):
        assert submitted[field]

    with pytest.raises(ValueError, match="already exists"):
        registry.submit(proposal, snapshot=snapshot)


def test_submit_rejects_absent_mismatched_or_already_pending_evidence(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    missing = _proposal(references=("trace/not-in-snapshot",))
    with pytest.raises(ValueError, match="absent"):
        registry.submit(missing, snapshot=_snapshot())

    mismatched = _proposal(value="different value")
    with pytest.raises(ValueError, match="target/action/value"):
        registry.submit(mismatched, snapshot=_snapshot())

    proposal = _proposal()
    pending_snapshot = _snapshot(pending=(proposal,))
    with pytest.raises(ValueError, match="already pending"):
        registry.submit(proposal, snapshot=pending_snapshot)


def test_top_level_metadata_tampering_breaks_submission_binding(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    _, proposal, _, _ = _submit(registry)
    path = tmp_path / AGENT / f"{proposal.proposal_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["proposal"]["reason"] = "rewritten after submission"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load(AGENT, proposal.proposal_id)


def test_exclusive_lock_refuses_concurrent_update(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    lock_path = tmp_path / AGENT / f"{proposal.proposal_id}.json.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("other-process", encoding="utf-8")
    with pytest.raises(ValueError, match="locked by another update"):
        registry.submit(proposal, snapshot=_snapshot())


def test_evaluation_is_recomputed_and_agent_cannot_govern_itself(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, manifest, _ = _submit(registry)

    with pytest.raises(ValueError, match="cannot evaluate"):
        registry.record_evaluation(
            AGENT,
            proposal.proposal_id,
            current_profile=profile,
            evidence_manifest=manifest,
            evaluated_by=AGENT,
        )

    failing = _manifest(proposal, verified=False)
    result = registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=failing,
        evaluated_by="evidence-harness",
    )
    assert result.passed is False
    assert registry.load(AGENT, proposal.proposal_id)["status"] == \
        "evaluated_failed"


def test_stale_profile_and_changed_evidence_block_decision(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, manifest, _ = _submit(registry)
    registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        evaluated_by="evidence-harness",
    )

    with pytest.raises(ValueError, match="identity state changed"):
        registry.record_decision(
            AGENT,
            proposal.proposal_id,
            current_profile=dataclasses.replace(
                profile, known_failures=("unrelated change",)),
            evidence_manifest=manifest,
            stable_lesson_ids=("LESSON-0001",),
            decision="approved",
            decided_by="operator",
            decision_reference="review/approved",
        )

    changed = json.loads(json.dumps(manifest))
    changed[REFERENCE]["source"] = "changed-source"
    with pytest.raises(ValueError, match="evidence changed"):
        registry.record_decision(
            AGENT,
            proposal.proposal_id,
            current_profile=profile,
            evidence_manifest=changed,
            stable_lesson_ids=("LESSON-0001",),
            decision="approved",
            decided_by="operator",
            decision_reference="review/approved",
        )


def test_evaluator_cannot_also_approve_and_agent_cannot_decide(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, manifest, _ = _submit(registry)
    registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        evaluated_by="evidence-harness",
    )

    for actor, match in (
        (AGENT, "cannot approve or reject"),
        ("evidence-harness", "different actors"),
    ):
        with pytest.raises(ValueError, match=match):
            registry.record_decision(
                AGENT,
                proposal.proposal_id,
                current_profile=profile,
                evidence_manifest=manifest,
                stable_lesson_ids=("LESSON-0001",),
                decision="approved",
                decided_by=actor,
                decision_reference="review/approved",
            )


def test_failing_evaluation_can_only_be_rejected(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, _, _ = _submit(registry)
    failing = _manifest(proposal, verified=False)
    registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=failing,
        evaluated_by="evidence-harness",
    )
    with pytest.raises(ValueError, match="cannot be approved"):
        registry.record_decision(
            AGENT,
            proposal.proposal_id,
            current_profile=profile,
            evidence_manifest=failing,
            decision="approved",
            decided_by="operator",
            decision_reference="review/failed",
        )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=failing,
        decision="rejected",
        decided_by="operator",
        decision_reference="review/rejected",
    )
    assert registry.load(AGENT, proposal.proposal_id)["status"] == "rejected"


def test_application_must_exactly_equal_recomputed_approved_profile(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, manifest, _ = _submit(registry)
    _evaluate_and_approve(registry, profile, proposal, manifest)
    correct = _applied_profile(profile, proposal, manifest)

    forged = dataclasses.replace(
        correct,
        soul_principles=correct.soul_principles + ("forged principle",),
    )
    with pytest.raises(ValueError, match="does not exactly match"):
        registry.record_application(
            AGENT,
            proposal.proposal_id,
            previous_profile=profile,
            updated_profile=forged,
            evidence_manifest=manifest,
            stable_lesson_ids=("LESSON-0001",),
            applied_by="operator",
            application_reference="identity/forged",
        )

    registry.record_application(
        AGENT,
        proposal.proposal_id,
        previous_profile=profile,
        updated_profile=correct,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        applied_by="operator",
        application_reference="identity/revision/0",
    )
    loaded = registry.load(AGENT, proposal.proposal_id)
    assert loaded["status"] == "probationary"
    assert loaded["events"][-1]["profile_fingerprint"] == \
        profile_fingerprint(correct)
    assert loaded["events"][-1]["revision_entry_digest"]


# --------------------------------------------------------------------------- #
# Probation evidence and governed rollback
# --------------------------------------------------------------------------- #


def test_confirmation_requires_outcome_specific_verified_evidence(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, manifest, _ = _submit(registry)
    _evaluate_and_approve(registry, profile, proposal, manifest)
    applied = _apply(registry, profile, proposal, manifest)

    with pytest.raises(ValueError, match="missing"):
        registry.record_outcome(
            AGENT,
            proposal.proposal_id,
            current_profile=applied,
            outcome="confirmed",
            evidence_manifest=manifest,
            recorded_by="post-change-reviewer",
            evidence_reference=OUTCOME_REFERENCE,
        )

    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        proposal,
        reference=OUTCOME_REFERENCE,
        outcomes=("confirmed",),
        source="post-change-harness",
        verified_by="post-change-verifier",
    ))
    registry.record_outcome(
        AGENT,
        proposal.proposal_id,
        current_profile=applied,
        outcome="confirmed",
        evidence_manifest=outcome_manifest,
        recorded_by="post-change-reviewer",
        evidence_reference=OUTCOME_REFERENCE,
    )
    confirmed = registry.load(AGENT, proposal.proposal_id)
    assert confirmed["status"] == "confirmed"
    assert confirmed["events"][-1]["outcome_evidence_digest"]


def test_outcome_verifier_reviewer_separation_and_profile_stability(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, proposal, manifest, _ = _submit(registry)
    _evaluate_and_approve(registry, profile, proposal, manifest)
    applied = _apply(registry, profile, proposal, manifest)
    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        proposal,
        reference=OUTCOME_REFERENCE,
        outcomes=("confirmed",),
        verified_by="post-change-verifier",
    ))

    with pytest.raises(ValueError, match="different actors"):
        registry.record_outcome(
            AGENT,
            proposal.proposal_id,
            current_profile=applied,
            outcome="confirmed",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-verifier",
            evidence_reference=OUTCOME_REFERENCE,
        )

    with pytest.raises(ValueError, match="identity state changed"):
        registry.record_outcome(
            AGENT,
            proposal.proposal_id,
            current_profile=dataclasses.replace(
                applied, soul_principles=applied.soul_principles + ("later",)),
            outcome="confirmed",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-reviewer",
            evidence_reference=OUTCOME_REFERENCE,
        )


def test_revert_requires_existing_canonical_reversal_bound_to_current_profile(
        tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, original, manifest, _ = _submit(registry)
    _evaluate_and_approve(registry, profile, original, manifest)
    applied = _apply(registry, profile, original, manifest)

    reversal = build_reversal_proposal(
        applied,
        original.proposal_id,
        proposal_id="REV-101",
        evidence_references=(REVERSAL_REFERENCE,),
        reason="Post-change evidence shows the revision should be reversed.",
        risk="Reversal may restore the original failure pattern.",
    )
    assert is_canonical_reversal(original, reversal)
    reversal_manifest = _evidence(
        reversal,
        reference=REVERSAL_REFERENCE,
        source="post-change-harness",
        verified_by="post-change-verifier",
    )
    reversal_snapshot = build_self_review_snapshot(
        applied, evidence_manifest=reversal_manifest)
    registry.submit(reversal, snapshot=reversal_snapshot)

    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        original,
        reference=OUTCOME_REFERENCE,
        outcomes=("reverted",),
        source="post-change-harness",
        verified_by="post-change-verifier",
    ))
    registry.record_outcome(
        AGENT,
        original.proposal_id,
        current_profile=applied,
        outcome="reverted",
        evidence_manifest=outcome_manifest,
        recorded_by="post-change-reviewer",
        evidence_reference=OUTCOME_REFERENCE,
        linked_proposal_id=reversal.proposal_id,
    )
    assert registry.load(AGENT, original.proposal_id)["status"] == "reverted"
    assert len(registry.all_records(AGENT)) == 2


def test_missing_reversal_is_refused(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, original, manifest, _ = _submit(registry)
    _evaluate_and_approve(registry, profile, original, manifest)
    applied = _apply(registry, profile, original, manifest)
    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        original,
        reference=OUTCOME_REFERENCE,
        outcomes=("reverted",),
        verified_by="post-change-verifier",
    ))

    with pytest.raises(ValueError, match="does not exist"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=applied,
            outcome="reverted",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-reviewer",
            evidence_reference=OUTCOME_REFERENCE,
            linked_proposal_id="REV-MISSING",
        )


def test_event_hash_tampering_and_unknown_fields_are_visible(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    _, proposal, _, _ = _submit(registry)
    path = tmp_path / AGENT / f"{proposal.proposal_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["events"][0]["actor"] = "attacker"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load(AGENT, proposal.proposal_id)


def test_registry_lists_records_deterministically(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    for agent_id, proposal_id in (
        ("zeta", "REV-2"),
        ("alpha", "REV-3"),
        ("alpha", "REV-1"),
    ):
        proposal = _proposal(
            agent_id=agent_id,
            proposal_id=proposal_id,
            value=f"failure-{agent_id}-{proposal_id}",
        )
        profile = _profile(agent_id=agent_id)
        manifest = _manifest(proposal, agent_id=agent_id)
        snapshot = build_self_review_snapshot(
            profile, evidence_manifest=manifest)
        registry.submit(proposal, snapshot=snapshot)

    assert [
        (record["agent_id"], record["proposal_id"])
        for record in registry.all_records()
    ] == [("alpha", "REV-1"), ("alpha", "REV-3"), ("zeta", "REV-2")]
