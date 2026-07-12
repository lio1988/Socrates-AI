"""Micro-Socratic Kernel v1 — tamper-evident receipts and hardened store.

Reuses the repository's hardened receipt persistence: hashed containment-checked
filenames, atomic no-overwrite publication, idempotency, immutable conflict, and
a fallback lock that survives the Windows DELETE_PENDING race (PermissionError)
without leaking a raw filesystem exception.
"""

import asyncio
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.dialogues.openclaw_socratic_kernel import (
    KernelPolicy,
    MicroSocraticError,
    MicroSocraticReceiptStore,
    MicroSocraticRequest,
    MicroSocraticKernelService,
    MockKernelProvider,
    build_receipt,
    verify_receipt,
)
from backend.dialogues.openclaw_socratic_kernel import receipts as receipts_mod
from backend.dialogues.openclaw_socratic_kernel.schemas import sha256_text

_NOW = "2026-07-11T00:00:00Z"
_EXP = "2026-07-11T01:00:00Z"


def _broken_link(src, dst):
    raise OSError("simulated: no hard-link support")


def _request(**overrides):
    base = dict(
        request_id="kernel-receipt", agent_id="local_apprentice_001",
        mode="standard", provider="mock", model="mock-auditor",
        task="Review this and list gaps.", draft="A draft to review.",
        purpose="pre-final self-check", max_tokens=1024, timeout_seconds=60.0,
        created_at=_NOW, expires_at=_EXP)
    base.update(overrides)
    return MicroSocraticRequest(**base)


def _receipt(question_suffix=""):
    request = _request(task="Review this and list gaps." + question_suffix)
    service = MicroSocraticKernelService(KernelPolicy(), worker_id="w",
                                         clock=lambda: _NOW)
    return asyncio.run(service.check(request, MockKernelProvider("mock"),
                                     now=_NOW)).receipt


def _hashed(request_id="kernel-receipt"):
    return sha256_text(request_id) + ".receipt.json"


# --------------------------------------------------------------------------- #
# build + verify
# --------------------------------------------------------------------------- #

def test_receipt_binds_request_and_check():
    receipt = _receipt()
    assert verify_receipt(receipt)["receipt_digest"] == receipt["receipt_digest"]
    assert receipt["isolated_check"] is True
    assert receipt["tools_executed"] is False
    assert receipt["consultation_executed"] is False


def test_receipt_stores_no_secrets_or_reasoning():
    blob = str(_receipt()).lower()
    for forbidden in ("api_key", "sk-ant", "bearer", "authorization",
                      "chain_of_thought", "reasoning", "raw_text", "scratchpad"):
        assert forbidden not in blob


def test_verify_unknown_field_refused():
    receipt = dict(_receipt())
    receipt["backdoor"] = 1
    with pytest.raises(MicroSocraticError, match="missing or unknown"):
        verify_receipt(receipt)


def test_verify_tampered_digest_refused():
    receipt = dict(_receipt())
    receipt["provider"] = "someone_else"
    with pytest.raises(MicroSocraticError, match="digest mismatch"):
        verify_receipt(receipt)


def test_negative_token_usage_refused():
    request = _request()
    service = MicroSocraticKernelService(KernelPolicy(), worker_id="w",
                                         clock=lambda: _NOW)
    outcome = asyncio.run(service.check(request, MockKernelProvider("mock"),
                                        now=_NOW))
    with pytest.raises(MicroSocraticError, match="counts"):
        build_receipt(request, outcome.check, worker_id="w", started_at=_NOW,
                      completed_at=_NOW, token_usage={"prompt_tokens": -1})


# --------------------------------------------------------------------------- #
# store: hashed/contained paths, idempotency, conflict
# --------------------------------------------------------------------------- #

def test_on_disk_name_is_hashed(tmp_path):
    store = MicroSocraticReceiptStore(tmp_path)
    path = store.save(_receipt())
    assert path.name == _hashed()
    assert store.load("kernel-receipt")["request_id"] == "kernel-receipt"


