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
from backend.dialogues.models import DialogPhase
from backend.dialogues.projection import (
    CedEventObserver,
    CedEventType,
    EventLedger,
    derive_projection_run_id,
    run_stream_id,
    session_stream_id,
    sha256_hex,
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

        # Run stream: run.started, then interleaved phase/role/task (and, on
        # the registry path, move.validated), then run.completed — contiguous.
        types = [e.event_type.value for e in run]
        assert types[0] == "run.started"
        assert types[-1] == "run.completed"
        middle = set(types[1:-1])
        assert {"role.assigned", "phase.started", "task.created"} <= middle
        assert middle <= {"role.assigned", "phase.started", "task.created",
                          "move.validated", "provider.failed"}
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
    "run_observed,expected_total",
    [(run_legacy_observed, 40), (run_registry_observed, 155)],
    ids=_RUNNER_IDS,
)
class TestExactFailureSequence:
    """Every emission attempt is isolated INDIVIDUALLY: no failure stops the
    subsequent emissions, and run.completed is still attempted after all
    prior failures.

    Locked TWO ways: (a) cross-mode parity — the raising-ledger attempt
    sequence must equal ["session.created"] + the run-stream event types of
    an ENABLED run of the same session (the round-4 invariant: success and
    failure modes agree on how many emissions were attempted, in what
    order); (b) an exact empirical total as a canary (legacy 40 = 1 session
    + 1 started + 8 phase + 15 role + 14 deliberation tasks + 1 completed;
    registry 155 adds 14 move.validated + 102 scoring tasks, minus the
    legacy ratification role)."""

    def test_raising_attempts_equal_enabled_emissions(
        self, run_observed, expected_total
    ):
        sid = "obs_fail_seq"
        enabled = CedEventObserver(EventLedger())
        run_observed(enabled, sid)
        run_id = derive_projection_run_id(sid)
        reference = ["session.created"] + [
            e.event_type.value
            for e in enabled.ledger.events_for_stream(run_stream_id(run_id))
        ]

        raising = CedEventObserver(_RaisingLedger())
        run_observed(raising, sid)
        types = [f.event_type for f in raising.failures]
        assert types == reference
        assert len(types) == expected_total
        assert types[-1] == "run.completed"
        assert all(f.error_type == "RuntimeError" for f in raising.failures)


_CANONICAL_PHASE_SEQUENCE = [
    "opening", "initial_response", "elenchus", "reflection",
    "reconstruction", "synthesis", "ratification", "complete",
]


def _phase_events(ledger, sid):
    run_id = derive_projection_run_id(sid)
    return [e for e in ledger.events_for_stream(run_stream_id(run_id))
            if e.event_type.value == "phase.started"]


@pytest.mark.parametrize("run_observed,run_baseline", _RUNNERS,
                         ids=_RUNNER_IDS)
