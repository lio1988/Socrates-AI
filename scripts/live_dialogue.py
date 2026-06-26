"""
Socratic dialogue runner — watch the council of agents deliberate, live or mock.

Doubly gated like the smoke: REAL agents only when CED_ENABLE_LIVE_PROVIDERS=1
AND a real ANTHROPIC_API_KEY; otherwise a deterministic MOCK dialogue (the
default — free, no network). A LIVE run makes ~10-15 model calls (the agents go
through a full Socratic dialogue), so it costs a little real money — use a cheap
model (Haiku). Shadow peer-scoring is OFF here to keep the call count (and cost)
down; the deliberation + council ratification still run.

Mock (free):
    python scripts/live_dialogue.py "your question"

Live (set flag + key + cheap models first, in PowerShell):
    $env:CED_ENABLE_LIVE_PROVIDERS = "1"
    $env:CED_LIVE_MODELS = "claude-haiku-4-5-20251001,claude-haiku-4-5-20251001"
    # load ANTHROPIC_API_KEY from .env into the environment (see README), then:
    python scripts/live_dialogue.py "Είναι η γνώση ατομική ή συλλογική;"

No key is ever printed; .env is never modified.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.live_providers import build_council          # noqa: E402
from backend.dialogues.models import ShadowScoringMode              # noqa: E402

DEFAULT_QUESTION = "Είναι η γνώση αποτέλεσμα ατομικής σκέψης ή συλλογικής διαλεκτικής διαδικασίας;"
_W = 78


def _clip(value, n: int) -> str:
    s = str(value).replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def main(argv=None) -> int:
    argv = sys.argv if argv is None else argv
    question = argv[1] if len(argv) > 1 else DEFAULT_QUESTION

    # Cheap: 2 seats (minimum quorum), NO shadow scoring -> fewer live calls.
    ced, mode = build_council(council_size=2, shadow_scoring_mode=ShadowScoringMode.OFF)

    print("=" * _W)
    if mode == "live":
        print("  SOCRATES AI — LIVE SOCRATIC DIALOGUE (real model calls)")
        print("  *** This makes ~10-15 real API calls — it costs a little money. ***")
    else:
        print("  SOCRATES AI — MOCK SOCRATIC DIALOGUE (offline, free, deterministic)")
        print("  (set CED_ENABLE_LIVE_PROVIDERS=1 + a real key for a live run)")
    print("=" * _W)
    print(f"  question : {question}")
    print(f"  council  : 2 agents | scoring: off | mode: {mode}")
    print("-" * _W)

    final = asyncio.run(ced.run_registry_session(question, session_id="live_dialogue"))
    state = ced.get_session("live_dialogue")

    print("  THE DIALOGUE — each agent's move, in order:")
    for mv in state.moves:
        role = mv.role.value.upper().replace("_", " ")
        print(f"    [{mv.phase.value:<16}] {role}")
        print(f"        {_clip(mv.content, _W - 8)}")
    print("-" * _W)

    # Per-phase trace — shows WHERE the dialogue stopped and WHY (provider statuses).
    rounds = (final.audit_summary or {}).get("registry_phase_rounds", [])
    print("  PER-PHASE TRACE (proceed / ok / failed providers + status):")
    for r in rounds:
        status = r.get("provider_status_counts") or r.get("provider_status_summary") or ""
        print(f"    {r.get('phase', ''):<16} proceed={r.get('proceed')} "
              f"ok={r.get('ok_providers')} failed={r.get('failed_providers')} {status}")
    # exact failure reasons + what the model actually returned (from CED-owned rounds)
    failed = [resp for rnd in getattr(state, "registry_rounds", [])
              for resp in rnd.responses if not resp.ok]
    if failed:
        print("  FAILED RESPONSES (provider | status | error | raw model output):")
        for resp in failed[:8]:
            print(f"    {resp.provider_id}")
            print(f"      status : {resp.status.value} | repair: {resp.repair_attempted}/{resp.repair_succeeded}")
            print(f"      error  : {resp.error_message}")          # full (not truncated)
            print(f"      raw    : {_clip(resp.raw_text, _W - 12)}")
    print("-" * _W)

    print(f"  ratification : {final.ratification_status}  (ratified={final.ratified})")
    print("-" * _W)
    print("  FINAL ANSWER (assembled by the council):")
    if final.synthesis:
        for s in final.synthesis.sections:
            print(f"    ## {s.section_name.value.replace('_', ' ').title()}")
            print(f"       {_clip(s.content, _W * 2)}")
    else:
        print("    (no answer — council did not reach quorum; safe fallback)")
    print("=" * _W)
    print(f"  Done. mode = {mode}. No key printed; .env untouched.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
