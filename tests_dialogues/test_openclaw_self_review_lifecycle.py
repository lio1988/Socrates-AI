"""Tests for bounded self-review, lifecycle audit, probation, and rollback."""

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
):
    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=agent_id,
        proposed_by=agent_id,
        target=target,
        action=action,
        value=value,
        reason="Repeated verified evidence shows this behavior.",
        evidence_references=(REFERENCE,),
        risk="The evidence window may be too small.",
    )


def _manifest(proposal=None, *, verified=True, agent_id=AGENT):
    proposal = proposal or _proposal()
    return {
        REFERENCE: {
            "verified": verified,
            "agent_id": agent_id,
            "source": "trace-harness",
            "supports": (f"{proposal.target}:{proposal.action}",),
            "value": proposal.value,
        },
        "trace/other-agent": {
            "verified": True,
            "agent_id": "agent_beta",
            "source": "trace-harness",
            "supports": ("identity:add_known_failure",),
            "value": "other agent failure",
        },
        "trace/unverified": {
            "verified": False,
            "agent_id": AGENT,
            "source": "trace-harness",
            "supports": ("identity:add_known_failure",),
            "value": "unverified value",
        },
    }


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
    evaluation = _evaluation(proposal, manifest)
    return approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        approved_by="operator",
        approval_reference="review/rev-100",
        approved_on="2026-07-10",
    )


# --------------------------------------------------------------------------- #
# Bounded self-review snapshot
# --------------------------------------------------------------------------- #


def test_snapshot_contains_only_verified_evidence_for_the_same_agent():
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest())

    assert [row.reference for row in snapshot.verified_evidence] == [REFERENCE]
    assert snapshot.verified_evidence[0].value == VALUE
    assert "agent_beta" not in json.dumps(snapshot.to_record())
    assert "unverified value" not in json.dumps(snapshot.to_record())


def test_snapshot_exposes_public_counts_not_hidden_scorecards():
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest())

    blind = snapshot.role_strengths["blind_spots"]
    assert blind == {"win_rate": 0.75, "wins": 3, "opportunities": 4}
    raw = json.dumps(snapshot.to_record())
    for forbidden in ("scorecard", "score_breakdown", "leaderboard"):
        assert forbidden not in raw


def test_snapshot_fingerprints_are_deterministic_and_state_bound():
    first = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest())
    second = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest())
    changed = build_self_review_snapshot(
        _profile(known_failures=("new failure",)),
        evidence_manifest=_manifest(),
    )

    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.profile_fingerprint == profile_fingerprint(_profile())
    assert changed.profile_fingerprint != first.profile_fingerprint
    assert changed.snapshot_fingerprint != first.snapshot_fingerprint


def test_pending_proposals_are_seat_bound_and_deduplicated():
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(),
        evidence_manifest=_manifest(),
        pending_proposals=(proposal, proposal),
    )
    assert snapshot.pending_proposal_ids == (proposal.proposal_id,)

    with pytest.raises(ValueError, match="another agent"):
        build_self_review_snapshot(
            _profile(),
            evidence_manifest=_manifest(),
            pending_proposals=(_proposal(agent_id="agent_beta"),),
        )


def test_verified_but_malformed_evidence_fails_closed():
    manifest = _manifest()
    manifest[REFERENCE]["supports"] = "identity:add_known_failure"
    with pytest.raises(ValueError, match="must be a sequence"):
        build_self_review_snapshot(_profile(), evidence_manifest=manifest)

    manifest = _manifest()
    manifest[REFERENCE]["source"] = ""
    with pytest.raises(ValueError, match="source must be non-empty"):
        build_self_review_snapshot(_profile(), evidence_manifest=manifest)


def test_secret_shaped_snapshot_data_is_refused():
    manifest = _manifest()
    manifest[REFERENCE]["value"] = "api_key=abcdefgh12345678"
    with pytest.raises(ValueError, match="secret-shaped"):
        build_self_review_snapshot(_profile(), evidence_manifest=manifest)

    with pytest.raises(ValueError, match="secret-shaped"):
        build_self_review_snapshot(
            _profile(soul_principles=("Bearer abcdefgh12345678",)),
            evidence_manifest=_manifest(),
        )


def test_instruction_is_proposal_only_and_exact_json_contract():
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest())
    instruction = build_self_revision_instruction(snapshot)
    summary = render_self_review_summary(snapshot)

    assert "Return exactly one JSON object and nothing else" in instruction
    assert "proposal only; no authority" in instruction
    assert REFERENCE in instruction
    assert "trace/other-agent" not in instruction
    assert "Snapshot fingerprint" in summary
    assert "grants no runtime authority" in summary


# --------------------------------------------------------------------------- #
# Append-only proposal lifecycle
# --------------------------------------------------------------------------- #


def test_registry_submit_round_trips_and_is_immutable(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest(proposal))

    path = registry.submit(
        proposal,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        submitted_on="2026-07-10",
    )
    loaded = registry.load(AGENT, proposal.proposal_id)

    assert path.exists()
    assert loaded["status"] == "submitted"
    assert loaded["proposal"] == proposal.to_record()
    assert len(loaded["events"]) == 1
    assert loaded["events"][0]["actor"] == AGENT
    assert loaded["events"][0]["event_hash"]
    assert list(path.parent.glob(".*.tmp")) == []

    with pytest.raises(ValueError, match="already exists"):
        registry.submit(
            proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)


