"""
Research R2 — record once, replay deterministically (offline).

Validates the record/replay machinery on controllable stand-ins (no live calls):
recording captures outputs, replay reproduces them exactly offline, partial caches
are handled honestly, and a multi-answerer comparison is reproduced from cache.
"""

import pytest

from backend.evaluation.baseline_harness import (
    synthetic_tasks, OracleAnswerer, SelfConsistencyAnswerer, run_benchmark, compare,
)
from backend.evaluation.record_replay import (
    AnswerCache, RecordingAnswerer, ReplayAnswerer, ReplayMiss,
    record_run, replay_run, SCHEMA_VERSION,
)


def test_record_then_replay_is_identical():
    tasks = synthetic_tasks(40)
    inner = OracleAnswerer(error_rate=0.35, seed="rr")
    cache = AnswerCache()
    rec = record_run(inner, tasks, cache)            # record once
    rep = replay_run(inner.name, tasks, cache)       # replay offline
    assert len(cache) == len(tasks)
    assert rep.accuracy == rec.accuracy
    assert [o.prediction for o in rep.outcomes] == [o.prediction for o in rec.outcomes]


def test_replay_is_offline_no_inner_needed():
    tasks = synthetic_tasks(10)
    cache = AnswerCache()
    record_run(OracleAnswerer(0.0, name="perfect"), tasks, cache)
    # replay needs only the cache + the name — no answerer object
    rep = run_benchmark(ReplayAnswerer("perfect", cache), tasks)
    assert rep.accuracy == 1.0


def test_cache_json_round_trip_and_schema_guard(tmp_path):
    tasks = synthetic_tasks(8)
    cache = AnswerCache()
    record_run(OracleAnswerer(0.5, name="a"), tasks, cache)
    path = str(tmp_path / "cache.json")
    cache.save(path)
    loaded = AnswerCache.load(path)
    assert len(loaded) == len(tasks)
    assert replay_run("a", tasks, loaded).n == len(tasks)
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "WRONG", "entries": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        AnswerCache.load(str(bad))


def test_replay_miss_raises_by_default():
    tasks = synthetic_tasks(6)
    cache = AnswerCache()
    record_run(OracleAnswerer(0.0, name="partial"), tasks[:3], cache)   # only first 3
    with pytest.raises(ReplayMiss):
        replay_run("partial", tasks, cache)                             # task 4 missing


def test_replay_miss_empty_mode_is_honest():
    tasks = synthetic_tasks(6)
    cache = AnswerCache()
    record_run(OracleAnswerer(0.0, name="partial"), tasks[:3], cache)
    rep = replay_run("partial", tasks, cache, on_miss="empty")
    assert rep.n == 6
    # the 3 missing replay as empty (wrong); only the 3 recorded perfect ones pass
    assert rep.accuracy == pytest.approx(0.5)


def test_recording_forwards_result():
    tasks = synthetic_tasks(5)
    inner = OracleAnswerer(0.0, name="fwd")
    cache = AnswerCache()
    wrapped = RecordingAnswerer(inner, cache)
    out = wrapped.answer(tasks[0])
    assert out.final_answer == tasks[0].gold          # forwarded unchanged
    assert cache.has("fwd", tasks[0].task_id)          # and recorded


def test_multi_answerer_comparison_reproduced_from_cache():
    # record council/single/self-consistency stand-ins ONCE, then reproduce the
    # matched-compute comparison entirely offline from the cache.
    tasks = synthetic_tasks(48)
    base = OracleAnswerer(error_rate=0.4, seed="single", name="single_model")
    answerers = [base, SelfConsistencyAnswerer(base, k=5, name="self_consistency@5")]

    cache = AnswerCache()
    live_rows = compare(answerers, tasks)              # "record" pass (here: stand-ins)
    for a in answerers:
        record_run(a, tasks, cache)

    replay = [ReplayAnswerer(a.name, cache) for a in answerers]
    replay_rows = compare(replay, tasks)

    # offline replay reproduces accuracy exactly (cost differs: replay cost is the
    # recorded cost, carried in the cached AnswerResult)
    assert [r.accuracy for r in replay_rows] == [r.accuracy for r in live_rows]
    assert replay_rows[1].accuracy > replay_rows[0].accuracy   # SC gain preserved


def test_schema_version_constant():
    assert SCHEMA_VERSION == "answer_cache_v0"
