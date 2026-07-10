"""
OpenClaw status — one command that answers "what is going on?".

Offline and read-only: counts what exists on disk, shows the env gates, and
recommends the next command. The ONLY optional network touch is a probe of
the LOCAL server, and only when the local-apprentice gate is already ON.

    .\\.venv\\Scripts\\python.exe scripts\\openclaw_status.py
    .\\.venv\\Scripts\\python.exe scripts\\openclaw_status.py --json

No cloud calls, no API keys read beyond gate presence, nothing promoted,
nothing mutated. See docs/openclaw_memory_lessons/OPERATOR_GUIDE.md.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_memory import (                       # noqa: E402
    load_jsonl,
    load_traces,
    parse_memory_lessons,
)
from backend.dialogues.openclaw_identity import IdentityRegistry      # noqa: E402
from backend.dialogues.openclaw_local import (                        # noqa: E402
    LOCAL_GATE_ENV,
    LOCAL_MODEL_ENV,
    DEFAULT_LOCAL_BASE_URL,
    probe_local_server,
)

_W = 78


def _count_stable_lessons():
    try:
        from backend.dialogues.openclaw_memory import load_stable_lessons
        return len(load_stable_lessons())
    except Exception:
        return None                       # lessons file missing/unreadable


def _count_proposals(proposals_dir: pathlib.Path):
    lessons = patches = 0
    lessons_path = proposals_dir / "PROPOSED_LESSONS.md"
    if lessons_path.exists():
        try:
            lessons = len(parse_memory_lessons(
                lessons_path.read_text(encoding="utf-8")))
        except Exception:
            lessons = -1                  # present but unparseable — flag it
    patches_path = proposals_dir / "PROPOSED_PROMPT_PATCHES.md"
    if patches_path.exists():
        patches = patches_path.read_text(encoding="utf-8").count("## PATCH-")
    return lessons, patches


def collect_status(env=None, *, probe=probe_local_server):
    """Everything the operator needs to know, as one dict (offline)."""
    env = os.environ if env is None else env

    trace_dir = env.get("CED_TRACE_DIR", str(_ROOT / "runs" / "openclaw_traces"))
    shadow_path = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow"))) / "shadow_records.jsonl"
    identity_dir = env.get("CED_IDENTITY_DIR",
                           str(_ROOT / "runs" / "openclaw_identity"))
    proposals_dir = pathlib.Path(env.get(
        "CED_PROPOSALS_DIR", str(_ROOT / "runs" / "openclaw_proposals")))

    traces = load_traces(trace_dir)
    shadow_records = load_jsonl(shadow_path)
    profiles = IdentityRegistry(identity_dir).all_profiles()
    lessons_pending, patches_pending = _count_proposals(proposals_dir)

    local_gate = env.get(LOCAL_GATE_ENV, "").strip() == "1"
    local_model = env.get(LOCAL_MODEL_ENV, "").strip()
    local_server = None
    if local_gate and local_model:
        base_url = env.get("CED_LOCAL_LLM_URL", "").strip() or DEFAULT_LOCAL_BASE_URL
        ok, message = probe(base_url, timeout=3.0)
        local_server = {"reachable": ok, "detail": message}

    status = {
        "stable_lessons": _count_stable_lessons(),
        "traces": {"count": len(traces), "dir": str(trace_dir)},
        "shadow_records": {"count": len(shadow_records),
                           "path": str(shadow_path)},
        "identity": [{
            "agent_id": p.agent_id,
            "identity_version": p.identity_version,
            "promotion_status": p.promotion_status,
            "sessions_analyzed": p.sessions_analyzed,
            "promotions_recorded": len(p.version_history),
            "next_gate": p.next_gate,
        } for p in profiles],
        "proposals": {"lessons": lessons_pending, "patches": patches_pending,
                      "dir": str(proposals_dir)},
        "gates": {
            "live_providers": env.get("CED_ENABLE_LIVE_PROVIDERS", "").strip() == "1",
            "local_apprentice": local_gate,
            "local_model": local_model or None,
        },
        "local_server": local_server,
    }
    status["next_command"] = _next_command(status)
    return status


def _next_command(status) -> str:
    """One honest recommendation, by pipeline stage."""
    if status["local_server"] is not None and not status["local_server"]["reachable"]:
        return ("start your local server (e.g. `ollama serve`), then: "
                "python scripts/shadow_dialogue.py")
    # A human decision waiting always outranks collecting more data.
    lessons = status["proposals"]["lessons"]
    patches = status["proposals"]["patches"]
    if lessons > 0 or patches > 0:
        return ("review the proposal files in " + status["proposals"]["dir"] +
                " (A/B test before promoting - OPERATOR_GUIDE Mode E/F)")
    if status["traces"]["count"] == 0 and status["shadow_records"]["count"] == 0:
        return "python scripts/shadow_dialogue.py   (collect first evidence - free demo)"
    return "python scripts/openclaw_review.py   (turn accumulated history into proposals)"


def main(argv=None, env=None, *, probe=probe_local_server) -> int:
    argv = sys.argv if argv is None else argv
    status = collect_status(env, probe=probe)

    if "--json" in argv:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    print("=" * _W)
    print("  OPENCLAW STATUS - what exists, what it means, what is next")
    print("=" * _W)
    sl = status["stable_lessons"]
    print(f"  stable lessons   : {sl if sl is not None else 'MEMORY_LESSONS.md missing/unreadable'}")
    print(f"  traces           : {status['traces']['count']} session(s) "
          f"in {status['traces']['dir']}")
    print(f"  shadow records   : {status['shadow_records']['count']} "
          f"in {status['shadow_records']['path']}")
    if status["identity"]:
        print("  identity registry:")
        for p in status["identity"]:
            print(f"    {p['agent_id']}: {p['identity_version']} "
                  f"({p['promotion_status']}) | sessions={p['sessions_analyzed']} "
                  f"| promotions={p['promotions_recorded']} "
                  f"| next gate={p['next_gate']}")
    else:
        print("  identity registry: empty (no apprentice has run yet)")
    lp, pp = status["proposals"]["lessons"], status["proposals"]["patches"]
    print(f"  pending proposals: lessons={lp if lp >= 0 else 'UNPARSEABLE'} "
          f"| prompt patches={pp}")
    g = status["gates"]
    print(f"  gates            : live={'ON' if g['live_providers'] else 'off'} "
          f"| local apprentice={'ON' if g['local_apprentice'] else 'off'} "
          f"| local model={g['local_model'] or 'not set'}")
    if status["local_server"] is not None:
        s = status["local_server"]
        print(f"  local server     : "
              f"{'reachable' if s['reachable'] else 'NOT REACHABLE'} "
              f"- {s['detail']}")
    print("-" * _W)
    print("  Next:")
    print(f"    {status['next_command']}")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
