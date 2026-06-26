"""
Phase 8D — Chat Dialogue Continuity Layer.

Turns Socrates AI from a one-shot question→answer system into a normal ongoing
chat. The user experience is a plain conversation (User → Socrates AI → User …);
behind every assistant reply, the CED-governed multi-agent council runs a full
`run_registry_session` turn.

Continuity lives in a SANITIZED PUBLIC conversation brief — never in hidden CED
internals. For every follow-up the council receives the public dialogue flow so
far (original question, prior council answer, established claims, caveats,
objections, unresolved questions, the user's current direction) plus the current
message, and is told to continue rather than restart.

Permanent invariant (unchanged): **Agents judge epistemic quality. CED governs
the protocol.** This layer only maintains conversation state, builds sanitized
public briefs, and routes each turn through the existing registry-backed council.
It never decides truth, never fabricates answers/scores/verdicts, and never
exposes hidden internals (raw scores, leaderboard internals, provider mappings,
task_log, audit traces, scoring weights) to agents or — in normal mode — to the
user.

Additive only: `run_session` and `run_registry_session` are untouched. Storage is
in-memory by default; optional JSON persistence is provided separately.

No live API calls · no keys · no `.env`.
"""

from __future__ import annotations

import asyncio
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .models import AssembledAnswer, FinalResponse
from .ced import CEDOrchestrator


# ── helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_conversation_id() -> str:
    return f"conv_{uuid.uuid4().hex[:12]}"


def _clip(text: Optional[str], n: int) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _dedupe_cap(items: List[str], cap: int) -> List[str]:
    """Order-preserving de-duplication, keeping the most recent `cap` entries."""
    seen, out = set(), []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out[-cap:]


# ── public conversation models (CED-owned; hidden traces kept separate) ───────

class ConversationStatus(str):
    ACTIVE = "active"
    CLOSED = "closed"


class PublicEpistemicMemory(BaseModel):
    """The sanitized public memory of the dialogue — safe to show agents/users."""
    original_question:      str = ""
    turn_summaries:         List[str] = Field(default_factory=list)
    established_claims:     List[str] = Field(default_factory=list)
    challenged_claims:      List[str] = Field(default_factory=list)
    caveats:                List[str] = Field(default_factory=list)
    objections:             List[str] = Field(default_factory=list)
    unresolved_questions:   List[str] = Field(default_factory=list)
    current_direction:      str = ""
    last_assistant_summary: str = ""


class ConversationTurn(BaseModel):
    """One user→council exchange. CED-owned record (full info)."""
    conversation_id:         str
    turn_index:              int
    user_message:            str
    ced_question_or_prompt:  str
    public_conversation_brief: str
    assistant_response:      str
    final_synthesis:         Optional[AssembledAnswer] = None
    ratification_status:     str = ""
    leaderboard_status:      str = ""
    # CED-owned; never placed in the public brief or normal-mode response.
    provider_status_summary: Dict[str, Any] = Field(default_factory=dict)
    unresolved_questions:    List[str] = Field(default_factory=list)
    caveats:                 List[str] = Field(default_factory=list)
    created_at:              datetime = Field(default_factory=_now)


class HiddenCedTrace(BaseModel):
    """
    Debug-only CED internals for one turn. MUST NOT be sent to agents and MUST
    NOT appear in normal user-facing responses — only when debug is requested.
    """
    conversation_id:         str
    turn_index:              int
    audit_summary:           Dict[str, Any] = Field(default_factory=dict)
    task_log_summary:        Dict[str, Any] = Field(default_factory=dict)
    scoring_summary:         Dict[str, Any] = Field(default_factory=dict)
    provider_status_details: Dict[str, Any] = Field(default_factory=dict)


class ConversationSession(BaseModel):
    """Full CED-owned conversation state. Agents never receive this object."""
    conversation_id:        str
    created_at:             datetime = Field(default_factory=_now)
    updated_at:             datetime = Field(default_factory=_now)
    turn_count:             int = 0
    turns:                  List[ConversationTurn] = Field(default_factory=list)
    latest_public_summary:  str = ""
    public_epistemic_memory: PublicEpistemicMemory = Field(default_factory=PublicEpistemicMemory)
    key_claims:             List[str] = Field(default_factory=list)
    caveated_claims:        List[str] = Field(default_factory=list)
    objections:             List[str] = Field(default_factory=list)
    unresolved_questions:   List[str] = Field(default_factory=list)
    current_topic:          str = ""
    current_user_goal:      str = ""
    status:                 str = ConversationStatus.ACTIVE
    # CED-owned hidden traces — excluded from public_view(); debug/persistence only.
    hidden_traces:          List[HiddenCedTrace] = Field(default_factory=list)

    def public_view(self) -> Dict[str, Any]:
        """Serialization WITHOUT hidden traces (safe for external display)."""
        data = self.model_dump(mode="json")
        data.pop("hidden_traces", None)
        return data


