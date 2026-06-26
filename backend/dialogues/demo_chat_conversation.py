"""
Phase 8D — Chat Dialogue Continuity demo (fully offline / mock).

Shows Socrates AI as a normal multi-turn chat where every assistant reply is
produced by the CED-governed registry-backed council. The user continues by
conversation_id; each turn builds on the sanitized PUBLIC dialogue flow so far.
Hidden CED internals (scores, leaderboard internals, provider mappings,
task_log, audit) are NEVER shown to the user in normal mode.

Mock providers only — NO real API calls, NO keys, NO .env.

Run:

    python -m backend.dialogues.demo_chat_conversation
"""

from __future__ import annotations

from typing import List

from .providers import FakeProvider
from .agent import SocraticAgent
from .ced import CEDOrchestrator
from .provider_registry import CouncilProviderRegistry, ScriptedMockProvider
from .conversation import ChatResponse, ConversationManager

_WIDTH = 78

CONVERSATION = [
    "Είναι η γνώση αποτέλεσμα ατομικής σκέψης ή συλλογικής διαλεκτικής διαδικασίας;",
    "Συνέχισε από το προηγούμενο και εξήγησε το δυνατότερο επιχείρημα υπέρ της συλλογικής διαλεκτικής.",
    "Ποια είναι η ισχυρότερη ένσταση σε αυτό;",
    "Άρα ποια είναι η πιο ισορροπημένη θέση;",
]

# Tokens that must NEVER appear in user-facing chat output (hidden internals).
_FORBIDDEN = ("mock_alpha", "mock_beta", "leaderboard", "task_log", "scoring",
              "audit", "micro_score", "provider_status", "scorecard", "weights")


def _clip(text: str, n: int) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def build_manager() -> ConversationManager:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    registry.register(ScriptedMockProvider("mock_alpha"))
    registry.register(ScriptedMockProvider("mock_beta"))
    ced = CEDOrchestrator(agents, provider, registry=registry)
    return ConversationManager(ced)


def _no_hidden_leak(resp: ChatResponse) -> bool:
    blob = (resp.public_conversation_brief + "\n" + resp.assistant_response + "\n"
            + resp.public_summary + "\n" + " ".join(resp.caveats)
            + "\n" + " ".join(resp.unresolved_questions)).lower()
    return not any(tok in blob for tok in _FORBIDDEN)


def render_turn(resp: ChatResponse, user_message: str) -> str:
    out: List[str] = []
    out.append("─" * _WIDTH)
    out.append(f"  TURN {resp.turn_index}")
    out.append("─" * _WIDTH)
    out.append(f"  conversation_id     : {resp.conversation_id}")
    out.append(f"  user                : {user_message}")
    out.append("")
    out.append("  Socrates AI (assistant_response):")
    for line in resp.assistant_response.splitlines():
        out.append(f"    {_clip(line, _WIDTH - 6)}")
    out.append("")
    out.append(f"  ratification_status : {resp.ratification_status}")
    out.append(f"  leaderboard_status  : {resp.leaderboard_status}")
    out.append(f"  registry-backed CED : {resp.registry_backed}")
    out.append(f"  caveats             : {resp.caveats or '(none)'}")
    out.append(f"  unresolved          : {[_clip(u, 70) for u in resp.unresolved_questions] or '(none)'}")
    out.append("")
    out.append("  public_conversation_brief used this turn (sanitized, no internals):")
    for line in resp.public_conversation_brief.splitlines():
        out.append(f"    {_clip(line, _WIDTH - 6)}")
    out.append("")
    leak_ok = _no_hidden_leak(resp)
    out.append(f"  hidden internals exposed? : {'NO ✓' if leak_ok else 'YES ✗ (LEAK!)'}")
    out.append(f"  debug field (normal mode) : {'hidden (None)' if resp.debug is None else 'PRESENT'}")
    out.append("")
    return "\n".join(out)


def render_report() -> str:
    out: List[str] = []
    out.append("╔" + "═" * (_WIDTH - 2) + "╗")
    out.append("║" + "PHASE 8D — CHAT DIALOGUE CONTINUITY (CED-GOVERNED COUNCIL)".center(_WIDTH - 2) + "║")
    out.append("║" + "NORMAL CHAT EXPERIENCE — MULTI-AGENT COUNCIL BEHIND EACH REPLY".center(_WIDTH - 2) + "║")
    out.append("║" + "MOCK / OFFLINE ONLY — NO REAL API CALLS".center(_WIDTH - 2) + "║")
    out.append("╚" + "═" * (_WIDTH - 2) + "╝")
    out.append("")

    manager = build_manager()
    cid = "demo_chat"
    responses: List[ChatResponse] = []
    for i, message in enumerate(CONVERSATION):
        if i == 0:
            resp = manager.start_chat(message, conversation_id=cid)
        else:
            resp = manager.continue_chat(cid, message)
        responses.append(resp)
        out.append(render_turn(resp, message))

    all_clean = all(_no_hidden_leak(r) for r in responses)
    all_registry = all(r.registry_backed for r in responses)
    indices = [r.turn_index for r in responses]
    out.append("═" * _WIDTH)
    out.append(f"  Turns: {indices}  (deterministic increment)")
    out.append(f"  Every turn registry-backed CED : {all_registry}")
    out.append(f"  Hidden internals never exposed : {all_clean}")
    out.append("  Done. Mock providers only — no real API calls were made.")
    out.append("═" * _WIDTH)
    return "\n".join(out)


def main() -> int:
    print(render_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