@pytest.mark.parametrize("evil", [
    "../../tmp/pwned", "..\\..\\pwned", "C:evil", "x:stream", "/abs", ".", "..",
])
def test_path_for_refuses_hostile_ids(tmp_path, evil):
    with pytest.raises(MicroSocraticError):
        MicroSocraticReceiptStore(tmp_path)._path_for(evil)


def test_valid_paths_stay_under_store(tmp_path):
    store = MicroSocraticReceiptStore(tmp_path)
    base = tmp_path.resolve()
    for rid in ("kernel-receipt", "kernel-standard-0a1b2c3d", "a.b_c-9"):
        assert store._path_for(rid).resolve().parent == base


def test_exact_rerun_idempotent(tmp_path):
    store = MicroSocraticReceiptStore(tmp_path)
    receipt = _receipt()
    assert store.save(receipt) == store.save(receipt)
    assert store.load("kernel-receipt")["receipt_digest"] == \
        receipt["receipt_digest"]


def test_conflicting_content_refused(tmp_path):
    store = MicroSocraticReceiptStore(tmp_path)
    store.save(_receipt())
    conflicting = _receipt(" (a very different task entirely)")
    assert conflicting["request_id"] == "kernel-receipt"
    with pytest.raises(MicroSocraticError, match="conflicting"):
        store.save(conflicting)


# --------------------------------------------------------------------------- #
# concurrency: primary path (atomic os.link)
# --------------------------------------------------------------------------- #

def _race(store, receipts):
    barrier = threading.Barrier(len(receipts))
    wins, conflicts, leaks = [], [], []

    def worker(rec):
        barrier.wait()
        try:
            store.save(rec)
            wins.append(rec["receipt_digest"])
        except MicroSocraticError:
            conflicts.append(rec["receipt_digest"])
        except Exception as exc:
            leaks.append(f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=len(receipts)) as pool:
        list(pool.map(worker, receipts))
    return wins, conflicts, leaks


def test_primary_concurrent_distinct_one_wins(tmp_path):
    store = MicroSocraticReceiptStore(tmp_path)
    receipts = [_receipt(f" v{i}") for i in range(8)]
    wins, conflicts, leaks = _race(store, receipts)
    assert leaks == [] and len(wins) == 1 and len(conflicts) == 7
    verify_receipt(store.load("kernel-receipt"))


# --------------------------------------------------------------------------- #
# concurrency: FALLBACK path (no hard-link) incl. Windows DELETE_PENDING race
# --------------------------------------------------------------------------- #

def test_fallback_concurrent_distinct_no_raw_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = MicroSocraticReceiptStore(tmp_path)
    receipts = [_receipt(f" fb{i}") for i in range(8)]
    wins, conflicts, leaks = _race(store, receipts)
    assert leaks == []                            # no raw PermissionError/JSON
    assert len(wins) == 1 and len(conflicts) == 7
    names = [p.name for p in tmp_path.iterdir()]
    assert names == [_hashed()]                   # one final, no orphan tmp/lock


def test_fallback_concurrent_identical_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = MicroSocraticReceiptStore(tmp_path)
    receipt = _receipt()
    wins, conflicts, leaks = _race(store, [receipt] * 8)
    assert leaks == [] and conflicts == []
    assert [p.name for p in tmp_path.iterdir()] == [_hashed()]


def test_fallback_lock_timeout_is_kernel_error(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts_mod.os, "link", _broken_link)
    store = MicroSocraticReceiptStore(tmp_path, lock_timeout=0.2, lock_poll=0.01)
    path = store._path_for("kernel-receipt")
    tmp_path.mkdir(parents=True, exist_ok=True)
    store._lock_for(path).write_text("", encoding="utf-8")   # stuck lock
    with pytest.raises(MicroSocraticError, match="lock timed out"):
        store.save(_receipt())
    assert not path.exists()


def test_malformed_final_receipt_is_kernel_error(tmp_path):
    store = MicroSocraticReceiptStore(tmp_path)
    path = store._path_for("kernel-receipt")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(MicroSocraticError):
        store.save(_receipt())