class ChatResponse(BaseModel):
    """What a chat call returns. `assistant_response` is what the user reads."""
    conversation_id:          str
    turn_index:               int
    assistant_response:       str
    public_conversation_brief: str
    ratification_status:      str
    leaderboard_status:       str
    caveats:                  List[str] = Field(default_factory=list)
    unresolved_questions:     List[str] = Field(default_factory=list)
    public_summary:           str = ""
    registry_backed:          bool = True
    debug:                    Optional[Dict[str, Any]] = None   # only when debug=True


# ── brief construction ────────────────────────────────────────────────────────

CONTINUE_INSTRUCTION = (
    "Instruction to agents: Continue the same dialogue. Do not restart from zero. "
    "Use the prior public conversation context. Do not assume hidden CED internals. "
    "If the user challenges a previous point, address that challenge directly."
)


def _bullets(items: List[str], empty: str = "(none yet)") -> List[str]:
    return [f"   - {i}" for i in items] if items else [f"   - {empty}"]


def build_full_brief(session: ConversationSession, new_user_message: str) -> str:
    """
    The sanitized public conversation brief (the structure the spec prescribes).
    Preserves the FULL public dialogue flow so far — not only the last turn — and
    contains NO hidden internals (no scores/leaderboard/provider/task_log/audit).
    """
    mem = session.public_epistemic_memory
    first = session.turn_count == 0
    lines: List[str] = ["Conversation so far:", ""]
    lines += ["1. Original user question:",
              f"   {mem.original_question or new_user_message}", ""]
    lines += ["2. Prior council answer:",
              f"   {mem.last_assistant_summary or '(none yet — this is the first turn)'}", ""]
    lines += ["3. Key claims established:"] + _bullets(mem.established_claims[-6:]) + [""]
    lines += ["4. Caveats:"] + _bullets(mem.caveats[-6:]) + [""]
    lines += ["5. Objections raised:"] + _bullets(mem.objections[-6:]) + [""]
    lines += ["6. Unresolved questions:"] + _bullets(mem.unresolved_questions[-6:]) + [""]
    lines += ["7. Recent user direction:",
              f"   {mem.current_direction or '(first turn — no prior direction)'}", ""]
    lines += ["8. Turn-by-turn flow:"] + (
        [f"   - {s}" for s in mem.turn_summaries[-8:]] if mem.turn_summaries
        else ["   - (this is the first turn)"]) + [""]
    lines += ["9. Current user message:", f"   {new_user_message}", ""]
    if first:
        lines += ["(This is the opening turn — establish the dialogue.)", ""]
    lines += [CONTINUE_INSTRUCTION]
    return "\n".join(lines)


def _compact_context(mem: PublicEpistemicMemory) -> str:
    """A short public continuation context handed to the council prompt (compressed)."""
    if not mem.original_question:
        return ""
    parts = [f"Original question: {mem.original_question}."]
    if mem.last_assistant_summary:
        parts.append(f"Council's current position: {mem.last_assistant_summary}")
    if mem.unresolved_questions:
        parts.append("Open issues: " + "; ".join(mem.unresolved_questions[-2:]) + ".")
    if mem.caveats:
        parts.append("Caveats so far: " + "; ".join(mem.caveats[-2:]) + ".")
    return " ".join(parts)


def _build_ced_prompt(user_message: str, compact_context: str) -> str:
    """The prompt handed to the council. Public only — no hidden internals."""
    if not compact_context:
        return user_message
    return (
        "You are continuing an ongoing Socratic dialogue.\n\n"
        f"Prior public context: {compact_context}\n\n"
        f"Current user message: {user_message}\n\n"
        "Task: Continue the dialogue from this point. Do not restart from zero. "
        "Address the user's current message while preserving the public epistemic "
        "state so far."
    )


# ── extraction from a FinalResponse (public signals only) ─────────────────────

def _extract_public(final: FinalResponse) -> Dict[str, Any]:
    """Pull PUBLIC signals out of a council result. Strips provider/agent identities."""
    sections: Dict[str, Optional[str]] = {}
    unresolved: List[str] = []
    if final.synthesis:
        for s in final.synthesis.sections:
            sections[s.section_name.value] = s.content if not s.unresolved else None
            if s.unresolved:
                unresolved.append(
                    f"The '{s.section_name.value.replace('_', ' ')}' could not be resolved this turn.")
    cr = (final.audit_summary or {}).get("council_ratification", {}) or {}
    # caveat text ONLY — provider_id / agent_id are deliberately dropped.
    caveats = [c["caveat"] for c in cr.get("caveats", [])
               if isinstance(c, dict) and c.get("caveat")]
    objections: List[str] = []
    for o in cr.get("attributed_critical_objections", []):
        if not isinstance(o, dict):
            continue
        txt = o.get("rationale") or o.get("required_fix") or "a blocking objection was raised"
        tgt = o.get("target_section")
        objections.append(txt + (f" (target: {tgt.replace('_', ' ')})" if tgt else ""))
    return {
        "sections": sections,
        "caveats": caveats,
        "objections": objections,
        "unresolved": unresolved,
        "quorum_failed": bool((final.audit_summary or {}).get("quorum_failed")),
    }


