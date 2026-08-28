"""Every attempted live call must leave exactly one terminal accounting record.

The exploratory Q2 council lost a call entirely. The Gemini seat was assigned
the reconstruction phase, produced nothing, and the artifact recorded no turn,
no error envelope and no finish reason — while the ledger and the turn records
both stood at 12, which rules out both transport failure (that path reserves and
records) and provider failure (that path writes a finish-reason line).

The cause was structural: the turn record used to be constructed at the dispatch
boundary, so every refusal before it — identity checks, rendering, the
pre-dispatch guard, ledger admission, claim minting, claim consumption — raised
past the point where anything was written down. The council still saw a failed
provider; the evidence file saw nothing at all.

These tests pin each of those paths. No sockets are opened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    execute_bounded_text_turn_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterDynamicTurnRequestV1,
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
)


def _policy() -> OpenRouterFrozenExecutionPolicyV1:
    return OpenRouterFrozenExecutionPolicyV1(
        model="openai/gpt-5-mini",
        provider_only=("openai/flex",),
        provider_order=("openai/flex",),
        output_limit_tokens=4096,
        temperature=None,
        seed=0,
        max_price_prompt_usd_per_million="0.125",
        max_price_completion_usd_per_million="1",
        max_price_request_usd="0",
        bounded_timeout_seconds=120,
    )


def _profile() -> OpenRouterEndpointCapabilityProfileV1:
    return OpenRouterEndpointCapabilityProfileV1(
        provider_selector="openai/flex",
        canonical_model_observed="openai/gpt-5-mini-2025-08-07",
        supported_parameters=(
            "max_tokens",
            "response_format",
            "seed",
            "structured_outputs",
        ),
        output_limit_parameter="max_tokens",
        evidence_sha256="0" * 64,
    )


def _ledger(maximum_total: int = 10**12) -> OpenRouterSessionLedgerV1:
    policy = _policy()
    return OpenRouterSessionLedgerV1(
        OpenRouterLiveTestSessionAuthorizationV1(
            operator_statement="offline terminal-accounting test; no socket opens",
            policy_id=policy.policy_id or "",
            profile_id=_profile().profile_id or "",
            model="openai/gpt-5-mini",
            provider_selector="openai/flex",
            maximum_calls=8,
            maximum_total_spend_picodollars=maximum_total,
            maximum_per_call_spend_picodollars=maximum_total,
            session_id="terminal-accounting",
        )
    )


def _turn() -> OpenRouterDynamicTurnRequestV1:
    return OpenRouterDynamicTurnRequestV1(
        system_prompt="You answer briefly and exactly.",
        user_content="Is this argument valid?",
        role_seat="socrates",
        dialogue_id="dlg-terminal",
        turn_id="turn-terminal",
        dialogue_phase="reconstruction",
    )


def _never_dispatch(**_kwargs):
    raise AssertionError("no dispatch may occur on a pre-dispatch refusal path")


def _run(*, tmp_path: Path, **overrides):
    kwargs = dict(
        policy=_policy(),
        profile=_profile(),
        ledger=_ledger(),
        claim_directory=tmp_path / "claims",
        max_input_tokens=65_536,
        turn=_turn(),
        response_format_override=None,
        expected_returned_models=("openai/gpt-5-mini",),
        expected_provider_display_names=("OpenAI",),
        dispatch=_never_dispatch,
    )
    kwargs.update(overrides)
    return execute_bounded_text_turn_v1(**kwargs)


def _refused_record(callable_, /, **kwargs):
    """Run a refusal and return the record parked on the raised exception.

    The exception is re-raised unchanged on purpose: an evaluator-canary leak
    and a duplicate claim consumption must both hard-stop, and callers depend on
    the exception type to do it. Only the accounting is added.
    """
    from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
        PRE_DISPATCH_RECORD_ATTRIBUTE_V1,
    )

    with pytest.raises(Exception) as caught:
        callable_(**kwargs)
    record = getattr(caught.value, PRE_DISPATCH_RECORD_ATTRIBUTE_V1, None)
    assert record is not None, "a refused attempt must still be accounted for"
    return record, caught.value


def test_pre_dispatch_guard_refusal_is_still_accounted(tmp_path: Path) -> None:
    """A guard refusal is the exact path that lost the Gemini reconstruction call."""

    def refusing_guard(_task, _rendered):
        raise ContractValidationError("rendered prompt is over the declared bound")

    record, exc = _refused_record(
        _run, tmp_path=tmp_path, pre_dispatch_guard=refusing_guard
    )
    assert isinstance(exc, ContractValidationError), "the original type must survive"
    assert record.failure_class.startswith("pre_dispatch_refusal:")
    assert "pre_dispatch_guard" in record.failure_class
    assert record.transport_completed is False
    # Nothing was dispatched, so nothing may be charged.
    assert record.worst_case_picodollars == 0
    assert record.observed_cost_picodollars is None


def test_identity_refusal_is_accounted_before_rendering(tmp_path: Path) -> None:
    record, _exc = _refused_record(
        _run, tmp_path=tmp_path, expected_returned_models=()
    )
    assert "identity_validation" in record.failure_class
    assert record.body_sha256 == "0" * 64, "nothing was rendered to hash"


def test_ledger_refusal_is_accounted(tmp_path: Path) -> None:
    record, _exc = _refused_record(
        _run, tmp_path=tmp_path, ledger=_ledger(maximum_total=1)
    )
    assert "ledger_admission" in record.failure_class
    assert record.transport_completed is False


def test_claim_collision_is_accounted_and_still_hard_stops(tmp_path: Path) -> None:
    """The claim store is one-shot; a second identical body must not vanish."""
    ledger = _ledger()

    def failing_transport(**_kwargs):
        raise RuntimeError("transport stopped after the claim was burned")

    first = _run(tmp_path=tmp_path, ledger=ledger, dispatch=failing_transport)
    assert first.record is not None

    record, exc = _refused_record(_run, tmp_path=tmp_path, ledger=ledger)
    assert "claim_consume" in record.failure_class
    assert isinstance(exc, ContractValidationError)
    assert "already consumed" in str(exc)


def test_a_refused_turn_reaches_the_adapter_records(tmp_path: Path) -> None:
    """The record must survive to `observability_rows`, not only be raised."""
    import asyncio

    from backend.dialogues.models import (
        AgentRole,
        AgentState,
        AgentTask,
        DialogPhase,
        TaskKind,
    )
    from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
        SocratesLiveOpenRouterAdapter,
    )

    def refusing_guard(_task, _rendered):
        raise ContractValidationError("refused for the test")

    adapter = SocratesLiveOpenRouterAdapter(
        provider_id="worker_beta",
        policy=_policy(),
        profile=_profile(),
        ledger=_ledger(),
        claim_directory=tmp_path / "claims",
        max_input_tokens=65_536,
        dispatch=_never_dispatch,
        pre_dispatch_guard=refusing_guard,
        worker_alias="Beta",
        expose_model_identity_to_worker=False,
        expected_returned_models=("openai/gpt-5-mini",),
        expected_provider_display_names=("OpenAI",),
        ced_parse_repair_attempts=0,
    )
    task = AgentTask(
        session_id="s",
        agent_id="a",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.RECONSTRUCTION,
        question="Is this argument valid?",
        task_kind=TaskKind.RECONSTRUCTION_PROPOSAL,
    )
    state = AgentState(
        agent_id="a",
        role=AgentRole.SOCRATES,
        primary_role=AgentRole.SOCRATES,
        assigned_role=AgentRole.SOCRATES,
    )
    response = asyncio.run(adapter.generate_agent_move(task, state))

    assert response.status.value != "ok"
    rows = adapter.observability_rows()
    assert len(rows) == 1, "the refused attempt must appear exactly once"
    assert rows[0]["failure_class"].startswith("pre_dispatch_refusal:")
    assert rows[0]["ced_move_accepted"] is None