class TestPhaseEvents:
    """phase.started semantics: the canonical SessionState.phase just ENTERED
    this phase and its work can begin — full coverage on both paths."""

    def test_exact_canonical_phase_sequence(self, run_observed, run_baseline):
        sid = "ph_seq"
        observer = CedEventObserver(EventLedger())
        run_observed(observer, sid)
        assert [e.phase for e in _phase_events(observer.ledger, sid)] == \
               _CANONICAL_PHASE_SEQUENCE

    def test_parity_with_phase_history_plus_current(self, run_observed,
                                                    run_baseline):
        sid = "ph_parity"
        observer = CedEventObserver(EventLedger())
        _, ced = run_observed(observer, sid)
        state = ced.get_session(sid)
        expected = [p.value for p in state.phase_history] + [state.phase.value]
        assert [e.phase for e in _phase_events(observer.ledger, sid)] == expected

    def test_each_phase_started_precedes_its_role_assignments(
        self, run_observed, run_baseline
    ):
        sid = "ph_order"
        observer = CedEventObserver(EventLedger())
        run_observed(observer, sid)
        run_id = derive_projection_run_id(sid)
        events = observer.ledger.events_for_stream(run_stream_id(run_id))
        started_seq = {e.phase: e.sequence for e in events
                       if e.event_type.value == "phase.started"}
        for e in events:
            if e.event_type.value == "role.assigned":
                assert started_seq[e.phase] < e.sequence, (
                    f"role.assigned@{e.phase} at seq {e.sequence} precedes "
                    f"phase.started at seq {started_seq[e.phase]}"
                )

    def test_run_lifecycle_brackets_phase_events(self, run_observed,
                                                 run_baseline):
        sid = "ph_bracket"
        observer = CedEventObserver(EventLedger())
        run_observed(observer, sid)
        run_id = derive_projection_run_id(sid)
        events = observer.ledger.events_for_stream(run_stream_id(run_id))
        by_type = {e.event_type.value: e.sequence for e in events
                   if e.event_type.value in ("run.started", "run.completed")}
        phases = _phase_events(observer.ledger, sid)
        # run.started precedes the first phase.started; COMPLETE precedes
        # run.completed.
        assert by_type["run.started"] < phases[0].sequence
        assert phases[-1].phase == "complete"
        assert phases[-1].sequence < by_type["run.completed"]

    def test_initial_opening_emitted_exactly_once(self, run_observed,
                                                  run_baseline):
        sid = "ph_opening_once"
        observer = CedEventObserver(EventLedger())
        run_observed(observer, sid)
        openings = [e for e in _phase_events(observer.ledger, sid)
                    if e.phase == "opening"]
        assert len(openings) == 1
        assert openings[0].round_index == 0


class TestPhaseEventFallbacks:
    """Fallback semantics: phase.started only for phases whose runner began."""

    @staticmethod
    def _registry_ced(adapters, observer):
        from backend.dialogues.provider_registry import CouncilProviderRegistry
        provider = FakeProvider()
        agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
        reg = CouncilProviderRegistry()
        for a in adapters:
            reg.register(a)
        return CEDOrchestrator(agents, provider, registry=reg,
                               event_observer=observer)

    def test_readiness_fallback_emits_no_phase_events(self):
        from backend.dialogues.provider_registry import ScriptedMockProvider
        sid = "ph_fb_ready"
        observer = CedEventObserver(EventLedger())
        ced = self._registry_ced([ScriptedMockProvider("mock_a")], observer)
        final = asyncio.run(ced.run_registry_session(QUESTION,
                                                     session_id=sid))
        assert final.ratification_status == "quorum_failed"
        run_id = derive_projection_run_id(sid)
        types = [e.event_type.value for e in
                 observer.ledger.events_for_stream(run_stream_id(run_id))]
        # No phase runner ever began: state.phase=OPENING is a construction
        # default, not evidence of execution (the documented exception).
        assert types == ["run.started", "run.completed"]
        assert _phase_events(observer.ledger, sid) == []

    def test_mid_phase_fallback_includes_only_started_phases(self):
        from backend.dialogues.provider_registry import (
            RateLimitedProvider, ScriptedMockProvider, TimeoutScriptedProvider,
        )
        sid = "ph_fb_quorum"
        observer = CedEventObserver(EventLedger())
        ced = self._registry_ced(
            [ScriptedMockProvider("mock_a"), TimeoutScriptedProvider(),
             RateLimitedProvider()],
            observer,
        )
        final = asyncio.run(ced.run_registry_session(QUESTION,
                                                     session_id=sid))
        assert final.ratification_status == "quorum_failed"
        phases = [e.phase for e in _phase_events(observer.ledger, sid)]
        # The blocked phase DID start (advance happens before its tasks);
        # nothing after it — and never RATIFICATION/COMPLETE.
        assert phases, "the blocked phase must appear as started"
        assert phases == _CANONICAL_PHASE_SEQUENCE[:len(phases)]
        assert "ratification" not in phases
        assert "complete" not in phases
        run_id = derive_projection_run_id(sid)
        types = [e.event_type.value for e in
                 observer.ledger.events_for_stream(run_stream_id(run_id))]
        assert types[-1] == "run.completed"