def _leaderboard_status(final: FinalResponse) -> str:
    if final.socratic_leaderboard is not None:
        return final.socratic_leaderboard.leaderboard_status.value
    au = final.audit_summary or {}
    return au.get("leaderboard_status") or au.get("scoring", {}).get("leaderboard_status") or "unavailable"


def _render_assistant_response(final: FinalResponse, pub: Dict[str, Any]) -> str:
    """The user-facing answer — readable markdown, never raw JSON, always honest."""
    if final.answer:                                   # ratified / ratified_with_caveats
        text = final.answer
        if pub["caveats"]:
            text += "\n\n_Caveats:_\n" + "\n".join(f"- {c}" for c in pub["caveats"])
        return text
    if pub["quorum_failed"]:
        return ("I could not finalize an answer this turn: the council did not reach quorum "
                "(too few providers responded successfully). This point stays open — ask me to "
                "retry or rephrase; it is kept in the conversation as unresolved.")
    if final.ratification_status == "repair_required":
        objs = "; ".join(pub["objections"]) or "an unresolved blocking objection"
        return ("The council raised a blocking objection, so I'm withholding a final answer pending "
                f"repair. Objection: {objs}.")
    return ("The council could not ratify an answer this turn; the point remains unresolved and is "
            "kept in the conversation for follow-up.")


def _public_summary(final: FinalResponse, pub: Dict[str, Any]) -> str:
    if final.answer:
        return _clip(pub["sections"].get("core_answer") or "", 220) or \
            "The council ratified a position this turn."
    if pub["quorum_failed"]:
        return "The council did not reach quorum this turn; the question remains open."
    if final.ratification_status == "repair_required":
        return "The council raised a blocking objection; the answer is withheld pending repair."
    return "The council could not ratify an answer this turn; the point remains unresolved."


# ── the conversation manager (chat entry points) ──────────────────────────────

