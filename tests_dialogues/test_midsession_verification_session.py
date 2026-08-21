"""Mid-session verification inside a canonical session.

Before this wiring the governing layer was a constant: every question, however
trivially checkable, returned `unresolved` with an empty basis. Honest, and
uninformative. These tests show it now discriminates, and that it still refuses
to move an objection without corroboration.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    ObjectionState, SupportState, VerificationVerdict,
)
from backend.dialogues.models import AgentState, AgentTask, ShadowScoringMode, TaskKind
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider

TASK = ("Four researchers present once each. Anna presents before Ben. "
        "Clara presents immediately before David. Ben does not present last.")
C3 = "Ben does not present last"


class VerifyingMock(ScriptedMockProvider):
    """A scripted seat that also answers objection-verification tasks.

    `holds` is what this seat reports; `span` lets a test make two seats cite
    different material while agreeing on the verdict.
    """

    def __init__(self, provider_id, *, holds=False, span=C3, malformed=False,
                 targets="conclusion"):
        super().__init__(provider_id)
        self._holds = holds
        self._span = span
        self._malformed = malformed
        self._targets = targets

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is not TaskKind.OBJECTION_VERIFICATION:
            return await super()._produce_raw_text(task, agent_state)
        if self._malformed:
            content = {"cited_spans": [{"text": "Ben must present last",
                                        "offset": 0}],
                       "condition_tested": "invented",
                       "objection_holds": True, "rationale": "fabricated"}
        else:
            content = {"cited_spans": [{"text": self._span,
                                        "offset": TASK.index(self._span)}],
                       "condition_tested": "does the objection hold?",
                       "objection_holds": self._holds,
                       "objection_targets": self._targets,
                       "rationale": "checked against the quoted constraint"}
        return json.dumps({"content": content, "confidence": 0.8})


def _run(seats, session_id):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for seat in seats:
        registry.register(seat)
    ced = CEDOrchestrator(agents, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(TASK, session_id=session_id))
    return ced, final


def _verdicts(final):
    return final.audit_summary["governing_release"].get("objection_verdicts", {})


# ── the layer now discriminates ──────────────────────────────────────────────

def test_corroborated_rejection_clears_the_objections_and_supports_release():
    """Two seats agree the objections fail, citing the same constraint."""
    seats = [VerifyingMock(f"seat{i}", holds=False) for i in range(3)]
    _ced, final = _run(seats, "mid_reject")
    verdicts = _verdicts(final)
    assert verdicts, "verification must have run"
    assert set(verdicts.values()) == {VerificationVerdict.CORROBORATED_INVALID.value}
    # Objections resolved away; nothing falsified and nothing left unresolved.
    governing = final.audit_summary["governing_release"]
    assert governing["unresolved_record_ids"] == []
    assert final.governing_epistemic_status != SupportState.FALSIFIED.value


def test_corroborated_validation_falsifies_and_blocks_the_release():
    """Two seats agree the objections hold. The claim is destroyed, loudly."""
    seats = [VerifyingMock(f"seat{i}", holds=True) for i in range(3)]
    _ced, final = _run(seats, "mid_validate")
    assert set(_verdicts(final).values()) == {
        VerificationVerdict.CORROBORATED_VALID.value}
    assert final.governing_epistemic_status == SupportState.FALSIFIED.value
    assert final.release_decision == "blocked"
    assert "falsified" in final.audit_summary["governing_release"]["blocked_reason"]


def test_the_governing_status_is_no_longer_a_constant():
    """The whole point: two sessions, same question, different verdicts."""
    _c1, rejecting = _run([VerifyingMock(f"a{i}", holds=False) for i in range(3)],
                          "mid_var_a")
    _c2, validating = _run([VerifyingMock(f"b{i}", holds=True) for i in range(3)],
                           "mid_var_b")
    assert rejecting.governing_epistemic_status != validating.governing_epistemic_status
    assert rejecting.release_decision != validating.release_decision


# ── the gate still refuses uncorroborated destruction ────────────────────────

def test_disagreement_leaves_objections_inconclusive_and_destroys_nothing():
    seats = [VerifyingMock("seat0", holds=True), VerifyingMock("seat1", holds=False),
             VerifyingMock("seat2", holds=True)]
    _ced, final = _run(seats, "mid_conflict")
    assert set(_verdicts(final).values()) == {VerificationVerdict.CONFLICTING.value}
    assert final.governing_epistemic_status != SupportState.FALSIFIED.value
    assert final.release_decision != "blocked"


def test_agreement_on_different_material_is_not_corroboration():
    seats = [VerifyingMock("seat0", holds=True, span=C3),
             VerifyingMock("seat1", holds=True, span="Anna presents before Ben"),
             VerifyingMock("seat2", holds=True, span="Clara presents immediately before David")]
    _ced, final = _run(seats, "mid_anchors")
    assert set(_verdicts(final).values()) == {
        VerificationVerdict.NO_ANCHOR_AGREEMENT.value}
    assert final.governing_epistemic_status != SupportState.FALSIFIED.value


def test_a_fabricated_citation_contributes_nothing_and_cannot_destroy():
    """Every seat lies about the task. Nothing is validated."""
    seats = [VerifyingMock(f"seat{i}", malformed=True) for i in range(3)]
    _ced, final = _run(seats, "mid_fabricated")
    assert set(_verdicts(final).values()) == {VerificationVerdict.NO_RECORDS.value}
    assert final.governing_epistemic_status != SupportState.FALSIFIED.value


def test_plain_seats_that_cannot_verify_leave_everything_unresolved():
    """The pre-wiring behaviour, still the safe default."""
    seats = [ScriptedMockProvider(f"seat{i}") for i in range(3)]
    _ced, final = _run(seats, "mid_plain")
    assert set(_verdicts(final).values()) <= {VerificationVerdict.NO_RECORDS.value}
    assert final.governing_epistemic_status == SupportState.UNRESOLVED.value


def test_too_few_seats_fails_quorum_before_any_release_is_reached():
    """A single seat cannot corroborate, and cannot even form a council.

    The registry minimum is two, so the session takes its fail-closed fallback
    and no release is produced at all. Nothing is falsified on one seat's word,
    which is the property that matters here.
    """
    seats = [VerifyingMock("solo", holds=True)]
    _ced, final = _run(seats, "mid_solo")
    assert final.audit_summary.get("quorum_failed") is True
    assert "governing_release" not in final.audit_summary
    assert final.governing_epistemic_status is None
    assert final.synthesis is None


# ── execution parity is unaffected ───────────────────────────────────────────

def test_verification_does_not_disturb_scoring_assembly_or_ratification():
    seats = [VerifyingMock(f"seat{i}", holds=False) for i in range(3)]
    _ced, final = _run(seats, "mid_parity")
    assert final.synthesis is not None
    assert [s.section_name.value for s in final.synthesis.sections] == [
        "core_answer", "crucial_stress_test", "blind_spots", "nuance",
        "final_verdict"]
    assert final.audit_summary["score_coverage"]["scores_collected"] > 0
    assert final.audit_summary["council_ratification"]["valid_verdicts"] >= 1


def test_verification_failure_never_destroys_the_canonical_response(monkeypatch):
    seats = [VerifyingMock(f"seat{i}", holds=False) for i in range(3)]

    async def exploding(*_a, **_k):
        raise RuntimeError("verifier blew up")

    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for seat in seats:
        registry.register(seat)
    ced = CEDOrchestrator(agents, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    ced.run_objection_verification = exploding
    final = asyncio.run(ced.run_registry_session(TASK, session_id="mid_boom"))
    assert final.synthesis is not None
    assert final.audit_summary["governing_release"]["available"] is False
