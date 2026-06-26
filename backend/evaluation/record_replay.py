"""
Research Phase R2 — record once, replay deterministically (offline-first).

The point (per RESEARCH.md / the user): never draw conclusions from live results
"in the air". Instead:

    record once   — run each answerer (council / single-model / self-consistency)
                    on the task set ONE time (live, gated) and cache every output;
    replay        — re-score offline, deterministically, forever, with NO live call
                    and NO cost;
    compare       — council vs single-model vs self-consistency on the SAME recorded
                    outputs, by external truth (accuracy / cost / calibration).

This layer records at the **answerer** granularity (one cached output per
(answerer, task)). That is exactly what the matched-compute benchmark needs, and
it keeps replay fully offline and reproducible.

No live call happens here — recording wraps whatever inner answerer you pass
(a live one only when YOU run it gated). Replay needs no network and no key.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional, Sequence

from .baseline_harness import AnswerResult, Answerer, EvalTask, RunReport, run_benchmark

SCHEMA_VERSION = "answer_cache_v0"


class ReplayMiss(KeyError):
    """No recorded answer exists for this (answerer, task)."""


def _ckey(name: str, task_id: str) -> str:
    return f"{name}::{task_id}"


class AnswerCache:
    """A deterministic cache of recorded answers, keyed by (answerer name, task id)."""

    def __init__(self, entries: Optional[Dict[str, dict]] = None) -> None:
        self.entries: Dict[str, dict] = dict(entries or {})

    # -- access --
    def get(self, name: str, task_id: str) -> Optional[AnswerResult]:
        raw = self.entries.get(_ckey(name, task_id))
        return None if raw is None else AnswerResult(**raw)

    def put(self, name: str, task_id: str, result: AnswerResult) -> None:
        self.entries[_ckey(name, task_id)] = asdict(result)

    def has(self, name: str, task_id: str) -> bool:
        return _ckey(name, task_id) in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    # -- persistence (local JSON; no secrets — only task ids + model outputs) --
    def save(self, path: str) -> None:
        doc = {"schema_version": SCHEMA_VERSION, "entries": self.entries}
        Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "AnswerCache":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version mismatch: expected {SCHEMA_VERSION!r}, got {doc.get('schema_version')!r}")
        return cls(doc.get("entries", {}))


class RecordingAnswerer:
    """
    Wraps an inner answerer: forwards each call AND records the result into the
    cache. Run this ONCE (with a live inner answerer, gated) to capture outputs;
    thereafter use `ReplayAnswerer`. Recording itself makes no extra call — it just
    saves what the inner answerer returned.
    """

    def __init__(self, inner: Answerer, cache: AnswerCache) -> None:
        self.inner = inner
        self.cache = cache
        self.name = inner.name

    def answer(self, task: EvalTask) -> AnswerResult:
        result = self.inner.answer(task)
        self.cache.put(self.name, task.task_id, result)
        return result


class ReplayAnswerer:
    """
    Replays recorded outputs for `name` — fully offline, deterministic, no network.
    `on_miss="raise"` (default) surfaces gaps loudly; `on_miss="empty"` returns an
    honest empty/zero-cost result so a partial cache still scores transparently.
    """

    def __init__(self, name: str, cache: AnswerCache, on_miss: str = "raise") -> None:
        self.name = name
        self.cache = cache
        self.on_miss = on_miss

    def answer(self, task: EvalTask) -> AnswerResult:
        result = self.cache.get(self.name, task.task_id)
        if result is None:
            if self.on_miss == "raise":
                raise ReplayMiss(_ckey(self.name, task.task_id))
            return AnswerResult(final_answer="", raw_text="", confidence=0.0,
                                cost_units=0.0, meta={"replay_miss": True})
        return result


def record_run(inner: Answerer, tasks: Sequence[EvalTask], cache: AnswerCache) -> RunReport:
    """Score `inner` once while recording every output into `cache` for later replay."""
    return run_benchmark(RecordingAnswerer(inner, cache), tasks)


def replay_run(name: str, tasks: Sequence[EvalTask], cache: AnswerCache,
               on_miss: str = "raise") -> RunReport:
    """Score a previously-recorded answerer offline from the cache."""
    return run_benchmark(ReplayAnswerer(name, cache, on_miss=on_miss), tasks)
