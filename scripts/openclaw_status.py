"""
OpenClaw status — one command that answers "what is going on?".

Offline and read-only: counts what exists on disk, shows the env gates, and
recommends the next command. The ONLY optional network touch is a probe of
the LOCAL server, and only when the local-apprentice gate is already ON.

    .\.venv\Scripts\python.exe scripts\openclaw_status.py
    .\.venv\Scripts\python.exe scripts\openclaw_status.py --json

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
from backend.dialogues.openclaw_identity import (                     # noqa: E402
    IdentityRegistry,
    SelfRevisionRegistry,
    SelfRevisionTransactionCoordinator,
)
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
        return None


def _count_proposals(proposals_dir: pathlib.Path):
    lessons = patches = 0
    lessons_path = proposals_dir / "PROPOSED_LESSONS.md"
    if lessons_path.exists():
        try:
            lessons = len(parse_memory_lessons(
                lessons_path.read_text(encoding="utf-8")))
        except Exception:
            lessons = -1
    patches_path = proposals_dir / "PROPOSED_PROMPT_PATCHES.md"
    if patches_path.exists():
        patches = patches_path.read_text(encoding="utf-8").count("## PATCH-")
    return lessons, patches


def _status_counts(records):
    by_status = {}
    for record in records:
        status = str(record.get("status", record.get("state", "unknown")))
        by_status[status] = by_status.get(status, 0) + 1
    return {key: by_status[key] for key in sorted(by_status)}


def collect_status(env=None, *, probe=probe_local_server):
    """Everything the operator needs to know, as one dict (offline)."""
    env = os.environ if env is None else env

    trace_dir = env.get("CED_TRACE_DIR", str(_ROOT / "runs" / "openclaw_traces"))
    shadow_path = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow"))) / \
        "shadow_records.jsonl"
    identity_dir = pathlib.Path(env.get(
        "CED_IDENTITY_DIR", str(_ROOT / "runs" / "openclaw_identity")))
    proposals_dir = pathlib.Path(env.get(
        "CED_PROPOSALS_DIR", str(_ROOT / "runs" / "openclaw_proposals")))
    self_revision_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_DIR",
        str(_ROOT / "runs" / "openclaw_self_revisions"),
    ))
    transaction_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_TRANSACTION_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_transactions"),
    ))

    traces = load_traces(trace_dir)
    shadow_records = load_jsonl(shadow_path)
    identity_registry = IdentityRegistry(identity_dir)
    lifecycle_registry = SelfRevisionRegistry(self_revision_dir)
    profiles = identity_registry.all_profiles()
    lessons_pending, patches_pending = _count_proposals(proposals_dir)
    self_revision_records = lifecycle_registry.all_records()
    transaction_records = SelfRevisionTransactionCoordinator(
        identity_registry,
        lifecycle_registry,
        transaction_dir,
    ).all_transactions()

    local_gate = env.get(LOCAL_GATE_ENV, "").strip() == "1"
    local_model = env.get(LOCAL_MODEL_ENV, "").strip()
    local_server = None
    if local_gate and local_model:
        base_url = env.get("CED_LOCAL_LLM_URL", "").strip() or DEFAULT_LOCAL_BASE_URL
        ok, message = probe(base_url, timeout=3.0)
        local_server = {"reachable": ok, "detail": message}

    incomplete_transactions = [
        {
            "agent_id": record["agent_id"],
            "proposal_id": record["proposal_id"],
            "state": record["state"],
        }
        for record in transaction_records
        if record["state"] != "committed"
    ]
    status = {
        "stable_lessons": _count_stable_lessons(),
        "traces": {"count": len(traces), "dir": str(trace_dir)},
        "shadow_records": {"count": len(shadow_records),
                           "path": str(shadow_path)},
        "identity": [{
            "agent_id": profile.agent_id,
            "identity_version": profile.identity_version,
            "promotion_status": profile.promotion_status,
            "sessions_analyzed": profile.sessions_analyzed,
            "promotions_recorded": len(profile.version_history),
            "self_revisions_recorded": len(profile.revision_history),
            "soul_principles": len(profile.soul_principles),
            "next_gate": profile.next_gate,
        } for profile in profiles],
        "proposals": {
            "lessons": lessons_pending,
            "patches": patches_pending,
            "dir": str(proposals_dir),
        },
        "self_revisions": {
            "count": len(self_revision_records),
            "by_status": _status_counts(self_revision_records),
            "dir": str(self_revision_dir),
        },
        "revision_transactions": {
            "count": len(transaction_records),
            "by_state": _status_counts(transaction_records),
            "incomplete": incomplete_transactions,
            "dir": str(transaction_dir),
        },
        "gates": {
            "live_providers": env.get(
                "CED_ENABLE_LIVE_PROVIDERS", "").strip() == "1",
            "local_apprentice": local_gate,
            "local_model": local_model or None,
        },
        "local_server": local_server,
    }
    status["next_command"] = _next_command(status)
    return status


def _next_command(status) -> str:
    """One honest recommendation, prioritizing recovery and human decisions."""
    incomplete = status["revision_transactions"]["incomplete"]
    if incomplete:
        transaction = incomplete[0]
        return (
            "python scripts/openclaw_recover_revision.py "
            f"{transaction['agent_id']} {transaction['proposal_id']}"
        )
    if status["local_server"] is not None and not status["local_server"]["reachable"]:
        return ("start your local server (e.g. `ollama serve`), then: "
                "python scripts/shadow_dialogue.py")

    revision_counts = status["self_revisions"]["by_status"]
    awaiting_review = sum(
        revision_counts.get(name, 0)
        for name in (
            "submitted", "evaluated_passed", "evaluated_failed", "approved",
        )
    )
    if awaiting_review:
        return ("review self-revision lifecycle records in " +
                status["self_revisions"]["dir"] +
                " (agents propose; a named non-self reviewer decides)")
    if revision_counts.get("probationary", 0):
        return ("collect post-change evidence for probationary self-revisions "
                "and record confirmed or reverted outcomes")

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
    stable = status["stable_lessons"]
    print(f"  stable lessons   : "
          f"{stable if stable is not None else 'MEMORY_LESSONS.md missing/unreadable'}")
    print(f"  traces           : {status['traces']['count']} session(s) "
          f"in {status['traces']['dir']}")
    print(f"  shadow records   : {status['shadow_records']['count']} "
          f"in {status['shadow_records']['path']}")
    if status["identity"]:
        print("  identity registry:")
        for profile in status["identity"]:
            print(f"    {profile['agent_id']}: {profile['identity_version']} "
                  f"({profile['promotion_status']}) | "
                  f"sessions={profile['sessions_analyzed']} "
                  f"| promotions={profile['promotions_recorded']} "
                  f"| self-revisions={profile['self_revisions_recorded']} "
                  f"| principles={profile['soul_principles']} "
                  f"| next gate={profile['next_gate']}")
    else:
        print("  identity registry: empty (no apprentice has run yet)")
    lessons = status["proposals"]["lessons"]
    patches = status["proposals"]["patches"]
    print(f"  pending proposals: "
          f"lessons={lessons if lessons >= 0 else 'UNPARSEABLE'} "
          f"| prompt patches={patches}")
    revisions = status["self_revisions"]
    revision_parts = [
        f"{name}={count}" for name, count in revisions["by_status"].items()
    ]
    print(f"  self-revisions   : total={revisions['count']}"
          f" | {'; '.join(revision_parts) if revision_parts else 'none'}")
    transactions = status["revision_transactions"]
    transaction_parts = [
        f"{name}={count}" for name, count in transactions["by_state"].items()
    ]
    print(f"  transactions     : total={transactions['count']}"
          f" | {'; '.join(transaction_parts) if transaction_parts else 'none'}")
    for transaction in transactions["incomplete"]:
        print(f"    RECOVERY NEEDED: {transaction['agent_id']}/"
              f"{transaction['proposal_id']} ({transaction['state']})")
    gates = status["gates"]
    print(f"  gates            : "
          f"live={'ON' if gates['live_providers'] else 'off'} "
          f"| local apprentice={'ON' if gates['local_apprentice'] else 'off'} "
          f"| local model={gates['local_model'] or 'not set'}")
    if status["local_server"] is not None:
        server = status["local_server"]
        print(f"  local server     : "
              f"{'reachable' if server['reachable'] else 'NOT REACHABLE'} "
              f"- {server['detail']}")
    print("-" * _W)
    print("  Next:")
    print(f"    {status['next_command']}")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
