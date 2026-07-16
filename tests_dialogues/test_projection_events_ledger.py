"""
Council Live View Foundation — audited contract tests: envelope + ledger.

Explicit audit cases covered here:
- session.created stream semantics (typed run_id=None, session stream,
  sentinel rejection)
- sequence starts at 1; gap-free; failed append leaves no gap
- duplicate does not consume sequence; same key/different content → conflict
- payload extra-field rejection; wrong payload type; wrong event/payload
  pairing; payload-version mismatch; NaN/Infinity rejection
- immutable read results; cross-run/cross-stream isolation
- deterministic injected clock; no global ledger singleton
- production package runtime-inert
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.dialogues.projection import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    CedEventConflictError,
    CedEventDraft,
    CedEventType,
    EventLedger,
    PAYLOAD_MODELS,
    build_draft,
    derive_idempotency_key,
    run_stream_id,
    semantic_digest,
    session_stream_id,
)


def _draft(**overrides) -> CedEventDraft:
    """A valid run-scoped role.assigned draft; overrides patch any field."""
    kwargs = dict(
        event_type=CedEventType.ROLE_ASSIGNED,
        session_id="sess_x",
        run_id="run_1",
        phase="opening",
        round_index=0,
        payload={"agent_id": "agent_0", "role": "socrates"},
        idempotency_parts=["run_1", "opening", 0, "agent_0"],
    )
    kwargs.update(overrides)
    return build_draft(**kwargs)


def _session_created(session_id="sess_x", question="What is knowledge?"):
    return build_draft(
        event_type=CedEventType.SESSION_CREATED,
        session_id=session_id,
        run_id=None,
        payload={"question": question},
        idempotency_parts=[session_id],
    )


# ── envelope contract ────────────────────────────────────────────────────────

class TestEnvelopeContract:
    def test_valid_draft_builds_with_payload_schema_and_version(self):
        d = _draft()
        assert d.schema_name == SCHEMA_NAME
        assert d.schema_version == SCHEMA_VERSION
        assert d.payload_schema == "role.assigned.payload"
        assert d.payload_version == 1

    def test_unknown_event_type_rejected(self):
        with pytest.raises(ValueError, match="is not a valid CedEventType"):
            _draft(event_type="council.coup_detat")

    def test_unknown_schema_name_rejected(self):
        with pytest.raises(ValidationError, match="unknown schema name"):
            CedEventDraft(
                schema_name="ced_epistemic_event_v999",
                payload_schema="role.assigned.payload",
                payload_version=1,
                event_type=CedEventType.ROLE_ASSIGNED,
                session_id="sess_x", run_id="run_1",
                phase="opening", round_index=0,
                idempotency_key="idem_k",
                payload={"agent_id": "a", "role": "r"},
            )

    def test_unsupported_envelope_version_rejected(self):
        with pytest.raises(ValidationError,
                           match="unsupported schema_version"):
            CedEventDraft(
                schema_version=2,
                payload_schema="role.assigned.payload",
                payload_version=1,
                event_type=CedEventType.ROLE_ASSIGNED,
                session_id="sess_x", run_id="run_1",
                phase="opening", round_index=0,
                idempotency_key="idem_k",
                payload={"agent_id": "a", "role": "r"},
            )

    def test_payload_extra_field_rejected(self):
        # Must fail BECAUSE of the smuggled field, not for any other reason.
        with pytest.raises(ValidationError) as exc_info:
            _draft(payload={"agent_id": "a", "role": "r",
                            "smuggled": "field"})
        text = str(exc_info.value)
        assert "smuggled" in text
        assert "Extra inputs are not permitted" in text

    def test_payload_missing_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            _draft(payload={"agent_id": "a"})   # no "role"
        text = str(exc_info.value)
        assert "role" in text
        assert "Field required" in text

    def test_payload_wrong_type_rejected(self):
        # strict typed payloads: no lax coercion.
        with pytest.raises(ValidationError) as exc_info:
            _draft(payload={"agent_id": "a", "role": 42})
        assert "valid string" in str(exc_info.value)
        with pytest.raises(ValidationError) as exc_info:
            build_draft(
                event_type=CedEventType.TASK_CREATED,
                session_id="sess_x", run_id="run_1",
                payload=dict(task_id="t", task_kind="k", agent_id="a",
                             slot_index="0",   # str, not int → reject
                             attempt_index=0, schema_name="s",
                             context_hash="h"),
                idempotency_parts=["t"],
            )
        assert "valid integer" in str(exc_info.value)

    def test_wrong_event_payload_pairing_rejected(self):
        with pytest.raises(ValidationError, match="pairing"):
            CedEventDraft(
                payload_schema="run.started.payload",   # wrong model name
                payload_version=1,
                event_type=CedEventType.ROLE_ASSIGNED,
                session_id="sess_x", run_id="run_1",
                phase="opening", round_index=0,
                idempotency_key="idem_k",
                payload={"agent_id": "a", "role": "r"},
            )

    def test_payload_version_mismatch_rejected(self):
        with pytest.raises(ValidationError, match="payload_version"):
            CedEventDraft(
                payload_schema="role.assigned.payload",
                payload_version=99,
                event_type=CedEventType.ROLE_ASSIGNED,
                session_id="sess_x", run_id="run_1",
                phase="opening", round_index=0,
                idempotency_key="idem_k",
                payload={"agent_id": "a", "role": "r"},
            )

    def test_move_validated_requires_split_hex_digests(self):
        payload = dict(
            move_id="m1", task_id="t1", agent_id="agent_0", role="socrates",
            confidence=0.7, raw_digest="a" * 64,
        )
        with pytest.raises(ValidationError) as exc_info:
            build_draft(event_type=CedEventType.MOVE_VALIDATED,
                        session_id="s", run_id="r", payload=payload,
                        idempotency_parts=["m1"])
        text = str(exc_info.value)                  # validated_digest missing
        assert "validated_digest" in text and "Field required" in text
        with pytest.raises(ValidationError) as exc_info:
            build_draft(event_type=CedEventType.MOVE_VALIDATED,
                        session_id="s", run_id="r",
                        payload={**payload, "validated_digest": "XYZ"},
                        idempotency_parts=["m1"])
        text = str(exc_info.value)                  # not a sha256 hex digest
        assert "validated_digest" in text and "match pattern" in text
        d = build_draft(event_type=CedEventType.MOVE_VALIDATED,
                        session_id="s", run_id="r",
                        payload={**payload, "validated_digest": "b" * 64},
                        idempotency_parts=["m1"])
        assert d.payload["raw_digest"] != d.payload["validated_digest"]

    def test_nan_and_infinity_rejected(self):
        base = dict(move_id="m1", task_id="t1", agent_id="a", role="r",
                    raw_digest="a" * 64, validated_digest="b" * 64)
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValidationError) as exc_info:
                build_draft(event_type=CedEventType.MOVE_VALIDATED,
                            session_id="s", run_id="r",
                            payload={**base, "confidence": bad},
                            idempotency_parts=["m1"])
            assert "finite" in str(exc_info.value)

    def test_phase_required_for_role_assigned(self):
        with pytest.raises(ValidationError, match="phase"):
            _draft(phase=None)

    def test_empty_idempotency_key_rejected(self):
        with pytest.raises(ValidationError,
                           match="idempotency_key must be non-empty"):
            _draft(idempotency_parts=None, idempotency_key="   ")

    def test_missing_idempotency_key_field_reported_as_missing(self):
        """
        Regression for the audit-caught bug: an undeclared idempotency_key
        field made extra=forbid reject EVERY draft, so raises-tests passed
        for the wrong reason. Prove the field exists and is REQUIRED.
        """
        with pytest.raises(ValidationError) as exc_info:
            CedEventDraft(
                payload_schema="role.assigned.payload",
                payload_version=1,
                event_type=CedEventType.ROLE_ASSIGNED,
                session_id="sess_x", run_id="run_1",
                phase="opening", round_index=0,
                payload={"agent_id": "a", "role": "r"},
                # idempotency_key deliberately omitted
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("idempotency_key",) and e["type"] == "missing"
                   for e in errors), errors

    def test_missing_idempotency_identity_rejected(self):
        with pytest.raises(ValueError,
                           match="idempotency_key or idempotency_parts"):
            _draft(idempotency_parts=None, idempotency_key=None)

    def test_extra_envelope_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            _draft(surprise_field="nope")
        text = str(exc_info.value)
        assert "surprise_field" in text
        assert "Extra inputs are not permitted" in text

    def test_draft_is_frozen(self):
        d = _draft()
        with pytest.raises(ValidationError, match="frozen"):
            d.session_id = "sess_hijack"

    def test_wire_dict_uses_schema_alias(self):
        ledger = EventLedger()
        sealed = ledger.append(_draft())
        wire = sealed.wire_dict()
        assert wire["schema"] == SCHEMA_NAME
        assert "schema_name" not in wire
        assert wire["payload_schema"] == "role.assigned.payload"
        assert wire["event_type"] == "role.assigned"
        assert wire["sequence"] == 1
        assert "+00:00" in wire["emitted_at"] or wire["emitted_at"].endswith("Z")


# ── session/run stream semantics ─────────────────────────────────────────────

class TestStreamSemantics:
    def test_session_created_requires_run_id_none(self):
        d = _session_created()
        assert d.run_id is None
        assert d.stream_id == session_stream_id("sess_x") == "session:sess_x"

    def test_session_created_with_run_id_rejected(self):
        with pytest.raises(ValidationError, match="session-scoped"):
            build_draft(
                event_type=CedEventType.SESSION_CREATED,
                session_id="sess_x", run_id="run_1",
                payload={"question": "q"},
                idempotency_parts=["sess_x"],
            )

    def test_run_scoped_event_requires_run_id(self):
        with pytest.raises(ValidationError, match="run-scoped"):
            _draft(run_id=None)

    def test_sentinel_run_id_rejected(self):
        for sentinel in ("none", "None", "NULL", "n/a"):
            with pytest.raises(ValidationError, match="sentinel"):
                _draft(run_id=sentinel)

    def test_session_and_run_streams_sequence_independently(self):
        ledger = EventLedger()
        s = ledger.append(_session_created())
        r1 = ledger.append(_draft())
        r2 = ledger.append(_draft(
            payload={"agent_id": "agent_1", "role": "empiricist"},
            idempotency_parts=["run_1", "opening", 0, "agent_1"],
        ))
        assert s.sequence == 1                      # session stream starts at 1
        assert (r1.sequence, r2.sequence) == (1, 2)  # run stream independent
        assert ledger.event_count("session:sess_x") == 1
        assert ledger.event_count(run_stream_id("run_1")) == 2

    def test_stream_id_is_derived_not_asserted(self):
        # There is no stream_id field to forge — it derives from typed ids.
        assert "stream_id" not in CedEventDraft.model_fields
        assert _draft().stream_id == "run:run_1"


# ── idempotency + semantic digest ────────────────────────────────────────────

class TestIdempotencySemantics:
    def test_key_derivation_deterministic(self):
        a = derive_idempotency_key(CedEventType.ROLE_ASSIGNED, "r", "p", 0, "x")
        b = derive_idempotency_key(CedEventType.ROLE_ASSIGNED, "r", "p", 0, "x")
        assert a == b

    def test_event_type_participates_in_key(self):
        a = derive_idempotency_key(CedEventType.PHASE_STARTED, "r", "p", 0)
        b = derive_idempotency_key(CedEventType.RUN_STARTED, "r", "p", 0)
        assert a != b

    def test_semantic_digest_excludes_event_id(self):
        d1 = _draft(event_id="evt_aaaa")
        d2 = _draft(event_id="evt_bbbb")
        assert d1.event_id != d2.event_id
        assert semantic_digest(d1) == semantic_digest(d2)

    def test_semantic_digest_sees_payload_content(self):
        d1 = _draft()
        d2 = _draft(payload={"agent_id": "agent_0", "role": "empiricist"})
        assert semantic_digest(d1) != semantic_digest(d2)

    def test_duplicate_same_content_returns_existing_no_new_sequence(self):
        ledger = EventLedger()
        first = ledger.append(_draft(event_id="evt_1st"))
        dup = ledger.append(_draft(event_id="evt_2nd"))  # same semantics
        assert dup is first
        assert ledger.event_count("run:run_1") == 1
        nxt = ledger.append(_draft(
            payload={"agent_id": "agent_1", "role": "empiricist"},
            idempotency_parts=["run_1", "opening", 0, "agent_1"],
        ))
        assert nxt.sequence == 2      # duplicate consumed no sequence

    def test_same_key_different_content_raises_conflict(self):
        ledger = EventLedger()
        ledger.append(_draft())
        conflicting = _draft(
            payload={"agent_id": "agent_0", "role": "empiricist"},
        )  # same idempotency parts → same key, different semantics
        with pytest.raises(CedEventConflictError,
                           match="different semantic content"):
            ledger.append(conflicting)
        # no mutation, no sequence consumed:
        events = ledger.events_for_run("run_1")
        assert len(events) == 1
        assert events[0].payload["role"] == "socrates"

    def test_failed_append_leaves_no_gap(self):
        ledger = EventLedger()
        ledger.append(_draft())
        with pytest.raises(CedEventConflictError):
            ledger.append(_draft(
                payload={"agent_id": "agent_0", "role": "empiricist"}))
        healthy = ledger.append(_draft(
            payload={"agent_id": "agent_1", "role": "empiricist"},
            idempotency_parts=["run_1", "opening", 0, "agent_1"],
        ))
        assert healthy.sequence == 2   # contiguous: 1, 2 — no gap from failure


# ── ledger behavior ──────────────────────────────────────────────────────────

class TestEventLedger:
    def test_sequence_starts_at_one_and_is_gap_free(self):
        ledger = EventLedger()
        for i in range(5):
            ledger.append(_draft(
                payload={"agent_id": f"agent_{i}", "role": "socrates"},
                idempotency_parts=["run_1", "opening", 0, f"agent_{i}"],
            ))
        seqs = [e.sequence for e in ledger.events_for_run("run_1")]
        assert seqs == [1, 2, 3, 4, 5]

    def test_sealed_event_is_frozen(self):
        ledger = EventLedger()
        sealed = ledger.append(_draft())
        with pytest.raises(ValidationError, match="frozen"):
            sealed.sequence = 99

    def test_read_results_are_immutable_tuples(self):
        ledger = EventLedger()
        ledger.append(_draft())
        view = ledger.events_for_run("run_1")
        assert isinstance(view, tuple)
        assert isinstance(ledger.events_since("run:run_1"), tuple)
        assert isinstance(ledger.stream_ids(), tuple)
        # a fresh tuple each call; ledger state cannot be reached through it
        assert ledger.events_for_run("run_1") == view
        assert ledger.event_count("run:run_1") == 1

    def test_cross_stream_isolation(self):
        ledger = EventLedger()
        a = ledger.append(_draft(run_id="run_A",
                                 idempotency_key="idem_shared"))
        b = ledger.append(_draft(run_id="run_B",
                                 idempotency_key="idem_shared"))
        assert a.sequence == 1 and b.sequence == 1
        assert a.event_id != b.event_id     # two distinct facts
        assert len(ledger.events_for_run("run_A")) == 1
        assert len(ledger.events_for_run("run_B")) == 1
        assert ledger.events_for_run("run_C") == ()
        # session streams are isolated from run streams too:
        ledger.append(_session_created())
        assert ledger.event_count("session:sess_x") == 1
        assert ledger.event_count("run:run_A") == 1

    def test_events_since_bounded_replay(self):
        ledger = EventLedger()
        for i in range(6):
            ledger.append(_draft(
                payload={"agent_id": f"agent_{i}", "role": "socrates"},
                idempotency_parts=["run_1", "opening", 0, f"agent_{i}"],
            ))
        assert [e.sequence for e in
                ledger.events_since("run:run_1")] == [1, 2, 3, 4, 5, 6]
        assert [e.sequence for e in
                ledger.events_since("run:run_1", after_sequence=4)] == [5, 6]
        assert [e.sequence for e in
                ledger.events_since("run:run_1", limit=2)] == [1, 2]

    def test_find_by_idempotency_key(self):
        ledger = EventLedger()
        sealed = ledger.append(_draft())
        assert ledger.find_by_idempotency_key(
            "run:run_1", sealed.idempotency_key) is sealed
        assert ledger.find_by_idempotency_key("run:run_1", "idem_no") is None

    def test_deterministic_injected_clock(self):
        fixed = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
        ledger = EventLedger(clock=lambda: fixed)
        sealed = ledger.append(_draft())
        assert sealed.emitted_at == fixed

    def test_ordering_authority_is_sequence_not_timestamp(self):
        fixed = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
        ledger = EventLedger(clock=lambda: fixed)   # identical timestamps
        e1 = ledger.append(_draft())
        e2 = ledger.append(_draft(
            payload={"agent_id": "agent_1", "role": "empiricist"},
            idempotency_parts=["run_1", "opening", 0, "agent_1"],
        ))
        assert e1.emitted_at == e2.emitted_at      # timestamp cannot order
        assert e1.sequence < e2.sequence           # sequence can

    def test_no_global_ledger_singleton(self):
        import backend.dialogues.projection.ledger as ledger_module
        instances = [v for v in vars(ledger_module).values()
                     if isinstance(v, EventLedger)]
        assert instances == [], "ledger module must not ship a shared instance"

    def test_payload_registry_complete_over_taxonomy(self):
        assert set(PAYLOAD_MODELS) == set(CedEventType)
        for et, model in PAYLOAD_MODELS.items():
            assert model.PAYLOAD_SCHEMA == f"{et.value}.payload"
            assert isinstance(model.PAYLOAD_VERSION, int)


# ── runtime-inertness guard ──────────────────────────────────────────────────

class TestRuntimeInertness:
    """The projection package must not touch the execution layer (Slice 0)."""

    FORBIDDEN_IMPORT_FRAGMENTS = (
        "from backend.dialogues.ced",
        "from backend.dialogues import ced",
        "from ..ced",
        "from .ced",
        "import ced",
        "provider_registry",
        "offline_provider_adapter",
        "live_providers",
        "from ..models",
        "from backend.dialogues.models",
    )

    def test_projection_package_imports_no_execution_code(self):
        pkg_dir = (
            pathlib.Path(__file__).resolve().parent.parent
            / "backend" / "dialogues" / "projection"
        )
        sources = list(pkg_dir.glob("*.py"))
        assert len(sources) >= 6, "projection package sources not found"
        for src in sources:
            text = src.read_text(encoding="utf-8")
            for fragment in self.FORBIDDEN_IMPORT_FRAGMENTS:
                assert fragment not in text, (
                    f"{src.name} references '{fragment}' — the Slice 0 "
                    "contract package must stay runtime-inert"
                )
