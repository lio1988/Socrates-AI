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
        except ConsultationError:
            conflicts.append(rec["receipt_digest"])
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
