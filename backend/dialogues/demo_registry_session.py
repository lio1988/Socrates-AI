"""
Full registry-backed mock session demo (Phase 8C) — developer/dev entry point.

Runs CEDOrchestrator.run_registry_session end-to-end through the provider
registry using ONLY deterministic mock providers (no real API, no network, no
keys). Prints a developer report: provider statuses, phases executed, move
count, shadow-scoring coverage, leaderboard, task_log, the final 5-section
synthesis, and the CED-owned audit (clearly marked hidden-from-agents).

This is ADDITIVE. It does not touch run_session(), the existing demos, or the
browser demo.

Run:

    python -m backend.dialogues.demo_registry_session
"""

from __future__ import annotations

import asyncio
from typing import List, Tuple, Type

from .models import DialogPhase, ShadowScoringMode
from .providers import FakeProvider
from .agent import SocraticAgent
from .ced import CEDOrchestrator
from .provider_registry import (
    CouncilProviderRegistry, BaseProviderAdapter,
    ScriptedMockProvider, TimeoutScriptedProvider, RateLimitedProvider,
)

DEMO_QUESTION = "Is knowledge merely justified true belief?"
_WIDTH = 78

# (title, [adapter factories]) — mock providers only.
SCENARIOS = {
    "A": ("Quorum succeeds with a partial failure", lambda: [
        ScriptedMockProvider("mock_alpha"),
        ScriptedMockProvider("mock_beta"),
        TimeoutScriptedProvider(),
    ]),
    "B": ("Quorum fails (too few valid providers)", lambda: [
        ScriptedMockProvider("mock_alpha"),
        TimeoutScriptedProvider(),
        RateLimitedProvider(),
    ]),
}


def build_session(adapter_factories, session_id: str, mode=ShadowScoringMode.ALL_PHASES):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for adapter in adapter_factories():
        registry.register(adapter)
    ced = CEDOrchestrator(agents, provider, registry=registry, shadow_scoring_mode=mode)
    final = asyncio.run(ced.run_registry_session(DEMO_QUESTION, session_id=session_id))
    return ced, ced.get_session(session_id), final


def render_scenario(name: str) -> str:
    title, factories = SCENARIOS[name]
    ced, state, final = build_session(factories, session_id=f"reg_session_{name}")
    au = final.audit_summary
    lb = final.socratic_leaderboard

    out: List[str] = []
    out.append("─" * _WIDTH)
    out.append(f"  SCENARIO {name} — {title}")
    out.append("─" * _WIDTH)
    out.append(f"  session id        : {state.session_id}")
    out.append(f"  question          : {final.question}")
    out.append(f"  execution mode    : {au.get('execution_mode')}")
    out.append(f"  ratification      : {final.ratification_status}  (ratified={final.ratified})")
    cr = au.get("council_ratification")
    if cr:
        out.append("  council ratification (per-provider verdicts — not majority voting):")
        for v in cr.get("verdicts", []):
            out.append(f"      {v['provider_id']:20} {v['verdict']:20} [{v['provider_status']}]")
        out.append(f"      valid={cr['valid_verdicts']}/{cr['quorum']}(quorum)  "
                   f"caveats={cr['caveat_count']}  critical_blocks={cr['critical_block_count']}")
        for o in cr.get("attributed_critical_objections", []):
            out.append(f"      ⛔ BLOCK by {o['provider_id']} → {o['target_section']} "
                       f"(severity={o['severity']}); fix: {o['required_fix']}")
    out.append("")

    pss = au.get("provider_status_summary", {})
    out.append("  providers (CED-owned — HIDDEN FROM AGENTS):")
    out.append(f"      available   : {pss.get('available_providers')}")
    out.append(f"      unavailable : {pss.get('unavailable_providers')}")
    out.append(f"      failed      : {pss.get('failed_providers')}")
    out.append(f"      minimum={pss.get('minimum_providers')}  quorum={pss.get('quorum_for_assembly')}")
    out.append("")

    out.append("  phases executed (registry-driven):")
    for r in au.get("registry_phase_rounds", []):
        out.append(f"      {r['phase']:16} proceed={r['proceed']}  "
                   f"moves={r.get('validated_moves', '-')}  "
                   f"ok={r['ok_providers']}  failed={r['failed_providers']}")
    out.append("")

    out.append(f"  move count        : {au.get('total_moves', len(state.moves))}")
    sc = au.get("score_coverage", {})
    out.append(f"  scores expected   : {sc.get('scores_expected')}")
    out.append(f"  scores collected  : {sc.get('scores_collected')}")
    out.append(f"  shadow mode       : {au.get('shadow_scoring_mode')}")
    if lb:
        out.append(f"  leaderboard status: {lb.leaderboard_status.value}")
        out.append(f"  scores_by_phase   : {sorted(lb.scores_by_phase.keys())}")
        out.append(f"  top_contributors  : {lb.top_contributors}")
    out.append(f"  task_log count    : {au.get('task_log_count')}  (HIDDEN FROM AGENTS)")
    out.append("")

    out.append("  final synthesis (5-section assembled answer):")
    if final.synthesis:
        for sec in final.synthesis.sections:
            body = sec.content if not sec.unresolved else "(unresolved)"
            out.append(f"      ## {sec.section_name.value}")
            out.append(f"         {body[:150]}{'…' if len(body) > 150 else ''}")
    else:
        out.append("      (no synthesis — quorum failed / safe fallback)")
        if au.get("warning"):
            out.append(f"      ⚠ {au['warning']}")
    out.append("")
    return "\n".join(out)


def render_report() -> str:
    out: List[str] = []
    out.append("╔" + "═" * (_WIDTH - 2) + "╗")
    out.append("║" + "FULL REGISTRY-BACKED MOCK SESSION".center(_WIDTH - 2) + "║")
    out.append("║" + "NO REAL API CALLS".center(_WIDTH - 2) + "║")
    out.append("║" + "CED-OWNED AUDIT — HIDDEN FROM AGENTS".center(_WIDTH - 2) + "║")
    out.append("╚" + "═" * (_WIDTH - 2) + "╝")
    out.append("")
    for name in SCENARIOS:
        out.append(render_scenario(name))
    out.append("═" * _WIDTH)
    out.append("  Done. Mock providers only — no real API calls were made.")
    out.append("═" * _WIDTH)
    return "\n".join(out)


def main() -> int:
    print(render_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
