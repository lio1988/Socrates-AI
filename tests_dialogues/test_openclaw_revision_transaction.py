"""Crash and recovery tests for self-revision application transactions."""

import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    SelfRevisionTransactionCoordinator,
    build_self_review_snapshot,
    profile_fingerprint,
)

AGENT = "agent_alpha"
PROPOSAL_ID = "REV-TX-1"
REFERENCE = "evidence/tx-1"
VALUE = "rushes exact-output tasks"


def _profile():
    return AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
        next_gate="gate_v0_3_to_v0_4",
        role_strengths={"blind_spots": 0.5},
        section_wins={"blind_spots": 1},
        section_opportunities={"blind_spots": 2},
        sessions_analyzed=2,
        ratified_sessions=2,
    )


def _proposal():
    return SelfRevisionProposal(
        proposal_id=PROPOSAL_ID,
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=VALUE,
        reason="Repeated attributed evidence shows this pattern.",
        evidence_references=(REFERENCE,),
        risk="The evidence window may still be narrow.",
    )


def _manifest():
    return {
        REFERENCE: {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-attribution",
            "supports": ["identity:add_known_failure"],
            "value": VALUE,
            "verified_by": "evidence-harness",
            "verification_reference": "verification/tx-1",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }


def _setup(tmp_path):
    identity = IdentityRegistry(tmp_path / "identity")
    lifecycle = SelfRevisionRegistry(tmp_path / "lifecycle")
    profile = _profile()
    proposal = _proposal()
    manifest = _manifest()
    identity.save_profile(profile)
    lifecycle.submit(
        proposal,
        snapshot=build_self_review_snapshot(
            profile, evidence_manifest=manifest),
    )
    lifecycle.record_evaluation(
        AGENT,
        PROPOSAL_ID,
        current_profile=profile,
        evidence_manifest=manifest,
        evaluated_by="evidence-harness",
    )
    lifecycle.record_decision(
        AGENT,
        PROPOSAL_ID,
        current_profile=profile,
        evidence_manifest=manifest,
        decision="approved",
        decided_by="operator",
        decision_reference="review/tx-1",
    )
    coordinator = SelfRevisionTransactionCoordinator(
        identity, lifecycle, tmp_path / "transactions")
    return identity, lifecycle, coordinator, profile, manifest


def test_happy_path_commits_both_identity_and_lifecycle(tmp_path):
    identity, lifecycle, coordinator, original, manifest = _setup(tmp_path)
    updated = coordinator.apply_approved(
        AGENT,
        PROPOSAL_ID,
        evidence_manifest=manifest,
        applied_by="operator",
        application_reference="identity/tx-1",
        applied_on="2026-07-10",
    )

    assert updated.known_failures == (VALUE,)
    assert identity.load_profile(AGENT) == updated
    assert lifecycle.load(AGENT, PROPOSAL_ID)["status"] == "probationary"
    journal = coordinator.load(AGENT, PROPOSAL_ID)
    assert journal["state"] == "committed"
    assert [event["event_type"] for event in journal["events"]] == [
        "prepared", "identity_saved", "lifecycle_recorded", "committed"]
    assert journal["payload"]["previous_governed_fingerprint"] == \
        profile_fingerprint(original)
    assert journal["payload"]["updated_governed_fingerprint"] == \
        profile_fingerprint(updated)


def test_recover_after_identity_save_before_lifecycle_application(tmp_path):
    identity, lifecycle, _, _, manifest = _setup(tmp_path)

    class FailBeforeLifecycle(SelfRevisionRegistry):
        def record_application(self, *args, **kwargs):
            raise RuntimeError("simulated crash before lifecycle application")

    failing = FailBeforeLifecycle(lifecycle.directory)
    coordinator = SelfRevisionTransactionCoordinator(
        identity, failing, tmp_path / "transactions")
    with pytest.raises(RuntimeError, match="simulated crash"):
        coordinator.apply_approved(
            AGENT,
            PROPOSAL_ID,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/tx-1",
        )

    assert identity.load_profile(AGENT).known_failures == (VALUE,)
    assert lifecycle.load(AGENT, PROPOSAL_ID)["status"] == "approved"
    assert coordinator.load(AGENT, PROPOSAL_ID)["state"] == "identity_saved"

    recovered = SelfRevisionTransactionCoordinator(
        identity, lifecycle, tmp_path / "transactions").recover(
            AGENT, PROPOSAL_ID)
    assert recovered.known_failures == (VALUE,)
    assert lifecycle.load(AGENT, PROPOSAL_ID)["status"] == "probationary"


def test_recover_after_lifecycle_application_before_journal_event(tmp_path):
    identity, lifecycle, _, _, manifest = _setup(tmp_path)

    class FailAfterLifecycle(SelfRevisionRegistry):
        def record_application(self, *args, **kwargs):
            result = super().record_application(*args, **kwargs)
            raise RuntimeError("simulated crash after lifecycle application")

    failing = FailAfterLifecycle(lifecycle.directory)
    coordinator = SelfRevisionTransactionCoordinator(
        identity, failing, tmp_path / "transactions")
    with pytest.raises(RuntimeError, match="simulated crash"):
        coordinator.apply_approved(
            AGENT,
            PROPOSAL_ID,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/tx-1",
        )

    assert identity.load_profile(AGENT).known_failures == (VALUE,)
    assert lifecycle.load(AGENT, PROPOSAL_ID)["status"] == "probationary"
    assert coordinator.load(AGENT, PROPOSAL_ID)["state"] == "identity_saved"

    recovered = SelfRevisionTransactionCoordinator(
        identity, lifecycle, tmp_path / "transactions").recover(
            AGENT, PROPOSAL_ID)
    assert recovered.known_failures == (VALUE,)
    assert SelfRevisionTransactionCoordinator(
        identity, lifecycle, tmp_path / "transactions").load(
            AGENT, PROPOSAL_ID)["state"] == "committed"


def test_recover_prepared_transaction_when_identity_write_failed(tmp_path):
    identity, lifecycle, _, original, manifest = _setup(tmp_path)

    class FailIdentity(IdentityRegistry):
        def save_profile(self, profile):
            if profile.revision_history:
                raise RuntimeError("simulated identity write failure")
            return super().save_profile(profile)

    failing_identity = FailIdentity(identity.directory)
    coordinator = SelfRevisionTransactionCoordinator(
        failing_identity, lifecycle, tmp_path / "transactions")
    with pytest.raises(RuntimeError, match="identity write failure"):
        coordinator.apply_approved(
            AGENT,
            PROPOSAL_ID,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/tx-1",
        )

    assert identity.load_profile(AGENT) == original
    assert lifecycle.load(AGENT, PROPOSAL_ID)["status"] == "approved"
    assert coordinator.load(AGENT, PROPOSAL_ID)["state"] == "prepared"

    recovered = SelfRevisionTransactionCoordinator(
        identity, lifecycle, tmp_path / "transactions").recover(
            AGENT, PROPOSAL_ID)
    assert recovered.known_failures == (VALUE,)


def test_recovery_allows_observational_refresh_but_refuses_governed_drift(
        tmp_path):
    identity, lifecycle, coordinator, _, manifest = _setup(tmp_path)

    class FailBeforeLifecycle(SelfRevisionRegistry):
        def record_application(self, *args, **kwargs):
            raise RuntimeError("stop after identity save")

    failing = SelfRevisionTransactionCoordinator(
        identity,
        FailBeforeLifecycle(lifecycle.directory),
        tmp_path / "transactions",
    )
    with pytest.raises(RuntimeError):
        failing.apply_approved(
            AGENT,
            PROPOSAL_ID,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/tx-1",
        )

    saved = identity.load_profile(AGENT)
    refreshed = dataclasses_replace_metrics(saved)
    identity.save_profile(refreshed)
    recovered = coordinator.recover(AGENT, PROPOSAL_ID)
    assert recovered.sessions_analyzed == 4
    assert recovered.known_failures == (VALUE,)


def test_conflicting_governed_state_refuses_recovery(tmp_path):
    identity, lifecycle, _, _, manifest = _setup(tmp_path)

    class FailBeforeLifecycle(SelfRevisionRegistry):
        def record_application(self, *args, **kwargs):
            raise RuntimeError("stop after identity save")

    failing = SelfRevisionTransactionCoordinator(
        identity,
        FailBeforeLifecycle(lifecycle.directory),
        tmp_path / "transactions",
    )
    with pytest.raises(RuntimeError):
        failing.apply_approved(
            AGENT,
            PROPOSAL_ID,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/tx-1",
        )
    saved = identity.load_profile(AGENT)
    drifted = dataclasses_replace_governed_drift(saved)
    # Direct registry save is correctly refused, so emulate external disk damage.
    path = identity.directory / f"{AGENT}.json"
    path.write_text(json.dumps(drifted.to_record()), encoding="utf-8")
    with pytest.raises(ValueError, match="conflicts|corrupt"):
        SelfRevisionTransactionCoordinator(
            identity, lifecycle, tmp_path / "transactions").recover(
                AGENT, PROPOSAL_ID)


def test_journal_tampering_and_duplicate_application_are_visible(tmp_path):
    identity, lifecycle, coordinator, _, manifest = _setup(tmp_path)
    coordinator.apply_approved(
        AGENT,
        PROPOSAL_ID,
        evidence_manifest=manifest,
        applied_by="operator",
        application_reference="identity/tx-1",
    )
    with pytest.raises(ValueError, match="already exists"):
        coordinator.apply_approved(
            AGENT,
            PROPOSAL_ID,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/tx-1",
        )

    path = tmp_path / "transactions" / AGENT / f"{PROPOSAL_ID}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["application_actor"] = "attacker"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        coordinator.load(AGENT, PROPOSAL_ID)


def dataclasses_replace_metrics(profile):
    import dataclasses
    return dataclasses.replace(
        profile,
        role_strengths={"blind_spots": 0.75},
        section_wins={"blind_spots": 3},
        section_opportunities={"blind_spots": 4},
        sessions_analyzed=4,
        ratified_sessions=3,
    )


def dataclasses_replace_governed_drift(profile):
    import dataclasses
    return dataclasses.replace(
        profile,
        soul_principles=("unaudited governed drift",),
    )
