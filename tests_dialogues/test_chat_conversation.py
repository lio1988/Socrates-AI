"""
Phase 8D — Chat Dialogue Continuity Layer (fully offline / mock).

Proves multi-turn chat continuity over a CED-governed registry-backed council:
turn indexing, public-brief continuity, hidden-internals never leak to agents/
users, each turn still runs the council, and existing entry points are intact.
NO live APIs, NO keys, NO .env.
"""

import json

import pytest

from backend.dialogues.models import AssembledAnswer, ShadowScoringMode
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.conversation import (
    ConversationManager, ConversationSession, ConversationTurn, ChatResponse,
    build_full_brief, save_conversation_json, load_conversation_json,
)

# True hidden-internal tokens that must NEVER appear in user-facing output.
# (Note: the aggregate *status* labels `ratification_status` / `leaderboard_status`
# ARE public per the chat-response shape — so bare "leaderboard"/"ratification" are
# NOT leaks; raw internals like provider ids, task_log, scorecards, raw scores are.)
HIDDEN_TOKENS = ("mock_alpha", "mock_beta", "task_log", "micro_score",
                 "scorecard", "average_scores", "cumulative", "coverage_ratio",
                 "scores_by_phase", "provider_status_summary", "scoring_backend",
                 "self_scoring_violations")

# Stricter set for the AGENT-FACING brief: agents must not even see leaderboard /
# audit machinery or provider ids referenced at all.
BRIEF_FORBIDDEN = HIDDEN_TOKENS + ("leaderboard", "audit", "provider_id", "execution_mode")

G1 = "Είναι η γνώση αποτέλεσμα ατομικής σκέψης ή συλλογικής διαλεκτικής διαδικασίας;"
G2 = "Συνέχισε από το προηγούμενο και εξήγησε το δυνατότερο επιχείρημα υπέρ της συλλογικής διαλεκτικής."
G3 = "Ποια είναι η ισχυρότερη ένσταση σε αυτό;"
G4 = "Άρα ποια είναι η πιο ισορροπημένη θέση;"


def _manager(provider_ids=("mock_alpha", "mock_beta")) -> ConversationManager:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for pid in provider_ids:
        registry.register(ScriptedMockProvider(pid))
    ced = CEDOrchestrator(agents, provider, registry=registry)
    return ConversationManager(ced)


def _no_hidden(text: str) -> bool:
    low = text.lower()
    return not any(tok in low for tok in HIDDEN_TOKENS)


# ── (1)(2)(3) ids + continuation + deterministic indexing ────────────────────

def test_start_chat_creates_conversation_id():
    m = _manager()
    r = m.start_chat(G1)
    assert r.conversation_id and isinstance(r.conversation_id, str)
    assert r.turn_index == 1
    assert r.conversation_id in m.list_conversations()


def test_continue_chat_same_conversation_id():
    m = _manager()
    r1 = m.start_chat(G1, conversation_id="cc")
    r2 = m.continue_chat("cc", G2)
    assert r1.conversation_id == r2.conversation_id == "cc"
    assert len(m.get_chat("cc").turns) == 2


def test_turn_index_increments_deterministically():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    idxs = [m.continue_chat("cc", q).turn_index for q in (G2, G3, G4)]
    assert idxs == [2, 3, 4]


def test_continue_unknown_conversation_raises():
    m = _manager()
    with pytest.raises(KeyError):
        m.continue_chat("nope", "hello")


# ── (4) each turn stores user_message + assistant_response ────────────────────

def test_each_turn_stores_user_and_assistant():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    m.continue_chat("cc", G2)
    turns = m.list_chat_turns("cc")
    assert turns[0].user_message == G1
    assert turns[1].user_message == G2
    for t in turns:
        assert t.assistant_response.strip()


# ── (5)(6)(7)(8) brief continuity ────────────────────────────────────────────

def test_followup_includes_public_brief():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    r2 = m.continue_chat("cc", G2)
    assert "Conversation so far:" in r2.public_conversation_brief
    assert "Instruction to agents:" in r2.public_conversation_brief


def test_second_turn_references_prior_context():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    r2 = m.continue_chat("cc", G2)
    brief = r2.public_conversation_brief
    assert G1 in brief                              # original question carried forward
    assert "Turn 1:" in brief                       # turn-by-turn flow
    assert "(none yet — this is the first turn)" not in brief  # prior answer now present


def test_third_turn_references_prior_objections_or_unresolved():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    m.continue_chat("cc", G2)
    r3 = m.continue_chat("cc", G3)
    brief = r3.public_conversation_brief
    obj_block = brief.split("5. Objections raised:")[1].split("6. Unresolved questions:")[0]
    unres_block = brief.split("6. Unresolved questions:")[1].split("7. Recent user direction:")[0]
    # by turn 3, at least one of objections/unresolved is populated (not "(none yet)")
    assert "(none yet)" not in obj_block or "(none yet)" not in unres_block


def test_brief_preserves_full_flow_not_only_last_turn():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    m.continue_chat("cc", G2)
    m.continue_chat("cc", G3)
    r4 = m.continue_chat("cc", G4)
    brief = r4.public_conversation_brief
    for marker in ("Turn 1:", "Turn 2:", "Turn 3:"):
        assert marker in brief                      # full flow, not just the last turn
    assert G4 in brief                              # current message present


# ── (9) brief never contains hidden internals ────────────────────────────────