class TestPhaseNoOpSuppression:
    """Same-phase re-entry is suppressed in CED — never via ledger dedupe —
    so enabled-success and enabled-failure agree on attempts."""

    def test_repeat_same_phase_adds_no_event(self):
        sid = "ph_noop_ok"
        observer = CedEventObserver(EventLedger())
        final, ced = run_legacy_observed(observer, sid)
        state = ced.get_session(sid)
        before = len(_phase_events(observer.ledger, sid))
        ced._advance_phase(state, state.phase)      # COMPLETE → COMPLETE no-op
        assert len(_phase_events(observer.ledger, sid)) == before

    def test_repeat_same_phase_adds_no_failure_on_raising_observer(self):
        observer = CedEventObserver(_RaisingLedger())
        ced = _legacy_council(observer)
        state = ced.create_session(QUESTION, session_id="ph_noop_raise")
        ced._advance_phase(state, DialogPhase.OPENING, initial_entry=True)
        assert len(observer.failures) == 1          # the fresh entry attempt
        ced._advance_phase(state, DialogPhase.OPENING)   # no-op re-entry
        assert len(observer.failures) == 1, (
            "a suppressed no-op must not even ATTEMPT an emission"
        )

    def test_opening_round_index_flows_into_phase_event(self):
        sid = "ph_round2"
        observer = CedEventObserver(EventLedger())
        ced = _legacy_council(observer)
        ced.create_session(QUESTION, session_id=sid)
        ced.run_opening_phase(sid, round_index=2)
        openings = [e for e in _phase_events(observer.ledger, sid)
                    if e.phase == "opening"]
        assert len(openings) == 1
        assert openings[0].round_index == 2

    def test_static_guard_single_advance_phase_caller(self):
        import pathlib
        import re
        ced_src = (pathlib.Path(__file__).resolve().parent.parent
                   / "backend" / "dialogues" / "ced.py").read_text(
                       encoding="utf-8")
        callers = re.findall(r"\.advance_phase\(", ced_src)
        assert len(callers) == 1, (
            "state.advance_phase must be called ONLY inside _advance_phase — "
            f"found {len(callers)} call sites"
        )


def _run_events(ledger, sid, event_type):
    run_id = derive_projection_run_id(sid)
    return [e for e in ledger.events_for_stream(run_stream_id(run_id))
            if e.event_type.value == event_type]


@pytest.mark.parametrize("run_observed,run_baseline", _RUNNERS,
                         ids=_RUNNER_IDS)
class TestExecutionEvents:
    """task.created parity with the canonical task_log (OBSERVED kinds only)
    — deterministic task ids are what make this stream reproducible."""

    def test_task_created_parity_with_task_log(self, run_observed,
                                               run_baseline):
        from backend.dialogues.ced import _OBSERVED_TASK_KINDS
        sid = "exe_tasks"
        observer = CedEventObserver(EventLedger())
        _, ced = run_observed(observer, sid)
        state = ced.get_session(sid)
        expected = [e for e in state.task_log
                    if e.task_kind in _OBSERVED_TASK_KINDS]
        events = _run_events(observer.ledger, sid, "task.created")
        assert len(events) == len(expected) > 0
        for ev, entry in zip(events, expected):
            assert ev.payload["task_id"] == entry.task_id
            assert ev.payload["task_kind"] == entry.task_kind.value
            assert ev.payload["agent_id"] == entry.agent_id
            assert ev.payload["slot_index"] == entry.slot_index
            assert ev.payload["attempt_index"] == entry.attempt_index
            assert ev.payload["schema_name"] == entry.schema_name
            assert ev.payload["context_hash"] == entry.context_hash

    def test_task_ids_are_deterministic_not_random(self, run_observed,
                                                   run_baseline):
        import re
        sid = "exe_task_ids"
        observer = CedEventObserver(EventLedger())
        _, ced = run_observed(observer, sid)
        ids = [e.payload["task_id"]
               for e in _run_events(observer.ledger, sid, "task.created")]
        # Two deterministic families: hardened "task_"+64hex (this slice) and
        # the pre-existing "stask_"+12hex score-task ids — never random _uid.
        assert ids and all(
            re.fullmatch(r"task_[0-9a-f]{64}", i)
            or re.fullmatch(r"stask_[0-9a-f]{12}", i)
            for i in ids)
        # Deterministic across a FRESH identical run (the routing-id disease
        # is cured for observed kinds).
        observer2 = CedEventObserver(EventLedger())
        run_observed(observer2, sid)
        ids2 = [e.payload["task_id"]
                for e in _run_events(observer2.ledger, sid, "task.created")]
        assert ids == ids2