def test_agent_cannot_evaluate_or_decide_its_own_proposal(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest(proposal))
    registry.submit(proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)

    with pytest.raises(ValueError, match="cannot evaluate"):
        registry.record_evaluation(
            AGENT, proposal.proposal_id, _evaluation(proposal),
            evaluated_by=AGENT,
        )

    registry.record_evaluation(
        AGENT, proposal.proposal_id, _evaluation(proposal),
        evaluated_by="evidence-harness",
    )
    with pytest.raises(ValueError, match="cannot approve or reject"):
        registry.record_decision(
            AGENT,
            proposal.proposal_id,
            decision="approved",
            decided_by=AGENT,
            decision_reference="review/1",
        )


def test_failing_evaluation_cannot_be_approved(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest(proposal))
    registry.submit(proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)

    failing = _evaluation(proposal, _manifest(proposal, verified=False))
    assert failing.passed is False
    registry.record_evaluation(
        AGENT, proposal.proposal_id, failing,
        evaluated_by="evidence-harness",
    )
    with pytest.raises(ValueError, match="cannot be approved"):
        registry.record_decision(
            AGENT,
            proposal.proposal_id,
            decision="approved",
            decided_by="operator",
            decision_reference="review/failed",
        )

    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        decision="rejected",
        decided_by="operator",
        decision_reference="review/rejected",
    )
    assert registry.load(AGENT, proposal.proposal_id)["status"] == "rejected"


def test_happy_path_reaches_probation_and_confirmation(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    manifest = _manifest(proposal)
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=manifest)
    registry.submit(proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)
    registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        _evaluation(proposal, manifest),
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        decision="approved",
        decided_by="operator",
        decision_reference="review/approved",
    )

    applied = _applied_profile(proposal=proposal, manifest=manifest)
    registry.record_application(
        AGENT,
        proposal.proposal_id,
        applied,
        applied_by="operator",
        application_reference="identity/revision/0",
    )
    probationary = registry.load(AGENT, proposal.proposal_id)
    assert probationary["status"] == "probationary"
    assert probationary["events"][-1]["profile_fingerprint"] == \
        profile_fingerprint(applied)
    assert probationary["events"][-1]["revision_index"] == 0

    registry.record_outcome(
        AGENT,
        proposal.proposal_id,
        outcome="confirmed",
        recorded_by="operator",
        evidence_reference="post-window/report-1",
    )
    confirmed = registry.load(AGENT, proposal.proposal_id)
    assert confirmed["status"] == "confirmed"
    assert len(confirmed["events"]) == 5


def test_application_requires_the_actual_profile_revision(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest(proposal))
    registry.submit(proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)
    registry.record_evaluation(
        AGENT, proposal.proposal_id, _evaluation(proposal),
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        decision="approved",
        decided_by="operator",
        decision_reference="review/approved",
    )

    with pytest.raises(ValueError, match="exactly one matching"):
        registry.record_application(
            AGENT,
            proposal.proposal_id,
            _profile(),
            applied_by="operator",
            application_reference="identity/missing",
        )


def test_outcome_requires_probation_and_revert_requires_new_linked_id(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest(proposal))
    registry.submit(proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)

    with pytest.raises(ValueError, match="probationary"):
        registry.record_outcome(
            AGENT,
            proposal.proposal_id,
            outcome="confirmed",
            recorded_by="operator",
            evidence_reference="report/1",
        )


def test_hash_chain_tampering_is_visible(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    proposal = _proposal()
    snapshot = build_self_review_snapshot(
        _profile(), evidence_manifest=_manifest(proposal))
    path = registry.submit(
        proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)

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
        registry.submit(
            proposal, snapshot_fingerprint=snapshot.snapshot_fingerprint)

    assert [
        (record["agent_id"], record["proposal_id"])
        for record in registry.all_records()
    ] == [("alpha", "REV-1"), ("alpha", "REV-3"), ("zeta", "REV-2")]
    assert [
        record["proposal_id"] for record in registry.all_records("alpha")
    ] == ["REV-1", "REV-3"]


# --------------------------------------------------------------------------- #
# Evidence-backed rollback is a NEW inverse proposal, never history deletion
# --------------------------------------------------------------------------- #


def test_reversal_proposal_is_canonical_and_preserves_old_history():
    original = _proposal()
    applied = _applied_profile(proposal=original)
    reversal = build_reversal_proposal(
        applied,
        original.proposal_id,
        proposal_id="REV-101",
        evidence_references=("post-window/regression-1",),
        reason="Post-change evidence shows the revision should be reversed.",
        risk="Reversal may restore the original failure pattern.",
    )

    assert reversal.action == "resolve_known_failure"
    assert reversal.value == original.value
    assert reversal.proposed_by == AGENT
    assert is_canonical_reversal(original, reversal) is True
    assert len(applied.revision_history) == 1
    assert applied.revision_history[0]["proposal_id"] == original.proposal_id


def test_reversal_rejects_reused_id_and_stale_effect():
    original = _proposal()
    applied = _applied_profile(proposal=original)

    with pytest.raises(ValueError, match="new proposal_id"):
        build_reversal_proposal(
            applied,
            original.proposal_id,
            proposal_id=original.proposal_id,
            evidence_references=("report/1",),
            reason="reverse",
            risk="risk",
        )

    stale = dataclasses.replace(applied, known_failures=())
    with pytest.raises(ValueError, match="no longer current"):
        build_reversal_proposal(
            stale,
            original.proposal_id,
            proposal_id="REV-102",
            evidence_references=("report/2",),
            reason="reverse stale effect",
            risk="risk",
        )
