"""
Council Live View — Slice 1 golden baseline (written BEFORE the observer hook).

Purpose: lock the deterministic canonical `FinalResponse` of an existing CED
run so that, once the flag-gated observer/emission hook is added, we can prove
it changes nothing:

    observer absent (this file, now)        → canonical bytes == baseline
    observer disabled (added with the hook) → canonical bytes == baseline
    observer enabled but raising (later)    → canonical bytes == baseline

History: this file was created BEFORE the hook existed (commit 65b5f14) and
locked the observer-ABSENT baseline first. The baseline classes below remain
that pre-hook checkpoint, unmodified; the observer classes
(`TestObserverEmission`, `TestAuthorityStateParity`, `TestExactFailureSequence`,
`TestObserverIsolationUnit`) were added AFTER the hook implementation and
prove — against that pre-locked baseline — that the hook changes nothing when
disabled or raising.

Determinism boundary (empirically established, not assumed): for a fixed
`(question, session_id)`, both `run_session` and `run_registry_session`
produce a `FinalResponse` whose JSON dump differs across runs in EXACTLY these
four paths — random uuids + wall-clock timestamps:

    ("response_id",)
    ("created_at",)
    ("synthesis", "answer_id")
    ("synthesis", "assembled_at")

The canonicalizer removes EXACTLY those paths — no key-name filtering, no
"strip wherever found" — so any OTHER non-determinism (a new differing path)
breaks these tests, which is the whole point of a golden baseline.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Set, Tuple

import pytest

from backend.dialogues import (
    CEDOrchestrator,
    FakeProvider,
    SocraticAgent,
    build_council,
)
from backend.dialogues.projection import (
    CedEventObserver,
    CedEventType,
    EventLedger,
    derive_projection_run_id,
    run_stream_id,
    session_stream_id,
)

QUESTION = "Is knowledge merely justified true belief?"

Path = Tuple[Any, ...]

# The EXACT paths that are non-deterministic by construction (random uuids /
# wall-clock timestamps), established empirically. Only these are removed.
VOLATILE_FINAL_RESPONSE_PATHS: Set[Path] = {
    ("response_id",),
    ("created_at",),
    ("synthesis", "answer_id"),
    ("synthesis", "assembled_at"),
}


# ── canonicalization (reused by the post-hook tests) ─────────────────────────

def _delete_path(dump: Dict, path: Path) -> None:
    """Delete an exact path from a nested dump. Missing path → safe no-op
    (existence is asserted separately in the boundary tests)."""
    *parents, last = path
    node: Any = dump
    for key in parents:
        if not isinstance(node, dict) or key not in node:
            return
        node = node[key]
    if isinstance(node, dict):
        node.pop(last, None)


def canonical_final_response_bytes(final) -> bytes:
    """Deterministic serialization of a FinalResponse: remove exactly the
    declared volatile paths, then sorted-key UTF-8 JSON, as real bytes (so the
    post-hook assertion is literally byte-identical, not merely string-equal)."""
    dump = final.model_dump(mode="json")
    for path in VOLATILE_FINAL_RESPONSE_PATHS:
        _delete_path(dump, path)
    return json.dumps(dump, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


# ── baseline runners (observer ABSENT — current code) ────────────────────────

def _legacy_council(event_observer=None):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    return CEDOrchestrator(agents, provider, event_observer=event_observer)


def _registry_council(event_observer=None):
    ced, mode = build_council(event_observer=event_observer)
    assert mode == "mock", f"golden baseline must run offline, got {mode!r}"
    return ced


def run_legacy_baseline(session_id: str = "golden_legacy_session"):
    return _legacy_council().run_session(QUESTION, session_id=session_id)


def run_registry_baseline(session_id: str = "golden_registry_session"):
    return asyncio.run(_registry_council().run_registry_session(
        QUESTION, session_id=session_id))


def run_legacy_observed(observer, session_id: str):
    ced = _legacy_council(observer)
    final = ced.run_session(QUESTION, session_id=session_id)
    return final, ced


def run_registry_observed(observer, session_id: str):
    ced = _registry_council(observer)
    final = asyncio.run(ced.run_registry_session(QUESTION,
                                                 session_id=session_id))
    return final, ced


# (run_observed, run_baseline) pairs — every observer test runs on BOTH paths.
_RUNNERS = [
    (run_legacy_observed, run_legacy_baseline),
    (run_registry_observed, run_registry_baseline),
]
_RUNNER_IDS = ["legacy", "registry"]


class _RaisingLedger:
    """Duck-typed ledger whose append always raises."""
    def append(self, draft):
        raise RuntimeError("ledger boom")


def authority_state_snapshot(state) -> Dict[str, Any]:
    """Explicit snapshot of the CANONICAL authority facts in a SessionState.

    Deliberately NOT a blind ``state.model_dump()``: each collection is
    projected field-by-field, excluding only the ids/timestamps that are
    random-by-construction (scorecard_id / score_id / ratification_id /
    answer_id / assembled_at / per-model timestamps) so that two separate
    executions of the same (question, session_id) are comparable. Everything
    authority-bearing — phases, roles, moves, drafts, scorecards, assembly,
    ratification — is included verbatim.
    """
    moves = [
        {
            "move_id": m.move_id,
            "agent_id": m.agent_id,
            "role": m.role.value,
            "phase": m.phase.value,
            "content": m.content,
            "confidence": m.confidence,
            "task_kind": m.task_kind.value if m.task_kind else None,
            "slot_index": m.slot_index,
            "attempt_index": m.attempt_index,
            "provider_id": m.provider_id,
        }
        for m in state.moves
    ]
    # SectionDraft carries no random-by-construction fields (draft ids are
    # deterministic — locked empirically by the golden baseline, where
    # selected_draft_id is byte-identical across runs).
    drafts = [d.model_dump(mode="json") for d in state.section_drafts]
    cards = [
        {
            **card.model_dump(mode="json",
                              exclude={"scorecard_id", "section_scores"}),
            "section_scores": [
                s.model_dump(mode="json", exclude={"score_id"})
                for s in card.section_scores
            ],
        }
        for card in state.draft_scorecards
    ]
    assembled = None
    if state.assembled_answer is not None:
        assembled = state.assembled_answer.model_dump(
            mode="json", exclude={"answer_id", "assembled_at"})
    council = None
    if state.council_ratification is not None:
        council = state.council_ratification.model_dump(
            mode="json", exclude={"verdicts"})
        # ratification_id / task_id / move_id on a verdict are random _uid()
        # routing ids of the ratification round-trip (empirically verified),
        # NOT authority content — the verdict, severity, target section,
        # rationale and required_fix are all kept verbatim.
        council["verdicts"] = [
            v.model_dump(mode="json",
                         exclude={"ratification_id", "task_id", "move_id"})
            for v in state.council_ratification.verdicts
        ]
    votes, status = [], None
    if state.final_response is not None:
        votes = [v.model_dump(mode="json")
                 for v in state.final_response.ratification_votes]
        status = state.final_response.ratification_status
    return {
        "phase_history": [p.value for p in state.phase_history],
        "role_history": [dict(r) for r in state.role_history],
        "moves": moves,
        "section_drafts": drafts,
        "draft_scorecards": cards,
        "assembled_answer": assembled,
        "ratification": {"council": council, "votes": votes,
                         "status": status},
    }


class _RecordFailingObserver(CedEventObserver):
    """Observer whose append AND record_failure both raise — the isolation
    choke must still swallow everything and leave the run untouched."""
    def append(self, draft):
        raise RuntimeError("append boom")

    def record_failure(self, event_type, error_type, message):
        raise RuntimeError("record boom")


# ── determinism-boundary helpers ─────────────────────────────────────────────

def _path_exists(dump: Any, path: Path) -> bool:
    node = dump
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return True


def _diff_paths(a: Any, b: Any) -> Set[Path]:
    """Full paths whose leaf values differ between two dumps. List traversal
    keeps the index in the path, so a differing list element yields a path
    NOT in the declared (string-only) volatile set — i.e. it is flagged."""
    out: Set[Path] = set()

    def walk(x: Any, y: Any, path: Path) -> None:
        if isinstance(x, dict) and isinstance(y, dict):
            for k in set(x) | set(y):
                if (k in x) != (k in y):
                    out.add(path + (k,))
                else:
                    walk(x.get(k), y.get(k), path + (k,))
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                out.add(path)
                return
            for i, (xi, yi) in enumerate(zip(x, y)):
                walk(xi, yi, path + (i,))
        elif x != y:
            out.add(path)

    walk(a, b, ())
    return out


def _assert_boundary(run_baseline) -> None:
    d1: Dict = run_baseline().model_dump(mode="json")
    d2: Dict = run_baseline().model_dump(mode="json")
    # Every declared volatile path must actually exist in both dumps, so a
    # typo or schema drift can never turn a deletion into a silent no-op.
    for path in VOLATILE_FINAL_RESPONSE_PATHS:
        assert _path_exists(d1, path), f"declared volatile path absent: {path}"
        assert _path_exists(d2, path), f"declared volatile path absent: {path}"
    observed = _diff_paths(d1, d2)
    assert observed, "expected the known uuid/timestamp volatility to be present"
    extra = observed - VOLATILE_FINAL_RESPONSE_PATHS
    assert not extra, (
        f"NEW non-deterministic path(s) outside the declared volatile set: "
        f"{sorted(map(str, extra))}"
    )


# ── tests: observer-absent baseline is locked ────────────────────────────────

class TestLegacyRunGoldenBaseline:
    def test_canonical_bytes_are_deterministic_across_runs(self):
        a = canonical_final_response_bytes(run_legacy_baseline())
        b = canonical_final_response_bytes(run_legacy_baseline())
        assert isinstance(a, bytes)
        assert a == b, "run_session canonical bytes are not deterministic"

    def test_raw_dumps_differ_only_in_declared_volatile_paths(self):
        _assert_boundary(run_legacy_baseline)

    def test_baseline_locks_a_real_answer(self):
        final = run_legacy_baseline()
        assert final.question == QUESTION
        assert final.synthesis is not None
        assert len(final.synthesis.sections) >= 1
        assert len(canonical_final_response_bytes(final)) > 200


class TestRegistryRunGoldenBaseline:
    def test_canonical_bytes_are_deterministic_across_runs(self):
        a = canonical_final_response_bytes(run_registry_baseline())
        b = canonical_final_response_bytes(run_registry_baseline())
        assert a == b, "run_registry_session canonical bytes are not deterministic"

    def test_raw_dumps_differ_only_in_declared_volatile_paths(self):
        _assert_boundary(run_registry_baseline)

    def test_baseline_locks_a_real_answer(self):
        final = run_registry_baseline()
        assert final.question == QUESTION
        assert final.synthesis is not None


class TestCanonicalizerHonesty:
    """Removing exactly the declared paths is what makes runs equal — proven
    by the fact that the raw dumps do differ while the canonical bytes match."""

    def test_removal_is_what_makes_runs_equal(self):
        f1, f2 = run_legacy_baseline(), run_legacy_baseline()
        raw_equal = (json.dumps(f1.model_dump(mode="json"), sort_keys=True)
                     == json.dumps(f2.model_dump(mode="json"), sort_keys=True))
        canon_equal = (canonical_final_response_bytes(f1)
                       == canonical_final_response_bytes(f2))
        assert not raw_equal, "raw dumps unexpectedly identical"
        assert canon_equal, "canonicalization failed to yield a stable baseline"


# ── observer emission (Slice 1) — both run paths ─────────────────────────────

def _stream_view(ledger, sid: str):
    """Per-stream event view EXCLUDING event_id + emitted_at."""
    run_id = derive_projection_run_id(sid)
    view = []
    for stream in (session_stream_id(sid), run_stream_id(run_id)):
        for e in ledger.events_for_stream(stream):
            view.append((stream, e.sequence, e.event_type.value,
                         e.run_id, e.payload))
    return view


@pytest.mark.parametrize("run_observed,run_baseline", _RUNNERS,
                         ids=_RUNNER_IDS)
class TestObserverEmission:
    def test_explicit_none_matches_omitted_baseline_bytes(
        self, run_observed, run_baseline
    ):
        sid = "obs_none"
        baseline = canonical_final_response_bytes(run_baseline(sid))
        final, _ = run_observed(None, sid)     # event_observer=None explicitly
        assert canonical_final_response_bytes(final) == baseline

    def test_enabled_observer_emits_expected_streams_and_sequences(
        self, run_observed, run_baseline
    ):
        sid = "obs_streams"
        observer = CedEventObserver(EventLedger())
        final, ced = run_observed(observer, sid)
        ledger = observer.ledger
        run_id = derive_projection_run_id(sid)

        sess = ledger.events_for_stream(session_stream_id(sid))
        run = ledger.events_for_stream(run_stream_id(run_id))

        # Session stream: exactly one session.created at sequence 1.
        assert [e.event_type.value for e in sess] == ["session.created"]
        assert sess[0].sequence == 1
        assert sess[0].payload == {"question": QUESTION}

        # Run stream: run.started, role.assigned…, run.completed — contiguous.
        types = [e.event_type.value for e in run]
        assert types[0] == "run.started"
        assert types[-1] == "run.completed"
        assert set(types[1:-1]) == {"role.assigned"}
        assert [e.sequence for e in run] == list(range(1, len(run) + 1))
        assert observer.failures == ()

        # run.completed payload FIDELITY: it must project the actual final,
        # not merely exist as the last event.
        completed = run[-1]
        assert completed.payload["ratification_status"] == \
               final.ratification_status
        if final.socratic_leaderboard is not None:
            assert completed.payload["leaderboard_status"] == (
                final.socratic_leaderboard.leaderboard_status.value
            )
        else:
            assert "leaderboard_status" not in completed.payload

    def test_role_assigned_events_match_role_history_exactly(
        self, run_observed, run_baseline
    ):
        sid = "obs_roles"
        observer = CedEventObserver(EventLedger())
        final, ced = run_observed(observer, sid)
        run_id = derive_projection_run_id(sid)
        state = ced.get_session(sid)

        role_events = [
            e for e in observer.ledger.events_for_stream(run_stream_id(run_id))
            if e.event_type.value == "role.assigned"
        ]
        assert len(role_events) == len(state.role_history) > 0
        for e, row in zip(role_events, state.role_history):
            assert e.phase == row["phase"]
            assert e.round_index == row["round_index"]
            assert e.payload["agent_id"] == row["agent_id"]
            assert e.payload["role"] == row["role"]

    def test_raising_ledger_leaves_final_byte_identical(
        self, run_observed, run_baseline
    ):
        sid = "obs_raise"
        baseline = canonical_final_response_bytes(run_baseline(sid))
        observer = CedEventObserver(_RaisingLedger())
        final, _ = run_observed(observer, sid)
        assert canonical_final_response_bytes(final) == baseline
        assert observer.failures, "raising ledger must record isolated failures"
        # bounded + sanitized: no raw exception object, message length capped
        for f in observer.failures:
            assert f.error_type == "RuntimeError"
            assert len(f.message) <= 256

    def test_record_failure_also_raising_leaves_final_byte_identical(
        self, run_observed, run_baseline
    ):
        sid = "obs_double_raise"
        baseline = canonical_final_response_bytes(run_baseline(sid))
        observer = _RecordFailingObserver(EventLedger())
        final, _ = run_observed(observer, sid)
        assert canonical_final_response_bytes(final) == baseline

    def test_event_stream_is_deterministic_across_fresh_ledgers(
        self, run_observed, run_baseline
    ):
        sid = "obs_determinism"
        o1 = CedEventObserver(EventLedger())
        o2 = CedEventObserver(EventLedger())
        run_observed(o1, sid)
        run_observed(o2, sid)
        # Same session_id → same run_id, event types, payloads, sequences;
        # only event_id + emitted_at (excluded from the view) may differ.
        assert _stream_view(o1.ledger, sid) == _stream_view(o2.ledger, sid)


@pytest.mark.parametrize("run_observed,run_baseline", _RUNNERS,
                         ids=_RUNNER_IDS)
class TestAuthorityStateParity:
    """The locked invariant beyond the FinalResponse bytes: a RAISING observer
    leaves the canonical SessionState / authority decisions identical to the
    observer-absent run."""

    def test_raising_observer_leaves_authority_state_identical(
        self, run_observed, run_baseline
    ):
        sid = "obs_authority"
        _, ced_absent = run_observed(None, sid)          # observer absent
        snap_absent = authority_state_snapshot(ced_absent.get_session(sid))

        observer = CedEventObserver(_RaisingLedger())
        _, ced_raising = run_observed(observer, sid)     # every emit raises
        snap_raising = authority_state_snapshot(ced_raising.get_session(sid))

        assert observer.failures, "sanity: the ledger did raise"
        assert snap_absent == snap_raising, (
            "a raising observer changed canonical authority state"
        )
        # The snapshot is non-trivial (locks real authority content).
        assert snap_absent["role_history"]
        assert snap_absent["moves"]
        assert snap_absent["assembled_answer"] is not None


@pytest.mark.parametrize(
    "run_observed,expected_role_failures",
    [(run_legacy_observed, 15), (run_registry_observed, 14)],
    ids=_RUNNER_IDS,
)
class TestExactFailureSequence:
    """Every emission attempt is isolated INDIVIDUALLY: no failure stops the
    subsequent emissions, and run.completed is still attempted after all
    prior failures. Locked as an exact ordered sequence, not just non-empty."""

    def test_raising_ledger_failure_sequence_is_exact(
        self, run_observed, expected_role_failures
    ):
        observer = CedEventObserver(_RaisingLedger())
        run_observed(observer, "obs_fail_seq")
        types = [f.event_type for f in observer.failures]
        expected = (["session.created", "run.started"]
                    + ["role.assigned"] * expected_role_failures
                    + ["run.completed"])
        assert types == expected
        assert len(types) == expected_role_failures + 3
        assert all(f.error_type == "RuntimeError" for f in observer.failures)


class TestObserverIsolationUnit:
    def test_emit_event_does_not_call_build_when_disabled(self):
        ced = _legacy_council(event_observer=None)
        called = []
        ced._emit_event(CedEventType.RUN_STARTED,
                        lambda: called.append(1) or None)
        assert called == [], "build() must not run when the observer is None"

    def test_disabled_run_touches_no_ledger(self):
        # A disabled run leaves the caller's ledger empty (nothing emitted).
        ledger = EventLedger()
        # observer built but NOT injected → CED never sees it.
        _ = CedEventObserver(ledger)
        run_legacy_baseline("obs_disabled")
        assert ledger.stream_ids() == ()

    def test_failure_history_is_bounded_with_visible_loss(self):
        # A long-lived observer must not grow without limit: history caps at
        # 256 (oldest drop first) while the total counter keeps counting.
        observer = CedEventObserver(EventLedger())
        for i in range(300):
            observer.record_failure("role.assigned", "RuntimeError",
                                    f"boom {i}")
        assert observer.total_failure_count == 300
        assert len(observer.failures) == 256
        assert observer.dropped_failure_count == 44
        assert observer.failures[0].message == "boom 44"    # oldest retained
        assert observer.failures[-1].message == "boom 299"  # newest retained