class TestExecutionEventsRegistry:
    """Registry-only facts: move.validated digests and provider.failed."""

    def test_move_validated_parity_and_digests(self):
        sid = "exe_moves"
        observer = CedEventObserver(EventLedger())
        _, ced = run_registry_observed(observer, sid)
        state = ced.get_session(sid)
        events = _run_events(observer.ledger, sid, "move.validated")
        # One event per registry deliberation move (state.moves holds exactly
        # those on this path).
        assert len(events) == len(state.moves) > 0
        moves_by_id = {m.move_id: m for m in state.moves}
        for ev in events:
            move = moves_by_id[ev.payload["move_id"]]
            assert ev.payload["agent_id"] == move.agent_id
            assert ev.payload["confidence"] == move.confidence
            # validated_digest is recomputable from the canonical content.
            recomputed = sha256_hex(json.dumps(
                move.content, sort_keys=True, ensure_ascii=False,
                separators=(",", ":")))
            assert ev.payload["validated_digest"] == recomputed
            assert ev.payload["raw_digest"] != ev.payload["validated_digest"]

    def test_provider_failed_parity_with_failed_entries(self):
        from backend.dialogues.ced import (
            _FAILURE_CATEGORY_BY_STATUS, _OBSERVED_TASK_KINDS,
        )
        from backend.dialogues.models import ProviderStatus
        from backend.dialogues.provider_registry import (
            CouncilProviderRegistry, ScriptedMockProvider,
            TimeoutScriptedProvider,
        )
        sid = "exe_provider_failed"
        observer = CedEventObserver(EventLedger())
        provider = FakeProvider()
        agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
        reg = CouncilProviderRegistry()
        for a in (ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b"),
                  TimeoutScriptedProvider()):
            reg.register(a)
        ced = CEDOrchestrator(agents, provider, registry=reg,
                              event_observer=observer)
        asyncio.run(ced.run_registry_session(QUESTION, session_id=sid))
        state = ced.get_session(sid)
        failed_entries = [
            e for e in state.task_log
            if e.task_kind in _OBSERVED_TASK_KINDS
            and e.provider_id is not None
            and e.provider_status is not None
            and e.provider_status != ProviderStatus.OK
        ]
        events = _run_events(observer.ledger, sid, "provider.failed")
        assert len(events) == len(failed_entries) > 0
        for ev, entry in zip(events, failed_entries):
            assert ev.payload["task_id"] == entry.task_id
            assert ev.payload["provider_id"] == entry.provider_id
            assert ev.payload["status"] == entry.provider_status.value
            assert ev.payload["failure_category"] == \
                _FAILURE_CATEGORY_BY_STATUS.get(entry.provider_status,
                                                "unknown")

    def test_legacy_path_emits_no_provider_or_move_events(self):
        sid = "exe_legacy_absence"
        observer = CedEventObserver(EventLedger())
        run_legacy_observed(observer, sid)
        assert _run_events(observer.ledger, sid, "move.validated") == []
        assert _run_events(observer.ledger, sid, "provider.failed") == []
        # …but legacy deliberation tasks ARE projected.
        assert _run_events(observer.ledger, sid, "task.created")

    def test_ratification_tasks_stay_deferred(self):
        sid = "exe_rat_deferred"
        observer = CedEventObserver(EventLedger())
        _, ced = run_registry_observed(observer, sid)
        kinds = {e.payload["task_kind"]
                 for e in _run_events(observer.ledger, sid, "task.created")}
        assert "council_ratification" not in kinds
        assert "tree_revision" not in kinds

    def test_every_agent_task_gets_a_deterministic_id(self):
        # Static guard: no AgentTask construction in ced.py may keep the random
        # _uid default — every site passes an explicit deterministic task_id
        # (or is an already-deterministic stask_ scoring task).
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "backend" / "dialogues" / "ced.py").read_text(encoding="utf-8")
        # Each `AgentTask(` opener must have a task_id= within its argument list.
        for m in re.finditer(r"AgentTask\(", src):
            window = src[m.start():m.start() + 400]
            assert "task_id=" in window, (
                "an AgentTask is built without an explicit deterministic "
                f"task_id near offset {m.start()}"
            )


