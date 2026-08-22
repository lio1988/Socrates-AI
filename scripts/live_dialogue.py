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

Optional feature switches (env-only, cost-conscious defaults):
    CED_OPENCLAW_LESSONS=0   # OFF switch — stable OpenClaw lessons load by
                             # default (local file, free; adds a little prompt
                             # context to deliberation calls)
    CED_TRACE_CAPTURE=0      # OFF switch — auditable JSONL trace per run is
                             # written by default (local file, free)
    CED_TRACE_DIR=path       # where traces go (default runs/openclaw_traces)
    CED_TREE_EXPANSIONS=2    # deliberation tree search: N revision expansions
                             # (default 0 = off; EACH one adds real model calls
                             # on a live run — enable deliberately)

No key is ever printed; .env is never modified.
"""

from __future__ import annotations

import asyncio
import os
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


def _resolve_features(env=None):
    """
    Env-configured optional features for build_council (cost-conscious):
    free local features (lessons, trace) default ON with an explicit OFF
    switch; anything that adds real model calls (tree search) defaults OFF.
    Failure-isolated: a broken/missing lessons file never blocks the dialogue.
    Returns (build_council_kwargs, human_notes).
    """
    env = os.environ if env is None else env
    features, notes = {}, []

    if env.get("CED_OPENCLAW_LESSONS", "1") != "0":
        try:
            from backend.dialogues.openclaw_memory import load_stable_lessons
            pool = load_stable_lessons()
        except Exception:
            pool = []
        if pool:
            features["openclaw_lessons"] = pool
            notes.append(f"lessons: {len(pool)} stable")
        else:
            notes.append("lessons: unavailable (skipped)")
    else:
        notes.append("lessons: off")

    if env.get("CED_TRACE_CAPTURE", "1") != "0":
        from backend.dialogues.openclaw_memory import TraceCapturer
        trace_dir = env.get("CED_TRACE_DIR",
                            str(_ROOT / "runs" / "openclaw_traces"))
        features["trace_capturer"] = TraceCapturer(output_dir=trace_dir)
        notes.append(f"trace: {trace_dir}")
    else:
        notes.append("trace: off")

    try:
        expansions = int(env.get("CED_TREE_EXPANSIONS", "0"))
    except ValueError:
        expansions = 0
    if expansions > 0:
        features["tree_expansions"] = expansions
        notes.append(f"tree: {expansions} expansions (adds real calls when live)")
    else:
        notes.append("tree: off")

    return features, notes


def main(argv=None) -> int:
    argv = sys.argv if argv is None else argv
    question = argv[1] if len(argv) > 1 else DEFAULT_QUESTION

    # Cheap: 2 seats (minimum quorum), NO shadow scoring -> fewer live calls.
    # Optional layers (lessons / trace / tree search) come from env switches.
    features, feature_notes = _resolve_features()
    ced, mode = build_council(council_size=4,
                              shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
                              **features)

    seats = len(ced.registry.all_adapters()) if ced.registry else 0
    scoring = ced.shadow_scoring_mode.value

    print("=" * _W)
    # "mixed" is a live mode too. Testing only for "live" announced a free
    # offline run while the council was making paid calls.
    if mode in ("live", "mixed"):
        print(f"  SOCRATES AI — LIVE SOCRATIC DIALOGUE ({mode}, real model calls)")
        print("  *** Real API calls — this costs real money. ***")
    else:
        print("  SOCRATES AI — MOCK SOCRATIC DIALOGUE (offline, free, deterministic)")
        print("  (set CED_ENABLE_LIVE_PROVIDERS=1 + a real key for a live run)")
    print("=" * _W)
    print(f"  question : {question}")
    # Derived, not typed: the shipped line read "2 agents | scoring: off"
    # throughout a four-seat scored run.
    print(f"  council  : {seats} seats | scoring: {scoring} | mode: {mode}")
    print(f"  features : {' | '.join(feature_notes)}")
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

    # The two layers, side by side and named. Quality, ratification and
    # agreement live on the left; nothing on the left can move the right.
    gr = (final.audit_summary or {}).get("governing_release") or {}
    print("  EPISTEMIC LAYERS (quality is not support):")
    print(f"    legacy status      : {final.epistemic_status.value}"
          f"   [compatibility, non-governing]")
    if not gr.get("available", False):
        print(f"    governing status   : unavailable ({gr.get('reason', 'not computed')})")
    else:
        print(f"    governing status   : {final.governing_epistemic_status}")
        print(f"    release decision   : {final.release_decision}")
        print(f"    basis records      : {gr.get('basis_record_ids') or '[] (nothing supports it)'}")
        print(f"    objection verdicts : {gr.get('objection_verdicts') or {}}")
        print(f"    unresolved records : {len(gr.get('unresolved_record_ids') or [])}")
        if gr.get("blocked_reason"):
            print(f"    blocked because    : {gr['blocked_reason']}")
    print("-" * _W)
    print("  FINAL ANSWER (assembled by the council):")
    if final.synthesis:
        for s in final.synthesis.sections:
            print(f"    ## {s.section_name.value.replace('_', ' ').title()}")
            print(f"       {_clip(s.content, _W * 2)}")
    else:
        print("    (no answer — council did not reach quorum; safe fallback)")
    # Operator view of the optional layers (CED-owned audit — agents never see it).
    audit = final.audit_summary or {}
    oc = audit.get("openclaw_lessons")
    if oc:
        print(f"  openclaw lessons : selected {oc.get('selected_count', 0)} "
              f"of {oc.get('pool_size', 0)} -> {oc.get('selected', [])}")
    tree = audit.get("deliberation_tree") or {}
    if tree.get("enabled"):
        print(f"  tree search      : {tree.get('revision_count', 0)} revisions | "
              f"amplification_gain={tree.get('amplification_gain')} | "
              f"best={tree.get('best_draft_id')}")
    capturer = features.get("trace_capturer")
    if capturer is not None and capturer.session_count:
        print(f"  trace            : {capturer.session_count} trace(s) -> "
              f"{capturer.output_dir}")
    print("=" * _W)
    print(f"  Done. mode = {mode}. No key printed; .env untouched.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
