"""External Self-Consultation v1 — tamper-evident receipts and their store.

A receipt binds one canonical request digest to one canonical result digest.
Exact reruns are idempotent; a different content under the same request_id is
refused; the digest changes when either the request or the result changes; no
keys or hidden reasoning are stored.
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.dialogues.openclaw_consultation import (
    ConsultationError,
    ConsultationPolicy,
    ConsultationReceiptStore,
    ExternalConsultationRequest,
    ExternalConsultationService,
    MockConsultationProvider,
    build_receipt,
    verify_receipt,
)
from backend.dialogues.openclaw_consultation import receipts as receipts_mod
from backend.dialogues.openclaw_consultation.schemas import sha256_text


def _broken_link(src, dst):
    """Simulate a filesystem without hard-link support (forces the fallback)."""
    raise OSError("simulated: no hard-link support")

_NOW = "2026-07-11T00:00:00Z"
_EXP = "2026-07-11T01:00:00Z"


def _request(**overrides):
    base = dict(
        request_id="req-receipt",
        requesting_agent_id="local_apprentice_001",
        mode="critic",
        consulted_provider="mock",
        consulted_model="mock-critic",
        consultation_relation="peer_model",
        question="Review this and list the biggest gaps.",
        purpose="find flaws",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at=_NOW,
        expires_at=_EXP,
        draft="A draft to review.",
    )
    base.update(overrides)
    return ExternalConsultationRequest(**base)


def _outcome(request, *, worker_id="test-worker"):
    service = ExternalConsultationService(
        ConsultationPolicy(), worker_id=worker_id, clock=lambda: _NOW)
    provider = MockConsultationProvider(provider_id="mock")
    return asyncio.run(service.consult(request, provider, now=_NOW))


# --------------------------------------------------------------------------- #
# build + verify
# --------------------------------------------------------------------------- #

def test_receipt_binds_request_and_result_digests():
    request = _request()
    outcome = _outcome(request)
    receipt = outcome.receipt
    assert receipt["request_digest"] == request.request_digest
    assert receipt["result_digest"] == outcome.result.response_digest
    assert verify_receipt(receipt)["receipt_digest"] == receipt["receipt_digest"]


def test_receipt_records_isolation_flags():
    receipt = _outcome(_request()).receipt
    assert receipt["isolated_session"] is True
    assert receipt["tools_disabled"] is True
    assert receipt["delegation_disabled"] is True


def test_receipt_stores_no_secrets_or_reasoning():
    receipt = _outcome(_request()).receipt
    blob = str(receipt).lower()
    for forbidden in ("api_key", "sk-ant", "bearer", "authorization",
                      "chain_of_thought", "reasoning", "raw_text"):
        assert forbidden not in blob


def test_build_receipt_refuses_result_from_a_different_request():
    request_a = _request(request_id="req-a")
    outcome_b = _outcome(_request(request_id="req-b", question="Different q."))
    with pytest.raises(ConsultationError, match="does not match its request"):
        build_receipt(request_a, outcome_b.result, worker_id="w",
                      started_at=_NOW, completed_at=_NOW)


def test_negative_token_usage_refused():
    request = _request()
    outcome = _outcome(request)
    with pytest.raises(ConsultationError, match="counts"):
        build_receipt(request, outcome.result, worker_id="w",
                      started_at=_NOW, completed_at=_NOW,
                      token_usage={"prompt_tokens": -1})


# --------------------------------------------------------------------------- #
# verify fails closed
# --------------------------------------------------------------------------- #

def test_verify_unknown_field_refused():
    receipt = dict(_outcome(_request()).receipt)
    receipt["backdoor"] = 1
    with pytest.raises(ConsultationError, match="missing or unknown"):
        verify_receipt(receipt)


def test_verify_tampered_digest_refused():
    receipt = dict(_outcome(_request()).receipt)
    receipt["provider"] = "someone_else"
    with pytest.raises(ConsultationError, match="digest mismatch"):
        verify_receipt(receipt)


# --------------------------------------------------------------------------- #
# store: idempotency + conflict refusal
# --------------------------------------------------------------------------- #

def test_exact_rerun_is_idempotent(tmp_path):
    receipt = _outcome(_request()).receipt
    store = ConsultationReceiptStore(tmp_path)
    first = store.save(receipt)
    second = store.save(receipt)               # identical content
    assert first == second
    assert store.load(receipt["request_id"])["receipt_digest"] == \
        receipt["receipt_digest"]


def test_conflicting_request_id_refused(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    original = _outcome(_request()).receipt
    store.save(original)
    # Same request_id, different content (different question => different digest).
    conflicting = _outcome(
        _request(question="A completely different question entirely.")).receipt
    assert conflicting["request_id"] == original["request_id"]
    assert conflicting["receipt_digest"] != original["receipt_digest"]
    with pytest.raises(ConsultationError, match="conflicting"):
        store.save(conflicting)


def test_receipt_digest_changes_when_request_changes():
    a = _outcome(_request()).receipt
    b = _outcome(_request(request_id="req-other")).receipt
    assert a["receipt_digest"] != b["receipt_digest"]


def test_receipt_digest_changes_when_result_changes():
    request = _request(mode="judge", draft=None,
                       candidates=("Answer A", "Answer B"),
                       consulted_model="mock-judge")
    # Different scripted verdict => different result digest => different receipt.
    from backend.dialogues.openclaw_consultation import (
        ConsultationRawResponse)

    def responder_tie(call):
        import json
        return ConsultationRawResponse(
            provider_status="ok",
            raw_text=json.dumps({"verdict": "tie",
                                 "criterion_scores": {"rigor": 5.0},
                                 "rationale": "even", "critical_difference":
                                 "no decisive gap"}))
    service = ExternalConsultationService(
        ConsultationPolicy(), worker_id="w", clock=lambda: _NOW)
    default = asyncio.run(service.consult(
        request, MockConsultationProvider(provider_id="mock"), now=_NOW))
    tie = asyncio.run(service.consult(
        request, MockConsultationProvider(provider_id="mock",
                                          responder=responder_tie), now=_NOW))
    assert default.result.response_digest != tie.result.response_digest
    assert default.receipt["receipt_digest"] != tie.receipt["receipt_digest"]


def test_store_load_missing_returns_none(tmp_path):
    assert ConsultationReceiptStore(tmp_path).load("nope") is None


# --------------------------------------------------------------------------- #
# HIGH — receipt filenames are hashed and contained (no traversal)
# --------------------------------------------------------------------------- #

def test_on_disk_name_is_hashed_not_raw_request_id(tmp_path):
    receipt = _outcome(_request()).receipt
    store = ConsultationReceiptStore(tmp_path)
    path = store.save(receipt)
    assert path.name == sha256_text("req-receipt") + ".receipt.json"
    # The raw request_id is still preserved INSIDE the verified JSON.
    assert store.load("req-receipt")["request_id"] == "req-receipt"


@pytest.mark.parametrize("evil", [
    "../../tmp/pwned", "..\\..\\pwned", "C:evil", "x:stream",
    "/absolute/path", "a/b/c", ".", "..",
])
def test_path_for_refuses_hostile_request_ids(tmp_path, evil):
    with pytest.raises(ConsultationError):
        ConsultationReceiptStore(tmp_path)._path_for(evil)


def test_every_valid_receipt_path_stays_under_the_store(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    base = tmp_path.resolve()
    for rid in ("req-receipt", "consult-critic-0a1b2c3d", "a.b_c-9"):
        resolved = store._path_for(rid).resolve()
        assert resolved.parent == base            # proven with resolve()
        assert str(resolved).startswith(str(base))


# --------------------------------------------------------------------------- #
# MEDIUM — atomic, immutable, concurrency-safe persistence
# --------------------------------------------------------------------------- #

def test_concurrent_distinct_content_exactly_one_wins(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    # Two DIFFERENT receipts sharing the same request_id.
    receipts = [
        _outcome(_request(question=f"Distinct question number {i}.")).receipt
        for i in range(8)
    ]
    assert len({r["receipt_digest"] for r in receipts}) == 8
    assert len({r["request_id"] for r in receipts}) == 1

    barrier = threading.Barrier(len(receipts))
    wins, conflicts = [], []

    def worker(rec):
        barrier.wait()                            # maximise the real race
        try:
            store.save(rec)
            wins.append(rec["receipt_digest"])
        except ConsultationError:
            conflicts.append(rec["receipt_digest"])

    with ThreadPoolExecutor(max_workers=len(receipts)) as pool:
        list(pool.map(worker, receipts))

    assert len(wins) == 1                          # no last-writer-wins
    assert len(conflicts) == len(receipts) - 1
    # The persisted final file is exactly the single winner and is valid.
    stored = store.load("req-receipt")
    assert stored["receipt_digest"] == wins[0]
    verify_receipt(stored)
    # Exactly one final receipt, and no orphan temp files left behind.
    assert [p.name for p in tmp_path.iterdir()] == [
        sha256_text("req-receipt") + ".receipt.json"]


def test_concurrent_identical_content_is_idempotent(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    barrier = threading.Barrier(8)
    errors = []

    def worker(_):
        barrier.wait()
        try:
            store.save(receipt)
        except Exception as exc:                  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))

    assert errors == []                            # identical content never conflicts
    assert store.load("req-receipt")["receipt_digest"] == receipt["receipt_digest"]
    assert [p.name for p in tmp_path.iterdir()] == [
        sha256_text("req-receipt") + ".receipt.json"]


def test_existing_final_receipt_is_verified_before_idempotent_return(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    path = store.save(receipt)
    # Corrupt the persisted final receipt, then a re-save must NOT silently
    # succeed — it re-verifies the existing file first.
    path.write_text(path.read_text(encoding="utf-8").replace(
        receipt["worker_id"], "tampered-worker"), encoding="utf-8")
    with pytest.raises(ConsultationError):
        store.save(receipt)


# --------------------------------------------------------------------------- #
# LOW fix — no-hard-link FALLBACK: lock-serialized atomic publication
# --------------------------------------------------------------------------- #

def _hashed(request_id="req-receipt"):
    return sha256_text(request_id) + ".receipt.json"


def _race(store, receipts):
    barrier = threading.Barrier(len(receipts))
    wins, conflicts, leaks = [], [], []

    def worker(rec):
        barrier.wait()
        try:
            store.save(rec)
            wins.append(rec["receipt_digest"])
        except ConsultationError as exc:
            conflicts.append(str(exc))
        except Exception as exc:                      # non-ConsultationError = leak
            leaks.append(f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=len(receipts)) as pool:
        list(pool.map(worker, receipts))
    return wins, conflicts, leaks


def _no_orphans(tmp_path):
    names = [p.name for p in tmp_path.iterdir()]
    assert not any(n.endswith(".tmp") for n in names), names
    assert not any(n.endswith(".lock") for n in names), names
    return names


class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        self.now += delay


def _receipt_bytes(receipt):
    verified = verify_receipt(receipt)
    return (json.dumps(verified, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def test_fallback_transient_delete_pending_permission_error_retries(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(
        tmp_path, lock_timeout=1.0, lock_poll=0.1)
    receipt = _outcome(_request()).receipt
    path = store._path_for(receipt["request_id"])
    lock = store._lock_for(path)
    real_open = receipts_mod.os.open
    clock = _FakeClock()
    attempts = []

    def transient_open(name, flags):
        assert os.fspath(name) == os.fspath(lock)
        attempts.append(name)
        if len(attempts) <= 3:
            raise PermissionError(13, "simulated DELETE_PENDING", name)
        return real_open(name, flags)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(receipts_mod.os, "open", transient_open)
    assert store.save(receipt) == path
    assert len(attempts) == 4
    assert verify_receipt(store.load(receipt["request_id"])) == receipt
    assert _no_orphans(tmp_path) == [_hashed()]


def test_fallback_permanent_permission_error_is_bounded_and_canonical(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(
        tmp_path, lock_timeout=3.0, lock_poll=1.0)
    receipt = _outcome(_request()).receipt
    path = store._path_for(receipt["request_id"])
    lock = store._lock_for(path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"pre-existing lock owner")
    clock = _FakeClock()
    attempts = []

    def denied_open(name, flags):
        assert os.fspath(name) == os.fspath(lock)
        attempts.append(name)
        raise PermissionError(13, "persistent DELETE_PENDING", name)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(receipts_mod.os, "open", denied_open)
    with pytest.raises(ConsultationError,
                       match="publication lock timed out"):
        store.save(receipt)
    # One deadline (t0+3) with a full 1.0 poll: attempts at t=0,1,2; the check
    # after the third sleep lands exactly on the deadline and stops - no
    # post-deadline acquisition (previously an off-by-one 4th attempt occurred).
    assert len(attempts) == 3
    assert not path.exists()
    assert lock.read_bytes() == b"pre-existing lock owner"
    assert sorted(p.name for p in tmp_path.iterdir()) == [lock.name]


def test_fallback_other_lock_open_oserror_is_canonical(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path)

    def failed_open(name, flags):
        raise OSError(5, "simulated non-contention lock failure", name)

    monkeypatch.setattr(receipts_mod.os, "open", failed_open)
    with pytest.raises(ConsultationError, match="lock acquisition failed"):
        store.save(_outcome(_request()).receipt)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("identical", [True, False],
                         ids=["identical", "conflicting"])
def test_fallback_delete_pending_reconciles_peer_publication_without_overwrite(
        tmp_path, monkeypatch, identical):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path)
    winner = _outcome(_request(question="peer winner")).receipt
    incoming = winner if identical else _outcome(
        _request(question="conflicting fallback writer")).receipt
    path = store._path_for(winner["request_id"])
    lock = store._lock_for(path)
    winner_bytes = _receipt_bytes(winner)
    clock = _FakeClock()
    attempts = []

    def publish_then_deny(name, flags):
        assert os.fspath(name) == os.fspath(lock)
        attempts.append(name)
        path.write_bytes(winner_bytes)
        raise PermissionError(13, "simulated DELETE_PENDING", name)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(receipts_mod.os, "open", publish_then_deny)
    if identical:
        assert store.save(incoming) == path
    else:
        with pytest.raises(ConsultationError, match="conflicting"):
            store.save(incoming)
    assert len(attempts) == 1
    assert path.read_bytes() == winner_bytes
    assert verify_receipt(store.load(winner["request_id"])) == winner
    assert _no_orphans(tmp_path) == [_hashed()]


def test_fallback_reconcile_retries_transient_permission_error(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(
        tmp_path, lock_timeout=1.0, lock_poll=0.1)
    receipt = _outcome(_request()).receipt
    path = store._path_for(receipt["request_id"])
    lock = store._lock_for(path)
    original_bytes = _receipt_bytes(receipt)
    real_open = receipts_mod.os.open
    path_type = type(path)
    real_read_text = path_type.read_text
    clock = _FakeClock()
    attempts = []

    def acquire_then_publish(name, flags):
        assert os.fspath(name) == os.fspath(lock)
        fd = real_open(name, flags)
        path.write_bytes(original_bytes)
        return fd

    def transient_read_text(current, *args, **kwargs):
        if current == path:
            attempts.append(current)
            if len(attempts) <= 3:
                raise PermissionError(
                    13, "simulated final-file sharing violation", current)
        return real_read_text(current, *args, **kwargs)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(receipts_mod.os, "open", acquire_then_publish)
    monkeypatch.setattr(path_type, "read_text", transient_read_text)
    assert store.save(receipt) == path
    assert len(attempts) == 4
    assert path.read_bytes() == original_bytes
    assert verify_receipt(json.loads(original_bytes.decode("utf-8"))) == receipt
    assert _no_orphans(tmp_path) == [_hashed()]


def test_fallback_acquired_lock_removed_after_conflict(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path)
    winner = _outcome(_request(question="peer publishes after lock")).receipt
    incoming = _outcome(_request(question="fallback conflict")).receipt
    path = store._path_for(winner["request_id"])
    lock = store._lock_for(path)
    winner_bytes = _receipt_bytes(winner)
    real_open = receipts_mod.os.open

    def acquire_then_publish(name, flags):
        assert os.fspath(name) == os.fspath(lock)
        fd = real_open(name, flags)
        path.write_bytes(winner_bytes)
        return fd

    monkeypatch.setattr(receipts_mod.os, "open", acquire_then_publish)
    with pytest.raises(ConsultationError, match="conflicting"):
        store.save(incoming)
    assert path.read_bytes() == winner_bytes
    assert _no_orphans(tmp_path) == [_hashed()]


def test_fallback_distinct_stress_twenty_trials(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    receipts = [_outcome(_request(question=f"stress distinct {i}")).receipt
                for i in range(8)]
    for trial in range(20):
        trial_dir = tmp_path / f"distinct-{trial}"
        store = ConsultationReceiptStore(trial_dir)
        wins, conflicts, leaks = _race(store, receipts)
        assert leaks == []
        assert len(wins) == 1 and len(conflicts) == 7
        assert all("conflicting" in message for message in conflicts)
        stored = store.load("req-receipt")
        assert stored["receipt_digest"] == wins[0]
        verify_receipt(stored)
        assert _no_orphans(trial_dir) == [_hashed()]


def test_fallback_identical_stress_twenty_trials(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    receipt = _outcome(_request()).receipt
    for trial in range(20):
        trial_dir = tmp_path / f"identical-{trial}"
        store = ConsultationReceiptStore(trial_dir)
        wins, conflicts, leaks = _race(store, [receipt] * 8)
        assert len(wins) == 8
        assert conflicts == [] and leaks == []
        assert verify_receipt(store.load("req-receipt")) == receipt
        assert _no_orphans(trial_dir) == [_hashed()]


def test_primary_link_path_remains_atomic_and_immutable(tmp_path, monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    conflicting = _outcome(_request(question="primary conflict")).receipt
    real_link = receipts_mod.os.link
    link_calls = []

    def tracked_link(src, dst):
        link_calls.append((src, dst))
        return real_link(src, dst)

    def unexpected_replace(*args):
        pytest.fail("os.replace fallback used despite working os.link")

    monkeypatch.setattr(receipts_mod.os, "link", tracked_link)
    # os.link is preferred UNDER the lock; the os.replace fallback must not run.
    monkeypatch.setattr(receipts_mod.os, "replace", unexpected_replace)
    path = store.save(receipt)
    original_bytes = path.read_bytes()
    assert store.save(receipt) == path
    with pytest.raises(ConsultationError, match="conflicting"):
        store.save(conflicting)
    assert len(link_calls) == 1
    assert path.read_bytes() == original_bytes
    assert verify_receipt(store.load(receipt["request_id"])) == receipt
    assert _no_orphans(tmp_path) == [_hashed()]


def test_fallback_concurrent_distinct_one_wins_no_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path)
    receipts = [_outcome(_request(question=f"distinct {i}")).receipt
                for i in range(8)]
    wins, conflicts, leaks = _race(store, receipts)
    assert leaks == []                                # no raw JSONDecodeError
    assert len(wins) == 1 and len(conflicts) == 7
    verify_receipt(store.load("req-receipt"))
    assert _no_orphans(tmp_path) == [_hashed()]       # one valid final, lock gone


def test_fallback_concurrent_identical_all_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    wins, conflicts, leaks = _race(store, [receipt] * 8)
    assert leaks == [] and conflicts == []            # idempotent, no raw errors
    assert store.load("req-receipt")["receipt_digest"] == receipt["receipt_digest"]
    assert _no_orphans(tmp_path) == [_hashed()]


def test_fallback_loser_never_reads_partial_when_publish_is_slow(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    real_replace = os.replace

    def slow_replace(src, dst):
        time.sleep(0.2)                               # widen the publish window
        return real_replace(src, dst)

    monkeypatch.setattr(receipts_mod.os, "replace", slow_replace)
    store = ConsultationReceiptStore(tmp_path)
    a = _outcome(_request(question="winner-or-loser A")).receipt
    b = _outcome(_request(question="winner-or-loser B")).receipt
    wins, conflicts, leaks = _race(store, [a, b])
    assert leaks == []                                # loser got no partial JSON
    assert len(wins) == 1 and len(conflicts) == 1
    verify_receipt(store.load("req-receipt"))


def test_fallback_publication_lock_timeout_is_consultation_error(
        tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path, lock_timeout=0.2, lock_poll=0.01)
    receipt = _outcome(_request()).receipt
    # Simulate a stuck/crashed writer holding the lock; the final never appears.
    path = store._path_for("req-receipt")
    lock = store._lock_for(path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    lock.write_text("", encoding="utf-8")
    with pytest.raises(ConsultationError, match="lock timed out"):
        store.save(receipt)
    assert not path.exists()                          # never overwritten/created
    # No new orphan temp; the stale lock is left for explicit operator action.
    leftovers = sorted(p.name for p in tmp_path.iterdir())
    assert leftovers == [lock.name]
    assert not any(n.endswith(".tmp") for n in leftovers)


def test_permanently_malformed_final_receipt_is_consultation_error(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    path = store._path_for("req-receipt")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text("this is not json at all", encoding="utf-8")   # corrupt
    with pytest.raises(ConsultationError):
        store.save(receipt)                           # normalized, not JSONDecodeError


def test_fallback_lock_removed_after_normal_success(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path)
    store.save(_outcome(_request()).receipt)
    assert _no_orphans(tmp_path) == [_hashed()]       # lock + tmp both gone


def test_fallback_process_level_contention(tmp_path):
    """Process-level forced fallback: exactly one valid final receipt, only
    conflicts/idempotent otherwise, no leaks (where subprocess spawn works)."""
    root = str(__import__("pathlib").Path(__file__).resolve().parents[1])
    worker = tmp_path / "proc_worker.py"
    worker.write_text(
        "import sys, os, json, time, pathlib\n"
        "sys.path.insert(0, sys.argv[4])\n"
        "from backend.dialogues.openclaw_consultation import receipts as rm\n"
        "from backend.dialogues.openclaw_consultation import ConsultationError\n"
        "rm.os.link = lambda s, d: (_ for _ in ()).throw(OSError('no link'))\n"
        "rec = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))\n"
        "start = float(sys.argv[3])\n"
        "while time.time() < start:\n"
        "    pass\n"
        "try:\n"
        "    rm.ConsultationReceiptStore(sys.argv[1]).save(rec)\n"
        "    print('WIN')\n"
        "except ConsultationError:\n"
        "    print('CONFLICT')\n"
        "except Exception as e:\n"
        "    print('LEAK:' + type(e).__name__)\n",
        encoding="utf-8")
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    recs = [_outcome(_request(question=f"proc distinct {i}")).receipt
            for i in range(4)]
    paths = []
    for i, rec in enumerate(recs):
        p = tmp_path / f"rec{i}.json"
        p.write_text(json.dumps(rec), encoding="utf-8")
        paths.append(str(p))
    start = time.time() + 2.0
    try:
        procs = [subprocess.Popen(
            [sys.executable, str(worker), str(store_dir), pp, str(start), root],
            stdout=subprocess.PIPE, text=True) for pp in paths]
        outs = [pr.communicate(timeout=60)[0].strip() for pr in procs]
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"subprocess spawn unavailable: {exc}")
    assert all(o in ("WIN", "CONFLICT") for o in outs), outs   # no LEAK
    assert outs.count("WIN") == 1
    files = [p.name for p in store_dir.iterdir()]
    assert files == [_hashed("req-receipt")]
    verify_receipt(json.loads((store_dir / files[0]).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# HIGH fix — primary and fallback publication share ONE exclusive lock
# --------------------------------------------------------------------------- #

def test_mixed_conflicting_primary_cannot_bypass_shared_lock(tmp_path,
                                                             monkeypatch):
    # A is forced to fallback and holds the shared lock; B has a working primary
    # os.link but must ALSO take the lock, so it cannot overwrite A's publication.
    store = ConsultationReceiptStore(tmp_path)
    a_rec = _outcome(_request(question="fallback winner A")).receipt
    b_rec = _outcome(_request(question="primary writer B")).receipt
    path = store._path_for("req-receipt")
    real_open, real_link = receipts_mod.os.open, receipts_mod.os.link
    real_replace = receipts_mod.os.replace
    tl = threading.local()
    a_holds_lock = threading.Event()
    b_reached_save = threading.Event()

    def link(src, dst):
        if getattr(tl, "fallback", False):
            raise OSError("A forced fallback")
        return real_link(src, dst)          # B primary link (must never publish)

    def sig_open(name, flags):
        fd = real_open(name, flags)
        if getattr(tl, "fallback", False):
            a_holds_lock.set()              # A has acquired the shared lock
        return fd

    def gated_replace(src, dst):
        assert b_reached_save.wait(timeout=5)
        return real_replace(src, dst)

    monkeypatch.setattr(receipts_mod.os, "link", link)
    monkeypatch.setattr(receipts_mod.os, "open", sig_open)
    monkeypatch.setattr(receipts_mod.os, "replace", gated_replace)
    results = {}

    def run_a():
        tl.fallback = True
        try:
            store.save(a_rec); results["A"] = "WIN"
        except ConsultationError:
            results["A"] = "CONFLICT"
        except Exception as exc:            # noqa: BLE001
            results["A"] = f"ERR:{type(exc).__name__}"

    def run_b():
        tl.fallback = False
        assert a_holds_lock.wait(timeout=5)
        b_reached_save.set()
        try:
            store.save(b_rec); results["B"] = "WIN"
        except ConsultationError:
            results["B"] = "CONFLICT"
        except Exception as exc:            # noqa: BLE001
            results["B"] = f"ERR:{type(exc).__name__}"

    ta, tb = threading.Thread(target=run_a), threading.Thread(target=run_b)
    ta.start(); tb.start(); ta.join(timeout=15); tb.join(timeout=15)
    assert results == {"A": "WIN", "B": "CONFLICT"}
    # The published final is the winner's content (proving B did not overwrite it).
    assert verify_receipt(store.load("req-receipt")) == a_rec
    assert _no_orphans(tmp_path) == [_hashed()]


def test_mixed_identical_primary_and_fallback_both_idempotent(tmp_path,
                                                              monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    shared = _outcome(_request(question="shared identical")).receipt
    path = store._path_for("req-receipt")
    real_open, real_link = receipts_mod.os.open, receipts_mod.os.link
    real_replace = receipts_mod.os.replace
    tl = threading.local()
    a_holds_lock = threading.Event()
    b_reached_save = threading.Event()

    def link(src, dst):
        if getattr(tl, "fallback", False):
            raise OSError("A forced fallback")
        return real_link(src, dst)

    def sig_open(name, flags):
        fd = real_open(name, flags)
        if getattr(tl, "fallback", False):
            a_holds_lock.set()
        return fd

    def gated_replace(src, dst):
        assert b_reached_save.wait(timeout=5)
        return real_replace(src, dst)

    monkeypatch.setattr(receipts_mod.os, "link", link)
    monkeypatch.setattr(receipts_mod.os, "open", sig_open)
    monkeypatch.setattr(receipts_mod.os, "replace", gated_replace)
    results = {}

    def run(name, is_fb, gate=None, wait=None):
        tl.fallback = is_fb
        if wait is not None:
            assert wait.wait(timeout=5)
        if gate is not None:
            gate.set()
        try:
            store.save(shared); results[name] = "WIN"     # idempotent success
        except Exception as exc:            # noqa: BLE001
            results[name] = f"ERR:{type(exc).__name__}"

    ta = threading.Thread(target=run, args=("A", True))
    tb = threading.Thread(target=run, args=("B", False, b_reached_save,
                                            a_holds_lock))
    ta.start(); tb.start(); ta.join(timeout=15); tb.join(timeout=15)
    assert results == {"A": "WIN", "B": "WIN"}
    assert verify_receipt(store.load("req-receipt")) == shared
    assert _no_orphans(tmp_path) == [_hashed()]


# --------------------------------------------------------------------------- #
# MEDIUM fix — one monotonic deadline, poll capped, no post-deadline op
# --------------------------------------------------------------------------- #

def test_single_deadline_is_not_reset_across_phases(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path, lock_timeout=3.0, lock_poll=1.0)
    receipt = _outcome(_request()).receipt
    path = store._path_for(receipt["request_id"])
    peer_bytes = _receipt_bytes(
        _outcome(_request(question="peer winner")).receipt)
    clock = _FakeClock()
    real_open = receipts_mod.os.open
    opens = []

    def open_then_peer_publishes(name, flags):
        opens.append(name)
        if len(opens) <= 2:
            if len(opens) == 2:
                path.write_bytes(peer_bytes)      # peer publishes during phase 1
            raise FileExistsError(17, "peer holds lock", name)
        return real_open(name, flags)

    path_type = type(path)
    real_read = path_type.read_text

    def denied_read(current, *args, **kwargs):
        if current == path:
            raise PermissionError(13, "final sharing denied", current)
        return real_read(current, *args, **kwargs)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(receipts_mod.os, "open", open_then_peer_publishes)
    monkeypatch.setattr(path_type, "read_text", denied_read)
    with pytest.raises(ConsultationError, match="timed out"):
        store.save(receipt)
    # 2s consumed acquiring (t=0,1) then reconcile reads under the SAME deadline
    # and stops exactly at t=3. A reset would have run the reconcile to t>=5.
    assert clock.now == 3.0


def test_poll_is_capped_to_remaining_time(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = ConsultationReceiptStore(tmp_path, lock_timeout=1.0, lock_poll=10.0)
    receipt = _outcome(_request()).receipt
    path = store._path_for(receipt["request_id"])
    lock = store._lock_for(path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"foreign lock")
    clock = _FakeClock()
    opens = []

    def denied_open(name, flags):
        opens.append(name)
        raise PermissionError(13, "held", name)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(receipts_mod.os, "open", denied_open)
    with pytest.raises(ConsultationError, match="lock timed out"):
        store.save(receipt)
    # Sleep capped to the 1.0 remaining, NOT the 10.0 poll; single attempt then
    # the post-sleep deadline check stops at t=1 (no post-deadline os.open).
    assert clock.now == 1.0
    assert len(opens) == 1


# --------------------------------------------------------------------------- #
# MEDIUM fix — operational + cleanup failures normalized; ownership honored
# --------------------------------------------------------------------------- #

def test_fallback_replace_failure_is_canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)

    def bad_replace(src, dst):
        raise PermissionError(13, "replace denied", dst)

    monkeypatch.setattr(receipts_mod.os, "replace", bad_replace)
    store = ConsultationReceiptStore(tmp_path)
    with pytest.raises(ConsultationError, match="publication failed"):
        store.save(_outcome(_request()).receipt)
    assert not any(p.name.endswith(".receipt.json")
                   for p in tmp_path.iterdir())          # no final fabricated
    assert _no_orphans(tmp_path) == []                   # owned lock + temp cleaned


def test_cleanup_close_failure_still_removes_lock_and_temp(tmp_path,
                                                           monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    real_close = receipts_mod.os.close

    def bad_close(fd):
        real_close(fd)                              # actually close (no fd leak)
        raise OSError(9, "close reported an error")

    monkeypatch.setattr(receipts_mod.os, "close", bad_close)
    with pytest.raises(ConsultationError, match="cleanup failed"):
        store.save(receipt)
    # publication succeeded; lock removal is still attempted (independent of the
    # close failure) and the owned temp is still cleaned.
    assert _no_orphans(tmp_path) == [_hashed()]


def test_cleanup_lock_unlink_failure_leaves_final_valid(tmp_path, monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    lock = store._lock_for(store._path_for("req-receipt"))
    real_unlink = receipts_mod.os.unlink

    def sel_unlink(target):
        if os.fspath(target) == os.fspath(lock):
            raise OSError(13, "lock unlink denied", target)
        return real_unlink(target)

    monkeypatch.setattr(receipts_mod.os, "unlink", sel_unlink)
    with pytest.raises(ConsultationError, match="cleanup failed"):
        store.save(receipt)
    assert verify_receipt(store.load("req-receipt")) == receipt   # final valid
    names = sorted(p.name for p in tmp_path.iterdir())
    assert not any(n.endswith(".receipt.tmp") for n in names)     # temp cleaned
    assert lock.name in names                                     # lock retained


def test_cleanup_temp_unlink_failure_leaves_final_valid(tmp_path, monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    real_unlink = receipts_mod.os.unlink

    def sel_unlink(target):
        if os.fspath(target).endswith(".receipt.tmp"):
            raise OSError(13, "temp unlink denied", target)
        return real_unlink(target)

    monkeypatch.setattr(receipts_mod.os, "unlink", sel_unlink)
    with pytest.raises(ConsultationError, match="cleanup failed"):
        store.save(receipt)
    assert verify_receipt(store.load("req-receipt")) == receipt   # final valid
    names = sorted(p.name for p in tmp_path.iterdir())
    assert not any(n.endswith(".receipt.lock") for n in names)    # lock cleaned
    assert any(n.endswith(".receipt.tmp") for n in names)         # temp retained


def test_publication_and_cleanup_both_fail_reports_primary_cause(tmp_path,
                                                                 monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)

    def bad_replace(src, dst):
        raise OSError(28, "no space left", dst)

    real_unlink = receipts_mod.os.unlink

    def sel_unlink(target):
        if os.fspath(target).endswith(".receipt.lock"):
            raise OSError(13, "lock unlink denied", target)
        return real_unlink(target)

    monkeypatch.setattr(receipts_mod.os, "replace", bad_replace)
    monkeypatch.setattr(receipts_mod.os, "unlink", sel_unlink)
    store = ConsultationReceiptStore(tmp_path)
    with pytest.raises(ConsultationError) as excinfo:
        store.save(_outcome(_request()).receipt)
    message = str(excinfo.value)
    assert "publication failed" in message          # principal cause preserved
    assert "cleanup also failed" in message          # secondary context appended
    names = [p.name for p in tmp_path.iterdir()]
    assert not any(n.endswith(".receipt.tmp") for n in names)     # temp cleaned
    assert not any(n.endswith(".receipt.json") for n in names)    # no final


# --------------------------------------------------------------------------- #
# MEDIUM fix — public load/all_receipts normalize malformed data
# --------------------------------------------------------------------------- #

def test_public_load_normalizes_malformed_final(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    path = store._path_for("req-receipt")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(ConsultationError):
        store.load("req-receipt")
    path.write_bytes(b"\xff\xfe\x00 invalid utf-8")
    with pytest.raises(ConsultationError):
        store.load("req-receipt")
    path.write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")
    with pytest.raises(ConsultationError):
        store.load("req-receipt")


def test_all_receipts_normalizes_and_preserves_order(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    store.save(_outcome(_request(request_id="alpha")).receipt)
    store.save(_outcome(_request(request_id="bravo")).receipt)
    got = store.all_receipts()
    assert len(got) == 2
    expected = sorted([sha256_text("alpha"), sha256_text("bravo")])
    assert [sha256_text(r["request_id"]) for r in got] == expected
    # A single malformed receipt fails closed (never silently skipped).
    store._path_for("alpha").write_text("broken", encoding="utf-8")
    with pytest.raises(ConsultationError):
        store.all_receipts()


# --------------------------------------------------------------------------- #
# LOW fix — foreign temp on UUID collision is never touched
# --------------------------------------------------------------------------- #

def test_foreign_temp_uuid_collision_is_never_deleted(tmp_path, monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    fixed = "deadbeefdeadbeefdeadbeefdeadbeef"

    class _FixedUUID:
        hex = fixed

    monkeypatch.setattr(receipts_mod.uuid, "uuid4", lambda: _FixedUUID())
    tmp_path.mkdir(parents=True, exist_ok=True)
    foreign = tmp_path / f".{fixed}.receipt.tmp"
    foreign.write_bytes(b"foreign-owner-bytes")
    with pytest.raises(ConsultationError, match="temp allocation failed"):
        store.save(_outcome(_request()).receipt)
    assert foreign.exists()
    assert foreign.read_bytes() == b"foreign-owner-bytes"     # never touched
    assert not any(p.name.endswith(".receipt.lock")
                   for p in tmp_path.iterdir())               # owned lock cleaned


# --------------------------------------------------------------------------- #
# permanent final-read sharing denial: bounded, canonical, no reset
# --------------------------------------------------------------------------- #

def test_permanent_final_read_denial_is_bounded_and_canonical(tmp_path,
                                                              monkeypatch):
    store = ConsultationReceiptStore(tmp_path, lock_timeout=3.0, lock_poll=1.0)
    receipt = _outcome(_request()).receipt
    store.save(receipt)                              # publish a valid final first
    path = store._path_for("req-receipt")
    final_bytes = path.read_bytes()
    clock = _FakeClock()
    path_type = type(path)
    real_read = path_type.read_text

    def denied(current, *args, **kwargs):
        if current == path:
            raise PermissionError(13, "final sharing denied", current)
        return real_read(current, *args, **kwargs)

    monkeypatch.setattr(receipts_mod, "time", clock)
    monkeypatch.setattr(path_type, "read_text", denied)
    with pytest.raises(ConsultationError, match="timed out"):
        store.save(receipt)                          # reconcile read denied
    assert clock.now == 3.0                           # one deadline, no reset
    assert path.read_bytes() == final_bytes           # final bytes unchanged


# --------------------------------------------------------------------------- #
# primary os.link remains preferred, acquired UNDER the lock
# --------------------------------------------------------------------------- #

def test_primary_publish_acquires_lock_before_link(tmp_path, monkeypatch):
    store = ConsultationReceiptStore(tmp_path)
    receipt = _outcome(_request()).receipt
    order = []
    real_open, real_link = receipts_mod.os.open, receipts_mod.os.link

    def rec_open(name, flags):
        order.append("lock-open")
        return real_open(name, flags)

    def rec_link(src, dst):
        order.append("link")
        return real_link(src, dst)

    def no_replace(src, dst):
        pytest.fail("os.replace fallback used despite working os.link")

    monkeypatch.setattr(receipts_mod.os, "open", rec_open)
    monkeypatch.setattr(receipts_mod.os, "link", rec_link)
    monkeypatch.setattr(receipts_mod.os, "replace", no_replace)
    assert store.save(receipt) == store._path_for("req-receipt")
    assert order[0] == "lock-open"                    # lock acquired FIRST
    assert order.count("link") == 1                   # os.link is the publish op
    assert order.index("lock-open") < order.index("link")
    assert _no_orphans(tmp_path) == [_hashed()]


# --------------------------------------------------------------------------- #
# mixed primary/fallback concurrency stress
# --------------------------------------------------------------------------- #

def _mixed_race(store, receipts):
    real_link = receipts_mod.os.link
    tl = threading.local()

    def link(src, dst):
        if getattr(tl, "fallback", False):
            raise OSError("forced fallback")
        return real_link(src, dst)

    barrier = threading.Barrier(len(receipts))
    wins, conflicts, leaks = [], [], []

    def worker(index):
        tl.fallback = (index % 2 == 0)          # half fallback, half primary
        barrier.wait()
        try:
            store.save(receipts[index]); wins.append(1)
        except ConsultationError:
            conflicts.append(1)
        except Exception as exc:                # noqa: BLE001
            leaks.append(type(exc).__name__)

    import backend.dialogues.openclaw_consultation.receipts as _rm
    original = _rm.os.link
    _rm.os.link = link
    try:
        with ThreadPoolExecutor(max_workers=len(receipts)) as pool:
            list(pool.map(worker, range(len(receipts))))
    finally:
        _rm.os.link = original
    return wins, conflicts, leaks


def test_mixed_conflicting_stress_twenty_trials(tmp_path):
    receipts = [_outcome(_request(question=f"mixed distinct {i}")).receipt
                for i in range(8)]
    for trial in range(20):
        trial_dir = tmp_path / f"mixed-distinct-{trial}"
        store = ConsultationReceiptStore(trial_dir)
        wins, conflicts, leaks = _mixed_race(store, receipts)
        assert leaks == []
        assert len(wins) == 1 and len(conflicts) == 7
        verify_receipt(store.load("req-receipt"))
        assert _no_orphans(trial_dir) == [_hashed()]


def test_mixed_identical_stress_twenty_trials(tmp_path):
    receipt = _outcome(_request()).receipt
    for trial in range(20):
        trial_dir = tmp_path / f"mixed-identical-{trial}"
        store = ConsultationReceiptStore(trial_dir)
        wins, conflicts, leaks = _mixed_race(store, [receipt] * 8)
        assert leaks == []
        assert len(wins) == 8 and conflicts == []
        assert verify_receipt(store.load("req-receipt")) == receipt
        assert _no_orphans(trial_dir) == [_hashed()]
