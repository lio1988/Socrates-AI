"""
Council Live View Foundation — contract matrix + vocabulary parity + coherence.

Round 1 (findings 6 + 9): 22/22 payload↔matrix agreement, closed-vocabulary
parity with backend.dialogues.models, semantic coherence validators.

Round 2 (findings 1, 4, 5, 6): 22/22 EXECUTABLE identity tests (same identity
→ same key; identity change → new key; same identity + different content →
ledger conflict; wrong supplied key → reject), receipt RULES
(required / optional_pending_integration / none), frozen registries,
Phase-27 parity fields (assembly_flags / flags_by_section), typed token
usage, per-voter ratification identity.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.dialogues.models import (
    AgentRole,
    CouncilVerdict,
    DialogPhase,
    PenaltyFlag,
    SectionName,
)
from backend.dialogues.projection import (
    CONTRACT_MATRIX,
    PAYLOAD_MODELS,
    PENALTY_FLAG_NAMES,
    PHASE_NAMES,
    PHASE_REQUIRED_TYPES,
    ROLE_NAMES,
    SECTION_NAMES,
    VERDICT_NAMES,
    AssemblySectionRef,
    CedEventConflictError,
    CedEventDraft,
    CedEventType,
    EventLedger,
    ProviderTokenUsage,
    build_draft,
    derive_event_idempotency_key,
)
from backend.dialogues.projection.payloads import (
    AssemblyCompletedPayload,
    BlockingObjectionRaisedPayload,
    DraftCreatedPayload,
    PeerScoreCompletedPayload,
    ProviderFailedPayload,
    QuorumEvaluatedPayload,
    RatificationVoteRecordedPayload,
    RunCompletedPayload,
    RunnerUpReplacedPayload,
    SectionWinnerSelectedPayload,
)

RECEIPT = dict(receipt_kind="provider", request_id="req_t1_p1_0",
               receipt_digest="c" * 64)


def _five_section_refs():
    return [
        dict(section="core_answer", selected_draft_id="d1", unresolved=False),
        dict(section="crucial_stress_test", selected_draft_id="d1",
             unresolved=False),
        dict(section="blind_spots", selected_draft_id="d1", unresolved=False),
        dict(section="nuance", selected_draft_id=None, unresolved=True),
        dict(section="final_verdict", selected_draft_id="d1",
             unresolved=False),
    ]


#: One valid draft recipe per event type (envelope extras + payload).
SAMPLES = {
    CedEventType.SESSION_CREATED: dict(
        run_id=None, payload={"question": "Q?"}),
    CedEventType.RUN_STARTED: dict(payload={}),
    CedEventType.ROLE_ASSIGNED: dict(
        phase="opening", round_index=0,
        payload={"agent_id": "agent_0", "role": "socrates"}),
    CedEventType.PHASE_STARTED: dict(
        phase="opening", round_index=0, payload={}),
    CedEventType.TASK_CREATED: dict(payload=dict(
        task_id="t1", task_kind="synthesis_draft", agent_id="agent_0",
        slot_index=0, attempt_index=0, schema_name="s", context_hash="h")),
    CedEventType.PROVIDER_REQUESTED: dict(payload=dict(
        task_id="t1", provider_id="p1", requested_model="m",
        attempt_index=0)),
    CedEventType.PROVIDER_COMPLETED: dict(
        receipt_ref=RECEIPT,
        payload=dict(task_id="t1", provider_id="p1", returned_model="m",
                     latency_ms=10.0, attempt_index=0)),
    CedEventType.PROVIDER_FAILED: dict(payload=dict(
        task_id="t1", provider_id="p1", status="timeout",
        failure_category="timeout", attempt_index=0)),
    CedEventType.MOVE_VALIDATED: dict(
        phase="synthesis", round_index=0,
        payload=dict(move_id="m1", task_id="t1", agent_id="agent_0",
                     role="socrates", confidence=0.7,
                     raw_digest="a" * 64, validated_digest="b" * 64)),
    CedEventType.DRAFT_CREATED: dict(payload=dict(
        draft_id="d1", author_agent_id="agent_0", move_id="m1",
        sections_present=["core_answer"])),
    CedEventType.PEER_SCORE_REQUESTED: dict(payload=dict(
        score_task_id="st1", target_id="m1", voter_id="agent_1")),
    CedEventType.PEER_SCORE_COMPLETED: dict(payload=dict(
        score_task_id="st1", score_id="sc1", voter_id="agent_1",
        scored_kind="move", overall_score=8.0, penalty_flags=[])),
    CedEventType.PEER_SCORE_MISSING: dict(payload=dict(
        score_task_id="st1", reason="timeout")),
    CedEventType.QUORUM_EVALUATED: dict(payload=dict(
        scope="phase:opening", expected=3, valid=3, status="complete")),
    CedEventType.SECTION_WINNER_SELECTED: dict(payload=dict(
        section="nuance", unresolved=False, selected_draft_id="d1",
        average_score=8.0, score_count=3)),
    CedEventType.ASSEMBLY_COMPLETED: dict(payload=dict(
        answer_id="ans1", sections=_five_section_refs(),
        unresolved_sections=["nuance"])),
    CedEventType.BLOCKING_OBJECTION_RAISED: dict(payload=dict(
        ratification_id="rat1", provider_id="p1", target_section="nuance",
        severity="critical", required_fix="fix")),
    CedEventType.RATIFICATION_VOTE_RECORDED: dict(payload=dict(
        ratification_id="rat1", voter_id="agent_1", verdict="accept")),
    CedEventType.RUNNER_UP_REPLACED: dict(payload=dict(
        section="nuance", from_draft="d1", to_draft="d2",
        via="peer_score_ranking", round=1)),
    CedEventType.SECTION_UNRESOLVED: dict(payload=dict(
        section="nuance", reason="no valid scores")),
    CedEventType.ANSWER_WITHHELD: dict(payload=dict(
        reason="critical block", status="repair_required")),
    CedEventType.RUN_COMPLETED: dict(payload=dict(
        ratification_status="ratified")),
}

#: One identity mutation per event type: (field, is_envelope, new_value).
IDENTITY_VARIANTS = {
    CedEventType.SESSION_CREATED:            ("session_id", True, "sess_y"),
    CedEventType.RUN_STARTED:                ("run_id", True, "run_2"),
    CedEventType.ROLE_ASSIGNED:              ("agent_id", False, "agent_1"),
    CedEventType.PHASE_STARTED:              ("round_index", True, 1),
    CedEventType.TASK_CREATED:               ("task_id", False, "t2"),
    CedEventType.PROVIDER_REQUESTED:         ("attempt_index", False, 1),
    CedEventType.PROVIDER_COMPLETED:         ("attempt_index", False, 1),
    CedEventType.PROVIDER_FAILED:            ("attempt_index", False, 1),
    CedEventType.MOVE_VALIDATED:             ("move_id", False, "m2"),
    CedEventType.DRAFT_CREATED:              ("draft_id", False, "d2"),
    CedEventType.PEER_SCORE_REQUESTED:       ("score_task_id", False, "st2"),
    CedEventType.PEER_SCORE_COMPLETED:       ("score_task_id", False, "st2"),
    CedEventType.PEER_SCORE_MISSING:         ("score_task_id", False, "st2"),
    CedEventType.QUORUM_EVALUATED:           ("scope", False, "phase:elenchus"),
    CedEventType.SECTION_WINNER_SELECTED:    ("section", False, "blind_spots"),
    CedEventType.ASSEMBLY_COMPLETED:         ("answer_id", False, "ans2"),
    CedEventType.BLOCKING_OBJECTION_RAISED:  ("provider_id", False, "p2"),
    CedEventType.RATIFICATION_VOTE_RECORDED: ("voter_id", False, "agent_2"),
    CedEventType.RUNNER_UP_REPLACED:         ("round", False, 2),
    CedEventType.SECTION_UNRESOLVED:         ("section", False, "blind_spots"),
    CedEventType.ANSWER_WITHHELD:            ("run_id", True, "run_2"),
    CedEventType.RUN_COMPLETED:              ("run_id", True, "run_2"),
}


def _spec_copy(event_type: CedEventType) -> dict:
    spec = {}
    for key, value in SAMPLES[event_type].items():
        spec[key] = dict(value) if isinstance(value, dict) else value
    spec["payload"] = dict(spec["payload"])
    return spec


def _sample_draft(event_type: CedEventType, *,
                  session_id: str = None,
                  actor_id: str = None) -> CedEventDraft:
    spec = _spec_copy(event_type)
    run_id = spec.pop("run_id", "run_1")
    kwargs = dict(
        event_type=event_type,
        session_id=session_id or f"sess_{event_type.name.lower()}",
        run_id=run_id,
        **spec,
    )
    if actor_id is not None:
        kwargs["actor_id"] = actor_id
    return build_draft(**kwargs)


def _sample_with_identity_variant(event_type: CedEventType) -> CedEventDraft:
    field, is_envelope, value = IDENTITY_VARIANTS[event_type]
    spec = _spec_copy(event_type)
    session_id = f"sess_{event_type.name.lower()}"
    run_id = spec.pop("run_id", "run_1")
    if is_envelope:
        if field == "session_id":
            session_id = value
        elif field == "run_id":
            run_id = value
        else:
            spec[field] = value
    else:
        spec["payload"][field] = value
    return build_draft(event_type=event_type, session_id=session_id,
                       run_id=run_id, **spec)


# ── 22/22 matrix agreement ───────────────────────────────────────────────────

class TestContractMatrixAgreement:
    def test_matrix_covers_taxonomy_exactly(self):
        assert set(CONTRACT_MATRIX) == set(CedEventType)

    def test_every_payload_model_matches_matrix_22_of_22(self):
        for event_type, contract in CONTRACT_MATRIX.items():
            model = PAYLOAD_MODELS[event_type]
            required = {name for name, field in model.model_fields.items()
                        if field.is_required()}
            optional = set(model.model_fields) - required
            assert required == set(contract.required_payload), (
                f"{event_type.value}: required payload fields diverge from "
                f"the contract matrix (model={sorted(required)}, "
                f"matrix={sorted(contract.required_payload)})"
            )
            assert optional == set(contract.optional_payload), (
                f"{event_type.value}: optional payload fields diverge from "
                f"the contract matrix (model={sorted(optional)}, "
                f"matrix={sorted(contract.optional_payload)})"
            )

    def test_phase_required_types_agree_with_matrix(self):
        from_matrix = {
            event_type
            for event_type, contract in CONTRACT_MATRIX.items()
            if "phase" in contract.required_envelope
        }
        assert from_matrix == PHASE_REQUIRED_TYPES
        assert CedEventType.MOVE_VALIDATED in PHASE_REQUIRED_TYPES

    def test_receipt_rules_match_matrix(self):
        # Round 3, finding 3: wire vocabulary is required | optional | none
        # ("pending integration" is documentation, not a schema value).
        required = {et for et, c in CONTRACT_MATRIX.items()
                    if c.receipt == "required"}
        optional = {et for et, c in CONTRACT_MATRIX.items()
                    if c.receipt == "optional"}
        assert required == {CedEventType.PROVIDER_COMPLETED}
        assert optional == {
            CedEventType.PROVIDER_FAILED,
            CedEventType.RATIFICATION_VOTE_RECORDED,
            CedEventType.BLOCKING_OBJECTION_RAISED,
        }

    def test_every_row_declares_projection_and_identity(self):
        for event_type, contract in CONTRACT_MATRIX.items():
            assert contract.projection in (
                "public", "derived", "redacted_until_reveal")
            assert contract.idempotency_identity, (
                f"{event_type.value}: idempotency identity must be explicit"
            )

    def test_peer_score_completed_is_redacted_until_reveal(self):
        contract = CONTRACT_MATRIX[CedEventType.PEER_SCORE_COMPLETED]
        assert contract.projection == "redacted_until_reveal"


# ── frozen registries (round 2, finding 6) ───────────────────────────────────

class TestRegistryImmutability:
    def test_contract_matrix_cannot_be_mutated(self):
        weaker = CONTRACT_MATRIX[CedEventType.RUN_STARTED]
        with pytest.raises(TypeError):
            CONTRACT_MATRIX[CedEventType.PROVIDER_COMPLETED] = weaker
        with pytest.raises(TypeError):
            del CONTRACT_MATRIX[CedEventType.PROVIDER_COMPLETED]

    def test_payload_registry_cannot_be_mutated(self):
        permissive = PAYLOAD_MODELS[CedEventType.RUN_STARTED]
        with pytest.raises(TypeError):
            PAYLOAD_MODELS[CedEventType.MOVE_VALIDATED] = permissive
        with pytest.raises(TypeError):
            del PAYLOAD_MODELS[CedEventType.MOVE_VALIDATED]

    def test_contract_rows_are_frozen(self):
        row = CONTRACT_MATRIX[CedEventType.PROVIDER_COMPLETED]
        with pytest.raises(AttributeError):
            row.receipt = "none"


# ── 22/22 executable identity (round 2, finding 1) ───────────────────────────

class TestExecutableIdentity22:
    def test_same_identity_same_content_same_key_22_of_22(self):
        for event_type in CedEventType:
            a = _sample_draft(event_type)
            b = _sample_draft(event_type)
            assert a.idempotency_key == b.idempotency_key, event_type

    def test_identity_field_change_changes_key_22_of_22(self):
        for event_type in CedEventType:
            base = _sample_draft(event_type)
            variant = _sample_with_identity_variant(event_type)
            assert base.idempotency_key != variant.idempotency_key, (
                f"{event_type.value}: mutating identity field "
                f"{IDENTITY_VARIANTS[event_type][0]!r} did not change the key"
            )

    def test_same_identity_different_content_conflicts_22_of_22(self):
        # actor_id is never an identity field: same key, different semantic
        # content → the ledger must refuse the contradictory fact.
        for event_type in CedEventType:
            ledger = EventLedger()
            ledger.append(_sample_draft(event_type))
            contradictory = _sample_draft(event_type, actor_id="agent_zzz")
            assert contradictory.idempotency_key == \
                   _sample_draft(event_type).idempotency_key
            with pytest.raises(CedEventConflictError):
                ledger.append(contradictory)

    def test_wrong_supplied_key_rejected_22_of_22(self):
        for event_type in CedEventType:
            good = _sample_draft(event_type)
            with pytest.raises(ValidationError, match="contract-derived"):
                CedEventDraft(**{**good.model_dump(),
                                 "idempotency_key": "idem_" + "f" * 64})

    def test_derive_event_key_refuses_missing_identity_field(self):
        with pytest.raises(ValueError, match="identity field"):
            derive_event_idempotency_key(
                CedEventType.TASK_CREATED, session_id="s", run_id="r",
                payload={})   # no task_id


# ── vocabulary parity with canonical CED enums ───────────────────────────────

class TestVocabularyParity:
    def test_sections_match_canonical(self):
        assert set(SECTION_NAMES) == {s.value for s in SectionName}

    def test_roles_match_canonical(self):
        assert set(ROLE_NAMES) == {r.value for r in AgentRole}

    def test_phases_match_canonical(self):
        assert set(PHASE_NAMES) == {p.value for p in DialogPhase}

    def test_penalty_flags_match_canonical(self):
        assert set(PENALTY_FLAG_NAMES) == {f.value for f in PenaltyFlag}

    def test_verdicts_match_canonical(self):
        assert set(VERDICT_NAMES) == {v.value for v in CouncilVerdict}


# ── semantic coherence validators ────────────────────────────────────────────

class TestQuorumCoherence:
    def test_valid_cannot_exceed_expected(self):
        with pytest.raises(ValidationError, match="cannot exceed"):
            QuorumEvaluatedPayload(scope="phase:opening", expected=3,
                                   valid=4, status="partial")

    def test_valid_within_expected_accepted(self):
        p = QuorumEvaluatedPayload(scope="phase:opening", expected=3,
                                   valid=2, status="partial")
        assert p.valid <= p.expected

    def test_status_is_closed_vocabulary(self):
        with pytest.raises(ValidationError):
            QuorumEvaluatedPayload(scope="s", expected=3, valid=3,
                                   status="looks_fine_to_me")


class TestPeerScoreCoherence:
    BASE = dict(score_task_id="stask_1", score_id="sc_1", voter_id="agent_3",
                overall_score=8.2, penalty_flags=[])

    def test_completed_score_requires_actual_score(self):
        with pytest.raises(ValidationError) as exc_info:
            PeerScoreCompletedPayload(
                **{**self.BASE, "scored_kind": "move",
                   "overall_score": None},
            )
        assert "overall_score" in str(exc_info.value)

    def test_section_scored_requires_section_and_draft(self):
        with pytest.raises(ValidationError, match="requires section"):
            PeerScoreCompletedPayload(**self.BASE, scored_kind="section")

    def test_move_scored_must_not_carry_section(self):
        with pytest.raises(ValidationError, match="must not carry"):
            PeerScoreCompletedPayload(
                **self.BASE, scored_kind="move",
                section="core_answer", draft_id="draft_1")

    def test_valid_section_scored_builds(self):
        p = PeerScoreCompletedPayload(
            **self.BASE, scored_kind="section",
            section="core_answer", draft_id="draft_1")
        assert p.section == "core_answer"

    def test_penalty_flags_closed_and_unique(self):
        with pytest.raises(ValidationError):
            PeerScoreCompletedPayload(
                **{**self.BASE, "penalty_flags": ["made_up_flag"]},
                scored_kind="move")
        with pytest.raises(ValidationError, match="duplicates"):
            PeerScoreCompletedPayload(
                **{**self.BASE,
                   "penalty_flags": ["vague", "vague"]},
                scored_kind="move")


class TestSectionWinnerCoherence:
    def test_unresolved_winner_carries_no_selection_data(self):
        with pytest.raises(ValidationError, match="must not carry"):
            SectionWinnerSelectedPayload(
                section="nuance", unresolved=True,
                selected_draft_id="draft_1", average_score=8.0, score_count=3)

    def test_unresolved_winner_carries_no_assembly_flags(self):
        with pytest.raises(ValidationError, match="must not carry"):
            SectionWinnerSelectedPayload(
                section="nuance", unresolved=True,
                assembly_flags=["vague"])

    def test_resolved_winner_requires_selection_data(self):
        with pytest.raises(ValidationError, match="requires"):
            SectionWinnerSelectedPayload(section="nuance", unresolved=False)

    def test_assembly_flags_closed_and_unique(self):
        with pytest.raises(ValidationError, match="duplicates"):
            SectionWinnerSelectedPayload(
                section="nuance", unresolved=False,
                selected_draft_id="d1", average_score=8.0, score_count=3,
                assembly_flags=["vague", "vague"])
        p = SectionWinnerSelectedPayload(
            section="nuance", unresolved=False,
            selected_draft_id="d1", average_score=8.0, score_count=3,
            assembly_flags=["unsupported_claim", "missed_uncertainty"])
        assert p.assembly_flags == ["unsupported_claim", "missed_uncertainty"]

    def test_both_coherent_forms_build(self):
        SectionWinnerSelectedPayload(section="nuance", unresolved=True)
        SectionWinnerSelectedPayload(
            section="nuance", unresolved=False,
            selected_draft_id="draft_1", average_score=8.0, score_count=3)


class TestAssemblyCoherence:
    def _refs(self):
        return [AssemblySectionRef(**ref) for ref in _five_section_refs()]

    def test_unresolved_sections_must_match_flagged_refs(self):
        with pytest.raises(ValidationError, match="must equal"):
            AssemblyCompletedPayload(
                answer_id="ans_1", sections=self._refs(),
                unresolved_sections=[])          # nuance is flagged, not listed

    def test_coherent_assembly_builds(self):
        p = AssemblyCompletedPayload(
            answer_id="ans_1", sections=self._refs(),
            unresolved_sections=["nuance"])
        assert p.unresolved_sections == ["nuance"]

    def test_assembly_requires_all_five_locked_sections(self):
        # Round 2: exactly one ref per locked section — a 2-section
        # "assembly" is not a canonical AssembledAnswer.
        partial = self._refs()[:2]
        with pytest.raises(ValidationError, match="five locked sections"):
            AssemblyCompletedPayload(answer_id="ans_1", sections=partial,
                                     unresolved_sections=[])

    def test_section_ref_coherence(self):
        with pytest.raises(ValidationError, match="no selected draft"):
            AssemblySectionRef(section="core_answer",
                               selected_draft_id="draft_1", unresolved=True)
        with pytest.raises(ValidationError, match="requires selected_draft_id"):
            AssemblySectionRef(section="core_answer",
                               selected_draft_id=None, unresolved=False)

    def test_thin_sections_subset_and_unique(self):
        with pytest.raises(ValidationError, match="duplicates"):
            AssemblyCompletedPayload(
                answer_id="ans_1", sections=self._refs(),
                unresolved_sections=["nuance"],
                thin_sections=["blind_spots", "blind_spots"])
        p = AssemblyCompletedPayload(
            answer_id="ans_1", sections=self._refs(),
            unresolved_sections=["nuance"],
            thin_sections=["blind_spots"])
        assert p.thin_sections == ["blind_spots"]

    def test_flags_by_section_keys_and_uniqueness(self):
        with pytest.raises(ValidationError, match="duplicate flags"):
            AssemblyCompletedPayload(
                answer_id="ans_1", sections=self._refs(),
                unresolved_sections=["nuance"],
                flags_by_section={"core_answer": ["vague", "vague"]})
        p = AssemblyCompletedPayload(
            answer_id="ans_1", sections=self._refs(),
            unresolved_sections=["nuance"],
            flags_by_section={"core_answer": ["unsupported_claim"]})
        assert p.flags_by_section == {"core_answer": ["unsupported_claim"]}

    def test_flags_on_unresolved_section_rejected(self):
        # Round 3, finding 5: nuance is unresolved → no winning content to
        # flag. flags_by_section keys must be RESOLVED sections only.
        with pytest.raises(ValidationError, match="RESOLVED"):
            AssemblyCompletedPayload(
                answer_id="ans_1", sections=self._refs(),
                unresolved_sections=["nuance"],
                flags_by_section={"nuance": ["unsupported_claim"]})


class TestClosedVocabularyPayloads:
    def test_draft_created_sections_closed_and_unique(self):
        with pytest.raises(ValidationError):
            DraftCreatedPayload(draft_id="d", author_agent_id="a",
                                move_id="m", sections_present=["intro"])
        with pytest.raises(ValidationError, match="duplicates"):
            DraftCreatedPayload(
                draft_id="d", author_agent_id="a", move_id="m",
                sections_present=["nuance", "nuance"])

    def test_blocking_objection_severity_locked_to_critical(self):
        with pytest.raises(ValidationError):
            BlockingObjectionRaisedPayload(
                ratification_id="rat_1", provider_id="p1",
                target_section="nuance", severity="minor",
                required_fix="fix it")
        p = BlockingObjectionRaisedPayload(
            ratification_id="rat_1", provider_id="p1",
            target_section="nuance", severity="critical",
            required_fix="fix it")
        assert p.severity == "critical"

    def test_ratification_vote_requires_voter(self):
        with pytest.raises(ValidationError) as exc_info:
            RatificationVoteRecordedPayload(
                ratification_id="rat_1", verdict="accept")
        assert "voter_id" in str(exc_info.value)

    def test_runner_up_via_closed_and_draft_must_change(self):
        with pytest.raises(ValidationError):
            RunnerUpReplacedPayload(section="nuance", from_draft="d1",
                                    to_draft="d2", via="chairman_fiat",
                                    round=1)
        with pytest.raises(ValidationError, match="must change"):
            RunnerUpReplacedPayload(section="nuance", from_draft="d1",
                                    to_draft="d1", via="peer_score_ranking",
                                    round=1)

    def test_provider_failed_status_closed(self):
        with pytest.raises(ValidationError):
            ProviderFailedPayload(task_id="t", provider_id="p",
                                  status="mostly_fine",
                                  failure_category="unknown",
                                  attempt_index=0)

    def test_token_usage_typed_and_non_negative(self):
        with pytest.raises(ValidationError):
            ProviderTokenUsage(input_tokens=-1)
        with pytest.raises(ValidationError) as exc_info:
            ProviderTokenUsage(surprise_counter=5)
        assert "surprise_counter" in str(exc_info.value)
        usage = ProviderTokenUsage(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100

    def test_run_completed_status_closed(self):
        with pytest.raises(ValidationError):
            RunCompletedPayload(ratification_status="probably_great")
        p = RunCompletedPayload(ratification_status="ratified",
                                leaderboard_status="complete")
        assert p.ratification_status == "ratified"