class ConversationManager:
    """
    Chat layer above the registry-backed council. `start_chat` opens a
    conversation; `continue_chat` carries the public dialogue forward by
    conversation_id. Every turn runs a full CED-governed council turn.
    """

    def __init__(self, orchestrator: CEDOrchestrator,
                 store: Optional[Dict[str, ConversationSession]] = None) -> None:
        if getattr(orchestrator, "registry", None) is None:
            raise RuntimeError(
                "ConversationManager requires a CEDOrchestrator with a CouncilProviderRegistry "
                "(chat turns run through the registry-backed council).")
        self.ced = orchestrator
        self._store: Dict[str, ConversationSession] = store if store is not None else {}

    # -- entry points --
    def start_chat(self, initial_message: str, *,
                   conversation_id: Optional[str] = None, debug: bool = False) -> ChatResponse:
        cid = conversation_id or _new_conversation_id()
        if cid in self._store:
            raise ValueError(f"conversation_id already exists: {cid}")
        session = ConversationSession(conversation_id=cid)
        self._store[cid] = session
        return self._run_turn(session, initial_message, debug=debug)

    def continue_chat(self, conversation_id: str, user_message: str, *,
                      debug: bool = False) -> ChatResponse:
        session = self._require(conversation_id)
        return self._run_turn(session, user_message, debug=debug)

    def get_chat(self, conversation_id: str) -> ConversationSession:
        return self._require(conversation_id)

    def list_chat_turns(self, conversation_id: str) -> List[ConversationTurn]:
        return list(self._require(conversation_id).turns)

    def build_conversation_brief(self, conversation_id: str, new_user_message: str) -> str:
        return build_full_brief(self._require(conversation_id), new_user_message)

    def list_conversations(self) -> List[str]:
        return list(self._store.keys())

    # -- internals --
    def _require(self, conversation_id: str) -> ConversationSession:
        if conversation_id not in self._store:
            raise KeyError(f"unknown conversation_id: {conversation_id}")
        return self._store[conversation_id]

    def _run_turn(self, session: ConversationSession, user_message: str,
                  *, debug: bool) -> ChatResponse:
        turn_index = session.turn_count + 1
        full_brief = build_full_brief(session, user_message)
        ced_prompt = _build_ced_prompt(user_message, _compact_context(session.public_epistemic_memory))

        # One full CED-governed council turn (registry-backed), fresh session id.
        turn_sid = f"{session.conversation_id}__t{turn_index}"
        final = asyncio.run(self.ced.run_registry_session(ced_prompt, session_id=turn_sid))

        pub = _extract_public(final)
        assistant = _render_assistant_response(final, pub)
        summary = _public_summary(final, pub)
        rat_status = final.ratification_status or "unresolved"
        lb_status = _leaderboard_status(final)
        au = final.audit_summary or {}

        # Record the turn (CED-owned).
        session.turn_count = turn_index
        session.turns.append(ConversationTurn(
            conversation_id=session.conversation_id, turn_index=turn_index,
            user_message=user_message, ced_question_or_prompt=ced_prompt,
            public_conversation_brief=full_brief, assistant_response=assistant,
            final_synthesis=final.synthesis, ratification_status=rat_status,
            leaderboard_status=lb_status,
            provider_status_summary=au.get("provider_status_summary", {}),
            unresolved_questions=pub["unresolved"], caveats=pub["caveats"],
        ))

        # Hidden trace (CED-owned; never to agents, never in normal response).
        session.hidden_traces.append(HiddenCedTrace(
            conversation_id=session.conversation_id, turn_index=turn_index,
            audit_summary=au,
            task_log_summary={"task_log_count": au.get("task_log_count")},
            scoring_summary=au.get("scoring", {}),
            provider_status_details=au.get("provider_status_summary", {}),
        ))

        self._update_memory(session, user_message, final, pub, summary)
        session.latest_public_summary = summary
        session.updated_at = _now()

        return ChatResponse(
            conversation_id=session.conversation_id, turn_index=turn_index,
            assistant_response=assistant, public_conversation_brief=full_brief,
            ratification_status=rat_status, leaderboard_status=lb_status,
            caveats=pub["caveats"],
            unresolved_questions=session.public_epistemic_memory.unresolved_questions[-8:],
            public_summary=summary, registry_backed=True,
            debug=(session.hidden_traces[-1].model_dump(mode="json") if debug else None),
        )

    def _update_memory(self, session: ConversationSession, user_message: str,
                       final: FinalResponse, pub: Dict[str, Any], summary: str) -> None:
        mem = session.public_epistemic_memory
        if not mem.original_question:
            mem.original_question = user_message
            session.current_topic = _clip(user_message, 120)
        mem.current_direction = user_message
        session.current_user_goal = _clip(user_message, 200)
        mem.last_assistant_summary = summary
        mem.turn_summaries.append(
            f"Turn {session.turn_count}: user said \"{_clip(user_message, 80)}\" "
            f"→ council {final.ratification_status or 'unresolved'}.")

        if (core := pub["sections"].get("core_answer")):
            mem.established_claims.append(_clip(core, 200))
        if (verdict := pub["sections"].get("final_verdict")):
            mem.established_claims.append(_clip(verdict, 200))
        for c in pub["caveats"]:
            mem.caveats.append(_clip(c, 200))
        if (nuance := pub["sections"].get("nuance")):
            mem.caveats.append(_clip(nuance, 200))
        if (stress := pub["sections"].get("crucial_stress_test")):
            mem.objections.append(_clip(stress, 200))
        for o in pub["objections"]:
            mem.objections.append(_clip(o, 200))
        if (blind := pub["sections"].get("blind_spots")):
            mem.unresolved_questions.append(_clip(blind, 200))
        for u in pub["unresolved"]:
            mem.unresolved_questions.append(_clip(u, 200))
        if pub["quorum_failed"]:
            mem.unresolved_questions.append(
                "A previous turn could not reach council quorum; this point remains open.")

        mem.established_claims = _dedupe_cap(mem.established_claims, 10)
        mem.caveats = _dedupe_cap(mem.caveats, 10)
        mem.objections = _dedupe_cap(mem.objections, 10)
        mem.unresolved_questions = _dedupe_cap(mem.unresolved_questions, 10)

        # Mirror onto the session aggregate fields.
        session.key_claims = list(mem.established_claims)
        session.caveated_claims = list(mem.caveats)
        session.objections = list(mem.objections)
        session.unresolved_questions = list(mem.unresolved_questions)


# ── optional JSON persistence (clearly separated; off by default, no DB) ──────

def save_conversation_json(session: ConversationSession, path: str) -> None:
    """Persist the FULL CED-owned record (incl. hidden traces) to a local JSON file."""
    pathlib.Path(path).write_text(session.model_dump_json(indent=2), encoding="utf-8")


def load_conversation_json(path: str) -> ConversationSession:
    return ConversationSession.model_validate_json(
        pathlib.Path(path).read_text(encoding="utf-8"))
