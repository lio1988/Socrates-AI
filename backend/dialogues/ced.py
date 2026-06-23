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

import asyncio
from typing import Dict, List, Optional, Tuple

from .models import (
    AgentMove,
    AgentRole,
    AgentState,
    AgentTask,
    AssembledAnswer,
    AssembledSection,
    CouncilRoundResult,
    DialogPhase,
    DraftScorecard,
    EpistemicLeaderboard,
    EpistemicStatus,
    FinalResponse,
    LeaderboardStatus,
    LEADERBOARD_INTERPRETATION_WARNING,
    MAX_LEADERBOARD_HARVEST_TIMEOUT,
    MAX_RATIFICATION_ROUNDS,
    MicroScore,
    ObjectionSeverity,
    PenaltyFlag,
    ProviderResponse,
    ProviderStatus,
    RatificationDecision,
    RatificationVote,
    ScoreBreakdown,
    SECTION_ORDER,
    SectionDraft,
    SectionName,
    SectionScore,
    SessionState,
    ShadowScoreHarvest,
    SyncGateStatus,
)
from .providers import LLMProvider
from .agent import SocraticAgent
from .provider_registry import CouncilProviderRegistry
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

# Phases whose agent moves are shadow-scored (every deliberation phase — incl.
# the Socratic opening question). RATIFICATION is the evaluator's verdict, not a
# peer-scored contribution, so it is excluded.
SCORED_PHASES: List[DialogPhase] = [
    DialogPhase.OPENING,
    DialogPhase.INITIAL_RESPONSE,
    DialogPhase.ELENCHUS,
    DialogPhase.REFLECTION,
    DialogPhase.RECONSTRUCTION,
    DialogPhase.SYNTHESIS,
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
        registry: Optional["CouncilProviderRegistry"] = None,
    ) -> None:
        if len(agents) < 2:
            raise ValueError("Council requires at least 2 agents.")
        self.agents = agents
        self.provider = provider
        # Optional Phase 8A provider-adapter registry. When present, its
        # availability/failure summary is surfaced in the audit (never to agents).
        self.registry = registry
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

    # ── Phase 8B: registry-backed council round (additive, parallel path) ─────

    def _build_round_task(
        self, state: SessionState, agent_id: str,
        role: AgentRole, phase: DialogPhase,
    ) -> AgentTask:
        """Build the AgentTask that all available providers will answer this round."""
        return AgentTask(
            session_id=state.session_id,
            agent_id=agent_id,
            role=role,
            phase=phase,
            question=state.question,
            output_schema={"_role": role.value, "_question": state.question},
            round_number=state.round_number,
        )

    async def run_registry_council_round(
        self,
        session_id: str,
        agent_id: str,
        role: AgentRole,
        phase: DialogPhase,
        timeout_seconds: Optional[float] = None,
    ) -> CouncilRoundResult:
        """
        Drive ONE multi-provider council round through the CouncilProviderRegistry.

        This is an additive, parallel execution path — it does NOT replace
        run_session() or the FakeProvider pipeline. It proves the registry can
        gather validated structured outputs from several providers with quorum,
        timeout, and error handling, and records audit metadata on the session.

        - Readiness (minimum providers) is checked first; if not met, returns a
          non-proceeding result with the registry warning and NO fabricated moves.
        - Provider timeouts / failures are recorded, never crash, never faked.
        - The result is stored on SessionState.registry_rounds (CED-owned audit).
        """
        if self.registry is None:
            raise RuntimeError(
                "run_registry_council_round requires a CouncilProviderRegistry "
                "(pass registry=... to CEDOrchestrator)."
            )
        state = self.get_session(session_id)

        ready, warning = self.registry.assess_readiness()
        if not ready:
            result = CouncilRoundResult(proceed=False, warning=warning)
            state.registry_rounds.append(result)
            return result

        agent_state = state.agent_states.get(
            agent_id,
            AgentState(agent_id=agent_id, primary_role=role, assigned_role=role),
        )
        task = self._build_round_task(state, agent_id, role, phase)
        result = await self.registry.gather_council_round(
            task, agent_state, timeout_seconds=timeout_seconds
        )
        state.registry_rounds.append(result)
        return result

    async def gather_registry_phase_round(
        self,
        session_state: SessionState,
        phase: DialogPhase,
        round_index: int = 0,
        timeout_seconds: Optional[float] = None,
    ) -> CouncilRoundResult:
        """
        Drive a FULL registry-backed council round for a phase: one move per
        deterministically-assigned agent/role.

        Contract:
          1. Roles come from the deterministic role plan (assign_roles_for_phase)
             — providers cannot choose or change role assignment.
          2. One AgentTask is built per assigned (agent, role); each is sent to a
             provider (deterministic round-robin over available adapters).
          3. ProviderResponses are collected; quorum/fallback decides `proceed`
             (effective quorum = min(configured quorum, #assigned agents)).
          4. Failures/timeouts are recorded as ProviderResponse metadata only —
             no fake AgentMove is ever fabricated for a failed provider.
          5. The result is recorded on SessionState.registry_rounds (CED-owned).

        Additive/parallel: does NOT touch run_session() or the FakeProvider path.
        """
        if self.registry is None:
            raise RuntimeError(
                "gather_registry_phase_round requires a CouncilProviderRegistry "
                "(pass registry=... to CEDOrchestrator)."
            )

        ready, warning = self.registry.assess_readiness()
        if not ready:
            result = CouncilRoundResult(proceed=False, warning=warning)
            session_state.registry_rounds.append(result)
            return result

        # Deterministic role plan for the phase — independent of any provider.
        assignment = self.assign_roles_for_phase(session_state, phase, round_index)
        items = sorted(assignment.items())   # deterministic order
        adapters = self.registry.available_adapters()

        async def _one(index: int, agent_id: str, role: AgentRole) -> "ProviderResponse":
            adapter = adapters[index % len(adapters)]   # round-robin provider mapping
            task = self._build_round_task(session_state, agent_id, role, phase)
            agent_state = session_state.agent_states.get(
                agent_id,
                AgentState(agent_id=agent_id, primary_role=role, assigned_role=role),
            )
            return await self.registry.run_adapter(
                adapter, task, agent_state, timeout_seconds
            )

        responses = list(await asyncio.gather(
            *(_one(i, aid, role) for i, (aid, role) in enumerate(items))
        ))

        # Effective quorum cannot exceed the number of assigned agents this phase.
        effective_quorum = min(self.registry.quorum_for_assembly, len(items)) if items else 0
        result = self.registry.finalize_round(responses, quorum=effective_quorum)
        session_state.registry_rounds.append(result)
        return result

    def registry_round_audit(self, result: CouncilRoundResult) -> Dict[str, Any]:
        """
        Developer/user-visible audit metadata for a registry round. Aggregate
        provider status only — never inserted into AgentState, never shown to
        agents, never contains raw keys.
        """
        status_counts: Dict[str, int] = {}
        for r in result.responses:
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
        audit = {
            "proceed": result.proceed,
            "warning": result.warning,
            "ok_providers": list(result.ok_provider_ids),
            "failed_providers": list(result.failed_provider_ids),
            "validated_moves": sum(1 for r in result.responses if r.ok),
            "provider_status_counts": status_counts,
        }
        if self.registry is not None:
            audit["provider_status_summary"] = self.registry.status_summary()
        return audit

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _agent_by_id(self, agent_id: str) -> SocraticAgent:
        try:
            return next(a for a in self.agents if a.agent_id == agent_id)
        except StopIteration:
            raise ValueError(f"Agent '{agent_id}' not registered with this orchestrator.")

    def _deterministic_move_id(
        self, state: SessionState, agent_id: str, phase: DialogPhase,
    ) -> str:
        """
        Deterministic, unique move id derived from
        (session_id, phase, agent_id, round_number, occurrence-in-phase).

        Replaces the random UUID so the WHOLE pipeline — not just role rotation —
        is reproducible for a given (question, session_id). The occurrence
        disambiguates an agent who acts twice in a phase (e.g. ratification rounds).
        """
        occurrence = sum(
            1 for m in state.moves if m.phase == phase and m.agent_id == agent_id
        )
        key = f"{state.session_id}|{phase.value}|{agent_id}|{state.round_number}|{occurrence}"
        return "move_" + format(stable_hash(key), "x")[:12]

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
        # Deterministic move id (drives reproducible shadow-scoring seeds).
        move.move_id = self._deterministic_move_id(state, agent.agent_id, phase)
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

    def _score_one_move(
        self, state: SessionState, move: AgentMove, scorer: SocraticAgent,
        phase: DialogPhase,
    ) -> MicroScore:
        """Produce one voter's MicroScore for one move (no self-scoring upstream)."""
        raw = scorer.provider.complete(
            system_prompt=(
                "You are scoring a council output. "
                "Evaluate only what is in front of you."
            ),
            user_prompt=f"Output: {move.content}",
            output_schema={
                "_role": "__move_score__",
                "_target": move.move_id,
                "_question": state.question,
            },
            agent_id=scorer.agent_id,
        )
        breakdown, status, flags = self._parse_breakdown(raw)
        return MicroScore(
            session_id=state.session_id,
            output_id=move.move_id,
            phase=phase,
            author_agent_id=move.agent_id,
            voter_agent_id=scorer.agent_id,
            score_breakdown=breakdown,
            confidence=self._clamp01(raw.get("confidence", 0.7)),
            justification=str(raw.get("justification", "")),
            penalty_flags=flags,
            provider_status=status,
        )

    def _move_score_pairs(self, state: SessionState, phase: DialogPhase):
        """(move, scorer) pairs that must be scored — every non-author pair."""
        return [
            (move, scorer)
            for move in state.moves_for_phase(phase)
            for scorer in self.agents
            if scorer.agent_id != move.agent_id   # no self-scoring
        ]

    @staticmethod
    def _normalize_phases(phases) -> List[DialogPhase]:
        """Accept None (→ all scored phases), a single phase, or a list."""
        if phases is None:
            return list(SCORED_PHASES)
        if isinstance(phases, DialogPhase):
            return [phases]
        return list(phases)

    def _phase_pairs(self, state: SessionState, phases: List[DialogPhase]):
        """Flat list of (move, scorer, phase) across the given phases."""
        return [
            (move, scorer, phase)
            for phase in phases
            for (move, scorer) in self._move_score_pairs(state, phase)
        ]

    def compute_shadow_scores(
        self,
        session_id: str,
        phases=None,
    ) -> List[MicroScore]:
        """
        Synchronous shadow scoring across every scored phase (default = all
        deliberation phases, incl. the Socratic opening). For every move, each
        *other* agent produces a multi-dimensional MicroScore. No agent scores
        its own output. Stored only on SessionState (never on AgentState, never
        inserted into AgentTask.context).

        `phases` accepts None (all scored phases), a single DialogPhase, or a list.
        """
        state = self.get_session(session_id)
        phase_list = self._normalize_phases(phases)
        micro = [
            self._score_one_move(state, move, scorer, phase)
            for (move, scorer, phase) in self._phase_pairs(state, phase_list)
        ]
        state.micro_scores = micro
        return micro

    # ── Epistemic Sync Gate (bounded final harvest of shadow scores) ──────────

    async def _score_move_async(
        self, state: SessionState, move: AgentMove, scorer: SocraticAgent,
        phase: DialogPhase,
    ) -> MicroScore:
        """
        Async wrapper around one scoring call. FakeProvider is synchronous and
        fast, so this resolves immediately; the seam exists so real, slow
        providers can be awaited (and timed out) without changing callers.
        Patchable in tests to simulate slow/timed-out scoring.
        """
        return self._score_one_move(state, move, scorer, phase)

    async def harvest_shadow_scores(
        self,
        session_state: SessionState,
        timeout_seconds: float = MAX_LEADERBOARD_HARVEST_TIMEOUT,
        phases=None,
    ) -> ShadowScoreHarvest:
        """
        Bounded final harvest of shadow-scoring tasks (the Epistemic Sync Gate),
        across every scored phase by default (incl. the Socratic opening).

        Scoring tasks run in parallel and are awaited only up to timeout_seconds.
        Completed scores are collected onto SessionState; outstanding tasks are
        recorded as timed out and cancelled; failures are recorded. The final
        response can always proceed — a partial (or empty) leaderboard never
        blocks it, and a scoring failure never crashes the CED.
        """
        phase_list = self._normalize_phases(phases)
        pairs = self._phase_pairs(session_state, phase_list)
        expected = len(pairs)

        harvest = ShadowScoreHarvest(
            session_id=session_state.session_id, scores_expected=expected,
        )
        if expected == 0:
            harvest.status = SyncGateStatus.UNAVAILABLE
            session_state.micro_scores = []
            session_state.shadow_harvest = harvest
            return harvest

        # Launch every scoring task, tagged with a stable id for audit records.
        task_meta: Dict[asyncio.Future, str] = {}
        for move, scorer, phase in pairs:
            task_id = f"{move.move_id}:{scorer.agent_id}"
            fut = asyncio.ensure_future(
                self._score_move_async(session_state, move, scorer, phase)
            )
            task_meta[fut] = task_id

        done, pending = await asyncio.wait(
            list(task_meta.keys()), timeout=timeout_seconds
        )

        collected: List[MicroScore] = []
        for fut in done:
            try:
                collected.append(fut.result())
            except Exception:
                harvest.failed_tasks.append(task_meta[fut])  # provider failed — no fake score

        for fut in pending:
            harvest.timed_out_tasks.append(task_meta[fut])    # timed out — provider_status TIMEOUT
            fut.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        collected_count = len(collected)
        harvest.scores_collected = collected_count
        harvest.coverage_ratio = (collected_count / expected) if expected else 0.0

        if collected_count == 0:
            harvest.status = (
                SyncGateStatus.TIMEOUT if harvest.timed_out_tasks
                else SyncGateStatus.UNAVAILABLE
            )
        elif collected_count >= expected:
            harvest.status = SyncGateStatus.COMPLETE
        else:
            harvest.status = SyncGateStatus.PARTIAL

        session_state.micro_scores = collected   # CED-owned; agents never see this
        session_state.shadow_harvest = harvest
        return harvest

    def _sync_harvest(self, state: SessionState, phases=None) -> ShadowScoreHarvest:
        """
        Build a harvest record from already-collected (synchronous) micro_scores,
        across every scored phase by default. Used by the default run_session
        pipeline. If an async harvest already ran and stored a record, it is reused.
        """
        if state.shadow_harvest is not None:
            return state.shadow_harvest

        phase_list = self._normalize_phases(phases)
        expected = sum(len(self._move_score_pairs(state, p)) for p in phase_list)
        collected = len(state.micro_scores)
        coverage = (collected / expected) if expected else 0.0
        if expected == 0 or collected == 0:
            status = SyncGateStatus.UNAVAILABLE
        elif collected >= expected:
            status = SyncGateStatus.COMPLETE
        else:
            status = SyncGateStatus.PARTIAL
        harvest = ShadowScoreHarvest(
            session_id=state.session_id, scores_expected=expected,
            scores_collected=collected, coverage_ratio=coverage, status=status,
        )
        state.shadow_harvest = harvest
        return harvest

    # ── CED-owned Epistemic Leaderboard (aggregate analytics, hidden) ─────────

    def build_epistemic_leaderboard(
        self,
        session_state: SessionState,
        harvest: ShadowScoreHarvest,
    ) -> EpistemicLeaderboard:
        """
        Aggregate the (CED-owned) MicroScores into a leaderboard. Uses aggregate
        data only — no raw MicroScore objects, no raw justifications. Never
        inserted into AgentState and never shown to agents.
        """
        micro = session_state.micro_scores
        expected = harvest.scores_expected
        collected = harvest.scores_collected
        coverage = harvest.coverage_ratio

        # Aggregate overall_score per AUTHOR agent (whose output was scored).
        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        by_phase: Dict[str, Dict[str, List[float]]] = {}
        for ms in micro:
            a = ms.author_agent_id
            ov = float(ms.overall_score or 0.0)
            sums[a] = sums.get(a, 0.0) + ov
            counts[a] = counts.get(a, 0) + 1
            ph = ms.phase.value
            by_phase.setdefault(ph, {}).setdefault(a, []).append(ov)

        averages = {a: round(sums[a] / counts[a], 4) for a in sums}
        cumulative = {a: round(sums[a], 4) for a in sums}
        scores_by_phase = {
            ph: {a: round(sum(v) / len(v), 4) for a, v in agents.items()}
            for ph, agents in by_phase.items()
        }
        top_contributors = sorted(averages, key=lambda a: (-averages[a], a))

        if expected == 0 or collected == 0:
            status = LeaderboardStatus.UNAVAILABLE
        elif coverage >= 1.0:
            status = LeaderboardStatus.COMPLETE
        else:
            status = LeaderboardStatus.PARTIAL

        notable: List[str] = []
        if status == LeaderboardStatus.PARTIAL:
            notable.append(
                f"Partial coverage: {collected}/{expected} shadow scores collected."
            )
        if harvest.timed_out_tasks:
            notable.append(f"{len(harvest.timed_out_tasks)} scoring task(s) timed out.")
        if harvest.failed_tasks:
            notable.append(f"{len(harvest.failed_tasks)} scoring task(s) failed.")

        leaderboard = EpistemicLeaderboard(
            session_id=session_state.session_id,
            leaderboard_status=status,
            scores_expected=expected,
            scores_collected=collected,
            coverage_ratio=round(coverage, 4),
            average_scores_by_agent=averages,
            cumulative_scores_by_agent=cumulative,
            scores_by_phase=scores_by_phase,
            top_contributors=top_contributors,
            notable_events=notable,
            interpretation_warning=LEADERBOARD_INTERPRETATION_WARNING,
        )
        session_state.epistemic_leaderboard = leaderboard
        return leaderboard

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
                            "_question": state.question,
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

        # Epistemic sync gate (final harvest) + CED-owned leaderboard.
        harvest = self._sync_harvest(state)
        leaderboard = self.build_epistemic_leaderboard(state, harvest)

        ratification_status = (
            "blocked" if hard_blocked
            else "unresolved" if unresolved
            else "ratified"
        )

        # CED-owned audit summary (no raw scores, no raw voter-level objects).
        audit_summary = {
            "phases_completed": [p.value for p in state.phase_history],
            "num_agents": len(self.agents),
            "total_moves": len(state.moves),
            "final_evaluator": evaluator.agent_id,
            "ratification_status": ratification_status,
            "ratification_rounds": rounds,
            "unresolved_sections": [s.value for s in unresolved],
            "hard_blocked": hard_blocked,
            "role_history_summary": self._role_history_summary(state),
            "score_coverage": {
                "scores_expected": harvest.scores_expected,
                "scores_collected": harvest.scores_collected,
                "coverage_ratio": harvest.coverage_ratio,
                "sync_gate_status": harvest.status.value,
                "timed_out": len(harvest.timed_out_tasks),
                "failed": len(harvest.failed_tasks),
            },
            "leaderboard_status": leaderboard.leaderboard_status.value,
            "aggregate_scores_by_agent": leaderboard.average_scores_by_agent,
        }

        # Phase 8A: surface provider availability/failure to the developer-visible
        # audit only (never inserted into AgentState, never shown to agents).
        if self.registry is not None:
            audit_summary["provider_status_summary"] = self.registry.status_summary()

        final = FinalResponse(
            session_id=session_id,
            question=state.question,
            # Phase 7 separated contract
            synthesis=assembled,
            ratification_status=ratification_status,
            audit_summary=audit_summary,
            socratic_leaderboard=leaderboard,
            # Retained backward-compatible fields
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

    @staticmethod
    def _role_history_summary(state: SessionState) -> Dict[str, List[str]]:
        """Compact {phase: [agent→role, ...]} view of role_history (audit/debug)."""
        summary: Dict[str, List[str]] = {}
        for rec in state.role_history:
            summary.setdefault(rec["phase"], []).append(
                f"{rec['agent_id']}→{rec['role']}"
            )
        return summary

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