class TestTaskCreatedTiming:
    """task.created is a CONSTRUCTION-time fact (PR #74 review fix 1): emitted
    before the agent/provider runs, and NOT re-emitted by the task logger."""

    def test_task_created_precedes_the_move_it_produces(self):
        sid = "tc_order"
        observer = CedEventObserver(EventLedger())
        run_registry_observed(observer, sid)
        run_id = derive_projection_run_id(sid)
        events = observer.ledger.events_for_stream(run_stream_id(run_id))
        created_seq = {e.payload["task_id"]: e.sequence for e in events
                       if e.event_type.value == "task.created"}
        for e in events:
            if e.event_type.value == "move.validated":
                tid = e.payload["task_id"]
                assert created_seq[tid] < e.sequence

    def test_task_created_survives_execution_exception(self):
        # A task built then thrown-on during execution still has task.created,
        # because the fact ("created") is true regardless of the outcome.
        sid = "tc_throw"
        observer = CedEventObserver(EventLedger())
        ced = _legacy_council(observer)
        ced.create_session(QUESTION, session_id=sid)
        boom = ced.agents[0]
        original = boom.execute

        def raising(task):
            raise RuntimeError("execute boom")

        boom.execute = raising
        with pytest.raises(RuntimeError, match="execute boom"):
            ced.run_session(QUESTION, session_id=sid)
        boom.execute = original
        # The throwing agent's OWN task.created was emitted before the throw —
        # the "created" fact holds even though no TaskLogEntry/move followed.
        created = _run_events(observer.ledger, sid, "task.created")
        assert any(e.payload["agent_id"] == boom.agent_id for e in created)
        # …and that task never produced a move.validated (execution failed).
        thrown_task_ids = {e.payload["task_id"] for e in created
                           if e.payload["agent_id"] == boom.agent_id}
        move_task_ids = {e.payload["task_id"]
                         for e in _run_events(observer.ledger, sid,
                                              "move.validated")}
        assert thrown_task_ids.isdisjoint(move_task_ids)

    def test_record_task_log_does_not_emit_task_created(self):
        # The logger emits provider.failed only; construction events come from
        # _emit_task_created (no double emission).
        sid = "tc_no_dup"
        observer = CedEventObserver(EventLedger())
        _, ced = run_registry_observed(observer, sid)
        state = ced.get_session(sid)
        from backend.dialogues.ced import _OBSERVED_TASK_KINDS
        # One task.created per observed task_log entry — never two.
        observed_entries = sum(1 for e in state.task_log
                               if e.task_kind in _OBSERVED_TASK_KINDS)
        created = _run_events(observer.ledger, sid, "task.created")
        assert len(created) == observed_entries
        assert len({e.payload["task_id"] for e in created}) == len(created)


class TestFailureCategoryMapping:
    """PR #74 review fix 2: only evidence-carrying statuses map to a category;
    UNAVAILABLE (and error/degraded/fallback/disabled) are honestly unknown."""

    def test_unavailable_is_unknown_not_network(self):
        from backend.dialogues.ced import _FAILURE_CATEGORY_BY_STATUS
        from backend.dialogues.models import ProviderStatus
        assert _FAILURE_CATEGORY_BY_STATUS.get(
            ProviderStatus.UNAVAILABLE, "unknown") == "unknown"
        for status in (ProviderStatus.ERROR, ProviderStatus.DEGRADED,
                       ProviderStatus.FALLBACK, ProviderStatus.DISABLED):
            assert _FAILURE_CATEGORY_BY_STATUS.get(status, "unknown") == \
                "unknown"

    def test_evidence_statuses_map_to_their_category(self):
        from backend.dialogues.ced import _FAILURE_CATEGORY_BY_STATUS
        from backend.dialogues.models import ProviderStatus
        assert _FAILURE_CATEGORY_BY_STATUS[ProviderStatus.TIMEOUT] == "timeout"
        assert _FAILURE_CATEGORY_BY_STATUS[ProviderStatus.RATE_LIMITED] == \
            "rate_limit"
        assert _FAILURE_CATEGORY_BY_STATUS[ProviderStatus.MISSING_KEY] == "auth"


