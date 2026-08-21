"""H1 Hybrid epistemic ledger shadow-mode invariants.

The H1 observer may record canonical artifacts, but it cannot influence CED
authority, provider behavior, scoring, assembly, ratification, or public output.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import itertools
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_shadow import (
    HybridLedgerConflict,
    HybridRecordKind,
    HybridShadowObserver,
    HybridEpistemicLedger,
)
from backend.dialogues.models import ShadowScoringMode
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider


QUESTION = "Is knowledge merely justified true belief?"
FIXED_NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class ModelSeatProvider(ScriptedMockProvider):
    def __init__(self, provider_id: str, model: str) -> None:
        super().__init__(provider_id)
        self.model = model
        self.calls = []

    async def generate_agent_move(self, task, agent_state):
        self.calls.append((
            task.agent_id,
            task.role.value,
            task.phase.value,
            task.task_kind.value if task.task_kind else None,
            task.round_number,
            task.slot_index,
            task.attempt_index,
        ))
        return await super().generate_agent_move(task, agent_state)


class ExplodingLedger(HybridEpistemicLedger):
    def __init__(self, explode_on: int = 3) -> None:
        super().__init__()
        self._explode_on = explode_on
        self._append_calls = 0

    def append(self, *args, **kwargs):
        self._append_calls += 1
        if self._append_calls == self._explode_on:
            raise RuntimeError("shadow append failed")
        return super().append(*args, **kwargs)


class SnapshotObserver(HybridShadowObserver):
    def capture_session(self, state, final, *, provider_catalog=()):
        self.state_before = state.model_dump_json()
        self.final_before = final.model_dump_json()
        result = super().capture_session(
            state, final, provider_catalog=provider_catalog,
        )
        self.state_after = state.model_dump_json()
        self.final_after = final.model_dump_json()
        return result


def _patch_determinism(monkeypatch):
    counter = itertools.count()
    monkeypatch.setattr(
        "backend.dialogues.models._uid",
        lambda prefix="": f"{prefix}{next(counter):012d}",
    )
    monkeypatch.setattr("backend.dialogues.models._utcnow", lambda: FIXED_NOW)
    return counter


def _registry_ced(*, observer=None):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    registry.register(ModelSeatProvider("seat_a", "openai/gpt-4.1-mini"))
    registry.register(ModelSeatProvider("seat_b", "openai/gpt-4o-mini"))
    registry.register(ModelSeatProvider(
        "seat_c", "meta-llama/llama-3.3-70b-instruct",
    ))
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(3)]
    ced = CEDOrchestrator(
        agents,
        provider,
        registry=registry,
        assembly_fallback=True,
        hybrid_shadow=observer,
    )
    return ced


def _legacy_ced(*, observer=None):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(3)]
    return CEDOrchestrator(agents, provider, hybrid_shadow=observer)


def _call_trace(ced):
    return {
        adapter.provider_id: list(adapter.calls)
        for adapter in ced.registry.all_adapters()
    }


def _run_registry(ced, session_id="h1-shadow-parity"):
    final = asyncio.run(ced.run_registry_session(
        QUESTION,
        session_id=session_id,
    ))
    return final, ced.get_session(session_id)


def _without_wall_clock(model):
    dynamic = {
        "timestamp", "created_at", "updated_at", "assembled_at", "latency_ms",
    }

    def clean(value):
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if key not in dynamic
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(model.model_dump(mode="json"))


def test_ledger_is_deterministic_idempotent_append_only_and_replayable():
    ledger = HybridEpistemicLedger()
    first = ledger.append(
        session_id="session-1",
        kind=HybridRecordKind.SESSION_OBSERVED,
        subject_ref="session:session-1",
        payload={"question_sha256": "a" * 64},
    )
    duplicate = ledger.append(
        session_id="session-1",
        kind=HybridRecordKind.SESSION_OBSERVED,
        subject_ref="session:session-1",
        payload={"question_sha256": "a" * 64},
    )
    second = ledger.append(
        session_id="session-1",
        kind=HybridRecordKind.PHASE_OBSERVED,
        subject_ref="phase:0:opening",
        payload={"phase": "opening", "ordinal": 0},
    )

    assert duplicate == first
    assert first.sequence == 1
    assert second.sequence == 2
    assert second.previous_record_id == first.record_id
    assert len(ledger.records("session-1")) == 2
    assert ledger.replay("session-1") == ledger.records("session-1")

    clone = HybridEpistemicLedger.from_records(ledger.records("session-1"))
    assert clone.records("session-1") == ledger.records("session-1")

    with pytest.raises(HybridLedgerConflict):
        ledger.append(
            session_id="session-1",
            kind=HybridRecordKind.SESSION_OBSERVED,
            subject_ref="session:session-1",
            payload={"question_sha256": "b" * 64},
        )


def test_ledger_reads_do_not_expose_mutable_internal_payloads():
    ledger = HybridEpistemicLedger()
    ledger.append(
        session_id="session-immutable",
        kind=HybridRecordKind.SESSION_OBSERVED,
        subject_ref="session:session-immutable",
        payload={"nested": {"value": 1}},
    )
    read = ledger.records("session-immutable")
    read[0].payload["nested"]["value"] = 99
    assert ledger.records("session-immutable")[0].payload == {
        "nested": {"value": 1},
    }


def test_registry_shadow_is_byte_identical_and_call_identical(monkeypatch):
    _patch_determinism(monkeypatch)
    baseline = _registry_ced()
    baseline_final, baseline_state = _run_registry(baseline)
    baseline_calls = _call_trace(baseline)

    _patch_determinism(monkeypatch)
    ledger = HybridEpistemicLedger()
    observer = SnapshotObserver(ledger)
    shadow = _registry_ced(observer=observer)
    shadow_final, shadow_state = _run_registry(shadow)

    assert _without_wall_clock(shadow_final) == _without_wall_clock(baseline_final)
    assert _without_wall_clock(shadow_state) == _without_wall_clock(baseline_state)
    assert _call_trace(shadow) == baseline_calls
    assert observer.final_before == observer.final_after == shadow_final.model_dump_json()
    assert observer.state_before == observer.state_after == shadow_state.model_dump_json()
    assert shadow.hybrid_shadow_failures("h1-shadow-parity") == ()


def test_legacy_shadow_is_byte_identical(monkeypatch):
    _patch_determinism(monkeypatch)
    baseline = _legacy_ced()
    baseline_final = baseline.run_session(QUESTION, session_id="h1-legacy")
    baseline_state = baseline.get_session("h1-legacy")

    _patch_determinism(monkeypatch)
    ledger = HybridEpistemicLedger()
    observer = SnapshotObserver(ledger)
    shadow = _legacy_ced(observer=observer)
    shadow_final = shadow.run_session(QUESTION, session_id="h1-legacy")
    shadow_state = shadow.get_session("h1-legacy")

    assert _without_wall_clock(shadow_final) == _without_wall_clock(baseline_final)
    assert _without_wall_clock(shadow_state) == _without_wall_clock(baseline_state)
    assert observer.final_before == observer.final_after == shadow_final.model_dump_json()
    assert observer.state_before == observer.state_after == shadow_state.model_dump_json()
    assert ledger.records("h1-legacy")


def test_shadow_append_failure_cannot_change_canonical_output(monkeypatch):
    _patch_determinism(monkeypatch)
    baseline = _registry_ced()
    baseline_final, baseline_state = _run_registry(baseline, "h1-failure")
    baseline_calls = _call_trace(baseline)

    _patch_determinism(monkeypatch)
    shadow = _registry_ced(
        observer=HybridShadowObserver(ExplodingLedger()),
    )
    shadow_final, shadow_state = _run_registry(shadow, "h1-failure")

    assert _without_wall_clock(shadow_final) == _without_wall_clock(baseline_final)
    assert _without_wall_clock(shadow_state) == _without_wall_clock(baseline_state)
    assert _call_trace(shadow) == baseline_calls
    assert shadow.hybrid_shadow_failures("h1-failure") == ("RuntimeError",)
    assert "hybrid" not in shadow_final.model_dump_json().lower()


def test_shadow_records_exact_model_provenance_without_raw_prompts_or_secrets():
    ledger = HybridEpistemicLedger()
    observer = HybridShadowObserver(ledger)
    ced = _registry_ced(observer=observer)
    final, state = _run_registry(ced, "h1-provenance")

    records = ledger.records("h1-provenance")
    kinds = {record.kind for record in records}
    assert {
        HybridRecordKind.SESSION_OBSERVED,
        HybridRecordKind.PROVIDER_OBSERVED,
        HybridRecordKind.ROLE_ASSIGNMENT_OBSERVED,
        HybridRecordKind.PHASE_OBSERVED,
        HybridRecordKind.TASK_OBSERVED,
        HybridRecordKind.MOVE_OBSERVED,
        HybridRecordKind.SECTION_DRAFT_OBSERVED,
        HybridRecordKind.MOVE_QUALITY_SCORE_OBSERVED,
        HybridRecordKind.SECTION_QUALITY_SCORE_OBSERVED,
        HybridRecordKind.ASSEMBLY_OBSERVED,
        HybridRecordKind.RATIFICATION_OBSERVED,
        HybridRecordKind.FINAL_RESPONSE_OBSERVED,
    } <= kinds

    providers = {
        record.payload["provider_id"]: record.payload["model"]
        for record in records
        if record.kind == HybridRecordKind.PROVIDER_OBSERVED
    }
    assert providers == {
        "seat_a": "openai/gpt-4.1-mini",
        "seat_b": "openai/gpt-4o-mini",
        "seat_c": "meta-llama/llama-3.3-70b-instruct",
    }
    assert all(record.authority == "shadow_non_authoritative" for record in records)

    blob = json.dumps([r.model_dump(mode="json") for r in records], sort_keys=True)
    assert QUESTION not in blob
    assert final.answer not in blob
    assert "api_key" not in blob.lower()
    assert "authorization" not in blob.lower()
    assert "system_prompt" not in blob.lower()
    assert "hybrid" not in state.model_dump()
    assert "hybrid" not in final.model_dump()


def test_quality_records_are_explicitly_non_epistemic():
    ledger = HybridEpistemicLedger()
    ced = _registry_ced(observer=HybridShadowObserver(ledger))
    _run_registry(ced, "h1-quality")

    quality = [
        r for r in ledger.records("h1-quality")
        if r.kind in {
            HybridRecordKind.MOVE_QUALITY_SCORE_OBSERVED,
            HybridRecordKind.SECTION_QUALITY_SCORE_OBSERVED,
        }
    ]
    assert quality
    assert all(r.payload["signal_class"] == "quality_only" for r in quality)
    assert all("verification" not in r.payload for r in quality)
    assert all("epistemic_support" not in r.payload for r in quality)


def test_duplicate_capture_is_idempotent_and_replay_deterministic():
    ledger = HybridEpistemicLedger()
    observer = HybridShadowObserver(ledger)
    ced = _registry_ced(observer=observer)
    final, state = _run_registry(ced, "h1-replay")
    first = ledger.records("h1-replay")

    observer.capture_session(
        state,
        final,
        provider_catalog=ced._council_roster(),
    )
    second = ledger.records("h1-replay")

    assert second == first
    assert ledger.replay("h1-replay") == first
    assert [r.sequence for r in first] == list(range(1, len(first) + 1))
    assert len({r.record_id for r in first}) == len(first)
    assert len({r.idempotency_key for r in first}) == len(first)


def test_shadow_record_stream_is_deterministic_across_equivalent_runs():
    streams = []
    for _ in range(2):
        ledger = HybridEpistemicLedger()
        ced = _registry_ced(observer=HybridShadowObserver(ledger))
        _run_registry(ced, "h1-equivalent-replay")
        streams.append([
            record.model_dump(mode="json")
            for record in ledger.records("h1-equivalent-replay")
        ])
    assert streams[0] == streams[1]


def test_quorum_fallback_is_observed_without_fabricated_answer():
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    registry.register(ModelSeatProvider("only_seat", "openai/gpt-4.1-mini"))
    ledger = HybridEpistemicLedger()
    ced = CEDOrchestrator(
        [SocraticAgent("agent_0", provider), SocraticAgent("agent_1", provider)],
        provider,
        registry=registry,
        hybrid_shadow=HybridShadowObserver(ledger),
    )

    final, _state = _run_registry(ced, "h1-fallback")
    last = ledger.records("h1-fallback")[-1]

    assert final.ratification_status == "quorum_failed"
    assert final.answer == ""
    assert last.kind == HybridRecordKind.FINAL_RESPONSE_OBSERVED
    assert last.payload["ratification_status"] == "quorum_failed"
    assert last.payload["answer_present"] is False


def test_default_disabled_has_no_shadow_side_effects():
    ced = _registry_ced()
    final, state = _run_registry(ced, "h1-disabled")
    assert ced.hybrid_shadow is None
    assert ced.hybrid_shadow_failures("h1-disabled") == ()
    assert "hybrid" not in final.model_dump()
    assert "hybrid" not in state.model_dump()
