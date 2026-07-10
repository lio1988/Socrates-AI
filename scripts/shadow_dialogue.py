"""
Shadow Apprentice runner — watch a local model learn beside the council.

The council answers normally (mock by default — free, deterministic). AFTER
each final answer exists, the apprentice gets the same question plus the exact
synthesis memory lessons recorded by the council's injected-context ledger, is
judged blind by the council's own seats, and is compared per section against
the council's assembled winners. Nothing the apprentice does can change a
final answer (Goal 11, Stage 1).

Demo (free, mock apprentice — see the whole flow with zero setup):
    python scripts/shadow_dialogue.py
    python scripts/shadow_dialogue.py "your question"

Real local apprentice (needs a local OpenAI-compatible server, e.g. Ollama;
no cloud credits, in PowerShell):
    $env:CED_ENABLE_LOCAL_APPRENTICE = "1"
    $env:CED_LOCAL_LLM_MODEL = "llama3.1:8b"
    # optional: $env:CED_LOCAL_LLM_URL = "http://localhost:11434/v1"
    python scripts/shadow_dialogue.py

Optional switches (env-only):
    CED_OPENCLAW_LESSONS=0    # OFF switch - lessons reach neither side
    CED_SHADOW_SESSIONS=3     # questions in one batch (default 3)
    CED_SHADOW_DIR=path       # shadow record directory
    CED_IDENTITY_DIR=path     # identity registry directory
    CED_SHADOW_BATCH_ID=id    # deterministic test/replay id; do not reuse for
                              # independent promotion evidence

Every normal invocation creates a fresh random batch id, preventing repeated
operator runs from reusing the same evidence session ids. The evidence collector
also deduplicates identical replays and rejects conflicting duplicates.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import sys
import uuid

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
from backend.dialogues.openclaw_memory import load_jsonl              # noqa: E402
from backend.dialogues.openclaw_shadow import ShadowApprentice        # noqa: E402
from backend.dialogues.openclaw_identity import (                     # noqa: E402
    IdentityRegistry,
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
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _resolve_apprentice(env=None, *, probe=probe_local_server):
    """Resolve a gated real local adapter or a free deterministic demo adapter."""
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
        count = max(1, int(env.get("CED_SHADOW_SESSIONS", "3")))
    except ValueError:
        count = 3
    return (DEFAULT_QUESTIONS * (
        (count // len(DEFAULT_QUESTIONS)) + 1))[:count]


def _batch_id(env) -> str:
    explicit = str(env.get("CED_SHADOW_BATCH_ID", "")).strip()
    if explicit:
        if not _BATCH_ID_RE.fullmatch(explicit):
            raise ValueError(
                "CED_SHADOW_BATCH_ID must be 1-64 filesystem-safe characters")
        return explicit
    return uuid.uuid4().hex[:12]


def _save_records(records, env):
    out_dir = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow")))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "shadow_records.jsonl"
    with path.open("a", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(
                record, ensure_ascii=False, default=str) + "\n")
    return path


def _accumulated_profile(agent_id, records, registry):
    """Recompute evidence while preserving previously earned identity fields."""
    import dataclasses

    fresh = build_identity_profile(
        agent_id,
        records,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
    )
    stored = registry.load_profile(agent_id)
    if stored is None:
        return fresh
    return dataclasses.replace(
        fresh,
        identity_version=stored.identity_version,
        promotion_status=stored.promotion_status,
        next_gate=stored.next_gate,
        version_history=stored.version_history,
        known_failures=stored.known_failures,
        stable_lessons=stored.stable_lessons,
    )


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

    try:
        batch_id = _batch_id(env)
    except ValueError as exc:
        print(f"Invalid shadow batch id: {exc}")
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
    print(f"  evidence id: {batch_id}")
    print("  rule       : the apprentice observes and is judged - it can")
    print("               NEVER change a council answer (Stage 1).")
    print("-" * _W)

    runner = None
    for question_index, question in enumerate(questions):
        ced, council_mode = build_council(
            council_size=2,
            shadow_scoring_mode=ShadowScoringMode.OFF,
            openclaw_lessons=lessons,
        )
        if runner is None:
            runner = ShadowApprentice(
                apprentice,
                ced.registry.all_adapters(),
                lessons=lessons,
            )
        session_id = f"shadow_dialogue_{batch_id}_{question_index}"
        final, record = asyncio.run(runner.shadow_session(
            ced, question, session_id=session_id))
        print(f"  [{question_index + 1}/{len(questions)}] {question[:56]}")
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

    path = _save_records(runner.shadow_records, env)
    all_records = load_jsonl(path)
    registry = IdentityRegistry(env.get(
        "CED_IDENTITY_DIR", str(_ROOT / "runs" / "openclaw_identity")))
    profile = _accumulated_profile(
        apprentice.provider_id, all_records, registry)
    registry_path = registry.save_profile(profile)
    print(render_soul_card(profile))
    print("-" * _W)

    evidence = evidence_from_shadow_traces(
        apprentice.provider_id, all_records)
    gate = next_gate_for(profile.identity_version)
    if gate is None:
        print(f"  gate: none - {profile.identity_version} is the end of the "
              "current chain")
    else:
        result = evaluate_gate(gate, evidence)
        print(f"  gate {gate.gate_id}: "
              f"{'PASSED (a human may now record the promotion)' if result.passed else 'not yet'}")
        print(f"    {result.reasons[0]}")
    print(f"  history          : {len(all_records)} shadow record(s) "
          f"across all runs -> {path}")
    print(f"  identity registry-> {registry_path}")
    print("-" * _W)
    print("  Next:")
    print("    python scripts/openclaw_review.py   (turn history into proposals)")
    print("    python scripts/openclaw_status.py   (the joined-up view)")
    print("=" * _W)
    print(f"  Done. mode = {mode}. The apprentice earned evidence, "
          "not authority.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
