"""
Shadow Apprentice runner — watch a local model learn beside the council.

The council answers normally (mock by default — free, deterministic). AFTER
each final answer exists, the apprentice gets the same question plus the same
selected memory lessons, is judged blind by the council's own seats, and is
compared per section against the council's assembled winners. Nothing the
apprentice does can change a final answer (Goal 11, Stage 1).

Demo (free, mock apprentice — see the whole flow with zero setup):
    python scripts/shadow_dialogue.py
    python scripts/shadow_dialogue.py "your question"

Real local apprentice (needs a local OpenAI-compatible server, e.g. Ollama;
no cloud credits, in PowerShell):
    $env:CED_ENABLE_LOCAL_APPRENTICE = "1"
    $env:CED_LOCAL_LLM_MODEL = "llama3.1:8b"     # any model you have pulled
    # optional: $env:CED_LOCAL_LLM_URL = "http://localhost:11434/v1"
    python scripts/shadow_dialogue.py

Optional switches (env-only):
    CED_OPENCLAW_LESSONS=0    # OFF switch - stable lessons reach the
                              # apprentice by default (same key as the council)
    CED_SHADOW_SESSIONS=3     # how many questions in a batch run (default 3)
    CED_SHADOW_DIR=path       # where shadow records go
                              # (default runs/openclaw_shadow)

Every session appends a marked shadow record (shadow_run=true) to disk; the
run ends with the apprentice's SOUL CARD and its progress against identity
gate v0.3 -> v0.4 (3 verified shadow blind_spots wins). The card is
descriptive, not authority. No key is ever printed; .env is never modified.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.live_providers import build_council            # noqa: E402
from backend.dialogues.models import ShadowScoringMode                # noqa: E402
from backend.dialogues.provider_registry import ScriptedMockProvider  # noqa: E402
from backend.dialogues.openclaw_local import (                        # noqa: E402
    DEFAULT_APPRENTICE_ID,
    LOCAL_GATE_ENV,
    probe_local_server,
    resolve_local_adapter,
)
from backend.dialogues.openclaw_shadow import ShadowApprentice        # noqa: E402
from backend.dialogues.openclaw_identity import (                     # noqa: E402
    build_identity_profile,
    evaluate_gate,
    evidence_from_shadow_traces,
    next_gate_for,
    render_soul_card,
)

DEFAULT_QUESTIONS = [
    "Είναι η γνώση αποτέλεσμα ατομικής σκέψης ή συλλογικής διαλεκτικής;",
    "Μπορεί ένα σύστημα να βελτιώνεται χωρίς εξωτερικό κριτή;",
    "Τι διακρίνει την πεποίθηση από την τεκμηριωμένη γνώση;",
]
_W = 78


def _resolve_apprentice(env=None, *, probe=probe_local_server):
    """(adapter_or_None, mode, note). Modes: 'local' (gated, server probed OK),
    'local-unavailable' (gated but the server is down -> honest stop, never a
    silent mock fallback), 'demo' (gate off -> free deterministic mock)."""
    env = os.environ if env is None else env
    if env.get(LOCAL_GATE_ENV, "").strip() == "1":
        adapter, reason = resolve_local_adapter(env)
        if adapter is None:
            return None, "local-unavailable", reason
        ok, message = probe(adapter.base_url, timeout=3.0)
        if not ok:
            return None, "local-unavailable", message
        return adapter, "local", reason
    return (ScriptedMockProvider(DEFAULT_APPRENTICE_ID), "demo",
            f"demo apprentice (mock; set {LOCAL_GATE_ENV}=1 + "
            "CED_LOCAL_LLM_MODEL for a real local model)")


def _resolve_lessons(env=None):
    env = os.environ if env is None else env
    if env.get("CED_OPENCLAW_LESSONS", "1") == "0":
        return None, "lessons: off"
    try:
        from backend.dialogues.openclaw_memory import load_stable_lessons
        pool = load_stable_lessons()
    except Exception:
        pool = []
    return (pool or None,
            f"lessons: {len(pool)} stable" if pool else "lessons: unavailable")


def _questions(argv, env):
    if len(argv) > 1:
        return [argv[1]]
    try:
        n = max(1, int(env.get("CED_SHADOW_SESSIONS", "3")))
    except ValueError:
        n = 3
    return (DEFAULT_QUESTIONS * ((n // len(DEFAULT_QUESTIONS)) + 1))[:n]


def _save_records(records, env):
    out_dir = pathlib.Path(env.get("CED_SHADOW_DIR",
                                   str(_ROOT / "runs" / "openclaw_shadow")))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "shadow_records.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    apprentice, mode, apprentice_note = _resolve_apprentice(env)
    if apprentice is None:
        print("=" * _W)
        print("  SHADOW APPRENTICE - cannot run the local apprentice:")
        print(f"    {apprentice_note}")
        print("=" * _W)
        return 1

    lessons, lessons_note = _resolve_lessons(env)
    questions = _questions(argv, env)

    print("=" * _W)
    if mode == "local":
        print("  SHADOW APPRENTICE - REAL LOCAL MODEL (no cloud credits)")
    else:
        print("  SHADOW APPRENTICE - DEMO (mock apprentice, free, deterministic)")
    print("=" * _W)
    print(f"  apprentice : {apprentice_note}")
    print(f"  features   : {lessons_note} | sessions: {len(questions)}")
    print(f"  rule       : the apprentice observes and is judged - it can")
    print(f"               NEVER change a council answer (Stage 1).")
    print("-" * _W)

    for qi, question in enumerate(questions):
        # A fresh council per question; the runner accumulates the records.
        ced, council_mode = build_council(
            council_size=2, shadow_scoring_mode=ShadowScoringMode.OFF)
        if qi == 0:
            runner = ShadowApprentice(apprentice,
                                      ced.registry.all_adapters(),
                                      lessons=lessons)
        final, record = asyncio.run(runner.shadow_session(
            ced, question, session_id=f"shadow_dialogue_{qi}"))
        print(f"  [{qi + 1}/{len(questions)}] {question[:56]}")
        print(f"      council : ratified={final.ratified} (mode: {council_mode})")
        if not record["ok"]:
            print(f"      shadow  : FAILED ({record.get('reason')})")
            continue
        wins = record["shadow_wins"]
        total = len(record["shadow_comparison"])
        print(f"      shadow  : won {wins}/{total} sections "
              f"| lessons used: {record.get('lessons_selected', 0)}")
        for row in record["shadow_comparison"]:
            marker = "WIN " if row["shadow_win"] else "    "
            print(f"        {marker}{row['section_name']:<20} "
                  f"apprentice={row['apprentice_score']} "
                  f"council={row['council_score']}")
    print("-" * _W)

    # Identity: what the apprentice has PROVEN so far (descriptive only).
    path = _save_records(runner.shadow_records, env)
    profile = build_identity_profile(apprentice.provider_id,
                                     runner.shadow_records,
                                     promotion_status="shadow_apprentice",
                                     identity_version="v0.3")
    print(render_soul_card(profile))
    print("-" * _W)
    evidence = evidence_from_shadow_traces(apprentice.provider_id,
                                           runner.shadow_records)
    gate = next_gate_for("v0.3")
    result = evaluate_gate(gate, evidence)
    print(f"  gate {gate.gate_id}: "
          f"{'PASSED (a human may now record the promotion)' if result.passed else 'not yet'}")
    print(f"    {result.reasons[0]}")
    print(f"  shadow records -> {path}")
    print("=" * _W)
    print(f"  Done. mode = {mode}. The apprentice earned evidence, "
          f"not authority.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
