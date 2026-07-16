"""
Council Live View — Slice 1 golden baseline (written BEFORE the observer hook).

Purpose: lock the deterministic canonical `FinalResponse` of an existing CED
run so that, once the flag-gated observer/emission hook is added, we can prove
it changes nothing:

    observer absent (this file, now)        → canonical bytes == baseline
    observer disabled (added with the hook) → canonical bytes == baseline
    observer enabled but raising (later)    → canonical bytes == baseline

The observer hook does not exist yet; this file locks only the observer-ABSENT
baseline and the determinism boundary. The disabled/raises assertions are
added with the hook, reusing `canonical_final_response_bytes` here.

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

This module touches NO production code: `ced.py` is unchanged.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Set, Tuple

from backend.dialogues import (
    CEDOrchestrator,
    FakeProvider,
    SocraticAgent,
    build_council,
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

def run_legacy_baseline(session_id: str = "golden_legacy_session"):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    ced = CEDOrchestrator(agents, provider)
    return ced.run_session(QUESTION, session_id=session_id)


def run_registry_baseline(session_id: str = "golden_registry_session"):
    ced, mode = build_council()
    assert mode == "mock", f"golden baseline must run offline, got {mode!r}"
    return asyncio.run(ced.run_registry_session(QUESTION,
                                                session_id=session_id))


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
