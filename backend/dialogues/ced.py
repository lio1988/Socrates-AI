"""
CEDOrchestrator (V1)

The Council of Epistemic Deliberators orchestrates the full Socratic pipeline.
It owns every byte of session state; agents are stateless tools that receive a
task and return a structured move.

Pipeline:
  OPENING → INITIAL_RESPONSE → ELENCHUS → REFLECTION
          → RECONSTRUCTION → SYNTHESIS
          → [shadow scoring] → [blind assembly]
          → RATIFICATION → COMPLETE
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import (
    AgentMove,
    AgentRole,
    AgentState,
    AgentTask,
    AssembledAnswer,
    AssembledSection,
    DialogPhase,
    DraftScorecard,
    EpistemicStatus,
    FinalResponse,
    MAX_RATIFICATION_ROUNDS,
    MicroScore,
    ObjectionSeverity,
    PenaltyFlag,
    ProviderStatus,
    RatificationDecision,
    RatificationVote,
    ScoreBreakdown,
    SECTION_ORDER,
    SectionDraft,
    SectionName,
    SectionScore,
    SessionState,
)
from .providers import LLMProvider
from .agent import SocraticAgent
from .role_assignment import assign_primary_roles, stable_hash


# ── Deterministic per-phase role scheduling tables ────────────────────────────
#
# CED owns role assignment. Agents never choose their own role and providers
# never influence it. Each phase draws its agents from a deterministic rotation
# of the (sorted) agent IDs, seeded by session_id and shifted by phase + round.

# Stable phase ordering used as the rotation's phase offset.
_PHASE_INDEX: Dict[DialogPhase, int] = {
    DialogPhase.OPENING:          0,
    DialogPhase.INITIAL_RESPONSE: 1,
    DialogPhase.ELENCHUS:         2,
    DialogPhase.REFLECTION:       3,
    DialogPhase.RECONSTRUCTION:   4,
    DialogPhase.SYNTHESIS:        5,
    DialogPhase.RATIFICATION:     6,
}

# Ordered role slots filled by rotation, per phase. Each slot is handed to a
# distinct rotated agent (collisions only occur when agents < slots).
_PHASE_ROLE_SLOTS: Dict[DialogPhase, List[AgentRole]] = {
    DialogPhase.OPENING:          [AgentRole.SOCRATES],
    DialogPhase.INITIAL_RESPONSE: [AgentRole.ELENCHUS_CRITIC,
                                   AgentRole.EMPIRICIST,
                                   AgentRole.SYNTHESIZER],
    DialogPhase.ELENCHUS:         [AgentRole.ELENCHUS_CRITIC,
                                   AgentRole.EMPIRICIST],
    DialogPhase.RECONSTRUCTION:   [AgentRole.MAIEUTIC_RECONSTRUCTOR],
    DialogPhase.RATIFICATION:     [AgentRole.FINAL_EVALUATOR],
}

# Phases where every agent takes the same role (no rotation slots).
_PHASE_ALL_AGENTS_ROLE: Dict[DialogPhase, AgentRole] = {
    DialogPhase.SYNTHESIS: AgentRole.SYNTHESIZER,
}

# Phases shown in the demo's role-rotation plan (in display order).
_PLAN_PHASES: List[DialogPhase] = [
    DialogPhase.OPENING,
    DialogPhase.INITIAL_RESPONSE,
    DialogPhase.ELENCHUS,
    DialogPhase.RECONSTRUCTION,
    DialogPhase.SYNTHESIS,
    DialogPhase.RATIFICATION,
]


class CEDOrchestrator:
    """
    Central orchestrator.  All session state is stored here; agents never hold
    a reference to any session object, scorecard, or history.

    Shadow scores are computed and stored internally and are never included in
    any AgentTask.context.
    """

    def __init__(
        self,
        agents: List[SocraticAgent],
        provider: LLMProvider,
    ) -> None:
        if len(agents) < 2:
            raise ValueError("Council requires at least 2 agents.")
        self.agents = agents
        self.provider = provider
        self._sessions: Dict[str, SessionState] = {}

    # ── Session management ────────────────────────────────────────────────────

    def create_session(
        self,
        question: str,
        session_id: Optional[str] = None,
    ) -> SessionState:
        """Create a new session, assign primary roles, register it in the store."""
        state = SessionState(question=question)
        if session_id:
            state.session_id = session_id

        agent_ids = [a.agent_id for a in self.agents]
        primary_roles = assign_primary_roles(agent_ids, state.session_id)

        state.agent_states = {
            aid: AgentState(
                agent_id=aid,
                primary_role=role,
                assigned_role=role,
            )
            for aid, role in primary_roles.items()
        }
        self._sessions[state.session_id] = state
        return state

    def get_session(self, session_id: str) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise KeyError(f"Session '{session_id}' not found.")

    # keep _get_session as an alias for backward compatibility with tests
    _get_session = get_session

    # ── Deterministic role assignment ─────────────────────────────────────────

    def get_role_assignment(self, session_id: str) -> Dict[str, AgentRole]:
        """
        Return the *primary* role label for each agent (debug/demo only).

        This is a stable per-session display label — actual phase execution uses
        assign_roles_for_phase(), which reassigns roles per phase.
        """
        state = self.get_session(session_id)
        return {aid: s.primary_role for aid, s in state.agent_states.items()}

    def _ordered_agent_ids(self) -> List[str]:
        """Canonical agent ordering for rotation — sorted, insertion-independent."""
        return sorted(a.agent_id for a in self.agents)

    def assign_roles_for_phase(
        self,
        session_state: SessionState,
        phase: DialogPhase,
        round_index: int = 0,
    ) -> Dict[str, AgentRole]:
        """
        Deterministically assign roles for a single phase.

        Pure function of (session_id, phase, round_index, ordered agent IDs):
        no agent input, no provider call, no mutation of session_state. The same
        arguments always yield the same mapping; different session_ids or rounds
        yield deterministically different mappings.

        Rotation (V1, simple and testable):

            offset         = stable_hash(session_id) % n
            rotated        = agent_ids[offset:] + agent_ids[:offset]
            phase_offset   = phase_index + round_index
            agent_for_role = rotated[(role_index + phase_offset) % n]

        Returns: {agent_id: AgentRole} for the agents active in this phase.
        For "all agents" phases (e.g. SYNTHESIS) every agent maps to the role.
        """
        agent_ids = self._ordered_agent_ids()
        n = len(agent_ids)

        # Phases where every agent takes the same role.
        all_agents_role = _PHASE_ALL_AGENTS_ROLE.get(phase)
        if all_agents_role is not None:
            return {aid: all_agents_role for aid in agent_ids}

        offset = stable_hash(session_state.session_id) % n
        rotated = agent_ids[offset:] + agent_ids[:offset]
        phase_offset = _PHASE_INDEX.get(phase, 0) + round_index

        assignment: Dict[str, AgentRole] = {}
        for role_index, role in enumerate(_PHASE_ROLE_SLOTS.get(phase, [])):
            agent_id = rotated[(role_index + phase_offset) % n]
            assignment[agent_id] = role
        return assignment

    def _apply_phase_roles(
        self,
        state: SessionState,
        phase: DialogPhase,
        assignment: Dict[str, AgentRole],
        round_index: int = 0,
    ) -> None:
        """
        Record an assignment into role_history and mirror it onto AgentState
        (assigned_role) so the current phase role is observable for debugging.
        """
        state.record_role_assignment(phase, round_index, assignment)
        for agent_id, role in assignment.items():
            if agent_id in state.agent_states:
                state.agent_states[agent_id].assigned_role = role

    def get_phase_role_plan(
        self, session_id: str
    ) -> List[Tuple[DialogPhase, Dict[str, AgentRole]]]:
        """
        Return the deterministic role plan per phase (for demo/debug display).
        Does not run the pipeline or mutate state.
        """
        state = self.get_session(session_id)
        return [
            (phase, self.assign_roles_for_phase(state, phase))
            for phase in _PLAN_PHASES
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _agent_by_id(self, agent_id: str) -> SocraticAgent:
        try:
            return next(a for a in self.agents if a.agent_id == agent_id)
        except StopIteration:
            raise ValueError(f"Agent '{agent_id}' not registered with this orchestrator.")

    def _dispatch(self, state: SessionState, agent: SocraticAgent,
                  role: AgentRole, phase: DialogPhase,
                  context: dict, extra_schema: dict) -> AgentMove:
        """Build an AgentTask, dispatch to the agent, record the move."""
        schema = {"_role": role.value, **extra_schema}
        task = AgentTask(
            session_id=state.session_id,
            agent_id=agent.agent_id,
            role=role,
            phase=phase,
            question=state.question,
            context=context,
            output_schema=schema,
            round_number=state.round_number,
        )
        move = agent.execute(task)
        state.moves.append(move)
        return move

    # ── Phase methods ─────────────────────────────────────────────────────────

    def run_opening_phase(self, session_id: str, round_index: int = 0) -> AgentMove:
        """SOCRATES (deterministically assigned for this phase/round) asks one question."""
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.OPENING)

        assignment = self.assign_roles_for_phase(state, DialogPhase.OPENING, round_index)
        self._apply_phase_roles(state, DialogPhase.OPENING, assignment, round_index)

        socrates_id = next(
            (aid for aid, r in assignment.items() if r == AgentRole.SOCRATES), None
        )
        if socrates_id is None:
            raise RuntimeError(f"No SOCRATES assigned for session '{session_id}'.")

        agent = self._agent_by_id(socrates_id)
        return self._dispatch(
            state, agent,
            role=AgentRole.SOCRATES,
            phase=DialogPhase.OPENING,
            context={},
            extra_schema={},
        )

    def run_initial_response_phase(self, session_id: str) -> List[AgentMove]:
        """ELENCHUS_CRITIC, EMPIRICIST, and SYNTHESIZER give initial responses."""
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.INITIAL_RESPONSE)

        opening_moves = state.moves_for_phase(DialogPhase.OPENING)
        socratic_q = (
            opening_moves[0].content.get("question", state.question)
            if opening_moves else state.question
        )
        ctx = {
            "original_question": state.question,
            "socratic_opening_question": socratic_q,
        }

        assignment = self.assign_roles_for_phase(state, DialogPhase.INITIAL_RESPONSE)
        self._apply_phase_roles(state, DialogPhase.INITIAL_RESPONSE, assignment)

        moves: List[AgentMove] = []
        for agent_id, role in sorted(assignment.items()):
            agent = self._agent_by_id(agent_id)
            m = self._dispatch(state, agent, role,
                               DialogPhase.INITIAL_RESPONSE, ctx, {})
            moves.append(m)
        return moves

    def run_elenchus_phase(self, session_id: str) -> List[AgentMove]:
        """Deterministically-assigned critics challenge the initial responses."""
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.ELENCHUS)

        initial_moves = state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)
        # Agents see content but not the authoring agent IDs (minimal awareness)
        ctx = {
            "initial_responses": [
                {"role": m.role.value, "content": m.content}
                for m in initial_moves
            ]
        }

        assignment = self.assign_roles_for_phase(state, DialogPhase.ELENCHUS)
        self._apply_phase_roles(state, DialogPhase.ELENCHUS, assignment)

        moves: List[AgentMove] = []
        for agent_id, role in sorted(assignment.items()):
            agent = self._agent_by_id(agent_id)
            m = self._dispatch(state, agent, role,
                               DialogPhase.ELENCHUS, ctx, {})
            moves.append(m)
        return moves

    def run_reflection_phase(self, session_id: str) -> List[AgentMove]:
        """
        Agents who gave initial responses revise their positions.
        Their assigned_role is temporarily changed to REFLECTOR by the CED.
        primary_role is preserved for use in subsequent phases.
        """
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.REFLECTION)

        initial_moves = state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)
        elenchus_moves = state.moves_for_phase(DialogPhase.ELENCHUS)

        critiques = [m.content for m in elenchus_moves]
        responder_ids = [m.agent_id for m in initial_moves]

        # CED assigns REFLECTOR to exactly the agents who authored an initial
        # response (you reflect on your own position). Recorded in role_history.
        reflection_assignment = {aid: AgentRole.REFLECTOR for aid in responder_ids}
        self._apply_phase_roles(state, DialogPhase.REFLECTION, reflection_assignment)

        moves: List[AgentMove] = []
        for m_initial in initial_moves:
            agent = self._agent_by_id(m_initial.agent_id)
            ctx = {
                "my_initial_response": m_initial.content,
                "critiques_from_council": critiques,
            }
            m = self._dispatch(state, agent, AgentRole.REFLECTOR,
                               DialogPhase.REFLECTION, ctx, {})
            moves.append(m)
        return moves

    def run_reconstruction_phase(self, session_id: str) -> List[AgentMove]:
        """
        MAIEUTIC_RECONSTRUCTOR (deterministically assigned for this phase) builds
        a stronger position from the surviving insights.
        """
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.RECONSTRUCTION)

        assignment = self.assign_roles_for_phase(state, DialogPhase.RECONSTRUCTION)
        self._apply_phase_roles(state, DialogPhase.RECONSTRUCTION, assignment)

        reflection_moves = state.moves_for_phase(DialogPhase.REFLECTION)
        elenchus_moves = state.moves_for_phase(DialogPhase.ELENCHUS)

        ctx = {
            "reflected_positions": [m.content for m in reflection_moves],
            "critiques": [m.content for m in elenchus_moves],
        }

        moves: List[AgentMove] = []
        for agent_id, role in sorted(assignment.items()):
            agent = self._agent_by_id(agent_id)
            m = self._dispatch(state, agent, role,
                               DialogPhase.RECONSTRUCTION, ctx, {})
            moves.append(m)
        return moves

    def run_synthesis_phase(self, session_id: str) -> List[AgentMove]:
        """
        ALL agents produce a synthesis draft (every agent → SYNTHESIZER).
        Multiple competing drafts feed the blind assembly step.
        """
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.SYNTHESIS)

        assignment = self.assign_roles_for_phase(state, DialogPhase.SYNTHESIS)
        self._apply_phase_roles(state, DialogPhase.SYNTHESIS, assignment)

        reconstruction_moves = state.moves_for_phase(DialogPhase.RECONSTRUCTION)
        reflection_moves = state.moves_for_phase(DialogPhase.REFLECTION)

        ctx = {
            "reconstructed_positions": [m.content for m in reconstruction_moves],
            "reflected_positions": [m.content for m in reflection_moves],
        }

        moves: List[AgentMove] = []
        for agent in self.agents:
            role = assignment.get(agent.agent_id, AgentRole.SYNTHESIZER)
            # _sections tells the provider to emit the locked 5-section draft.
            m = self._dispatch(state, agent, role,
                               DialogPhase.SYNTHESIS, ctx, {"_sections": True})
            moves.append(m)

        # Convert each synthesis move into a structured 5-section SectionDraft.
        self.build_section_drafts(session_id)
        return moves

    # ── 5-Section drafts ──────────────────────────────────────────────────────

    def build_section_drafts(self, session_id: str) -> List[SectionDraft]:
        """Turn synthesis moves into locked 5-section SectionDrafts (CED-owned)."""
        state = self.get_session(session_id)
        drafts: List[SectionDraft] = []
        for m in state.moves_for_phase(DialogPhase.SYNTHESIS):
            c = m.content
            drafts.append(SectionDraft(
                draft_id=f"draft_{m.move_id}",   # deterministic
                session_id=session_id,
                author_agent_id=m.agent_id,
                move_id=m.move_id,
                core_answer=str(c.get("core_answer", "")),
                crucial_stress_test=str(c.get("crucial_stress_test", "")),
                blind_spots=str(c.get("blind_spots", "")),
                nuance=str(c.get("nuance", "")),
                final_verdict=str(c.get("final_verdict", "")),
            ))
        state.section_drafts = drafts
        return drafts

    # ── Shadow Scoring ────────────────────────────────────────────────────────

    # ── Score-parsing helpers (robust against malformed provider output) ──────

    @staticmethod
    def _clamp01(value: Any, default: float = 0.7) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _variance(values: List[float]) -> float:
        """Population variance (0.0 for fewer than two values)."""
        n = len(values)
        if n < 2:
            return 0.0
        mean = sum(values) / n
        return sum((v - mean) ** 2 for v in values) / n

    def _parse_flags(self, raw_flags: Any) -> List[PenaltyFlag]:
        flags: List[PenaltyFlag] = []
        if isinstance(raw_flags, list):
            for f in raw_flags:
                try:
                    flags.append(PenaltyFlag(f))
                except (ValueError, TypeError):
                    continue
        return flags

    def _parse_status(self, raw_status: Any) -> ProviderStatus:
        try:
            return ProviderStatus(raw_status)
        except (ValueError, TypeError):
            return ProviderStatus.OK

    def _parse_breakdown(self, raw: Dict[str, Any]):
        """
        Return (ScoreBreakdown, ProviderStatus, penalty_flags).
        Malformed/missing breakdowns are recorded cleanly (zeros + ERROR +
        SCHEMA_VIOLATION) rather than crashing orchestration.
        """
        flags = self._parse_flags(raw.get("penalty_flags", []))
        status = self._parse_status(raw.get("provider_status", "ok"))
        bd = raw.get("score_breakdown")
        dims = list(ScoreBreakdown.model_fields.keys())
        try:
            breakdown = ScoreBreakdown(**{k: float(bd[k]) for k in dims})
        except (TypeError, ValueError, KeyError):
            breakdown = ScoreBreakdown(**{k: 0.0 for k in dims})
            status = ProviderStatus.ERROR
            if PenaltyFlag.SCHEMA_VIOLATION not in flags:
                flags = flags + [PenaltyFlag.SCHEMA_VIOLATION]
        return breakdown, status, flags

    # ── Shadow Scoring (move-level, 0–10, CED-owned, hidden) ──────────────────

    def compute_shadow_scores(
        self,
        session_id: str,
        phase: DialogPhase = DialogPhase.SYNTHESIS,
    ) -> List[MicroScore]:
        """
        For every move in the phase, each *other* agent produces a multi-
        dimensional MicroScore. No agent scores its own output. Stored only on
        SessionState (never on AgentState, never inserted into AgentTask.context).
        """
        state = self.get_session(session_id)
        micro: List[MicroScore] = []

        for move in state.moves_for_phase(phase):
            for scorer in self.agents:
                if scorer.agent_id == move.agent_id:
                    continue  # no self-scoring — hard constraint

                raw = scorer.provider.complete(
                    system_prompt=(
                        "You are scoring a council output. "
                        "Evaluate only what is in front of you."
                    ),
                    user_prompt=f"Output: {move.content}",
                    output_schema={"_role": "__move_score__", "_target": move.move_id},
                    agent_id=scorer.agent_id,
                )
                breakdown, status, flags = self._parse_breakdown(raw)
                micro.append(MicroScore(
                    session_id=session_id,
                    output_id=move.move_id,
                    phase=phase,
                    author_agent_id=move.agent_id,
                    voter_agent_id=scorer.agent_id,
                    score_breakdown=breakdown,
                    confidence=self._clamp01(raw.get("confidence", 0.7)),
                    justification=str(raw.get("justification", "")),
                    penalty_flags=flags,
                    provider_status=status,
                ))

        state.micro_scores = micro
        return micro

    # ── Section-level Scoring (per draft × section, 0–10) ─────────────────────

    def score_section_drafts(self, session_id: str) -> List[DraftScorecard]:
        """
        For each 5-section draft, every non-author agent produces a DraftScorecard
        with one SectionScore per section. Sections that cannot be scored are
        recorded in missing_sections rather than silently dropped.
        """
        state = self.get_session(session_id)
        cards: List[DraftScorecard] = []

        for draft in state.section_drafts:
            for scorer in self.agents:
                if scorer.agent_id == draft.author_agent_id:
                    continue  # no self-scoring

                section_scores: List[SectionScore] = []
                missing: List[SectionName] = []
                for section in SECTION_ORDER:
                    content = draft.section_text(section)
                    if not content.strip():
                        missing.append(section)
                        continue
                    raw = scorer.provider.complete(
                        system_prompt="Score one section of a council draft.",
                        user_prompt=f"Section: {section.value}\nContent: {content}",
                        output_schema={
                            "_role": "__section_score__",
                            "_target": draft.draft_id,
                            "_section": section.value,
                        },
                        agent_id=scorer.agent_id,
                    )
                    breakdown, status, flags = self._parse_breakdown(raw)
                    try:
                        section_scores.append(SectionScore(
                            session_id=session_id,
                            section_name=section,
                            draft_id=draft.draft_id,
                            author_agent_id=draft.author_agent_id,
                            voter_agent_id=scorer.agent_id,
                            score_breakdown=breakdown,
                            confidence=self._clamp01(raw.get("confidence", 0.7)),
                            justification=str(raw.get("justification", "")),
                            penalty_flags=flags,
                            provider_status=status,
                        ))
                    except Exception:
                        missing.append(section)

                cards.append(DraftScorecard(
                    session_id=session_id,
                    draft_id=draft.draft_id,
                    author_agent_id=draft.author_agent_id,
                    voter_agent_id=scorer.agent_id,
                    section_scores=section_scores,
                    missing_sections=missing,
                ))

        state.draft_scorecards = cards
        return cards

    # ── Blind Section Assembly (section-by-section, mechanical) ───────────────

    def _section_ranking(
        self, state: SessionState, section: SectionName
    ) -> List[Dict[str, Any]]:
        """
        Rank drafts for one section by the tie-breaker chain:
          1. highest average overall_score
          2. lower variance
          3. higher score_count
          4. deterministic draft_id order
        """
        by_draft: Dict[str, List[float]] = {}
        for ss in state.section_scores_for(section):
            by_draft.setdefault(ss.draft_id, []).append(float(ss.overall_score))

        stats: List[Dict[str, Any]] = []
        for draft_id, vals in by_draft.items():
            stats.append({
                "draft_id": draft_id,
                "average_score": sum(vals) / len(vals),
                "score_count": len(vals),
                "variance": self._variance(vals),
            })
        stats.sort(key=lambda s: (
            -s["average_score"],   # 1. highest average
            s["variance"],         # 2. lower variance
            -s["score_count"],     # 3. higher count
            s["draft_id"],         # 4. deterministic id order
        ))
        return stats

    def _section_assembled(
        self, section: SectionName, entry: Dict[str, Any],
        drafts_by_id: Dict[str, SectionDraft],
    ) -> AssembledSection:
        d = drafts_by_id.get(entry["draft_id"])
        return AssembledSection(
            section_name=section,
            selected_draft_id=entry["draft_id"],
            selected_author_agent_id=d.author_agent_id if d else "",
            content=d.section_text(section) if d else "",
            average_score=round(entry["average_score"], 4),
            score_count=entry["score_count"],
            variance=round(entry["variance"], 6),
        )

    def assemble_sections(self, session_id: str) -> AssembledAnswer:
        """
        Section-by-section blind assembly: independently for each of the five
        sections, pick the draft with the highest average overall_score (with
        deterministic tie-breakers). CED never chooses winners semantically.
        """
        state = self.get_session(session_id)
        drafts_by_id = {d.draft_id: d for d in state.section_drafts}

        assembled_sections: List[AssembledSection] = []
        for section in SECTION_ORDER:
            ranking = self._section_ranking(state, section)
            if ranking:
                assembled_sections.append(
                    self._section_assembled(section, ranking[0], drafts_by_id)
                )
            else:
                # No valid scores for this section → unresolved placeholder.
                assembled_sections.append(AssembledSection(
                    section_name=section,
                    selected_draft_id="",
                    selected_author_agent_id="",
                    content="",
                    average_score=0.0,
                    score_count=0,
                    variance=0.0,
                    unresolved=True,
                ))

        assembled = AssembledAnswer(session_id=session_id, sections=assembled_sections)
        state.assembled_answer = assembled
        return assembled

    # ── Ratification (RatificationVote, runner-up replacement, 2 rounds) ──────

    def _epistemic_hint(self, state: SessionState) -> str:
        scores = [ms.overall_score for ms in state.micro_scores
                  if ms.overall_score is not None]
        if not scores:
            return "uncertain"
        avg = sum(scores) / len(scores)   # 0–10 scale
        if avg >= 7.5:
            return "well_supported"
        if avg >= 5.5:
            return "contested"
        return "speculative"

    def _parse_vote(self, content: Dict[str, Any], voter_id: str) -> RatificationVote:
        try:
            decision = RatificationDecision(content.get("decision", "approve"))
        except (ValueError, TypeError):
            decision = RatificationDecision.APPROVE
        try:
            severity = ObjectionSeverity(content.get("severity", "none"))
        except (ValueError, TypeError):
            severity = ObjectionSeverity.NONE
        target = content.get("target_section")
        section = None
        if target:
            try:
                section = SectionName(target)
            except (ValueError, TypeError):
                section = None
        return RatificationVote(
            voter_agent_id=content.get("voter_agent_id", voter_id),
            decision=decision,
            severity=severity,
            target_section=section,
            reason=str(content.get("reason", "")),
        )

    def _apply_section_choice(
        self, assembled: AssembledAnswer, section: SectionName,
        entry: Dict[str, Any], drafts_by_id: Dict[str, SectionDraft],
    ) -> None:
        sec = assembled.section(section)
        d = drafts_by_id.get(entry["draft_id"])
        if sec and d:
            sec.selected_draft_id = entry["draft_id"]
            sec.selected_author_agent_id = d.author_agent_id
            sec.content = d.section_text(section)
            sec.average_score = round(entry["average_score"], 4)
            sec.score_count = entry["score_count"]
            sec.variance = round(entry["variance"], 6)
            sec.unresolved = False

    @staticmethod
    def _mark_section_unresolved(assembled: AssembledAnswer, section: SectionName) -> None:
        sec = assembled.section(section)
        if sec:
            sec.unresolved = True

    def run_ratification_phase(self, session_id: str) -> FinalResponse:
        """
        The deterministically-assigned FINAL_EVALUATOR votes on the assembled
        answer (up to MAX_RATIFICATION_ROUNDS rounds).

        Blocking policy:
          - Only BLOCKING_OBJECTION at CRITICAL severity blocks.
          - minor/major objections are recorded but never block.
          - A critical objection targeting a section triggers a runner-up
            replacement; if none remains (or rounds are exhausted) the section
            is marked unresolved.
          - A critical objection with no target_section hard-blocks the answer.
        """
        state = self.get_session(session_id)
        state.advance_phase(DialogPhase.RATIFICATION)

        assembled = state.assembled_answer
        if assembled is None:
            raise RuntimeError(
                "assemble_sections() must be called before run_ratification_phase()."
            )

        assignment = self.assign_roles_for_phase(state, DialogPhase.RATIFICATION)
        self._apply_phase_roles(state, DialogPhase.RATIFICATION, assignment)
        evaluator_id = next(
            (aid for aid, r in assignment.items() if r == AgentRole.FINAL_EVALUATOR),
            self._ordered_agent_ids()[0],
        )
        evaluator = self._agent_by_id(evaluator_id)
        epistemic_hint = self._epistemic_hint(state)

        drafts_by_id = {d.draft_id: d for d in state.section_drafts}
        rank_index: Dict[SectionName, int] = {
            s.section_name: 0 for s in assembled.sections
        }

        votes: List[RatificationVote] = []
        blocking_objections: List[str] = []
        # Sections assembly could not resolve (e.g. no acceptable draft) start unresolved.
        unresolved: List[SectionName] = [
            s.section_name for s in assembled.sections if s.unresolved
        ]
        hard_blocked = False
        ep_status_raw = epistemic_hint

        rounds = 0
        while rounds < MAX_RATIFICATION_ROUNDS:
            rounds += 1
            move = self._dispatch(
                state, evaluator,
                role=AgentRole.FINAL_EVALUATOR,
                phase=DialogPhase.RATIFICATION,
                context={"assembled_draft": assembled.full_text()},
                extra_schema={"_epistemic_hint": epistemic_hint},
            )
            ep_status_raw = move.content.get("epistemic_status", ep_status_raw)
            vote = self._parse_vote(move.content, evaluator_id)
            votes.append(vote)

            if not vote.is_critical_block():
                # Approve, or a minor/major objection: record but do not block.
                if vote.decision == RatificationDecision.BLOCKING_OBJECTION and vote.reason:
                    blocking_objections.append(vote.reason)
                break

            # Critical block from here on.
            if vote.reason:
                blocking_objections.append(vote.reason)

            if vote.target_section is None:
                hard_blocked = True   # whole-answer critical block
                break

            section = vote.target_section
            ranking = self._section_ranking(state, section)
            next_idx = rank_index.get(section, 0) + 1
            if next_idx < len(ranking):
                rank_index[section] = next_idx
                self._apply_section_choice(assembled, section, ranking[next_idx], drafts_by_id)
                if rounds >= MAX_RATIFICATION_ROUNDS:
                    # No round left to re-validate the replacement → unresolved.
                    self._mark_section_unresolved(assembled, section)
                    if section not in unresolved:
                        unresolved.append(section)
                # else: loop again for a re-vote
            else:
                # No runner-up available → unresolved.
                self._mark_section_unresolved(assembled, section)
                if section not in unresolved:
                    unresolved.append(section)
                break

        assembled.unresolved_sections = list(unresolved)
        ratified = (not hard_blocked) and (len(unresolved) == 0)

        try:
            ep_status = EpistemicStatus(ep_status_raw)
        except (ValueError, TypeError):
            ep_status = EpistemicStatus.UNCERTAIN

        # Advance to COMPLETE so RATIFICATION appears in phase_history.
        state.advance_phase(DialogPhase.COMPLETE)

        final = FinalResponse(
            session_id=session_id,
            question=state.question,
            answer="" if hard_blocked else assembled.full_text(),
            ratified=ratified,
            blocking_objections=blocking_objections,
            unresolved_sections=list(unresolved),
            ratification_votes=votes,
            epistemic_status=ep_status,
            council_summary={
                "phases_completed": [p.value for p in state.phase_history],
                "num_agents": len(self.agents),
                "total_moves": len(state.moves),
                "evaluator_agent": evaluator.agent_id,
                "epistemic_hint_used": epistemic_hint,
                "ratification_rounds": rounds,
                "unresolved_sections": [s.value for s in unresolved],
                "hard_blocked": hard_blocked,
            },
        )
        state.final_response = final
        return final

    # ── Full pipeline runner ──────────────────────────────────────────────────

    def run_session(
        self,
        question: str,
        session_id: Optional[str] = None,
    ) -> FinalResponse:
        """Run a complete Socratic Council session end-to-end."""
        state = self.create_session(question, session_id=session_id)
        sid = state.session_id

        self.run_opening_phase(sid)
        self.run_initial_response_phase(sid)
        self.run_elenchus_phase(sid)
        self.run_reflection_phase(sid)
        self.run_reconstruction_phase(sid)
        self.run_synthesis_phase(sid)          # also builds 5-section drafts
        self.compute_shadow_scores(sid)        # move-level shadow scores
        self.score_section_drafts(sid)         # section-level scores
        self.assemble_sections(sid)            # blind section assembly
        return self.run_ratification_phase(sid)
