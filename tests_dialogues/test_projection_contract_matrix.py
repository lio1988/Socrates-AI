"""
Council Live View Foundation — contract matrix + vocabulary parity + coherence.

Hardening round 1 (review findings 6 + 9):
- 22/22: every implemented payload model's required/optional fields equal the
  explicit CONTRACT_MATRIX (which encodes the parent mapping §9.2);
- the taxonomy's phase-required set and the matrix agree;
- closed projection vocabularies (sections/roles/phases/penalty flags/
  verdicts) are IDENTICAL to the canonical enums in backend.dialogues.models
  (tests may import models; the production projection package may not);
- semantic coherence validators actually fire.
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
    CedEventType,
)
from backend.dialogues.projection.payloads import (
    AssemblyCompletedPayload,
    BlockingObjectionRaisedPayload,
    DraftCreatedPayload,
    PeerScoreCompletedPayload,
    ProviderFailedPayload,
    QuorumEvaluatedPayload,
    RunCompletedPayload,
    RunnerUpReplacedPayload,
    SectionWinnerSelectedPayload,
)


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

    def test_receipt_requirement_matches_matrix(self):
        with_receipt = {
            event_type
            for event_type, contract in CONTRACT_MATRIX.items()
            if contract.receipt_required
        }
        assert with_receipt == {CedEventType.PROVIDER_COMPLETED}

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


# ── semantic coherence validators (finding 9) ────────────────────────────────

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

    def test_resolved_winner_requires_selection_data(self):
        with pytest.raises(ValidationError, match="requires"):
            SectionWinnerSelectedPayload(section="nuance", unresolved=False)

    def test_both_coherent_forms_build(self):
        SectionWinnerSelectedPayload(section="nuance", unresolved=True)
        SectionWinnerSelectedPayload(
            section="nuance", unresolved=False,
            selected_draft_id="draft_1", average_score=8.0, score_count=3)


class TestAssemblyCoherence:
    def _refs(self):
        return [
            AssemblySectionRef(section="core_answer",
                               selected_draft_id="draft_1", unresolved=False),
            AssemblySectionRef(section="nuance",
                               selected_draft_id=None, unresolved=True),
        ]

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

    def test_section_ref_coherence(self):
        with pytest.raises(ValidationError, match="no selected draft"):
            AssemblySectionRef(section="core_answer",
                               selected_draft_id="draft_1", unresolved=True)
        with pytest.raises(ValidationError, match="requires selected_draft_id"):
            AssemblySectionRef(section="core_answer",
                               selected_draft_id=None, unresolved=False)

    def test_thin_sections_must_reference_assembled_sections(self):
        with pytest.raises(ValidationError, match="thin_sections"):
            AssemblyCompletedPayload(
                answer_id="ans_1", sections=self._refs(),
                unresolved_sections=["nuance"],
                thin_sections=["blind_spots"])   # not in assembled sections

    def test_duplicate_section_refs_rejected(self):
        dup = [
            AssemblySectionRef(section="core_answer",
                               selected_draft_id="draft_1", unresolved=False),
            AssemblySectionRef(section="core_answer",
                               selected_draft_id="draft_2", unresolved=False),
        ]
        with pytest.raises(ValidationError, match="repeat"):
            AssemblyCompletedPayload(answer_id="ans_1", sections=dup,
                                     unresolved_sections=[])


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
                                  failure_category="unknown")

    def test_run_completed_status_closed(self):
        with pytest.raises(ValidationError):
            RunCompletedPayload(ratification_status="probably_great")
        p = RunCompletedPayload(ratification_status="ratified",
                                leaderboard_status="complete")
        assert p.ratification_status == "ratified"