class TestMoveValidatedIsolation:
    """PR #74 review fix 3: non-finite move content raises INSIDE the builder,
    so it is an isolated observer failure — never a CED/protocol failure."""

    def _one_task_move(self, content):
        from backend.dialogues.models import AgentMove, AgentRole, DialogPhase
        ced = _legacy_council(CedEventObserver(EventLedger()))
        state = ced.create_session(QUESTION, session_id="mv_iso")
        task = ced._build_round_task(
            state, "agent_0", AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS)
        move = AgentMove(task_id=task.task_id, agent_id="agent_0",
                         role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
                         content=content, confidence=0.7)
        return ced, state, task, move

    def test_builder_raises_on_nan_content(self):
        ced, state, task, move = self._one_task_move({"x": float("nan")})
        with pytest.raises(ValueError):
            ced._build_move_validated_event(state, task, move, "raw text")

    def test_emit_isolates_nan_as_observer_failure(self):
        ced, state, task, move = self._one_task_move({"x": float("inf")})
        # Must NOT raise out of _emit_event; recorded as an isolated failure.
        ced._emit_event(
            CedEventType.MOVE_VALIDATED,
            lambda: ced._build_move_validated_event(state, task, move, "raw"))
        assert len(ced._event_observer.failures) == 1
        assert ced._event_observer.failures[0].event_type == "move.validated"

    def test_finite_content_builds_normally(self):
        ced, state, task, move = self._one_task_move({"text": "ok"})
        draft = ced._build_move_validated_event(state, task, move, "raw text")
        assert draft.payload["move_id"] == move.move_id
        assert draft.payload["raw_digest"] != draft.payload["validated_digest"]