def test_brief_has_no_hidden_internals():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    m.continue_chat("cc", G2)
    r3 = m.continue_chat("cc", G3)
    low = r3.public_conversation_brief.lower()
    assert not any(tok in low for tok in BRIEF_FORBIDDEN)   # strict agent-facing check
    # the build_conversation_brief helper output is equally clean
    low2 = m.build_conversation_brief("cc", G4).lower()
    assert not any(tok in low2 for tok in BRIEF_FORBIDDEN)


def test_user_facing_response_has_no_hidden_internals():
    m = _manager()
    r = m.start_chat(G1)
    blob = (r.assistant_response + r.public_summary + " ".join(r.caveats)
            + " ".join(r.unresolved_questions))
    assert _no_hidden(blob)
    assert r.debug is None                          # hidden trace not exposed in normal mode


# ── (10)(11)(12) each turn is CED-governed + records statuses ─────────────────

def test_each_turn_is_registry_backed():
    m = _manager()
    r1 = m.start_chat(G1, conversation_id="cc")
    r2 = m.continue_chat("cc", G2)
    assert r1.registry_backed is True and r2.registry_backed is True
    # the hidden trace confirms the registry execution mode (debug-only)
    sess = m.get_chat("cc")
    assert sess.hidden_traces[0].audit_summary.get("execution_mode") == "registry"


def test_turn_records_ratification_and_leaderboard_status():
    m = _manager()
    r = m.start_chat(G1)
    assert r.ratification_status == "ratified"
    assert r.leaderboard_status in ("complete", "partial", "failed", "unavailable", "disabled")
    t = m.list_chat_turns(r.conversation_id)[0]
    assert t.ratification_status == r.ratification_status
    assert t.leaderboard_status == r.leaderboard_status


# ── (13) quorum_failed / unresolved carried honestly into the next brief ─────

def test_quorum_failure_is_carried_into_next_brief():
    m = _manager(provider_ids=("only_one",))          # 1 < minimum 2 → quorum fails
    r1 = m.start_chat(G1, conversation_id="qf")
    assert r1.ratification_status == "quorum_failed"
    assert "quorum" in r1.assistant_response.lower()  # honest, readable
    r2 = m.continue_chat("qf", G2)
    assert "quorum" in r2.public_conversation_brief.lower()  # carried forward honestly
    assert _no_hidden(r2.public_conversation_brief)


# ── (14) readable, user-facing, not raw JSON ─────────────────────────────────

def test_response_is_readable_not_raw_json():
    m = _manager()
    r = m.start_chat(G1)
    assert "## Core Answer" in r.assistant_response   # readable markdown
    with pytest.raises((json.JSONDecodeError, ValueError)):
        json.loads(r.assistant_response)              # not raw JSON


def test_debug_mode_exposes_trace_only_when_requested():
    m = _manager()
    r = m.start_chat(G1, debug=True)
    assert r.debug is not None
    assert "audit_summary" in r.debug                 # internals available ONLY in debug


# ── (15)(16) no live APIs, no .env required ──────────────────────────────────

def test_chat_uses_only_mock_providers():
    m = _manager()
    for adapter in m.ced.registry.all_adapters():
        assert getattr(adapter, "is_fake", False) is True


def test_chat_does_not_require_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CED_ENABLE_LIVE_PROVIDERS", raising=False)
    m = _manager()
    r = m.start_chat(G1)
    assert r.assistant_response                        # runs with no env at all
    assert r.ratification_status == "ratified"         # full council ran, no network/key needed


# ── (17)(18) existing entry points unchanged ─────────────────────────────────

def test_run_session_backward_compatible():
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    ced = CEDOrchestrator(agents, p)                   # no registry needed
    final = ced.run_session("Is knowledge JTB?", session_id="rs")
    assert final.ratified is True
    assert "execution_mode" not in final.audit_summary  # legacy path


def test_run_registry_session_backward_compatible():
    import asyncio
    m = _manager()
    final = asyncio.run(m.ced.run_registry_session("Is knowledge JTB?", session_id="rrs"))
    assert isinstance(final.synthesis, AssembledAnswer)
    assert final.audit_summary["execution_mode"] == "registry"


def test_manager_requires_registry():
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    ced = CEDOrchestrator(agents, p)                   # no registry
    with pytest.raises(RuntimeError, match="registry"):
        ConversationManager(ced)


# ── (19) chat demo runs; (extras) persistence + public_view ──────────────────

def test_chat_demo_runs_clean():
    from backend.dialogues import demo_chat_conversation as d
    report = d.render_report()
    assert "PHASE 8D" in report
    assert "Turns: [1, 2, 3, 4]" in report
    assert _no_hidden(report)                          # demo never prints internals


def test_public_view_excludes_hidden_traces():
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    view = m.get_chat("cc").public_view()
    assert "hidden_traces" not in view
    assert view["turns"]                               # public turn data still present


def test_json_persistence_round_trip(tmp_path):
    m = _manager()
    m.start_chat(G1, conversation_id="cc")
    m.continue_chat("cc", G2)
    path = str(tmp_path / "conv.json")
    save_conversation_json(m.get_chat("cc"), path)
    loaded = load_conversation_json(path)
    assert isinstance(loaded, ConversationSession)
    assert loaded.conversation_id == "cc"
    assert loaded.turn_count == 2
    assert len(loaded.turns) == 2
