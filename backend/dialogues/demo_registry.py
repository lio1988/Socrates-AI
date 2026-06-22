"""
Registry-backed mock council demo (Phase 8B.2) — developer/dev entry point.

Exposes the Phase 8B provider-registry council path
(`CEDOrchestrator.gather_registry_phase_round`) outside unit tests, using ONLY
deterministic mock providers. It demonstrates deterministic role assignment,
one move per assigned agent/role, provider statuses, quorum/fallback behaviour,
and the CED-owned provider audit — all hidden from agents.

This is ADDITIVE. It does not touch `run_session()`, the existing Python demo
(`backend.dialogues.demo`), or the browser demo (`socrates_demo.html`).

NO REAL API CALLS. No `.env`. No API keys are read or printed.

Run:

    python -m backend.dialogues.demo_registry
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Tuple, Type

from .models import AgentRole, CouncilRoundResult, DialogPhase
from .providers import FakeProvider
from .agent import SocraticAgent
from .ced import CEDOrchestrator
from .provider_registry import (
    CouncilProviderRegistry, BaseProviderAdapter,
    AlwaysOKProvider, TimeoutProvider, InvalidJSONProvider,
    SchemaErrorProvider, RateLimitedProvider,
)

DEMO_QUESTION = "Is knowledge merely justified true belief?"
# SYNTHESIS assigns ALL agents the synthesizer role → a clean 1:1 agent↔provider
# mapping so every registered mock provider (incl. failing ones) is exercised.
DEMO_PHASE = DialogPhase.SYNTHESIS

# Each scenario: (title, [provider adapter classes]). Mock providers only.
SCENARIOS: Dict[str, Tuple[str, List[Type[BaseProviderAdapter]]]] = {
    "A": ("Quorum succeeds with partial failure",
          [AlwaysOKProvider, AlwaysOKProvider, TimeoutProvider, InvalidJSONProvider]),
    "B": ("Quorum fails",
          [AlwaysOKProvider, TimeoutProvider, InvalidJSONProvider, SchemaErrorProvider]),
    "C": ("Mixed failures, CED does not crash",
          [AlwaysOKProvider, RateLimitedProvider, SchemaErrorProvider, TimeoutProvider]),
}

_WIDTH = 78


# ── Scenario building (mock providers only) ──────────────────────────────────

def build_scenario(provider_classes: List[Type[BaseProviderAdapter]],
                   num_agents: int = 4,
                   session_id: str = "registry_demo"):
    """Build a CED + registry of mock providers + a session. No real APIs."""
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(num_agents)]
    registry = CouncilProviderRegistry()
    for cls in provider_classes:
        registry.register(cls())
    ced = CEDOrchestrator(agents, provider, registry=registry)
    state = ced.create_session(DEMO_QUESTION, session_id=session_id)
    return ced, state, registry


def run_scenario(name: str):
    """Run one scenario's phase round and return (ced, state, registry, result)."""
    _title, classes = SCENARIOS[name]
    ced, state, registry = build_scenario(classes, session_id=f"registry_demo_{name}")
    result: CouncilRoundResult = asyncio.run(
        ced.gather_registry_phase_round(state, DEMO_PHASE)
    )
    return ced, state, registry, result


# ── Report rendering (developer-visible; safe labels only) ───────────────────

def render_scenario(name: str) -> str:
    title, _classes = SCENARIOS[name]
    ced, state, registry, result = run_scenario(name)
    audit = ced.registry_round_audit(result)
    name_by_id = {a.provider_id: a.provider_name for a in registry.all_adapters()}
    plan = ced.assign_roles_for_phase(state, DEMO_PHASE)

    out: List[str] = []
    out.append("─" * _WIDTH)
    out.append(f"  SCENARIO {name} — {title}")
    out.append("─" * _WIDTH)
    out.append(f"  session id        : {state.session_id}")
    out.append(f"  phase             : {DEMO_PHASE.value}")
    out.append("  deterministic role plan (providers cannot influence this):")
    for agent_id, role in sorted(plan.items()):
        out.append(f"      {agent_id} -> {role.value}")
    out.append(f"  registered providers : "
               f"{', '.join(a.provider_id for a in registry.all_adapters())}")
    out.append("")
    out.append("  provider responses (one per assigned agent/role):")
    for r in result.responses:
        pname = name_by_id.get(r.provider_id, r.provider_id)
        has_move = "yes" if r.parsed_move is not None else "no"
        line = (f"      [{r.status.value:<12}] {r.provider_id:<18} "
                f"({pname})  agent={r.agent_id}  parsed_move={has_move}")
        out.append(line)
        if r.error_message:
            out.append(f"          error: {r.error_message}")
    out.append("")
    out.append(f"  quorum met / proceed : {result.proceed}")
    out.append(f"  valid moves          : {audit['validated_moves']}")
    out.append(f"  failed providers     : {len(result.failed_provider_ids)} "
               f"({', '.join(result.failed_provider_ids) or '—'})")
    if result.warning:
        out.append(f"  ⚠ warning            : {result.warning}")
    out.append("")
    out.append("  CED-OWNED PROVIDER AUDIT — HIDDEN FROM AGENTS")
    out.append(f"      proceed                : {audit['proceed']}")
    out.append(f"      ok_providers           : {audit['ok_providers']}")
    out.append(f"      failed_providers       : {audit['failed_providers']}")
    out.append(f"      provider_status_counts : {audit['provider_status_counts']}")
    if "provider_status_summary" in audit:
        s = audit["provider_status_summary"]
        out.append(f"      available_providers    : {s['available_providers']}")
        out.append(f"      unavailable_providers  : {s['unavailable_providers']}")
        out.append(f"      minimum_providers      : {s['minimum_providers']}")
        out.append(f"      quorum_for_assembly    : {s['quorum_for_assembly']}")
    out.append("")
    return "\n".join(out)


def render_report() -> str:
    """Full developer report for all scenarios (returned as a string)."""
    out: List[str] = []
    out.append("╔" + "═" * (_WIDTH - 2) + "╗")
    out.append("║" + "REGISTRY-BACKED MOCK COUNCIL DEMO".center(_WIDTH - 2) + "║")
    out.append("║" + "NO REAL API CALLS".center(_WIDTH - 2) + "║")
    out.append("║" + "CED-OWNED PROVIDER AUDIT — HIDDEN FROM AGENTS".center(_WIDTH - 2) + "║")
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