class TestDeterministicTaskIdHardening:
    """PR #74 review fix 4: versioned, collision-resistant, full-width id."""

    def _ced_state(self):
        ced = _legacy_council(None)
        return ced, ced.create_session(QUESTION, session_id="tid")

    def test_id_is_task_prefix_plus_64_hex(self):
        import re
        from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
        ced, state = self._ced_state()
        tid = ced._deterministic_task_id(
            state, "agent_0", DialogPhase.OPENING, AgentRole.SOCRATES,
            TaskKind.SOCRATIC_QUESTION, 0, 0, 0)
        assert re.fullmatch(r"task_[0-9a-f]{64}", tid)

    def test_delimiter_collision_resistance(self):
        from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
        ced, state = self._ced_state()
        a = ced._deterministic_task_id(
            state, "agent_0|x", DialogPhase.OPENING, AgentRole.SOCRATES,
            TaskKind.SOCRATIC_QUESTION, 0, 0, 0)
        b = ced._deterministic_task_id(
            state, "agent_0", DialogPhase.OPENING, AgentRole.SOCRATES,
            TaskKind.SOCRATIC_QUESTION, 0, 0, 0)
        # A "|" in one component can never make two different tuples alias.
        assert a != b

    def test_every_identity_field_changes_the_id(self):
        from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
        ced, state = self._ced_state()
        base = ced._deterministic_task_id(
            state, "agent_0", DialogPhase.OPENING, AgentRole.SOCRATES,
            TaskKind.SOCRATIC_QUESTION, 0, 0, 0)
        variants = [
            ced._deterministic_task_id(state, "agent_1", DialogPhase.OPENING,
                                       AgentRole.SOCRATES,
                                       TaskKind.SOCRATIC_QUESTION, 0, 0, 0),
            ced._deterministic_task_id(state, "agent_0", DialogPhase.ELENCHUS,
                                       AgentRole.SOCRATES,
                                       TaskKind.SOCRATIC_QUESTION, 0, 0, 0),
            ced._deterministic_task_id(state, "agent_0", DialogPhase.OPENING,
                                       AgentRole.EMPIRICIST,
                                       TaskKind.SOCRATIC_QUESTION, 0, 0, 0),
            ced._deterministic_task_id(state, "agent_0", DialogPhase.OPENING,
                                       AgentRole.SOCRATES,
                                       TaskKind.INITIAL_RESPONSE, 0, 0, 0),
            ced._deterministic_task_id(state, "agent_0", DialogPhase.OPENING,
                                       AgentRole.SOCRATES,
                                       TaskKind.SOCRATIC_QUESTION, 2, 0, 0),
            ced._deterministic_task_id(state, "agent_0", DialogPhase.OPENING,
                                       AgentRole.SOCRATES,
                                       TaskKind.SOCRATIC_QUESTION, 0, 1, 0),
            ced._deterministic_task_id(state, "agent_0", DialogPhase.OPENING,
                                       AgentRole.SOCRATES,
                                       TaskKind.SOCRATIC_QUESTION, 0, 0, 1),
        ]
        assert all(v != base for v in variants)
        assert len(set(variants)) == len(variants)

    def test_no_task_kind_is_none_anywhere(self):
        # The demo round-task builder now supplies a real TaskKind (a None
        # would raise on .value inside the id helper).
        from backend.dialogues.models import AgentRole, DialogPhase
        ced, state = self._ced_state()
        task = ced._build_round_task(
            state, "agent_0", AgentRole.SOCRATES, DialogPhase.OPENING)
        assert task.task_id.startswith("task_")
        assert task.task_kind is not None

    def test_explicit_round_changes_opening_task_id(self):
        # Integration (not just the unit helper): the SAME session at two
        # opening rounds yields two different task ids — proves the explicit
        # round is threaded end-to-end, not read from the mutable
        # state.round_number.
        def opening_task_id(round_index):
            observer = CedEventObserver(EventLedger())
            ced = _legacy_council(observer)
            sid = "round_thread"
            ced.create_session(QUESTION, session_id=sid)
            ced.run_opening_phase(sid, round_index=round_index)
            created = _run_events(observer.ledger, sid, "task.created")
            assert len(created) == 1
            return created[0].payload["task_id"]

        assert opening_task_id(0) != opening_task_id(2)

    def test_explicit_round_changes_opening_move_id(self):
        # Real legacy integration: move identity must follow the same explicit
        # phase round as the AgentTask, not the mutable state.round_number. Two
        # agents make rounds 0 and 2 select the same Socrates, isolating round
        # identity from agent identity.
        def opening_move_id(round_index):
            provider = FakeProvider()
            agents = [
                SocraticAgent(f"agent_{i}", provider) for i in range(2)
            ]
            ced = CEDOrchestrator(agents, provider)
            sid = "move_round_thread"
            state = ced.create_session(QUESTION, session_id=sid)
            ced.run_opening_phase(sid, round_index=round_index)
            assert len(state.moves) == 1
            return state.moves[0].agent_id, state.moves[0].move_id

        agent_0, move_0 = opening_move_id(0)
        agent_2, move_2 = opening_move_id(2)
        assert agent_0 == agent_2
        assert move_0 != move_2

    def test_task_and_move_ids_share_canonical_identity_fields(self):
        import re
        from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
        ced, state = self._ced_state()
        fields = (
            state, "agent_0", DialogPhase.OPENING, AgentRole.SOCRATES,
            TaskKind.SOCRATIC_QUESTION,
        )

        task_0_a = ced._deterministic_task_id(*fields, 0, 0, 0)
        task_0_b = ced._deterministic_task_id(*fields, 0, 0, 0)
        move_0_a = ced._deterministic_move_id(*fields, 0, 0, 0)
        move_0_b = ced._deterministic_move_id(*fields, 0, 0, 0)
        task_2 = ced._deterministic_task_id(*fields, 2, 0, 0)
        move_2 = ced._deterministic_move_id(*fields, 2, 0, 0)

        assert task_0_a == task_0_b
        assert move_0_a == move_0_b
        assert task_0_a != task_2
        assert move_0_a != move_2
        assert re.fullmatch(r"task_[0-9a-f]{64}", task_0_a)
        assert re.fullmatch(r"move_[0-9a-f]{64}", move_0_a)

    def test_no_fabricated_task_kind_for_unmapped_phase(self):
        # An unmapped phase must fail BEFORE dispatch — never be coerced to
        # INITIAL_RESPONSE just to keep going.
        from backend.dialogues.models import AgentRole, DialogPhase
        ced, state = self._ced_state()
        with pytest.raises(ValueError, match="No canonical TaskKind"):
            ced._build_round_task(
                state, "agent_0", AgentRole.SOCRATES, DialogPhase.COMPLETE)

        registry_ced = _registry_council(None)
        registry_state = registry_ced.create_session(
            QUESTION, session_id="strict_registry_phase")
        with pytest.raises(ValueError, match="No canonical TaskKind"):
            asyncio.run(registry_ced._run_registry_phase(
                registry_state, DialogPhase.COMPLETE, None))
        assert registry_state.phase == DialogPhase.OPENING
        assert registry_state.task_log == []


class TestStandaloneRegistryEmission:
    """Every observer-visible task construction emits task.created BEFORE
    provider execution, regardless of which public runner the caller used
    (PR #74 review fix 2 — no path-dependent event gaps)."""

    @staticmethod
    def _registry_ced(observer):
        from backend.dialogues.provider_registry import (
            CouncilProviderRegistry, ScriptedMockProvider,
        )
        provider = FakeProvider()
        agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
        reg = CouncilProviderRegistry()
        for a in (ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")):
            reg.register(a)
        return CEDOrchestrator(agents, provider, registry=reg,
                               event_observer=observer)

    def test_run_registry_council_round_emits_task_created(self):
        from backend.dialogues.models import AgentRole, DialogPhase
        sid = "std_council"
        observer = CedEventObserver(EventLedger())
        ced = self._registry_ced(observer)
        ced.create_session(QUESTION, session_id=sid)
        result = asyncio.run(ced.run_registry_council_round(
            sid, "agent_0", AgentRole.SOCRATES, DialogPhase.OPENING))
        created = _run_events(observer.ledger, sid, "task.created")
        assert len(created) == 1
        assert created[0].payload["task_kind"] == "socratic_question"
        assert result.proceed  # provider results unaffected

    def test_gather_registry_phase_round_emits_one_per_task(self):
        from backend.dialogues.models import DialogPhase
        sid = "std_gather"
        observer = CedEventObserver(EventLedger())
        ced = self._registry_ced(observer)
        state = ced.create_session(QUESTION, session_id=sid)
        result = asyncio.run(ced.gather_registry_phase_round(
            state, DialogPhase.INITIAL_RESPONSE))
        assignment = ced.assign_roles_for_phase(
            state, DialogPhase.INITIAL_RESPONSE)
        created = _run_events(observer.ledger, sid, "task.created")
        assert len(created) == len(assignment) > 0
        assert result.proceed

    def test_gather_registry_phase_round_threads_explicit_round(self):
        from backend.dialogues.models import DialogPhase
        def ids_for_round(ri):
            observer = CedEventObserver(EventLedger())
            ced = self._registry_ced(observer)
            state = ced.create_session(QUESTION, session_id="std_round")
            asyncio.run(ced.gather_registry_phase_round(
                state, DialogPhase.INITIAL_RESPONSE, round_index=ri))
            return sorted(e.payload["task_id"] for e in
                          _run_events(observer.ledger, "std_round",
                                      "task.created"))
        assert ids_for_round(0) != ids_for_round(2)

    def test_standalone_raising_ledger_stays_isolated(self):
        from backend.dialogues.models import AgentRole, DialogPhase
        sid = "std_iso"
        observer = CedEventObserver(_RaisingLedger())
        ced = self._registry_ced(observer)
        ced.create_session(QUESTION, session_id=sid)
        # A raising ledger must not break the round; results unaffected.
        result = asyncio.run(ced.run_registry_council_round(
            sid, "agent_0", AgentRole.SOCRATES, DialogPhase.OPENING))
        assert result.proceed
        assert observer.failures  # isolated failure recorded, run intact


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
