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
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    AgentMove,
    AgentRole,
    AgentState,
    AgentTask,
    AssembledAnswer,
    AssembledSection,
    CouncilRatification,
    CouncilRatificationStatus,
    CouncilRoundResult,
    CouncilVerdict,
    DialogPhase,
    DraftScorecard,
    FinalSynthesisMode,
    ObjectionSeverity,
    RatificationVerdict,
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
    ShadowScoringMode,
    SyncGateStatus,
    TaskKind,
    TaskLogEntry,
)
from .providers import LLMProvider
from .agent import SocraticAgent
from .provider_registry import CouncilProviderRegistry
from .hybrid_epistemic import (
    UNMAPPED_TARGET,
    ClaimRecord,
    ObjectionTargetProvenance,
    apply_verification,
    parse_verification_response,
    HybridEpistemicState,
    ObjectionRecord,
    ReleaseDecision,
    SupportState,
    VerificationClass,
    freeze_release,
    stable_id as _hybrid_id,
)
from .task_checker import (
    CheckerStatus,
    ProblemClass,
    evaluate_candidate,
    model_task,
    receipt_refutation,
    receipt_support,
)
from .reasoning_prompts import (
    SOCRATIC_AIM_CONSTRAINT,
    SOCRATIC_AIM_OPEN,
    SOCRATIC_FOLLOWUP_MANDATE,
    SOCRATIC_OPENING_MANDATE,
)
from .socratic import (
    AporiaRecord,
    CommitmentRecord,
    InjectionCheck,
    InquiryState,
    aporia_from_content,
    check_answer_injection,
    commitment_events_from_reflection,
    commitments_from_move,
    live_commitments,
    parse_grounding,
    read_inquiry_state,
    read_operator,
    resolve_grounding,
)
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
    # Socrates returns here rather than in a phase of his own: the elenchus is
    # where the answers he provoked are already in context, and a new
    # DialogPhase would ripple through sixty-seven files for no gain.
    DialogPhase.ELENCHUS:         [AgentRole.ELENCHUS_CRITIC,
                                   AgentRole.EMPIRICIST,
                                   AgentRole.SOCRATES],
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

# Phase-specific scoring rubric (V1, deterministic). A Socratic question is not
# judged by the same yardstick as a final synthesis. The seven score dimensions
# stay the same; the rubric identity is recorded on each MicroScore (CED-owned)
# and passed to the provider as a hint (never exposes scoring machinery to agents).
PHASE_RUBRICS: Dict[DialogPhase, Tuple[str, str]] = {
    DialogPhase.OPENING: (
        "question_quality",
        "assumption exposure, clarity forcing, productive uncertainty, usefulness to later reasoning"),
    DialogPhase.INITIAL_RESPONSE: (
        "initial_answer_quality",
        "relevance, clarity, epistemic honesty, useful starting claims"),
    DialogPhase.ELENCHUS: (
        "objection_quality",
        "strongest criticism, hidden assumptions, contradictions, falsifiability"),
    DialogPhase.REFLECTION: (
        "revision_quality",
        "valid revision, intellectual honesty, response to criticism"),
    DialogPhase.RECONSTRUCTION: (
        "repair_quality",
        "improved model/claim, integration of objections, better explanatory structure"),
    DialogPhase.SYNTHESIS: (
        "synthesis_quality",
        "final usefulness, coherence, accuracy, nuance, epistemic honesty"),
}


def rubric_for(phase: DialogPhase) -> Tuple[str, str]:
    """(rubric_name, focus) for a phase; a generic default for unmapped phases."""
    return PHASE_RUBRICS.get(phase, ("general_quality", "overall contribution quality"))


def rubric_for_move(move: "AgentMove", phase: DialogPhase) -> Tuple[str, str]:
    """The rubric a move is judged by — its own kind first, then its phase.

    Socrates executes inside ELENCHUS, and judging a question by the objection
    rubric would score it on "strongest criticism, contradictions,
    falsifiability" — none of which a question is trying to do. A question is
    judged as a question wherever it is asked.
    """
    if getattr(move, "task_kind", None) is TaskKind.SOCRATIC_QUESTION:
        return PHASE_RUBRICS[DialogPhase.OPENING]
    return rubric_for(phase)


# Deterministic task_kind per deliberation phase (Phase 8C registry session).
#: A role that keeps its own kind of task wherever it acts. Socrates asks a
#: question in any phase; giving him the phase's kind would hand him the
#: objection contract and make him an objector.
ROLE_TASK_KIND: Dict[AgentRole, TaskKind] = {
    AgentRole.SOCRATES: TaskKind.SOCRATIC_QUESTION,
}

PHASE_TASK_KIND: Dict[DialogPhase, TaskKind] = {
    DialogPhase.OPENING:          TaskKind.SOCRATIC_QUESTION,
    DialogPhase.INITIAL_RESPONSE: TaskKind.INITIAL_RESPONSE,
    DialogPhase.ELENCHUS:         TaskKind.ELENCHUS_OBJECTION,
    DialogPhase.REFLECTION:       TaskKind.REFLECTION_REVISION,
    DialogPhase.RECONSTRUCTION:   TaskKind.RECONSTRUCTION_PROPOSAL,
    DialogPhase.SYNTHESIS:        TaskKind.SYNTHESIS_DRAFT,
}

# Deliberation phases driven through the provider registry in Phase 8C (the
# RATIFICATION verdict still runs through the council's own evaluator).
#: The group that repeats while CED permits another Socratic follow-up. The
#: examination must see the UPDATED commitments, so the critics run again too.
SOCRATIC_CYCLE_PHASES: Tuple[DialogPhase, ...] = (
    DialogPhase.ELENCHUS, DialogPhase.REFLECTION,
)

REGISTRY_SESSION_PHASES: List[DialogPhase] = [
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
        shadow_scoring_mode: ShadowScoringMode = ShadowScoringMode.ALL_PHASES,
        final_synthesis_mode: FinalSynthesisMode = FinalSynthesisMode.COUNCIL_RATIFICATION,
        assembly_fallback: bool = False,
        lesson_store=None,
        seat_health=None,
        ai_learning: bool = False,
        topic_skill=None,
        open_questions=None,
        calibration=None,
        ratification_repair: str = "block",
        phase_retry: bool = False,
        max_socratic_followups: int = 2,
        training_corpus=None,
        score_weighting: str = "uniform",
        cohesion_margin: float = 0.0,
        openclaw_lessons=None,
        trace_capturer=None,
        tree_expansions: int = 0,
        tree_exploration: float = 0.5,
        hybrid_shadow=None,
    ) -> None:
        if len(agents) < 2:
            raise ValueError("Council requires at least 2 agents.")
        if final_synthesis_mode != FinalSynthesisMode.COUNCIL_RATIFICATION:
            raise NotImplementedError(
                f"final_synthesis_mode '{final_synthesis_mode.value}' is reserved "
                "for V2/V3; only 'council_ratification' is implemented in V1."
            )
        self.agents = agents
        self.provider = provider
        self.final_synthesis_mode = final_synthesis_mode
        # Optional Phase 8A provider-adapter registry. When present, its
        # availability/failure summary is surfaced in the audit (never to agents).
        self.registry = registry
        # How much shadow scoring to run (cost control; default = all phases).
        self.shadow_scoring_mode = shadow_scoring_mode
        # When True, a section with NO valid peer scores falls back to a real
        # synthesis draft (deterministic) instead of staying empty/unresolved.
        # Off by default (preserves the strict no-score=unresolved behavior);
        # the live council enables it so real-model runs still produce an answer.
        self.assembly_fallback = assembly_fallback
        # Phase 13 self-improvement (both optional; None = behavior unchanged):
        # lesson_store: EpistemicLessonStore — ratified outcomes feed future
        #   dialogues as PUBLIC lessons; seat_health: SeatHealthTracker — CED-owned
        #   operational telemetry per provider seat (content-blind).
        self.lesson_store = lesson_store
        self.seat_health = seat_health
        # Phase 13D: when True (and a lesson_store exists), lessons are AUTHORED
        # by a council agent (LESSON_DISTILLATION) and the council also reviews
        # its own process (PROCESS_REVIEW). Any AI failure falls back honestly to
        # the mechanical extractor — never fabricated.
        self.ai_learning = ai_learning
        # Phase 14: per-(seat, topic) skill profile (CED-owned analytics, hidden
        # from agents) + per-session lesson-retrieval cache (lessons, mode).
        self.topic_skill = topic_skill
        self._session_lessons: Dict[str, Tuple[List[Dict[str, Any]], str]] = {}
        # Phase 15 (living system): OpenQuestionLedger — the system's own research
        # agenda — plus a rolling record of session outcomes for compute_vitals.
        self.open_questions = open_questions
        self._session_outcomes: List[Dict[str, Any]] = []
        # Phase 17: CalibrationLedger — Brier-scored confidence calibration per
        # seat (CED-owned analytics, hidden from agents like the leaderboard).
        self.calibration = calibration
        # Phase 19: what to do on a critical ratification block —
        #   "block" (Option A, default): withhold the answer, mark repair_required;
        #   "runner_up" (Option B): mechanically swap each blocked section for its
        #   peer-scored runner-up draft and re-ratify (max MAX_RATIFICATION_ROUNDS).
        if ratification_repair not in ("block", "runner_up"):
            raise ValueError(f"ratification_repair must be 'block' or 'runner_up', "
                             f"got {ratification_repair!r}")
        self.ratification_repair = ratification_repair
        # Phase 20: phase rescue — retry ONLY the failed slots of a quorum-failed
        # phase, once, rerouted to the next seat. Off by default (strict legacy
        # behavior); build_council enables it for the capable/live path.
        self.phase_retry = phase_retry
        #: Q1 opening + at most this many follow-up questions. CED enforces it;
        #: Socrates may ask to continue and is not obeyed past the bound.
        self.max_socratic_followups = max_socratic_followups
        self._phase_retries: Dict[str, List[Dict[str, Any]]] = {}
        #: Who actually served each slot, per phase. Observability only.
        self._phase_dispatch: Dict[str, List[Dict[str, Any]]] = {}
        #: Append-only commitment history per session. New understanding extends
        #: it; nothing here is ever rewritten.
        self._commitments: Dict[str, List[CommitmentRecord]] = {}
        self._aporia: Dict[str, List[AporiaRecord]] = {}
        self._socratic_audit_rows: Dict[str, List[Dict[str, Any]]] = {}
        self._cycle_log: Dict[str, List[Dict[str, Any]]] = {}
        # Phase 22: optional Teacher-Loop corpus — harvests SFT + peer-score
        # preference data from each finished session (duck-typed: .ingest_session).
        self.training_corpus = training_corpus
        # Phase 23: how peer scores aggregate to pick a section winner —
        #   "uniform" (default): plain mean, identical to all prior behavior;
        #   "confidence": mean weighted by each voter's SELF-REPORTED confidence
        #   in that score (a mechanical weighted average — still no semantic CED
        #   judgement; a low-confidence vote still counts, just less).
        if score_weighting not in ("uniform", "confidence"):
            raise ValueError(f"score_weighting must be 'uniform' or 'confidence', "
                             f"got {score_weighting!r}")
        self.score_weighting = score_weighting
        # Phase 25: coherence-aware assembly. 0.0 (default) = OFF, byte-for-byte
        # the old per-section score-winner pick. When > 0, a section may be taken
        # from a globally-stronger (more coherent-anchor) draft instead of the raw
        # score-winner ONLY IF that draft is within `cohesion_margin` (0–10 scale)
        # of the winner — trading a bounded, sub-margin section-quality delta for
        # a less fragmented, more internally-coherent whole answer. Mechanical.
        if cohesion_margin < 0:
            raise ValueError(f"cohesion_margin must be >= 0, got {cohesion_margin!r}")
        self.cohesion_margin = float(cohesion_margin)
        self._cohesion_overrides = 0   # sections cohesion moved off the score-winner
        # OpenClaw Memory Lessons: when a lesson pool is provided, relevant
        # behavioral lessons are injected into DELIBERATION contexts only (never
        # into anonymous judging tasks like scoring/ratification). The pool is a
        # sequence of MemoryLesson records from the openclaw_memory subpackage;
        # None (default) = byte-for-byte unchanged behavior — no lessons injected.
        self.openclaw_lessons = openclaw_lessons
        # OpenClaw trace capture: duck-typed consumer with
        # .ingest_session(state, final) — same pattern as training_corpus.
        # Captures auditable per-run traces (no keys/credentials/hidden CoT).
        self.trace_capturer = trace_capturer
        # Deliberation Tree Search: search as a policy-improvement operator
        # (docs/deliberation_tree/ARCHITECTURE.md). 0 (default) = OFF, byte-for-
        # byte the one-shot pipeline. When > 0: after section scoring, CED spends
        # `tree_expansions` UCB-selected revision tasks enriching the draft pool
        # before blind assembly. Selection uses CED-owned scores (protocol
        # governance, precedented by Phases 19/20/21); the revising agent sees
        # ONLY the parent draft's section texts + a generic mandate — never
        # scores, tree statistics, ids, or identities.
        if tree_expansions < 0:
            raise ValueError(f"tree_expansions must be >= 0, got {tree_expansions!r}")
        self.tree_expansions = int(tree_expansions)
        self.tree_exploration = float(tree_exploration)
        self._tree_audits: Dict[str, Dict[str, Any]] = {}
        # Injected-context ledger: per session, which OpenClaw lessons ACTUALLY
        # entered which phase/agent context (CED-owned; feeds the audit).
        self._injected_lessons: Dict[str, List[Dict[str, Any]]] = {}
        # Debug-only: store sanitized task context in the task_log (off by default).
        self.debug_task_log: bool = False
        self._sessions: Dict[str, SessionState] = {}
        # Canonical execution identity: one logical agent remains bound to one
        # physical provider/model seat for the lifetime of a registry session.
        # Phase roles rotate over these stable identities; only the existing
        # explicit phase-retry path may select the next seat.
        self._session_adapter_bindings: Dict[
            str, Dict[str, "LLMProviderAdapter"]
        ] = {}
        self._session_adapter_orders: Dict[str, List["LLMProviderAdapter"]] = {}
        # H1 Hybrid ledger: optional post-finalization observation only. It is
        # deliberately absent from SessionState/FinalResponse and cannot affect
        # canonical decisions. Capture failures stay on this bounded diagnostic
        # side channel and are never promoted to answer authority.
        self.hybrid_shadow = hybrid_shadow
        self._hybrid_shadow_diagnostics: Dict[str, List[str]] = {}

    def hybrid_shadow_failures(self, session_id: str) -> Tuple[str, ...]:
        """Bounded observer-only diagnostics; never part of canonical state."""
        return tuple(self._hybrid_shadow_diagnostics.get(session_id, ()))

    def _capture_hybrid_shadow(
        self, state: SessionState, final: FinalResponse,
    ) -> None:
        """Capture after canonical finalization, isolated from every authority path."""
        if self.hybrid_shadow is None:
            return
        try:
            provider_catalog = self._council_roster() if self.registry is not None else ()
            self.hybrid_shadow.capture_session(
                state, final, provider_catalog=provider_catalog,
            )
        except Exception as exc:
            diagnostics = self._hybrid_shadow_diagnostics.setdefault(
                state.session_id, [],
            )
            if len(diagnostics) < 3:
                diagnostics.append(type(exc).__name__)

    def _phases_for_mode(self) -> List[DialogPhase]:
        """Phases to shadow-score given the configured mode ([] when OFF)."""
        mode = self.shadow_scoring_mode
        if mode == ShadowScoringMode.OFF:
            return []
        if mode == ShadowScoringMode.SYNTHESIS_ONLY:
            return [DialogPhase.SYNTHESIS]
        if mode == ShadowScoringMode.SAMPLED:
            return [DialogPhase.OPENING, DialogPhase.SYNTHESIS]
        return list(SCORED_PHASES)   # ALL_PHASES

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
        if self.registry is not None:
            self._bind_session_adapters(state)
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
          2. One AgentTask is built per assigned (agent, role); each is sent to
             that logical agent's deterministic session-bound provider seat.
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

        async def _one(agent_id: str, role: AgentRole) -> "ProviderResponse":
            adapter = self._adapter_for_agent(session_state, agent_id)
            task = self._build_round_task(session_state, agent_id, role, phase)
            agent_state = session_state.agent_states.get(
                agent_id,
                AgentState(agent_id=agent_id, primary_role=role, assigned_role=role),
            )
            return await self.registry.run_adapter(
                adapter, task, agent_state, timeout_seconds
            )

        responses = list(await asyncio.gather(
            *(_one(aid, role) for aid, role in items)
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

    # ── Phase 8C: full registry-backed mock session ───────────────────────────

    def _council_roster(self) -> List[Dict[str, str]]:
        """PUBLIC panel composition: which model/company holds each seat. This is
        deliberation-context info only — judging tasks never receive it."""
        from .reasoning_prompts import model_company
        roster = []
        for a in (self._healthy_adapters() if self.registry else []):
            model = getattr(a, "model", None) or "mock"
            roster.append({"seat": a.provider_id, "model": model,
                           "company": model_company(model)})
        return roster

    def _provider_label(self, provider_id: Optional[str]) -> str:
        """'model (company)' label for the seat that produced a move."""
        from .reasoning_prompts import model_company
        if not provider_id or not self.registry:
            return "unattributed"
        for a in self.registry.all_adapters():
            if a.provider_id == provider_id:
                model = getattr(a, "model", None) or "mock"
                return f"{model} ({model_company(model)})"
        return "unattributed"

    def _dialogue_transcript(self, state: SessionState) -> List[Dict[str, Any]]:
        """The WHOLE dialogue so far, in order, with speaker attribution — so each
        agent reasons over the full flow before its next move. Public moves only;
        never scores/leaderboard/audit."""
        return [{
            "phase": m.phase.value,
            "role": m.role.value,
            "by": self._provider_label(m.provider_id),
            "content": m.content,
        } for m in state.moves]

    def _registry_phase_context(
        self, state: SessionState, phase: DialogPhase, agent_id: str,
    ) -> Dict[str, Any]:
        """Build the per-phase context for a registry-driven task (minimal-awareness
        safe — no scores/leaderboard). Every deliberation phase carries the council
        roster (who is in the room) and the full dialogue_so_far transcript."""
        base: Dict[str, Any] = {
            "council_roster": self._council_roster(),
            "dialogue_so_far": self._dialogue_transcript(state),
        }
        asked = self.socratic_questions(state)
        if asked and phase is not DialogPhase.OPENING:
            base["socratic_questions_so_far"] = asked
        # Phase 13: PUBLIC lessons from prior ratified dialogues on related
        # questions (never scores/identities) — the council builds on its past.
        # Phase 14: prefer the per-session cache (AI-ranked when ai_learning).
        if self.lesson_store is not None:
            cached = self._session_lessons.get(state.session_id)
            lessons = cached[0] if cached else self.lesson_store.relevant(state.question, k=3)
            if lessons:
                base["lessons_from_prior_dialogues"] = lessons
            # Phase 13D: the council's own advice to its future self (process
            # meta-reflection) — general guidance, not question-specific.
            guidance = getattr(self.lesson_store, "process_guidance", lambda k=2: [])()
            if guidance:
                base["process_lessons_from_past_dialogues"] = guidance
        # OpenClaw Memory Lessons: inject relevant behavioral guidance into
        # deliberation contexts only. The lessons are external, auditable, and
        # sanitized — agents see guidance text, never scores or match reasons.
        if self.openclaw_lessons is not None:
            from .openclaw_memory import retrieve_lessons, render_memory_lessons_block
            retrieved = retrieve_lessons(
                self.openclaw_lessons,
                task_text=state.question,
                phase=phase,
            )
            if retrieved:
                base["openclaw_memory_lessons"] = render_memory_lessons_block(retrieved)
                # Injected-context ledger: record what ACTUALLY entered this
                # context (per phase/agent), so the audit reports reality —
                # never a re-run of retrieval that may disagree with it.
                self._injected_lessons.setdefault(state.session_id, []).append({
                    "phase": phase.value,
                    "agent_id": agent_id,
                    "lesson_ids": [r.lesson_id for r in retrieved],
                })
        specific = self._phase_specific_context(state, phase, agent_id)
        base.update(specific)
        return base

    def _phase_specific_context(
        self, state: SessionState, phase: DialogPhase, agent_id: str,
    ) -> Dict[str, Any]:
        """Phase-targeted extracts (kept alongside the full transcript so each role
        sees BOTH the whole flow and the material it must directly engage)."""
        if phase == DialogPhase.OPENING:
            # Which question the task admits, decided by the same reducer the
            # checker uses. The council is told the SHAPE to ask for, never a
            # solution or a solution count — the mandate carries neither.
            regime = self._socratic_regime(state)
            aim = (SOCRATIC_AIM_CONSTRAINT if regime == "finite_constraint"
                   else SOCRATIC_AIM_OPEN)
            return {"socratic_question_mandate":
                    SOCRATIC_OPENING_MANDATE + "\n\n" + aim}
        if phase == DialogPhase.INITIAL_RESPONSE:
            return {"original_question": state.question,
                    "socratic_opening_question": self._socratic_opening(state)}
        if phase == DialogPhase.ELENCHUS:
            if self._role_in_phase(state, phase, agent_id) is AgentRole.SOCRATES:
                # He is asking, not attacking. The escalation mandates below are
                # written for a critic and would turn the question into one.
                # Everything here already happened publicly; nothing from the
                # checker, the scores or the release reaches this task.
                return {
                    "socratic_followup_mandate": SOCRATIC_FOLLOWUP_MANDATE,
                    "socratic_opening_question": self._socratic_opening(state),
                    "public_commitments": self.public_commitments(state),
                    "elenchus_critiques": self._public_critiques(state),
                    "public_disagreements": self._public_disagreements(state),
                    "aporia_records": [a.to_dict() for a in self.aporia_records(state)],
                    "initial_responses": [
                        {"role": m.role.value, "content": m.content}
                        for m in state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)],
                }
            # The critic must know what hidden assumption Socrates targeted —
            # otherwise the elenchus cannot press where the dialogue is pointed.
            ctx: Dict[str, Any] = {
                "socratic_opening_question": self._socratic_opening(state),
                "initial_responses": [
                    {"role": m.role.value, "content": m.content}
                    for m in state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)],
            }
            # Phase 14 — Confidence-Adaptive Dialectic: uniform HIGH confidence is
            # exactly where herding hides → escalate to a devil's-advocate mandate;
            # uniform LOW confidence → map the uncertainty honestly instead of
            # forcing an answer. Trigger is mechanical (confidence metadata only).
            adaptive = self._adaptive_dialectic(state)
            if adaptive["devils_advocate_triggered"]:
                ctx["devils_advocate_mandate"] = (
                    "ESCALATION: every initial response arrived with uniformly HIGH "
                    f"confidence (mean {adaptive['initial_mean_confidence']}). Confident "
                    "agreement is precisely where collective error hides. Your mandate "
                    "this round: construct the STRONGEST possible case AGAINST the "
                    "emerging consensus — attack its load-bearing assumption directly. "
                    "If the consensus survives your best attack, it has earned its "
                    "confidence; do not manufacture a fake objection if none exists.")
            elif adaptive["uncertainty_mode_triggered"]:
                ctx["uncertainty_mapping_mandate"] = (
                    "The council's initial responses show uniformly LOW confidence "
                    f"(mean {adaptive['initial_mean_confidence']}). Do not force a "
                    "verdict this round: your mandate is to MAP the uncertainty — "
                    "identify exactly what is unknown, what evidence would settle it, "
                    "and which sub-questions are answerable now.")
            elif adaptive["confidence_disagreement_triggered"]:
                ctx["confidence_disagreement_mandate"] = (
                    "CALIBRATION DISAGREEMENT: the council disagrees about how certain "
                    f"to BE (confidence std {adaptive['initial_confidence_std']}). Some "
                    "seats are confident where others are not — that gap IS the "
                    "epistemic signal. Your mandate: locate exactly which premise the "
                    "confident and unconfident responses treat differently, and test "
                    "that premise directly.")
            elif adaptive["low_diversity_triggered"]:
                ctx["low_diversity_alert"] = (
                    "DIVERSITY ALERT: the initial responses are nearly IDENTICAL in "
                    f"content (diversity {adaptive['response_diversity']}). Agreement "
                    "between similar answers is not independent evidence — it may be "
                    "herding. Your mandate: find the angle every response missed, and "
                    "press the shared assumption they all took for granted.")
            return ctx
        if phase == DialogPhase.REFLECTION:
            mine = next((m for m in state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)
                         if m.agent_id == agent_id), None)
            latest = self._latest_socratic_question(state)
            return {
                "my_initial_response": mine.content if mine else {},
                # A critique attacks; a question asks. Bundling them taught the
                # reflector to treat the question as one more objection.
                "critiques_from_council": self._public_critiques(state),
                "socratic_question_to_answer": latest,
                "current_public_commitments": self.public_commitments(state),
            }
        if phase == DialogPhase.RECONSTRUCTION:
            return {
                "reflected_positions": [m.content for m in state.moves_for_phase(DialogPhase.REFLECTION)],
                "critiques": [m.content for m in state.moves_for_phase(DialogPhase.ELENCHUS)],
            }
        if phase == DialogPhase.SYNTHESIS:
            # The synthesis writes crucial_stress_test / blind_spots — it MUST see
            # the actual objections raised (else the dialectic's work is discarded
            # at the last mile and the stress test is invented, not earned).
            return {
                "socratic_opening_question": self._socratic_opening(state),
                "reconstructed_positions": [m.content for m in state.moves_for_phase(DialogPhase.RECONSTRUCTION)],
                "reflected_positions": [m.content for m in state.moves_for_phase(DialogPhase.REFLECTION)],
                "critiques_raised": [m.content for m in state.moves_for_phase(DialogPhase.ELENCHUS)],
            }
        return {}

    def _role_in_phase(self, state: SessionState, phase: DialogPhase,
                       agent_id: str) -> Optional[AgentRole]:
        """Which role this agent holds this phase. Pure and cheap to recompute."""
        return self._registry_phase_assignment(state, phase).get(agent_id)

    def _screen_socratic_move(self, state: SessionState, task: AgentTask,
                              resp: "ProviderResponse") -> Optional[str]:
        """Refuse a Socratic question that hands over an answer. None = accepted.

        Mechanical where a mechanical check exists and silent where it does not:
        an open-domain question reports NOT_APPLICABLE rather than a fabricated
        clean bill of health, and no model is asked to certify that no leak
        occurred.
        """
        content = resp.parsed_move.content
        question = str(content.get("question") or "") if isinstance(content, dict) else ""
        prior = [str(m.content) for m in state.moves]
        check, why = check_answer_injection(question, state.question, prior)

        row: Dict[str, Any] = {
            "phase": task.phase.value,
            "cycle": state.round_number,
            "provider_id": resp.provider_id,
            "question": question[:400],
            "operator": (read_operator(content).value
                         if read_operator(content) else None),
            "inquiry_state": (read_inquiry_state(content).value
                              if read_inquiry_state(content) else None),
            "injection_check": check.value,
            "injection_detail": why,
            "self_declared_new_proposition": (
                bool(content.get("introduces_new_proposition"))
                if isinstance(content, dict) else None),
        }
        if task.phase is not DialogPhase.OPENING:
            refs = parse_grounding(content.get("grounded_in")
                                   if isinstance(content, dict) else None)
            resolved, unresolved = resolve_grounding(refs, self._public_ids(state))
            row["grounded_in_resolved"] = [{"ref_type": t, "ref_id": i}
                                           for t, i in resolved]
            row["grounded_in_unresolved"] = [{"ref_type": t, "ref_id": i}
                                             for t, i in unresolved]
            row["is_grounded"] = bool(resolved)
        self._socratic_audit_rows.setdefault(state.session_id, []).append(row)

        if check is InjectionCheck.ANSWER_INJECTION_DETECTED:
            return why
        aporia = aporia_from_content(
            content, state.round_number,
            {c.commitment_id for c in self.commitment_ledger(state)})
        if aporia is not None:
            self._aporia.setdefault(state.session_id, []).append(aporia)
        return None

    def _public_ids(self, state: SessionState) -> Dict[str, set]:
        """Ids that already existed publicly when this task was built."""
        return {
            "commitment": {c.commitment_id for c in self.commitment_ledger(state)},
            "critique": {c["critique_id"] for c in self._public_critiques(state)},
            "aporia": {a.aporia_id for a in self.aporia_records(state)},
            "socratic_question": {m.move_id for m in self._socratic_moves(state)},
        }

    def _harvest_commitments(self, state: SessionState, phase: DialogPhase) -> None:
        """Read declared commitments into the append-only ledger.

        Declared, never inferred: a model's reading of what another model meant
        is not a fact about what it committed to.
        """
        ledger = self._commitments.setdefault(state.session_id, [])
        seen = {c.source_move_id for c in ledger}
        known = {c.commitment_id for c in ledger}
        for move in state.moves_for_phase(phase):
            if move.move_id in seen:
                continue
            if move.task_kind is TaskKind.INITIAL_RESPONSE:
                ledger.extend(commitments_from_move(
                    move.move_id, state.round_number, move.content,
                    provider_id=move.provider_id))
            elif move.task_kind is TaskKind.REFLECTION_REVISION:
                ledger.extend(commitment_events_from_reflection(
                    move.move_id, state.round_number, move.content, known,
                    provider_id=move.provider_id))

    def _socratic_followups_made(self, state: SessionState) -> int:
        return sum(1 for m in self._socratic_moves(state)
                   if m.phase is not DialogPhase.OPENING)

    def another_socratic_cycle(self, state: SessionState) -> Tuple[bool, str]:
        """CED decides, mechanically. Socrates recommends and is not obeyed.

        Aporia is deliberately not a stop condition: a collapsed position is
        usually where the next question belongs, not where the inquiry ends.
        """
        used = self._socratic_followups_made(state)
        if used >= self.max_socratic_followups:
            return False, f"max_socratic_followups={self.max_socratic_followups} reached"
        asked = [m for m in self._socratic_moves(state)
                 if m.phase is not DialogPhase.OPENING]
        if not asked:
            return False, "no valid Socratic question was produced this cycle"
        state_hint = read_inquiry_state(asked[-1].content)
        if state_hint is not InquiryState.CONTINUE_INQUIRY:
            return False, f"inquiry_state={state_hint.value if state_hint else 'absent'}"
        return True, "continue_inquiry within bound"

    def _socratic_moves(self, state: SessionState) -> List["AgentMove"]:
        return [m for m in state.moves if m.role is AgentRole.SOCRATES]

    def _latest_socratic_question(self, state: SessionState) -> str:
        asked = self._socratic_moves(state)
        if not asked:
            return ""
        content = asked[-1].content if isinstance(asked[-1].content, dict) else {}
        return str(content.get("question") or "")

    def _public_critiques(self, state: SessionState) -> List[Dict[str, Any]]:
        """Objections actually raised. Socratic questions are not among them."""
        return [{"critique_id": m.move_id, "role": m.role.value, "content": m.content}
                for m in state.moves_for_phase(DialogPhase.ELENCHUS)
                if m.role is not AgentRole.SOCRATES]

    def commitment_ledger(self, state: SessionState) -> List[CommitmentRecord]:
        """The append-only history of what this council put its name to."""
        return list(self._commitments.get(state.session_id, []))

    def public_commitments(self, state: SessionState) -> List[Dict[str, Any]]:
        """The positions still standing, derived without editing the history."""
        return [c.to_dict() for c in live_commitments(self.commitment_ledger(state))]

    def _public_disagreements(self, state: SessionState) -> List[Dict[str, Any]]:
        """Where two providers hold live commitments and are not the same voice.

        Deliberately shallow: this reports who is standing where, and makes no
        claim about which of them is right or even that they truly conflict.
        Deciding that is the council's work, prompted by a question.
        """
        by_provider: Dict[str, List[str]] = {}
        for record in live_commitments(self.commitment_ledger(state)):
            if record.provider_id:
                by_provider.setdefault(record.provider_id, []).append(record.claim)
        if len(by_provider) < 2:
            return []
        return [{"provider": self._provider_label(pid), "claims": claims}
                for pid, claims in sorted(by_provider.items())]

    def aporia_records(self, state: SessionState) -> List[AporiaRecord]:
        return list(self._aporia.get(state.session_id, []))

    def socratic_questions(self, state: SessionState) -> List[Dict[str, Any]]:
        """Every question Socrates has put, in order. Awareness across the whole
        dialogue rather than one shot at the start."""
        asked: List[Dict[str, Any]] = []
        for move in state.moves:
            if move.role is not AgentRole.SOCRATES:
                continue
            content = move.content if isinstance(move.content, dict) else {}
            asked.append({"phase": move.phase.value,
                          "question": str(content.get("question") or "")})
        return asked

    def _socratic_regime(self, state: SessionState) -> str:
        """Which kind of question this task admits. Deterministic and free.

        A task that reduces to explicit finite constraints has nothing hidden to
        expose; one that does not is where classical elenchus belongs. The
        reduction is the checker's, so the two stay in step: if the checker can
        model the task, the opening is asked to probe the answer space rather
        than to look for an assumption that is printed on the page.
        """
        model, _reason = model_task(state.question)
        return "finite_constraint" if model is not None else "open"

    def _socratic_audit(self, state: SessionState) -> Dict[str, Any]:
        """What the opening actually was. Observability only — decides nothing.

        The rival candidate is run through the checker so the audit can say
        whether the question pointed at a real near miss or a phantom. That
        result is never shown to the council and never reaches a claim: a
        model's guess must not become evidence, and a probe is a guess.
        """
        opening = state.moves_for_phase(DialogPhase.OPENING)
        regime = self._socratic_regime(state)
        audit: Dict[str, Any] = {"regime": regime, "asked": bool(opening)}
        if not opening:
            return audit
        content = opening[0].content if isinstance(opening[0].content, dict) else {}
        audit["question"] = str(content.get("question") or "")[:400]

        if regime == "finite_constraint":
            rival = content.get("rival_candidate")
            audit["rival_candidate"] = rival if isinstance(rival, str) else None
            audit["discriminating_rule"] = content.get("discriminating_rule")
            if isinstance(rival, str) and rival.strip():
                probe = evaluate_candidate(state.question, f"The order is {rival}")
                audit["rival_checker_result"] = probe.result.value
                audit["rival_violated"] = list(probe.violated_constraints)
                # A near miss is what was asked for; the true answer or an
                # unreadable string means the question did not do its job.
                audit["rival_is_a_near_miss"] = (
                    probe.result is CheckerStatus.INVALID
                    and len(probe.violated_constraints) == 1)
        else:
            one = str(content.get("if_answered_one_way") or "").strip()
            other = str(content.get("if_answered_another_way") or "").strip()
            audit["branches_given"] = bool(one and other)
            # Identical consequences mean the answer cannot change the
            # conclusion, which is the definition of a wasted question.
            audit["branches_discriminate"] = bool(one and other and one != other)
        return audit

    @staticmethod
    def _socratic_opening(state: SessionState) -> str:
        opening = state.moves_for_phase(DialogPhase.OPENING)
        if not opening:
            return state.question
        c = opening[0].content
        return str(c.get("question") or c.get("socratic_question") or state.question)

    def _registry_phase_assignment(
        self, state: SessionState, phase: DialogPhase,
    ) -> Dict[str, AgentRole]:
        """Deterministic role assignment for a registry-driven phase."""
        if phase == DialogPhase.SYNTHESIS:
            return {a.agent_id: AgentRole.SYNTHESIZER for a in self.agents}
        if phase == DialogPhase.REFLECTION:
            responders = [m.agent_id for m in state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)]
            return {aid: AgentRole.REFLECTOR for aid in responders}
        return self.assign_roles_for_phase(state, phase, state.round_number)

    def _healthy_adapters(self) -> List["LLMProviderAdapter"]:
        """Phase 16 self-healing: quarantined seats (chronic, evidence-gated
        failures per SeatHealthTracker) are actually EXCLUDED from deliberation —
        but only while the council still meets its minimum. Better a shaky seat
        than no quorum; the exclusion is mechanical and audited."""
        adapters = self.registry.available_adapters()
        if self.seat_health is None:
            return adapters
        quarantined = set(self.seat_health.quarantined())
        if not quarantined:
            return adapters
        healthy = [a for a in adapters if a.provider_id not in quarantined]
        if len(healthy) >= self.registry.minimum_providers:
            return healthy
        return adapters

    def _quarantine_exclusions(self) -> List[str]:
        """Seat ids actually excluded right now (for the audit)."""
        if self.seat_health is None or self.registry is None:
            return []
        all_ids = [a.provider_id for a in self.registry.available_adapters()]
        healthy_ids = {a.provider_id for a in self._healthy_adapters()}
        return sorted(s for s in all_ids if s not in healthy_ids)

    def _seat_ranking_key(self, provider_id: str, topic: str):
        """Deterministic ranking key: unrated seats FIRST (a new seat deserves a
        chance — same philosophy as SeatHealthTracker.rank_seats), then among
        seats with a track record, higher topic skill and lower failure rate
        win. Ties (including 'no data at all', the common early-session case)
        are broken by Python's STABLE sort, which preserves the original
        registration/round-robin order — so with no analytics yet, routing is
        byte-for-byte the pre-Phase-21 order, not an arbitrary string sort."""
        skill = self.topic_skill.profile(provider_id).get(topic) if self.topic_skill else None
        stats = self.seat_health.stats().get(provider_id) if self.seat_health else None
        failure_rate = stats.failure_rate if (stats is not None and stats.tasks) else None
        has_data = skill is not None or failure_rate is not None
        return (1 if has_data else 0,
                -(skill if skill is not None else 0.0),
                failure_rate if failure_rate is not None else 0.0)

    def _ranked_adapters(self, state: SessionState) -> List["LLMProviderAdapter"]:
        """
        Phase 21 — analytics-informed seat routing: when a phase needs FEWER
        provider seats than are healthy and available, prefer the ones CED's own
        accumulated topic-skill + reliability analytics rate best for THIS
        question's topic — mechanical, from aggregate numbers only, never from
        content. With no trackers attached this is a no-op (returns
        `_healthy_adapters()` unchanged — the original round-robin order).
        Role assignment (who plays which Socratic role) is untouched: this only
        changes WHICH PROVIDER executes an already-assigned agent's task.
        """
        adapters = self._healthy_adapters()
        if self.topic_skill is None and self.seat_health is None:
            return adapters
        from .topic import classify_topic
        topic = classify_topic(state.question).value
        return sorted(adapters, key=lambda a: self._seat_ranking_key(a.provider_id, topic))

    def _bind_session_adapters(self, state: SessionState) -> None:
        """Bind each logical agent to one ranked provider seat for this session.

        The ranked adapter order preserves the existing analytics-informed seat
        preference. The binding is then frozen, so phase-local active-agent lists
        cannot restart physical routing from adapter slot zero.
        """
        adapters = self._ranked_adapters(state)
        self._session_adapter_orders[state.session_id] = adapters
        self._session_adapter_bindings[state.session_id] = (
            {
                agent_id: adapters[index % len(adapters)]
                for index, agent_id in enumerate(self._ordered_agent_ids())
            }
            if adapters else {}
        )

    def _adapter_for_agent(
        self, state: SessionState, agent_id: str, failover_offset: int = 0,
    ) -> "LLMProviderAdapter":
        """Resolve a session-stable provider seat for one logical agent.

        ``failover_offset`` is used only by the existing bounded phase-retry
        mechanism. An offset of one selects the next physical seat in the frozen
        session order; ordinary phase execution always uses zero.
        """
        if state.session_id not in self._session_adapter_bindings:
            self._bind_session_adapters(state)
        order = self._session_adapter_orders.get(state.session_id, [])
        binding = self._session_adapter_bindings.get(state.session_id, {})
        adapter = binding.get(agent_id)
        if not order or adapter is None:
            raise RuntimeError(
                f"No provider adapter is bound to agent {agent_id!r} "
                f"for session {state.session_id!r}."
            )
        base_index = next(
            index for index, candidate in enumerate(order) if candidate is adapter
        )
        return order[(base_index + failover_offset) % len(order)]

    def _distinct_retry_offset(
        self, state: SessionState, agent_id: str, taken: Set[str],
    ) -> Optional[int]:
        """First failover offset landing on a seat no sibling slot is using.

        Returns None when every seat in the frozen order is already serving this
        phase. Rerouting onto a busy seat would leave two slots authored by one
        provider, which reads as a full council and is not one.
        """
        order = self._session_adapter_orders.get(state.session_id, [])
        for offset in range(1, len(order)):
            candidate = self._adapter_for_agent(state, agent_id,
                                                failover_offset=offset)
            if candidate.provider_id not in taken:
                return offset
        return None

    async def _run_registry_phase(
        self, state: SessionState, phase: DialogPhase,
        timeout_seconds: Optional[float],
    ) -> CouncilRoundResult:
        """
        Drive ONE deliberation phase through the registry: one task per
        deterministically-assigned agent/role, validated into moves, with
        per-phase quorum. Move ids come from task identity (NOT completion order).
        """
        state.advance_phase(phase)
        assignment = self._registry_phase_assignment(state, phase)
        self._apply_phase_roles(state, phase, assignment)
        items = sorted(assignment.items())
        adapters = self._ranked_adapters(state)   # Phase 21: analytics-informed routing
        phase_task_kind = PHASE_TASK_KIND.get(phase, TaskKind.INITIAL_RESPONSE)
        want_sections = (phase == DialogPhase.SYNTHESIS)

        def _build_task(agent_id: str, role: AgentRole, slot: int,
                        attempt: int = 0) -> AgentTask:
            schema: Dict[str, Any] = {"_role": role.value, "_question": state.question}
            if want_sections:
                schema["_sections"] = True
            return AgentTask(
                session_id=state.session_id, agent_id=agent_id, role=role, phase=phase,
                question=state.question,
                context=self._registry_phase_context(state, phase, agent_id),
                output_schema=schema, round_number=state.round_number,
                task_kind=ROLE_TASK_KIND.get(role, phase_task_kind),
                slot_index=slot, attempt_index=attempt,
            )

        async def _one(slot: int, agent_id: str, role: AgentRole,
                       attempt: int = 0, offset: int = 0):
            task = _build_task(agent_id, role, slot, attempt)
            agent_state = state.agent_states.get(
                agent_id, AgentState(agent_id=agent_id, primary_role=role, assigned_role=role))
            adapter = self._adapter_for_agent(state, agent_id, failover_offset=offset)
            resp = await self.registry.run_adapter(adapter, task, agent_state, timeout_seconds)
            return task, resp

        dispatch: List[Dict[str, Any]] = []

        def _absorb(pairs) -> List[ProviderResponse]:
            """Validate responses into moves + task-log entries (no fabrication)."""
            out: List[ProviderResponse] = []
            for task, resp in pairs:
                out.append(resp)
                if (resp.ok and resp.parsed_move is not None
                        and task.task_kind is TaskKind.SOCRATIC_QUESTION):
                    verdict = self._screen_socratic_move(state, task, resp)
                    if verdict is not None:
                        # Answer injection. The question is refused before it can
                        # anchor anyone; the phase continues without it.
                        self._record_task_log(state, task, None,
                                              provider_id=resp.provider_id,
                                              provider_status=resp.status)
                        continue
                # Who actually served which slot. Recorded from the dispatch
                # itself rather than reconstructed from moves afterwards, so a
                # rerouted retry is visible as a reroute.
                served = next((a for a in self.registry.all_adapters()
                               if a.provider_id == resp.provider_id), None)
                dispatch.append({
                    "slot_index": task.slot_index,
                    "logical_agent_id": task.agent_id,
                    "assigned_role": task.role.value,
                    "provider_id": resp.provider_id,
                    "model_id": getattr(served, "model",
                                        getattr(served, "model_id", None)),
                    "attempt_index": task.attempt_index,
                    "retry": task.attempt_index > 0,
                    "ok": resp.ok,
                })
                if resp.ok:
                    move = resp.parsed_move
                    # Deterministic identity — independent of which provider/when.
                    move.move_id = self._deterministic_move_id(
                        state, task.agent_id, phase, task.role,
                        task.task_kind, task.slot_index, task.attempt_index)
                    move.task_kind = task.task_kind
                    move.slot_index = task.slot_index
                    move.attempt_index = task.attempt_index
                    move.provider_id = resp.provider_id   # producer (no-self-scoring)
                    state.moves.append(move)
                    self._record_task_log(state, task, move.move_id,
                                          provider_id=resp.provider_id,
                                          provider_status=resp.status)
                else:
                    # Failed provider → task trace only, NO fabricated move.
                    self._record_task_log(state, task, None,
                                          provider_id=resp.provider_id,
                                          provider_status=resp.status)
            return out

        # Two waves, one await between them. Socrates asks last so the critiques
        # are already public when his task is built — a question asked at the
        # same moment as the objections cannot be grounded in them. Everything
        # else about dispatch, binding, quorum and retry is untouched.
        slots = [(i, aid, role) for i, (aid, role) in enumerate(items)]
        wave_a = [x for x in slots if x[2] is not AgentRole.SOCRATES]
        wave_b = [x for x in slots if x[2] is AgentRole.SOCRATES]

        pairs = list(await asyncio.gather(
            *(_one(i, aid, role) for i, aid, role in wave_a)))
        responses = _absorb(pairs)
        if wave_b:
            later = list(await asyncio.gather(
                *(_one(i, aid, role) for i, aid, role in wave_b)))
            responses = responses + _absorb(later)
            pairs = pairs + later
        effective_quorum = min(self.registry.quorum_for_assembly, len(items)) if items else 0

        # Phase 20 — phase rescue (opt-in): a transient failure in one phase must
        # not destroy the whole session (and everything already paid for). Retry
        # ONLY the failed slots, ONCE, REROUTED to the next seat (offset+1), with
        # attempt_index=1 so move identity stays deterministic and duplicate-free.
        # All attempts remain in the task_log — nothing is hidden or rewritten.
        ok_count = sum(1 for r in responses if r.ok)
        if (self.phase_retry and adapters and items
                and ok_count < effective_quorum):
            failed = [(t.slot_index, items[t.slot_index][0], items[t.slot_index][1])
                      for t, r in pairs if not r.ok]
            # Seats already serving this phase: the successful siblings, plus
            # each reroute as it is planned, so two failed slots cannot both be
            # sent to the same free seat.
            taken = {r.provider_id for _, r in pairs if r.ok}
            plan: List[Tuple[int, str, AgentRole, int]] = []
            degraded: List[int] = []
            for slot, aid, role in failed:
                offset = self._distinct_retry_offset(state, aid, taken)
                if offset is None:
                    # Nowhere distinct to go — a two-seat council whose sibling
                    # already holds the only alternative. The reroute proceeds
                    # so the phase can still be rescued, and the duplication is
                    # recorded rather than left to be discovered in a trace.
                    # Independence is already unreachable at this council size;
                    # what must not happen is losing it silently at a size where
                    # it was available, which is the case above.
                    offset, was_degraded = 1, True
                else:
                    was_degraded = False
                if was_degraded:
                    degraded.append(slot)
                taken.add(self._adapter_for_agent(
                    state, aid, failover_offset=offset).provider_id)
                plan.append((slot, aid, role, offset))
            retry_pairs = list(await asyncio.gather(
                *(_one(slot, aid, role, attempt=1, offset=offset)
                  for slot, aid, role, offset in plan)))
            retry_responses = _absorb(retry_pairs)
            merged = [r for _, r in pairs if r.ok] + retry_responses
            rescued = sum(1 for r in merged if r.ok) >= effective_quorum
            self._phase_retries.setdefault(state.session_id, []).append({
                "phase": phase.value,
                "failed_slots": [slot for slot, _, _ in failed],
                "retried_slots": [slot for slot, _, _, _ in plan],
                "degraded_duplicate_slots": degraded,
                "degraded_reason": ("no distinct healthy seat; the sibling's "
                                    "provider was reused" if degraded else None),
                "first_failed_providers": [r.provider_id for _, r in pairs if not r.ok],
                "retry_ok_providers": [r.provider_id for r in retry_responses if r.ok],
                "rescued": rescued,
            })
            responses = merged

        self._phase_dispatch.setdefault(state.session_id, []).append({
            "phase": phase.value, "slots": dispatch,
        })
        self._harvest_commitments(state, phase)
        result = self.registry.finalize_round(responses, quorum=effective_quorum)
        state.registry_rounds.append(result)
        return result

    async def run_registry_session(
        self,
        question: str,
        session_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> FinalResponse:
        """
        Phase 8C — full registry-backed mock session (NO real API calls).

        Drives every deliberation phase through CouncilProviderRegistry mock
        providers (deterministic roles, per-phase quorum, JSON/schema validation,
        failure/timeout recording), then runs the existing scoring → blind
        assembly → ratification machinery. Additive: does not replace run_session.

        Returns a FinalResponse whose audit_summary separates provider status,
        registry phase rounds, task_log summary and shadow-scoring mode. If the
        registry is not ready (or a phase fails quorum) a safe non-proceeding
        FinalResponse is returned — never a crash, never a fake answer.
        """
        if self.registry is None:
            raise RuntimeError(
                "run_registry_session requires a CouncilProviderRegistry "
                "(pass registry=... to CEDOrchestrator)."
            )
        state = self.create_session(question, session_id=session_id)
        sid = state.session_id

        ready, warning = self.registry.assess_readiness()
        if not ready:
            return self._registry_fallback_final(state, warning, blocked_phase=None)

        # Phase 14: resolve relevant lessons ONCE per session (AI-ranked when
        # ai_learning; keyword otherwise) and cache for every phase context.
        if self.lesson_store is not None:
            self._session_lessons[sid] = await self._resolve_session_lessons(state)

        phase_results: List[Tuple[DialogPhase, CouncilRoundResult]] = []
        cycle_log: List[Dict[str, Any]] = []
        for phase in REGISTRY_SESSION_PHASES:
            result = await self._run_registry_phase(state, phase, timeout_seconds)
            phase_results.append((phase, result))
            if not result.proceed:
                return self._registry_fallback_final(state, result.warning, blocked_phase=phase,
                                                     phase_results=phase_results)
            if phase is not DialogPhase.REFLECTION:
                continue
            # One dialectical cycle has closed: the council committed, was
            # examined, was asked, and answered. CED — not Socrates — decides
            # whether the next question would still do work.
            while True:
                allowed, why = self.another_socratic_cycle(state)
                cycle_log.append({"after_cycle": state.round_number,
                                  "continue": allowed, "reason": why})
                if not allowed:
                    break
                state.round_number += 1
                for cycle_phase in SOCRATIC_CYCLE_PHASES:
                    result = await self._run_registry_phase(
                        state, cycle_phase, timeout_seconds)
                    phase_results.append((cycle_phase, result))
                    if not result.proceed:
                        return self._registry_fallback_final(
                            state, result.warning, blocked_phase=cycle_phase,
                            phase_results=phase_results)
        self._cycle_log[sid] = cycle_log

        # Downstream council machinery (reads CED-owned state.moves).
        self.build_section_drafts(sid)
        # Phase 8C.2 — peer scoring ALSO goes through the registry (not self.agents).
        await self.run_registry_shadow_scores(state, timeout_seconds)   # move-level
        await self.score_section_drafts_with_registry(state, timeout_seconds)  # section-level
        # Deliberation Tree Search (opt-in): UCB-selected revision expansions
        # enrich the draft pool BEFORE blind assembly (superset — never worse).
        if self.tree_expansions > 0:
            await self._run_deliberation_tree(state, timeout_seconds)
        self.assemble_sections(sid)

        # Phase 8C.1 — COUNCIL ratification through the registry (no single
        # Final Evaluator monopoly). Deliberation already used the registry above.
        ratification = await self.run_council_ratification(state, timeout_seconds)

        # Phase 19 — ratification repair Option B (opt-in): when the council
        # raises a schema-valid critical block on specific sections, CED swaps
        # each blocked section for its RUNNER-UP draft (peer-score ranking; a
        # purely mechanical selection) and asks the council to ratify AGAIN —
        # bounded by MAX_RATIFICATION_ROUNDS. CED never overrides a block: if no
        # runner-up exists or rounds run out, repair_required stands honestly.
        repair_audit: Dict[str, Any] = {"mode": self.ratification_repair,
                                        "rounds_used": 0, "repairs": [],
                                        "round_statuses": [ratification.status.value]}
        if self.ratification_repair == "runner_up":
            tried: Dict[SectionName, set] = {}
            while (ratification.status == CouncilRatificationStatus.REPAIR_REQUIRED
                   and repair_audit["rounds_used"] < MAX_RATIFICATION_ROUNDS):
                repairs = self._repair_blocked_sections(state, ratification, tried)
                if not repairs:
                    repair_audit["outcome"] = "unrepairable_no_runner_up"
                    break
                repair_audit["repairs"].extend(repairs)
                repair_audit["rounds_used"] += 1
                ratification = await self.run_council_ratification(state, timeout_seconds)
                repair_audit["round_statuses"].append(ratification.status.value)
            if "outcome" not in repair_audit:
                repair_audit["outcome"] = ("repaired_and_ratified"
                                           if ratification.is_ratified()
                                           else ratification.status.value)

        final = self._build_council_final(state, ratification)
        final.audit_summary["ratification_repair"] = repair_audit
        # H7: the governing release authority. Canonical phases, scoring,
        # assembly and ratification are unchanged above; only the final
        # epistemic verdict moves here, from a quality threshold to a
        # decision computed from records.
        await self._apply_governing_release(state, final)

        # Augment the (already CED-owned) audit with Phase 8C provider/registry info.
        final.audit_summary.update(self._registry_session_audit(state, phase_results))
        await self._self_improvement_ingest(state, final)
        self._capture_hybrid_shadow(state, final)
        return final

    def project_governing_state(self, state: SessionState,
                                final: FinalResponse) -> HybridEpistemicState:
        """Project a finalized canonical session into the governing core.

        Assembled sections become claims; elenchus moves and schema-valid
        critical ratification objections become objections in the RAISED state.
        RAISED is deliberate: no verification runs during a canonical session
        yet, so an objection is recorded and unresolved rather than destructive.
        """
        core = HybridEpistemicState(state.session_id, state.question)
        section_claims: Dict[str, str] = {}
        for section in (final.synthesis.sections if final.synthesis else []):
            if section.unresolved:
                continue
            claim_id = _hybrid_id("claim", state.session_id,
                                  section.section_name.value)
            section_claims[section.section_name.value] = claim_id
            core.add_claim(ClaimRecord(
                claim_id=claim_id,
                text=section.content,
                section=section.section_name.value,
                verification_class=VerificationClass.NOT_CURRENTLY_VERIFIABLE,
            ))
        if not section_claims:
            return core

        def _declared(content) -> Optional[str]:
            """A section or claim the objection itself names, or None.

            Only an explicit identifier counts. Nothing is inferred from how
            many agents agreed, how confident they were, or what scored highest
            — those decide nothing here, by construction.
            """
            if not isinstance(content, dict):
                return None
            named = content.get("target_section") or content.get("target_claim_id")
            if not isinstance(named, str):
                return None
            key = named.strip().lower()
            if key in section_claims:
                return section_claims[key]
            if named in set(section_claims.values()):
                return named
            return None

        for move in state.moves:
            if move.phase is not DialogPhase.ELENCHUS:
                continue
            if move.role is AgentRole.SOCRATES:
                continue        # he asked a question; asking is not objecting
            target = _declared(move.content)
            core.add_objection(ObjectionRecord(
                objection_id=_hybrid_id("obj", move.move_id),
                target_claim_id=target or UNMAPPED_TARGET,
                target_provenance=(
                    ObjectionTargetProvenance.DECLARED_IDENTIFIER if target
                    else ObjectionTargetProvenance.UNMAPPED),
                text=str(move.content)[:400],
                # The seat, not the logical agent: verification filters peers by
                # provider_id, and an agent_id never matches one, which silently
                # let a seat corroborate its own objection.
                raised_by=move.provider_id or move.agent_id,
            ))

        def _project_ratification(objection_id: str, named: Optional[str],
                                   text: str, raised_by: Optional[str]) -> None:
            target = section_claims.get(named) if named else None
            core.add_objection(ObjectionRecord(
                objection_id=objection_id,
                target_claim_id=target or UNMAPPED_TARGET,
                target_provenance=(
                    ObjectionTargetProvenance.RATIFICATION_TARGET_SECTION if target
                    else ObjectionTargetProvenance.UNMAPPED),
                text=text or "critical blocking objection",
                raised_by=raised_by,
            ))

        # The council path. `final.ratification_votes` belongs to the legacy
        # single-evaluator session and is empty on every registry run, so for the
        # whole life of this layer the best-targeted objections in the system —
        # the only ones carrying a declared target_section — were the only ones
        # being discarded. A council that returned repair_required was invisible
        # to the layer deciding the release.
        council = (final.audit_summary or {}).get("council_ratification") or {}
        for entry in council.get("attributed_critical_objections") or []:
            if not isinstance(entry, dict):
                continue
            _project_ratification(
                _hybrid_id("obj_rat", str(entry.get("provider_id") or ""),
                           str(entry.get("rationale") or "")),
                entry.get("target_section"),
                str(entry.get("rationale") or ""),
                # The seat, so peer exclusion can keep a ratifier from verifying
                # its own objection.
                entry.get("provider_id") or entry.get("agent_id"))

        # The legacy single-evaluator path, unchanged and still honoured.
        for vote in final.ratification_votes:
            if not vote.is_critical_block():
                continue
            _project_ratification(
                _hybrid_id("obj_rat", vote.voter_agent_id, vote.reason),
                vote.target_section.value if vote.target_section else None,
                vote.reason, vote.voter_agent_id)
        return core

    async def run_objection_verification(
        self, state: SessionState, core, timeout_seconds: Optional[float] = None,
    ) -> Dict[str, str]:
        """Ask peer seats to check each raised objection against the task.

        Every objection is checked by every seat that did not raise it — no
        self-verification, mirroring the no-self-scoring rule. A verdict moves
        an objection only when independent verifiers corroborate each other on
        the same cited span; anything less leaves it unresolved, because this is
        the one path where a model's reading can destroy a correct claim.
        """
        verdicts: Dict[str, str] = {}
        if self.registry is None or not core.objections:
            return verdicts
        adapters = self._healthy_adapters()
        if len(adapters) < 2:                     # corroboration is impossible
            return verdicts

        for objection_id, objection in sorted(core.objections.items()):
            if not objection.is_mapped:
                # It can move no claim whatever the verdict, so paying models to
                # decide it would buy nothing. It stays RAISED and visible.
                continue
            peers = [a for a in adapters if a.provider_id != objection.raised_by]
            if len(peers) < 2:
                continue
            task = AgentTask(
                task_id=f"verify_{objection_id}",
                session_id=state.session_id,
                agent_id=objection.target_claim_id,
                role=AgentRole.FINAL_EVALUATOR,
                phase=DialogPhase.ELENCHUS,
                question=state.question,
                context={"objection_under_test": objection.text,
                         "original_task": core.task_text},
                output_schema={"_role": "__objection_verification__",
                               "_objection": objection_id},
                task_kind=TaskKind.OBJECTION_VERIFICATION,
            )
            agent_state = AgentState(agent_id=objection.target_claim_id,
                                     primary_role=AgentRole.FINAL_EVALUATOR,
                                     assigned_role=AgentRole.FINAL_EVALUATOR)
            responses = await asyncio.gather(*(
                self.registry.run_adapter(a, task, agent_state, timeout_seconds)
                for a in peers))
            records = []
            for adapter, response in zip(peers, responses):
                if not response.ok or response.parsed_move is None:
                    continue
                record = parse_verification_response(
                    response.parsed_move.content,
                    task_text=core.task_text,
                    claim_id=objection.target_claim_id,
                    objection_id=objection_id,
                    verifier_provider_id=adapter.provider_id)
                if record is not None:
                    records.append(record)
            verdict, _reason = apply_verification(core, objection_id, records)
            verdicts[objection_id] = verdict.value
        return verdicts

    def apply_deterministic_checks(self, core) -> Dict[str, Any]:
        """Evaluate each assembled claim against the task, deterministically.

        No model calls and no network: the checker reduces the task itself to
        finite constraints and enumerates. It is the only channel that can put a
        record into a claim's basis, and it declines far more tasks than it
        accepts — a task it cannot represent unambiguously produces nothing,
        which leaves every claim where it was.
        """
        model, reason = model_task(core.task_text)
        if model is None:
            return {"applicable": False, "reason": reason.value}

        summary: Dict[str, Any] = {
            "applicable": True,
            "problem_class": ProblemClass.FINITE_ORDERING.value,
            "entities": list(model.entities),
            "constraints": list(model.constraint_names),
            "solution_count": len(model.solutions),
            "claims": {},
        }
        for claim_id, claim in sorted(core.claims.items()):
            receipt = evaluate_candidate(core.task_text, claim.text)
            entry: Dict[str, Any] = {"result": receipt.result.value,
                                     "reason": receipt.reason}
            if receipt.result is CheckerStatus.VALID:
                entry["unique"] = receipt.candidate_is_unique
                support = receipt_support(receipt, claim_id)
                if support is not None:
                    core.add_evidence(support)
                    entry["receipt"] = receipt.digest()
            elif receipt.result is CheckerStatus.INVALID:
                entry["violated"] = list(receipt.violated_constraints)
                refutation = receipt_refutation(receipt, claim_id, core.task_text)
                if refutation is not None:
                    core.add_verification(refutation)
                    entry["receipt"] = receipt.digest()
            summary["claims"][claim_id] = entry
        return summary

    async def _apply_governing_release(self, state: SessionState,
                                       final: FinalResponse) -> None:
        """Decide the release from records and record it on the response.

        Failure-isolated: if projection raises, the canonical response still
        stands and the audit reports the governing verdict as unavailable rather
        than inventing one.
        """
        legacy = final.epistemic_status.value
        try:
            core = self.project_governing_state(state, final)
            # H3 mid-session verification: peers check each raised objection
            # against the task before anything is frozen. Only corroborated
            # verdicts move an objection; the rest stay unresolved.
            verdicts = await self.run_objection_verification(state, core)
            # The only channel that can produce support, and the cheapest: it
            # runs no models at all.
            checks = self.apply_deterministic_checks(core)
            quality = [ms.score_breakdown.weighted_overall()
                       for ms in state.micro_scores]
            release = freeze_release(
                core,
                assembled_claim_ids=list(core.claims),
                quality_mean=(round(sum(quality) / len(quality), 6)
                              if quality else None),
                legacy_epistemic_status=legacy,
            )
        except Exception as exc:                  # never fabricate a verdict
            final.audit_summary["governing_release"] = {
                "available": False,
                "reason": type(exc).__name__,
                "legacy_epistemic_status": legacy,
                "legacy_epistemic_status_authority": "legacy_non_governing",
            }
            return

        states = set(release.claim_states.values())
        if release.release_decision is ReleaseDecision.RELEASE_SUPPORTED:
            governing = SupportState.SUPPORTED.value
        elif SupportState.FALSIFIED.value in states:
            governing = SupportState.FALSIFIED.value
        elif SupportState.EXTERNAL_EVIDENCE_REQUIRED.value in states:
            governing = SupportState.EXTERNAL_EVIDENCE_REQUIRED.value
        elif SupportState.UNRESOLVED.value in states:
            governing = SupportState.UNRESOLVED.value
        else:
            governing = SupportState.UNSUPPORTED.value

        final.governing_epistemic_status = governing
        final.release_decision = release.release_decision.value
        final.audit_summary["governing_release"] = {
            "available": True,
            # Observability only. Nothing below reads these back; they exist so
            # that "which claim did this objection hold up, and on what
            # authority" is answerable from the audit instead of inferred.
            "objections": [
                {
                    "objection_id": o.objection_id,
                    "target_claim_id": o.target_claim_id,
                    "target_section": (core.claims[o.target_claim_id].section
                                       if o.target_claim_id in core.claims else None),
                    "scope": o.scope.value,
                    "targeting_provenance": o.target_provenance.value,
                    "state": o.state.value,
                    "raised_by": o.raised_by,
                }
                for o in sorted(core.objections.values(),
                                key=lambda x: x.objection_id)
            ],
            "deterministic_checks": checks,
            "release_decision": release.release_decision.value,
            "objection_verdicts": verdicts,
            "governing_epistemic_status": governing,
            "claim_states": release.claim_states,
            "basis_record_ids": release.basis_record_ids,
            "unresolved_record_ids": release.unresolved_record_ids,
            "blocked_reason": release.blocked_reason,
            "frozen_digest": release.frozen_digest,
            "quality_mean": release.quality_mean,
            "legacy_epistemic_status": legacy,
            "legacy_epistemic_status_authority": "legacy_non_governing",
        }

    def _epistemic_consistency(self, state: SessionState) -> Dict[str, Any]:
        """Phase 18: mechanical marker↔confidence consistency check. An agent that
        tags its central claim 'unsubstantiated_claim' yet reports confidence 0.9
        is being epistemically inconsistent — CED records it (never rewrites it)."""
        from .reasoning_prompts import MARKER_CONFIDENCE_BANDS
        tagged = 0
        violations: List[Dict[str, Any]] = []
        for m in state.moves:
            if not m.epistemic_markers:
                continue
            tagged += 1
            marker = m.epistemic_markers[0].value
            ceiling = MARKER_CONFIDENCE_BANDS.get(marker)
            if ceiling is not None and m.confidence > ceiling + 1e-9:
                violations.append({"move_id": m.move_id, "marker": marker,
                                   "confidence": m.confidence, "ceiling": ceiling})
        return {"moves_tagged": tagged, "violations": violations,
                "violation_count": len(violations)}

    def _record_outcome(self, state: SessionState, final: FinalResponse) -> None:
        """Rolling vital-signs record (bounded; CED-owned; hidden from agents)."""
        adaptive = self._adaptive_dialectic(state)
        self._session_outcomes.append({
            "session_id": state.session_id,
            "ratified": bool(final.ratified),
            "ratification_status": final.ratification_status,
            "quorum_failed": bool((final.audit_summary or {}).get("quorum_failed")),
            "initial_mean_confidence": adaptive.get("initial_mean_confidence"),
        })
        del self._session_outcomes[:-100]        # keep the last 100

    def vitals(self) -> Dict[str, Any]:
        """Phase 15: one honest snapshot of the system's health (homeostasis)."""
        from .living_system import compute_vitals
        return compute_vitals(self._session_outcomes, seat_health=self.seat_health,
                              lesson_store=self.lesson_store, ledger=self.open_questions)

    async def _resolve_session_lessons(self, state: SessionState) -> Tuple[List[Dict[str, Any]], str]:
        """Phase 14: pick the lessons this session should see — a council seat
        selects genuine transfer when ai_learning (honest keyword fallback)."""
        try:
            if self.ai_learning and self.registry is not None:
                from .self_improvement import rank_lessons_with_council
                return await rank_lessons_with_council(self, state.question, k=3)
            return self.lesson_store.relevant(state.question, k=3), "keyword"
        except Exception:
            return [], "keyword"

    # Confidence-Adaptive Dialectic (Phase 14): thresholds on the mean confidence
    # of the INITIAL responses (CED-owned metadata; a purely mechanical trigger).
    HIGH_CONSENSUS_CONFIDENCE = 0.80    # everyone confident → herding risk → escalate
    LOW_CONFIDENCE_FLOOR = 0.45         # everyone unsure → map uncertainty honestly
    # Phase 26: a section winner backed by fewer than this many PEER scores is
    # "thinly corroborated" — one reviewer's opinion, not a corroborated result.
    WELL_CORROBORATED_MIN = 2
    # Phase 27: penalty flags voters raise on the WINNING content. These two are
    # stylistic; every other flag (unsupported_claim, logical_gap, overconfidence,
    # missed_uncertainty, logical/schema issues, unfair_attack, irrelevant) is a
    # substantive epistemic concern that should be visible on the final answer.
    STYLISTIC_FLAG_VALUES = frozenset({"vague", "rhetorical_fluff"})
    # Diversity guard (Phase 16): a SECOND, independent herding signal — content
    # similarity of the initial responses (keyword Jaccard; purely mechanical).
    LOW_DIVERSITY_FLOOR = 0.35          # 1.0 = fully diverse, 0.0 = identical
    # Confidence-disagreement signal (Phase 17): high VARIANCE of the initial
    # confidences means the council disagrees about how certain to BE — an
    # epistemic signal distinct from both the mean and the content similarity.
    CONFIDENCE_DISAGREEMENT_STD = 0.20  # population std of confidences

    def _response_diversity(self, state: SessionState) -> Optional[float]:
        """Mean pairwise keyword DIVERSITY (1 − Jaccard) of the initial responses.
        Near-identical answers from 'independent' seats are not independent
        evidence — they are the signature of herding."""
        from .self_improvement import _keywords
        initial = state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)
        if len(initial) < 2:
            return None
        kw = [_keywords(str(m.content)) for m in initial]
        sims, pairs = 0.0, 0
        for i in range(len(kw)):
            for j in range(i + 1, len(kw)):
                union = kw[i] | kw[j]
                sims += (len(kw[i] & kw[j]) / len(union)) if union else 1.0
                pairs += 1
        return round(1.0 - sims / pairs, 4)

    def _adaptive_dialectic(self, state: SessionState) -> Dict[str, Any]:
        initial = state.moves_for_phase(DialogPhase.INITIAL_RESPONSE)
        diversity = self._response_diversity(state)
        if not initial:
            return {"initial_mean_confidence": None,
                    "initial_confidence_std": None,
                    "devils_advocate_triggered": False,
                    "uncertainty_mode_triggered": False,
                    "confidence_disagreement_triggered": False,
                    "response_diversity": diversity,
                    "low_diversity_triggered": False}
        confs = [m.confidence for m in initial]
        mean_conf = round(sum(confs) / len(confs), 4)
        std = round((sum((c - mean_conf) ** 2 for c in confs) / len(confs)) ** 0.5, 4)
        return {
            "initial_mean_confidence": mean_conf,
            "initial_confidence_std": std,
            "devils_advocate_triggered": mean_conf >= self.HIGH_CONSENSUS_CONFIDENCE,
            "uncertainty_mode_triggered": mean_conf <= self.LOW_CONFIDENCE_FLOOR,
            "confidence_disagreement_triggered": (len(confs) >= 2
                                                  and std >= self.CONFIDENCE_DISAGREEMENT_STD),
            "response_diversity": diversity,
            "low_diversity_triggered": (diversity is not None
                                        and diversity <= self.LOW_DIVERSITY_FLOOR),
        }

    async def _self_improvement_ingest(self, state: SessionState, final: FinalResponse) -> None:
        """Phase 13 hooks (no-ops when the stores are absent): seat telemetry from
        the task_log; a PUBLIC lesson only from a RATIFIED outcome. With
        ai_learning, the lesson is AUTHORED by a council agent and the council
        reviews its own process — any AI failure falls back to the mechanical
        extractor. Failures here must never break a session result."""
        if self.trace_capturer is not None:
            try:
                self.trace_capturer.ingest_session(state, final)
            except Exception:
                final.audit_summary["trace_capture_error"] = True
        try:
            self._record_outcome(state, final)
            if self.seat_health is not None:
                self.seat_health.ingest_session(state)
            if self.topic_skill is not None:
                self.topic_skill.ingest_session(state)
            if self.calibration is not None:
                self.calibration.ingest_session(state)
            if self.training_corpus is not None:
                self.training_corpus.ingest_session(state, final)
            if self.open_questions is not None:
                self.open_questions.ingest_session(state, final)
            if self.lesson_store is None:
                return
            lesson = None
            if self.ai_learning:
                from .self_improvement import (
                    distill_lesson_with_council, review_process_with_council,
                )
                lesson = await distill_lesson_with_council(self, state, final)
                process = await review_process_with_council(self, state)
                if process is not None:
                    self.lesson_store.add_process(process)
                    final.audit_summary["process_lesson_recorded"] = True
            if lesson is not None:
                self.lesson_store.add(lesson)
                final.audit_summary["lesson_recorded"] = True
                final.audit_summary["lesson_distilled_by"] = "council"
            else:
                mechanical = self.lesson_store.ingest(state, final)
                if mechanical is not None:
                    final.audit_summary["lesson_recorded"] = True
                    final.audit_summary["lesson_distilled_by"] = "mechanical"
        except Exception:   # telemetry must never take down a dialogue
            final.audit_summary["self_improvement_error"] = True

    def _registry_session_audit(
        self, state: SessionState,
        phase_results: List[Tuple[DialogPhase, CouncilRoundResult]],
    ) -> Dict[str, Any]:
        """CED-owned audit add-ons for a registry session (hidden from agents)."""
        cached = self._session_lessons.get(state.session_id)
        from .topic import classify_topic
        return {
            "execution_mode": "registry",
            "adaptive_dialectic": self._adaptive_dialectic(state),
            "epistemic_consistency": self._epistemic_consistency(state),
            "score_weighting": self._weighting_audit(state),
            "assembly_coherence": self._assembly_coherence(state),
            "assembly_reliability": self._assembly_reliability(state),
            "assembly_flags": self._assembly_flags(state),
            "quarantine_excluded": self._quarantine_exclusions(),
            "phase_retries": self._phase_retries.get(state.session_id, []),
            "phase_dispatch": self._phase_dispatch.get(state.session_id, []),
            "socratic_opening": self._socratic_audit(state),
            "seat_routing": {
                "topic": classify_topic(state.question).value,
                "order": [a.provider_id for a in self._ranked_adapters(state)],
                "analytics_informed": bool(self.topic_skill or self.seat_health),
            },
            "lesson_retrieval": (cached[1] if cached else None),
            "openclaw_lessons": self._openclaw_audit(state),
            "deliberation_tree": self._tree_audits.get(
                state.session_id, {"enabled": False}),
            "shadow_scoring_mode": self.shadow_scoring_mode.value,
            "provider_status_summary": self.registry.status_summary(),
            "registry_phase_rounds": [
                {
                    "phase": ph.value,
                    "proceed": res.proceed,
                    "ok_providers": list(res.ok_provider_ids),
                    "failed_providers": list(res.failed_provider_ids),
                    "validated_moves": sum(1 for r in res.responses if r.ok),
                    "repairs": sum(1 for r in res.responses if r.repair_attempted),
                }
                for ph, res in phase_results
            ],
            "task_log_count": len(state.task_log),
            "task_log_summary": self._task_log_summary(state),
            "scoring": self._registry_scoring_audit(state),
        }

    def _openclaw_audit(self, state: SessionState) -> Optional[Dict[str, Any]]:
        """OpenClaw Memory Lessons audit (CED-owned, hidden from agents).

        Reports the injected-context LEDGER — what actually entered agent
        contexts during the session, per phase/agent — never a fresh re-run
        of retrieval, which could disagree with runtime reality (runtime
        retrieval is phase-aware; a question-only re-run is not)."""
        if self.openclaw_lessons is None:
            return None
        injections = self._injected_lessons.get(state.session_id, [])
        selected = sorted({lid for inj in injections
                           for lid in inj["lesson_ids"]})
        return {
            "enabled": True,
            "pool_size": len(self.openclaw_lessons),
            "selected": selected,
            "selected_count": len(selected),
            "injections": injections,
        }

    def _registry_scoring_audit(self, state: SessionState) -> Dict[str, Any]:
        """Phase 8C.2 registry-scoring audit (hidden from agents)."""
        h = state.shadow_harvest
        section_scores = [s for c in state.draft_scorecards for s in c.section_scores]
        scores_by_phase: Dict[str, int] = {}
        self_violations = 0
        for ms in state.micro_scores:
            scores_by_phase[ms.phase.value] = scores_by_phase.get(ms.phase.value, 0) + 1
            if ms.voter_agent_id == ms.author_agent_id:
                self_violations += 1
        return {
            "scoring_backend": "registry",
            "scoring_mode": self.shadow_scoring_mode.value,
            "scores_expected": h.scores_expected if h else 0,
            "scores_collected": h.scores_collected if h else 0,
            "scores_failed": len(state.failed_score_tasks),
            "failed_score_tasks": list(state.failed_score_tasks),
            "scores_by_phase": scores_by_phase,
            "sync_gate_status": h.status.value if h else "unavailable",
            "leaderboard_status": (state.epistemic_leaderboard.leaderboard_status.value
                                   if state.epistemic_leaderboard else "unavailable"),
            "section_scores_collected": len(section_scores),
            "section_scores_failed": len(state.section_scores_failed),
            "self_scoring_violations": self_violations,
            "scoring_provider_status_summary": self.registry.status_summary(),
        }

    @staticmethod
    def _task_log_summary(state: SessionState) -> Dict[str, Any]:
        by_phase: Dict[str, int] = {}
        linked = 0
        for e in state.task_log:
            by_phase[e.phase.value] = by_phase.get(e.phase.value, 0) + 1
            if e.move_id is not None:
                linked += 1
        return {"entries": len(state.task_log), "with_move": linked, "by_phase": by_phase}

    def _registry_fallback_final(
        self, state: SessionState, warning: Optional[str],
        blocked_phase: Optional[DialogPhase],
        phase_results: Optional[List[Tuple[DialogPhase, CouncilRoundResult]]] = None,
    ) -> FinalResponse:
        """Safe non-proceeding FinalResponse when readiness/quorum is not met."""
        # Phase 13: FAILED sessions are exactly where seat telemetry matters most —
        # the tracker learns which seats caused the quorum failure (content-blind).
        if self.seat_health is not None:
            try:
                self.seat_health.ingest_session(state)
            except Exception:
                pass   # telemetry must never take down even a fallback
        audit = {
            "execution_mode": "registry",
            "proceeded": False,
            "quorum_failed": True,
            "blocked_phase": blocked_phase.value if blocked_phase else None,
            "warning": warning,
            "shadow_scoring_mode": self.shadow_scoring_mode.value,
            "provider_status_summary": self.registry.status_summary(),
            "task_log_count": len(state.task_log),
        }
        if phase_results is not None:
            audit["registry_phase_rounds"] = [
                {"phase": ph.value, "proceed": res.proceed,
                 "ok_providers": list(res.ok_provider_ids),
                 "failed_providers": list(res.failed_provider_ids)}
                for ph, res in phase_results
            ]
        final = FinalResponse(
            session_id=state.session_id, question=state.question,
            synthesis=None, ratification_status="quorum_failed",
            audit_summary=audit, answer="", ratified=False,
            blocking_objections=[warning] if warning else [],
            council_summary={"execution_mode": "registry", "quorum_failed": True},
        )
        state.final_response = final
        # Phase 15: a failed dialogue is the loudest open question + a vital sign.
        try:
            self._record_outcome(state, final)
            if self.open_questions is not None:
                self.open_questions.ingest_session(state, final)
        except Exception:
            pass   # the living-system layer must never take down even a fallback
        self._capture_hybrid_shadow(state, final)
        return final

    # ── Phase 8C.1: Socratic Council Ratification (council-level, registry) ────

    def _parse_verdict(
        self, response: "ProviderResponse", task: AgentTask,
    ) -> Optional[RatificationVerdict]:
        """
        Parse one provider's verdict from a validated response. STRUCTURAL only:
        an unrecognised/absent verdict → None (invalid, never fabricated as ACCEPT).
        CED does not judge whether the verdict is philosophically correct.
        """
        if response.parsed_move is None:
            return None
        c = response.parsed_move.content if isinstance(response.parsed_move.content, dict) else {}
        try:
            verdict = CouncilVerdict(c.get("verdict"))
        except (ValueError, TypeError):
            return None   # invalid verdict — not counted, not fabricated
        try:
            severity = ObjectionSeverity(c.get("severity", "none"))
        except (ValueError, TypeError):
            severity = ObjectionSeverity.NONE
        target = c.get("target_section")
        section = None
        if target:
            try:
                section = SectionName(target)
            except (ValueError, TypeError):
                section = None
        return RatificationVerdict(
            session_id=task.session_id,
            agent_id=task.agent_id,
            provider_id=response.provider_id,
            verdict=verdict,
            rationale=str(c.get("rationale", "")),
            confidence=response.parsed_move.confidence,
            caveat=(str(c["caveat"]) if c.get("caveat") else None),
            blocking_objection=(str(c["blocking_objection"]) if c.get("blocking_objection") else None),
            target_section=section,
            severity=severity,
            required_fix=(str(c["required_fix"]) if c.get("required_fix") else None),
            provider_status=response.status,
            task_id=task.task_id,
            move_id=response.parsed_move.move_id,
        )

    async def run_council_ratification(
        self, state: SessionState, timeout_seconds: Optional[float] = None,
        round_index: int = 0,
    ) -> CouncilRatification:
        """
        Send a ratification task to EVERY available provider; each returns one
        independent verdict (ACCEPT / ACCEPT_WITH_CAVEAT / BLOCKING_OBJECTION).
        CED applies deterministic protocol rules — NOT majority voting, NOT
        semantic judgement, NEVER a fabricated ACCEPT.
        """
        assembled = state.assembled_answer
        synthesis_text = assembled.full_text() if assembled else ""
        adapters = self._healthy_adapters()
        quorum = self.registry.quorum_for_assembly

        def _build_task(slot: int, adapter) -> AgentTask:
            return AgentTask(
                session_id=state.session_id,
                agent_id=adapter.provider_id,          # the provider IS this council member
                role=AgentRole.FINAL_EVALUATOR,
                phase=DialogPhase.RATIFICATION,
                question=state.question,
                # Minimal-awareness context: only the answer + rubric. No scores.
                context={
                    "final_synthesis": synthesis_text,
                    "ratification_rubric": (
                        "Return one verdict: accept | accept_with_caveat | "
                        "blocking_objection. A blocking objection must be critical "
                        "and name target_section, rationale and required_fix."),
                },
                output_schema={"_role": AgentRole.FINAL_EVALUATOR.value,
                               "_question": state.question, "_ratification": True},
                task_kind=TaskKind.COUNCIL_RATIFICATION,
                slot_index=slot, attempt_index=round_index,
            )

        async def _one(slot: int, adapter):
            task = _build_task(slot, adapter)
            agent_state = AgentState(agent_id=adapter.provider_id,
                                     primary_role=AgentRole.FINAL_EVALUATOR,
                                     assigned_role=AgentRole.FINAL_EVALUATOR)
            resp = await self.registry.run_adapter(adapter, task, agent_state, timeout_seconds)
            return task, resp

        pairs = list(await asyncio.gather(
            *(_one(i, a) for i, a in enumerate(adapters)))) if adapters else []

        verdicts: List[RatificationVerdict] = []
        invalid = 0
        failed_providers: List[str] = []
        timed_out_providers: List[str] = []
        for task, resp in pairs:
            if resp.ok:
                v = self._parse_verdict(resp, task)
                if v is not None:
                    verdicts.append(v)
                    self._record_task_log(state, task, resp.parsed_move.move_id,
                                          provider_id=resp.provider_id, provider_status=resp.status)
                    continue
                invalid += 1   # schema-valid move but not a valid verdict
            # failure / invalid verdict → audited, no fabricated ACCEPT
            self._record_task_log(state, task, None,
                                  provider_id=resp.provider_id, provider_status=resp.status)
            if resp.status == ProviderStatus.TIMEOUT:
                timed_out_providers.append(resp.provider_id)
            else:
                failed_providers.append(resp.provider_id)

        criticals = [v for v in verdicts if v.is_schema_valid_critical_block()]
        caveats = [v for v in verdicts if v.is_caveat()]
        target_sections: List[SectionName] = []
        for v in criticals:
            if v.target_section and v.target_section not in target_sections:
                target_sections.append(v.target_section)

        # Deterministic protocol rules (NOT majority voting).
        if len(verdicts) == 0:
            status = CouncilRatificationStatus.RATIFICATION_FAILED
        elif len(verdicts) < quorum:
            status = CouncilRatificationStatus.RATIFICATION_QUORUM_FAILED
        elif criticals:                       # one valid critical block is enough
            status = CouncilRatificationStatus.REPAIR_REQUIRED
        elif caveats:
            status = CouncilRatificationStatus.RATIFIED_WITH_CAVEATS
        else:
            status = CouncilRatificationStatus.RATIFIED

        ratification = CouncilRatification(
            session_id=state.session_id, status=status, verdicts=verdicts,
            valid_verdicts=len(verdicts), invalid_verdicts=invalid, quorum=quorum,
            caveat_count=len(caveats), critical_block_count=len(criticals),
            target_sections=target_sections, failed_providers=failed_providers,
            timed_out_providers=timed_out_providers, rounds=round_index + 1,
        )
        state.council_ratification = ratification
        return ratification

    def _repair_blocked_sections(
        self, state: SessionState, ratification: "CouncilRatification",
        tried: Dict[SectionName, set],
    ) -> List[Dict[str, Any]]:
        """
        Option B repair — purely mechanical: for each section the council
        critically blocked, swap in the RUNNER-UP draft (next by peer-score
        ranking; deterministic draft_id order when no scores exist, mirroring the
        assembly fallback). CED selects only by rank/order — never by content.
        Returns the provenance records; empty when nothing can be swapped.
        """
        assembled = state.assembled_answer
        if assembled is None:
            return []
        drafts_by_id = {d.draft_id: d for d in state.section_drafts}
        repairs: List[Dict[str, Any]] = []
        for section in ratification.target_sections:
            current = assembled.section(section)
            if current is None:
                continue
            seen = tried.setdefault(section, set())
            if current.selected_draft_id:
                seen.add(current.selected_draft_id)
            replacement: Optional[AssembledSection] = None
            via = None
            # 1) peer-score ranking (the honest ordering when scores exist)
            for entry in self._section_ranking(state, section):
                if entry["draft_id"] not in seen:
                    replacement = self._section_assembled(section, entry, drafts_by_id)
                    via = "peer_ranking"
                    break
            # 2) no scores (e.g. shadow scoring off) → deterministic draft order,
            #    the same mechanical rule the assembly fallback uses
            if replacement is None:
                candidates = sorted(
                    (d for d in state.section_drafts
                     if d.draft_id not in seen and d.section_text(section).strip()),
                    key=lambda d: d.draft_id)
                if candidates:
                    d = candidates[0]
                    replacement = AssembledSection(
                        section_name=section, selected_draft_id=d.draft_id,
                        selected_author_agent_id=d.author_agent_id,
                        content=d.section_text(section),
                        average_score=0.0, score_count=0, variance=0.0)
                    via = "deterministic_order"
            if replacement is None:
                continue   # no untried runner-up — this section stays blocked
            seen.add(replacement.selected_draft_id)
            assembled.sections = [replacement if s.section_name == section else s
                                  for s in assembled.sections]
            repairs.append({"section": section.value,
                            "from_draft": current.selected_draft_id,
                            "to_draft": replacement.selected_draft_id,
                            "via": via})
        return repairs

    def _build_council_final(
        self, state: SessionState, ratification: CouncilRatification,
    ) -> FinalResponse:
        """Assemble the FinalResponse from a council ratification outcome."""
        state.advance_phase(DialogPhase.RATIFICATION)
        state.advance_phase(DialogPhase.COMPLETE)
        assembled = state.assembled_answer
        harvest = self._sync_harvest(state)
        leaderboard = self.build_epistemic_leaderboard(state, harvest)

        ratified = ratification.is_ratified()
        # Never present a non-ratified answer as the released answer.
        answer = assembled.full_text() if (ratified and assembled) else ""
        epistemic = self._epistemic_status_from_hint(self._epistemic_hint(state))

        # Attributed objection metadata (who raised what) — CED-owned audit only.
        objections = [
            {"provider_id": v.provider_id, "agent_id": v.agent_id,
             "target_section": v.target_section.value if v.target_section else None,
             "severity": v.severity.value, "rationale": v.rationale,
             "required_fix": v.required_fix}
            for v in ratification.verdicts if v.is_schema_valid_critical_block()
        ]
        caveat_meta = [
            {"provider_id": v.provider_id, "agent_id": v.agent_id, "caveat": v.caveat}
            for v in ratification.verdicts if v.is_caveat()
        ]
        audit = {
            "execution_mode": "registry",
            "final_synthesis_mode": self.final_synthesis_mode.value,
            # The epistemic_status on the FinalResponse is produced by
            # _epistemic_hint, which is a mean-quality threshold. It is retained
            # for compatibility and comparison and governs nothing: epistemic
            # support is decided by the hybrid core, never by a score. Stated
            # here so a reader of the audit cannot mistake the label for a
            # verdict about evidence.
            "legacy_epistemic_status_authority": "legacy_non_governing",
            "num_agents": len(self.agents),
            "total_moves": len(state.moves),
            "score_coverage": {
                "scores_expected": harvest.scores_expected,
                "scores_collected": harvest.scores_collected,
                "coverage_ratio": harvest.coverage_ratio,
                "sync_gate_status": harvest.status.value,
            },
            "council_ratification": {
                "status": ratification.status.value,
                "valid_verdicts": ratification.valid_verdicts,
                "invalid_verdicts": ratification.invalid_verdicts,
                "quorum": ratification.quorum,
                "caveat_count": ratification.caveat_count,
                "critical_block_count": ratification.critical_block_count,
                "target_sections": [s.value for s in ratification.target_sections],
                "failed_providers": ratification.failed_providers,
                "timed_out_providers": ratification.timed_out_providers,
                "verdicts": [
                    {"provider_id": v.provider_id, "agent_id": v.agent_id,
                     "verdict": v.verdict.value, "provider_status": v.provider_status.value}
                    for v in ratification.verdicts
                ],
                "attributed_critical_objections": objections,
                "caveats": caveat_meta,
            },
            "leaderboard_status": leaderboard.leaderboard_status.value,
        }

        final = FinalResponse(
            session_id=state.session_id, question=state.question,
            synthesis=assembled,
            ratification_status=ratification.status.value,
            audit_summary=audit,
            socratic_leaderboard=leaderboard,
            answer=answer,
            ratified=ratified,
            blocking_objections=[o["rationale"] for o in objections],
            unresolved_sections=list(ratification.target_sections),
            epistemic_status=epistemic,
            council_summary={
                "execution_mode": "registry",
                "final_synthesis_mode": self.final_synthesis_mode.value,
                "ratification_status": ratification.status.value,
                "valid_verdicts": ratification.valid_verdicts,
            },
        )
        state.final_response = final
        return final

    @staticmethod
    def _epistemic_status_from_hint(hint: str) -> EpistemicStatus:
        try:
            return EpistemicStatus(hint)
        except (ValueError, TypeError):
            return EpistemicStatus.UNCERTAIN

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _agent_by_id(self, agent_id: str) -> SocraticAgent:
        try:
            return next(a for a in self.agents if a.agent_id == agent_id)
        except StopIteration:
            raise ValueError(f"Agent '{agent_id}' not registered with this orchestrator.")

    def _deterministic_move_id(
        self, state: SessionState, agent_id: str, phase: DialogPhase,
        role: AgentRole, task_kind: TaskKind, slot_index: int, attempt_index: int,
    ) -> str:
        """
        Deterministic, unique move id derived ONLY from stable task identity —
        never from runtime completion/append order. With real async providers the
        return order may differ; this keeps move ids (and therefore scoring seeds,
        winners, leaderboard) identical regardless.

        Identity = session_id | phase | round_number | agent_id | assigned_role |
                   task_kind | slot_index | attempt_index.
        """
        key = "|".join([
            state.session_id, phase.value, str(state.round_number),
            agent_id, role.value, task_kind.value,
            str(slot_index), str(attempt_index),
        ])
        return "move_" + format(stable_hash(key), "x")[:12]

    def _dispatch(self, state: SessionState, agent: SocraticAgent,
                  role: AgentRole, phase: DialogPhase,
                  context: dict, extra_schema: dict,
                  task_kind: TaskKind, slot_index: int = 0,
                  attempt_index: int = 0) -> AgentMove:
        """Build an AgentTask, dispatch to the agent, record the move."""
        schema = {"_role": role.value, **extra_schema}
        move_id = self._deterministic_move_id(
            state, agent.agent_id, phase, role, task_kind, slot_index, attempt_index
        )
        task = AgentTask(
            session_id=state.session_id,
            agent_id=agent.agent_id,
            role=role,
            phase=phase,
            question=state.question,
            context=context,
            output_schema=schema,
            round_number=state.round_number,
            task_kind=task_kind,
            slot_index=slot_index,
            attempt_index=attempt_index,
        )
        move = agent.execute(task)
        # Deterministic identity (drives reproducible shadow-scoring seeds).
        move.move_id = move_id
        move.task_kind = task_kind
        move.slot_index = slot_index
        move.attempt_index = attempt_index
        state.moves.append(move)
        # CED-owned task trace (hidden from agents); linked to this move.
        self._record_task_log(state, task, move_id)
        return move

    @staticmethod
    def _context_hash(context: dict) -> str:
        """Stable hash of the sanitized task context (no raw prompt is stored)."""
        try:
            canonical = json.dumps(context, sort_keys=True, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            canonical = str(context)
        return format(stable_hash(canonical), "x")[:16]

    def _record_task_log(
        self, state: SessionState, task: AgentTask, move_id: Optional[str],
        provider_id: Optional[str] = None,
        provider_status: Optional[ProviderStatus] = None,
    ) -> None:
        """Append a CED-owned TaskLogEntry for one dispatched task (never to agents)."""
        entry = TaskLogEntry(
            task_id=task.task_id,
            move_id=move_id,
            session_id=state.session_id,
            phase=task.phase,
            round_index=task.round_number,
            agent_id=task.agent_id,
            assigned_role=task.role,
            task_kind=task.task_kind,
            slot_index=task.slot_index,
            attempt_index=task.attempt_index,
            schema_name=str(task.output_schema.get("_role", task.role.value)),
            context_hash=self._context_hash(task.context),
            provider_id=provider_id,
            provider_status=provider_status,
            debug_context=(dict(task.context) if self.debug_task_log else None),
        )
        state.task_log.append(entry)

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
            task_kind=TaskKind.SOCRATIC_QUESTION,
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
        for slot, (agent_id, role) in enumerate(sorted(assignment.items())):
            agent = self._agent_by_id(agent_id)
            m = self._dispatch(state, agent, role,
                               DialogPhase.INITIAL_RESPONSE, ctx, {},
                               task_kind=TaskKind.INITIAL_RESPONSE, slot_index=slot)
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
        for slot, (agent_id, role) in enumerate(sorted(assignment.items())):
            agent = self._agent_by_id(agent_id)
            m = self._dispatch(state, agent, role,
                               DialogPhase.ELENCHUS, ctx, {},
                               task_kind=TaskKind.ELENCHUS_OBJECTION, slot_index=slot)
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
        # Sort by agent_id so slot_index is stable regardless of move append order.
        for slot, m_initial in enumerate(sorted(initial_moves, key=lambda mm: mm.agent_id)):
            agent = self._agent_by_id(m_initial.agent_id)
            ctx = {
                "my_initial_response": m_initial.content,
                "critiques_from_council": critiques,
            }
            m = self._dispatch(state, agent, AgentRole.REFLECTOR,
                               DialogPhase.REFLECTION, ctx, {},
                               task_kind=TaskKind.REFLECTION_REVISION, slot_index=slot)
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
        for slot, (agent_id, role) in enumerate(sorted(assignment.items())):
            agent = self._agent_by_id(agent_id)
            m = self._dispatch(state, agent, role,
                               DialogPhase.RECONSTRUCTION, ctx, {},
                               task_kind=TaskKind.RECONSTRUCTION_PROPOSAL, slot_index=slot)
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
        for slot, agent in enumerate(sorted(self.agents, key=lambda a: a.agent_id)):
            role = assignment.get(agent.agent_id, AgentRole.SYNTHESIZER)
            # _sections tells the provider to emit the locked 5-section draft.
            m = self._dispatch(state, agent, role,
                               DialogPhase.SYNTHESIS, ctx, {"_sections": True},
                               task_kind=TaskKind.SYNTHESIS_DRAFT, slot_index=slot)
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
                provider_id=m.provider_id,       # producer (for no-self-scoring)
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
        INVARIANT: CED is not a scorer. A malformed/missing breakdown returns
        (None, ...) — CED NEVER fabricates a qualitative score (e.g. zeros) to
        stand in for a peer voter. The caller records the failure as metadata and
        the score stays MISSING.
        """
        flags = self._parse_flags(raw.get("penalty_flags", []))
        status = self._parse_status(raw.get("provider_status", "ok"))
        dims = list(ScoreBreakdown.model_fields.keys())
        # Two shapes carry the same seven dimensions: SCORE_CONTENT_DIRECTIVE tells
        # real providers to return them FLAT in `content`, while FakeProvider and
        # stored traces nest them under "score_breakdown". Accept either — nested
        # first, so an explicit breakdown always wins over stray top-level keys.
        for source in (raw.get("score_breakdown"), raw):
            try:
                breakdown = ScoreBreakdown(**{k: float(source[k]) for k in dims})
            except (TypeError, ValueError, KeyError):
                continue
            return breakdown, status, flags
        return None, ProviderStatus.SCHEMA_ERROR, flags  # no fabricated score

    # ── Shadow Scoring (move-level, 0–10, peer-attributed, CED-owned, hidden) ──

    def _score_one_move(
        self, state: SessionState, move: AgentMove, scorer: SocraticAgent,
        phase: DialogPhase,
    ) -> Optional[MicroScore]:
        """
        Ask ONE peer voter to score ONE move. Returns the peer's MicroScore, or
        None if the peer's score is invalid/missing (no self-scoring upstream).

        CED never invents the score: the breakdown/justification/flags all come
        from the voter's provider; CED only routes the task and validates.
        """
        rubric_name, rubric_focus = rubric_for(phase)
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
                # Phase-specific rubric hint (deterministic; not scoring machinery).
                "_rubric": rubric_name,
                "_rubric_focus": rubric_focus,
                "_phase": phase.value,
            },
            agent_id=scorer.agent_id,
        )
        breakdown, status, flags = self._parse_breakdown(raw)
        if breakdown is None:
            return None   # peer score failed/invalid — CED does NOT fabricate one
        return MicroScore(
            session_id=state.session_id,
            output_id=move.move_id,
            phase=phase,
            rubric_name=rubric_name,
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

    def _normalize_phases(self, phases) -> List[DialogPhase]:
        """Accept None (→ phases for the configured mode), a single phase, or a list."""
        if phases is None:
            return self._phases_for_mode()
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
        micro: List[MicroScore] = []
        failed: List[str] = []
        for (move, scorer, phase) in self._phase_pairs(state, phase_list):
            ms = self._score_one_move(state, move, scorer, phase)
            if ms is not None:
                micro.append(ms)               # valid peer score
            else:
                failed.append(f"{move.move_id}:{scorer.agent_id}")  # missing — not fabricated
        state.micro_scores = micro
        state.failed_score_tasks = failed
        return micro

    # ── Phase 8C.2: registry-backed peer scoring (move-level) ─────────────────

    def _deterministic_score_task_id(
        self, state: SessionState, target_id: str, voter_id: str,
        kind: TaskKind, slot_index: int, section: str = "",
    ) -> str:
        """Stable score-task id (independent of async completion order)."""
        key = "|".join([state.session_id, kind.value, target_id, voter_id,
                        section, str(slot_index)])
        return "stask_" + format(stable_hash(key), "x")[:12]

    def _build_move_score_task(
        self, state: SessionState, move: AgentMove, voter_id: str,
        phase: DialogPhase, slot_index: int,
    ) -> AgentTask:
        rubric_name, rubric_focus = rubric_for_move(move, phase)
        return AgentTask(
            task_id=self._deterministic_score_task_id(
                state, move.move_id, voter_id, TaskKind.MOVE_SCORE, slot_index),
            session_id=state.session_id,
            agent_id=voter_id,                      # the VOTER (registry provider)
            role=AgentRole.FINAL_EVALUATOR,
            phase=phase,
            question=state.question,
            # Minimal-awareness context: only the output to score + rubric.
            context={"output_to_score": move.content, "rubric_name": rubric_name,
                     "rubric_focus": rubric_focus},
            output_schema={"_role": "__move_score__", "_target": move.move_id,
                           "_question": state.question, "_rubric": rubric_name,
                           "_phase": phase.value},
            task_kind=TaskKind.MOVE_SCORE, slot_index=slot_index,
        )

    def _microscore_from_response(
        self, state: SessionState, move: AgentMove, voter_id: str,
        phase: DialogPhase, resp: "ProviderResponse",
    ) -> Optional[MicroScore]:
        """Validate a peer provider's score response → MicroScore, or None (missing)."""
        if not resp.ok or resp.parsed_move is None:
            return None
        content = resp.parsed_move.content if isinstance(resp.parsed_move.content, dict) else {}
        breakdown, status, flags = self._parse_breakdown(content)
        if breakdown is None:
            return None   # invalid peer score — CED does NOT fabricate one
        rubric_name = rubric_for_move(move, phase)[0]
        return MicroScore(
            session_id=state.session_id, output_id=move.move_id, phase=phase,
            rubric_name=rubric_name, author_agent_id=move.agent_id,
            voter_agent_id=voter_id, provider_id=voter_id,
            score_breakdown=breakdown,
            confidence=resp.parsed_move.confidence,
            justification=str(content.get("justification", "")),
            penalty_flags=flags, provider_status=resp.status,
        )

    def _eligible_score_voters(self, move: AgentMove):
        """Healthy registry providers that may score this move (peers, not the author/producer)."""
        return [a for a in self._healthy_adapters()
                if a.provider_id != move.provider_id]

    async def run_registry_shadow_scores(
        self, state: SessionState, timeout_seconds: Optional[float] = None,
    ) -> List[MicroScore]:
        """
        Move-level peer scoring routed through CouncilProviderRegistry. Each move
        is scored by every available PEER provider (excluding its producer). Failed
        / invalid / timed-out scores stay MISSING — never fabricated. Honours
        shadow_scoring_mode; builds the harvest + status the leaderboard reads.
        """
        phase_list = self._phases_for_mode()
        if not phase_list:   # shadow_scoring_mode == off
            state.micro_scores = []
            state.failed_score_tasks = []
            state.shadow_harvest = ShadowScoreHarvest(
                session_id=state.session_id, status=SyncGateStatus.DISABLED)
            return []

        # Build every (move, voter) scoring task deterministically.
        plan = []   # (phase, move, voter_adapter, slot)
        for phase in phase_list:
            for move in state.moves_for_phase(phase):
                for slot, voter in enumerate(self._eligible_score_voters(move)):
                    plan.append((phase, move, voter, slot))
        expected = len(plan)

        async def _one(phase, move, voter, slot):
            task = self._build_move_score_task(state, move, voter.provider_id, phase, slot)
            astate = AgentState(agent_id=voter.provider_id,
                                primary_role=AgentRole.FINAL_EVALUATOR,
                                assigned_role=AgentRole.FINAL_EVALUATOR)
            resp = await self.registry.run_adapter(voter, task, astate, timeout_seconds)
            return phase, move, voter, task, resp

        results = list(await asyncio.gather(*(_one(*p) for p in plan))) if plan else []

        micro: List[MicroScore] = []
        failed: List[str] = []
        timed_out = False
        for phase, move, voter, task, resp in results:
            ms = self._microscore_from_response(state, move, voter.provider_id, phase, resp)
            if ms is not None:
                micro.append(ms)
                self._record_task_log(state, task, resp.parsed_move.move_id,
                                      provider_id=voter.provider_id, provider_status=resp.status)
            else:
                failed.append(f"{move.move_id}:{voter.provider_id}")
                if resp.status == ProviderStatus.TIMEOUT:
                    timed_out = True
                self._record_task_log(state, task, None,
                                      provider_id=voter.provider_id, provider_status=resp.status)

        collected = len(micro)
        coverage = (collected / expected) if expected else 0.0
        if expected == 0:
            status = SyncGateStatus.UNAVAILABLE
        elif collected == 0:
            status = SyncGateStatus.TIMEOUT if timed_out else SyncGateStatus.FAILED
        elif collected >= expected:
            status = SyncGateStatus.COMPLETE
        else:
            status = SyncGateStatus.PARTIAL

        state.micro_scores = micro
        state.failed_score_tasks = failed
        state.shadow_harvest = ShadowScoreHarvest(
            session_id=state.session_id, scores_expected=expected,
            scores_collected=collected, coverage_ratio=coverage, status=status,
            failed_tasks=failed)
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
        # Shadow scoring explicitly disabled → report cleanly (not a failure).
        if phases is None and self.shadow_scoring_mode == ShadowScoringMode.OFF:
            harvest = ShadowScoreHarvest(
                session_id=session_state.session_id, status=SyncGateStatus.DISABLED,
            )
            session_state.micro_scores = []
            session_state.shadow_harvest = harvest
            return harvest

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
                ms = fut.result()
            except Exception:
                harvest.failed_tasks.append(task_meta[fut])  # provider failed — no fake score
                continue
            if ms is not None:
                collected.append(ms)                          # valid peer score
            else:
                harvest.failed_tasks.append(task_meta[fut])   # invalid score — NOT fabricated

        for fut in pending:
            harvest.timed_out_tasks.append(task_meta[fut])    # timed out — provider_status TIMEOUT
            fut.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        collected_count = len(collected)
        harvest.scores_collected = collected_count
        harvest.coverage_ratio = (collected_count / expected) if expected else 0.0

        if collected_count == 0:
            if harvest.timed_out_tasks:
                harvest.status = SyncGateStatus.TIMEOUT
            elif harvest.failed_tasks:
                harvest.status = SyncGateStatus.FAILED   # peers failed; no fabricated scores
            else:
                harvest.status = SyncGateStatus.UNAVAILABLE
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

        if phases is None and self.shadow_scoring_mode == ShadowScoringMode.OFF:
            harvest = ShadowScoreHarvest(
                session_id=state.session_id, status=SyncGateStatus.DISABLED,
            )
            state.shadow_harvest = harvest
            return harvest

        phase_list = self._normalize_phases(phases)
        expected = sum(len(self._move_score_pairs(state, p)) for p in phase_list)
        collected = len(state.micro_scores)
        failed = list(state.failed_score_tasks)
        coverage = (collected / expected) if expected else 0.0
        if expected == 0:
            status = SyncGateStatus.UNAVAILABLE          # nothing to score
        elif collected == 0:
            status = SyncGateStatus.FAILED if failed else SyncGateStatus.UNAVAILABLE
        elif collected >= expected:
            status = SyncGateStatus.COMPLETE
        else:
            status = SyncGateStatus.PARTIAL              # some peer scores missing
        harvest = ShadowScoreHarvest(
            session_id=state.session_id, scores_expected=expected,
            scores_collected=collected, coverage_ratio=coverage, status=status,
            failed_tasks=failed,
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

        if harvest.status == SyncGateStatus.DISABLED:
            status = LeaderboardStatus.DISABLED
        elif harvest.status == SyncGateStatus.FAILED:
            status = LeaderboardStatus.FAILED        # peers produced no valid scores
        elif expected == 0:
            status = LeaderboardStatus.UNAVAILABLE
        elif collected == 0:
            status = (LeaderboardStatus.FAILED if harvest.failed_tasks
                      else LeaderboardStatus.UNAVAILABLE)
        elif coverage >= 1.0:
            status = LeaderboardStatus.COMPLETE
        else:
            status = LeaderboardStatus.PARTIAL

        notable: List[str] = []
        if status == LeaderboardStatus.DISABLED:
            notable.append("Shadow scoring is disabled (shadow_scoring_mode=off).")
        if status == LeaderboardStatus.FAILED:
            notable.append("Peer scoring produced no valid scores; no scores were fabricated.")
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
                    if breakdown is None:
                        # Invalid peer score → MISSING. CED never fabricates one.
                        missing.append(section)
                        state.section_scores_failed.append(
                            f"{draft.draft_id}:{section.value}:{scorer.agent_id}")
                        continue
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

    # ── Phase 8C.2: registry-backed peer scoring (section-level) ──────────────

    def _build_section_score_task(
        self, state: SessionState, draft: SectionDraft, section: SectionName,
        voter_id: str, content: str, slot_index: int,
    ) -> AgentTask:
        return AgentTask(
            task_id=self._deterministic_score_task_id(
                state, draft.draft_id, voter_id, TaskKind.SECTION_SCORE,
                slot_index, section.value),
            session_id=state.session_id,
            agent_id=voter_id,                       # the VOTER (registry provider)
            role=AgentRole.FINAL_EVALUATOR,
            phase=DialogPhase.SYNTHESIS,
            question=state.question,
            context={"output_to_score": content, "section": section.value},
            output_schema={"_role": "__section_score__", "_target": draft.draft_id,
                           "_section": section.value, "_question": state.question},
            task_kind=TaskKind.SECTION_SCORE, slot_index=slot_index,
        )

    async def score_section_drafts_with_registry(
        self, state: SessionState, timeout_seconds: Optional[float] = None,
        drafts: Optional[List[SectionDraft]] = None,
    ) -> List[DraftScorecard]:
        """
        Section-level peer scoring routed through CouncilProviderRegistry. Each
        draft section is scored by every available PEER provider (excluding the
        draft's producer). Invalid/failed scores stay MISSING (recorded in
        missing_sections + section_scores_failed), never fabricated as zeros.

        `drafts` (deliberation tree): score ONLY these drafts and APPEND their
        scorecards to state.draft_scorecards instead of replacing the set —
        used to score tree revisions incrementally. Default None = the whole
        state.section_drafts pool with replace semantics (unchanged behavior).
        """
        cards: List[DraftScorecard] = []
        plan = []   # (draft, voter, section, content, slot)
        for draft in (state.section_drafts if drafts is None else drafts):
            voters = [a for a in self._healthy_adapters()
                      if a.provider_id != draft.provider_id]
            for vslot, voter in enumerate(voters):
                for section in SECTION_ORDER:
                    content = draft.section_text(section)
                    if content.strip():
                        plan.append((draft, voter, section, content, vslot))

        async def _one(draft, voter, section, content, vslot):
            task = self._build_section_score_task(
                state, draft, section, voter.provider_id, content, vslot)
            astate = AgentState(agent_id=voter.provider_id,
                                primary_role=AgentRole.FINAL_EVALUATOR,
                                assigned_role=AgentRole.FINAL_EVALUATOR)
            resp = await self.registry.run_adapter(voter, task, astate, timeout_seconds)
            return draft, voter, section, task, resp

        results = list(await asyncio.gather(*(_one(*p) for p in plan))) if plan else []

        # Group results into per-(draft, voter) scorecards.
        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for draft, voter, section, task, resp in results:
            key = (draft.draft_id, voter.provider_id)
            g = grouped.setdefault(key, {"draft": draft, "voter": voter.provider_id,
                                         "scores": [], "missing": []})
            content_dict = (resp.parsed_move.content if resp.ok and resp.parsed_move
                            and isinstance(resp.parsed_move.content, dict) else {})
            breakdown, status, flags = (self._parse_breakdown(content_dict)
                                        if resp.ok else (None, resp.status, []))
            if breakdown is None:
                g["missing"].append(section)
                state.section_scores_failed.append(
                    f"{draft.draft_id}:{section.value}:{voter.provider_id}")
                self._record_task_log(state, task, None, provider_id=voter.provider_id,
                                      provider_status=resp.status)
                continue
            g["scores"].append(SectionScore(
                session_id=state.session_id, section_name=section, draft_id=draft.draft_id,
                author_agent_id=draft.author_agent_id, voter_agent_id=voter.provider_id,
                provider_id=voter.provider_id, score_breakdown=breakdown,
                confidence=resp.parsed_move.confidence,
                justification=str(content_dict.get("justification", "")),
                penalty_flags=flags, provider_status=status))
            self._record_task_log(state, task, resp.parsed_move.move_id,
                                  provider_id=voter.provider_id, provider_status=resp.status)

        for key in sorted(grouped):
            g = grouped[key]
            cards.append(DraftScorecard(
                session_id=state.session_id, draft_id=g["draft"].draft_id,
                author_agent_id=g["draft"].author_agent_id, voter_agent_id=g["voter"],
                section_scores=g["scores"], missing_sections=g["missing"]))

        if drafts is None:
            state.draft_scorecards = cards
        else:
            state.draft_scorecards.extend(cards)
        return cards

    # ── Deliberation Tree Search (search as a policy-improvement operator) ────

    def _draft_mean_scores(self, state: SessionState) -> Dict[str, float]:
        """Mean overall peer score per draft_id across all scorecards. REAL
        scores only — a draft with zero valid peer scores is simply absent
        (never fabricated as 0). CED-owned; used for tree selection + audit."""
        by_draft: Dict[str, List[float]] = {}
        for card in state.draft_scorecards:
            for ss in card.section_scores:
                by_draft.setdefault(ss.draft_id, []).append(float(ss.overall_score))
        return {d: sum(v) / len(v) for d, v in by_draft.items()}

    async def _run_deliberation_tree(
        self, state: SessionState, timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Deliberation Tree Search (docs/deliberation_tree/ARCHITECTURE.md):
        spend `tree_expansions` UCB-selected revision tasks improving the most
        promising drafts, so blind assembly runs over an ENRICHED superset pool
        (never-worse: assembly can only gain candidates, never lose them).

        The AlphaGo mapping — drafts are the raw policy, peer scores the value
        estimates, this loop the search operator. Selection uses CED-owned
        scores (protocol governance); the REVISING agent sees only the parent
        draft's section texts + a generic mandate — no scores, no tree
        statistics, no ids, no identities. A failed revision is logged and
        skipped, never fabricated. Revisions are peer-scored through the same
        anonymous no-self-scoring path as original drafts.
        """
        from .deliberation_tree import DeliberationTree

        tree = DeliberationTree(exploration=self.tree_exploration)
        means = self._draft_mean_scores(state)
        drafts_by_id: Dict[str, SectionDraft] = {}
        for d in state.section_drafts:
            tree.add_root_draft(d.draft_id, means.get(d.draft_id))
            drafts_by_id[d.draft_id] = d

        # Authors captured BEFORE the loop (revision moves join the same phase).
        authors = [m.agent_id for m in state.moves_for_phase(DialogPhase.SYNTHESIS)]
        adapters = self._ranked_adapters(state)
        expansion_log: List[Dict[str, Any]] = []

        if not tree.nodes or not adapters or not authors:
            audit = {"enabled": True, "skipped": "no_drafts_or_adapters",
                     "expansion_log": expansion_log}
            self._tree_audits[state.session_id] = audit
            return audit

        for i in range(self.tree_expansions):
            parent_id = tree.select()
            parent = drafts_by_id[parent_id]
            agent_id = authors[i % len(authors)]
            context = self._registry_phase_context(
                state, DialogPhase.SYNTHESIS, agent_id)
            # Agent-visible: section TEXTS only — no draft id, author, or score.
            context["draft_under_revision"] = {
                s.value: parent.section_text(s) for s in SECTION_ORDER}
            context["revision_mandate"] = (
                "Produce a STRONGER complete five-section draft than the one in "
                "draft_under_revision. Keep what is genuinely strong; rewrite "
                "what is weak. Do not change things merely to look different.")
            task = AgentTask(
                session_id=state.session_id, agent_id=agent_id,
                role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
                question=state.question, context=context,
                output_schema={"_role": AgentRole.SYNTHESIZER.value,
                               "_question": state.question, "_sections": True},
                round_number=state.round_number,
                task_kind=TaskKind.TREE_REVISION, slot_index=i, attempt_index=0,
            )
            agent_state = state.agent_states.get(
                agent_id, AgentState(agent_id=agent_id,
                                     primary_role=AgentRole.SYNTHESIZER,
                                     assigned_role=AgentRole.SYNTHESIZER))
            adapter = self._adapter_for_agent(state, agent_id)
            resp = await self.registry.run_adapter(
                adapter, task, agent_state, timeout_seconds)

            if not resp.ok:
                # Budget spent, honestly recorded — never a fabricated draft.
                self._record_task_log(state, task, None,
                                      provider_id=resp.provider_id,
                                      provider_status=resp.status)
                expansion_log.append({"parent": parent_id, "ok": False,
                                      "provider_id": resp.provider_id})
                continue

            move = resp.parsed_move
            move.move_id = self._deterministic_move_id(
                state, agent_id, DialogPhase.SYNTHESIS, AgentRole.SYNTHESIZER,
                TaskKind.TREE_REVISION, i, 0)
            move.task_kind = TaskKind.TREE_REVISION
            move.slot_index = i
            move.attempt_index = 0
            move.provider_id = resp.provider_id
            state.moves.append(move)
            self._record_task_log(state, task, move.move_id,
                                  provider_id=resp.provider_id,
                                  provider_status=resp.status)

            c = move.content
            new_draft = SectionDraft(
                draft_id=f"draft_{move.move_id}",     # deterministic, like originals
                session_id=state.session_id,
                author_agent_id=move.agent_id,
                move_id=move.move_id,
                provider_id=move.provider_id,          # producer (no-self-scoring)
                core_answer=str(c.get("core_answer", "")),
                crucial_stress_test=str(c.get("crucial_stress_test", "")),
                blind_spots=str(c.get("blind_spots", "")),
                nuance=str(c.get("nuance", "")),
                final_verdict=str(c.get("final_verdict", "")),
            )
            state.section_drafts.append(new_draft)
            drafts_by_id[new_draft.draft_id] = new_draft

            # Same blind anonymous scoring path as every original draft.
            await self.score_section_drafts_with_registry(
                state, timeout_seconds, drafts=[new_draft])
            child_score = self._draft_mean_scores(state).get(new_draft.draft_id)
            tree.attach(parent_id, new_draft.draft_id, child_score)
            expansion_log.append({
                "parent": parent_id, "child": new_draft.draft_id, "ok": True,
                "child_score": round(child_score, 4) if child_score is not None else None,
            })

        audit = tree.audit()
        audit["expansion_log"] = expansion_log
        self._tree_audits[state.session_id] = audit
        return audit

    # ── Blind Section Assembly (section-by-section, mechanical) ───────────────

    def _section_ranking(
        self, state: SessionState, section: SectionName,
        weighting: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank drafts for one section by the tie-breaker chain:
          1. highest average overall_score (weighted by voter confidence when
             score_weighting == "confidence"; plain mean when "uniform")
          2. lower variance   3. higher score_count   4. deterministic draft_id
        `weighting` overrides self.score_weighting (used by the audit to compare
        the two aggregations); variance/count/id tie-breakers stay unchanged.
        """
        mode = weighting or self.score_weighting
        by_draft: Dict[str, List[Tuple[float, float]]] = {}   # draft -> [(score, weight)]
        for ss in state.section_scores_for(section):
            w = float(ss.confidence) if mode == "confidence" else 1.0
            by_draft.setdefault(ss.draft_id, []).append((float(ss.overall_score), w))

        stats: List[Dict[str, Any]] = []
        for draft_id, pairs in by_draft.items():
            scores = [s for s, _ in pairs]
            wsum = sum(w for _, w in pairs)
            # weighted mean; if every weight is 0 (all-zero confidence) fall back
            # to the plain mean so a section is never lost to a division by zero.
            avg = (sum(s * w for s, w in pairs) / wsum) if wsum > 0 \
                else (sum(scores) / len(scores))
            stats.append({
                "draft_id": draft_id,
                "average_score": avg,
                "score_count": len(pairs),
                "variance": self._variance(scores),
            })
        stats.sort(key=lambda s: (
            -s["average_score"],   # 1. highest average
            s["variance"],         # 2. lower variance
            -s["score_count"],     # 3. higher count
            s["draft_id"],         # 4. deterministic id order
        ))
        return stats

    def _assembly_coherence(self, state: SessionState) -> Dict[str, Any]:
        """Phase 24 observability: how fragmented the blind assembly is — i.e. how
        many DISTINCT drafts the five resolved sections were stitched from. High
        fragmentation ⇒ higher cross-section-incoherence risk (which the ratifier
        is told to check). CED-owned audit; a metric, never a semantic judgement,
        and never shown to agents."""
        assembled = state.assembled_answer
        if assembled is None:
            return {"resolved_sections": 0, "distinct_source_drafts": 0,
                    "fragmentation": 0.0, "single_source": True}
        resolved = [s for s in assembled.sections if not s.unresolved and s.selected_draft_id]
        drafts = {s.selected_draft_id for s in resolved}
        n = len(resolved)
        return {
            "resolved_sections": n,
            "distinct_source_drafts": len(drafts),
            "fragmentation": round(len(drafts) / n, 4) if n else 0.0,
            "single_source": len(drafts) <= 1,
            "cohesion_margin": self.cohesion_margin,
            "cohesion_overrides": self._cohesion_overrides,
        }

    def _assembly_reliability(self, state: SessionState) -> Dict[str, Any]:
        """Phase 26 observability: per-section CORROBORATION depth. Each resolved
        section carries the number of PEER scores its winning draft got; a section
        that won on a single score (or none, via fallback) rests on thin evidence.
        This surfaces which parts of the answer are well-corroborated vs one-voter
        opinions — an epistemic-honesty signal. CED-owned audit; a mechanical
        count, never a semantic judgement, and never shown to agents."""
        assembled = state.assembled_answer
        empty = {"resolved_sections": 0, "min_corroboration": 0,
                 "mean_corroboration": 0.0, "thinly_corroborated_sections": 0,
                 "thin_sections": [], "well_corroborated": True}
        if assembled is None:
            return empty
        resolved = [s for s in assembled.sections if not s.unresolved and s.selected_draft_id]
        if not resolved:
            return empty
        counts = [s.score_count for s in resolved]
        thin = [s.section_name.value for s in resolved
                if s.score_count < self.WELL_CORROBORATED_MIN]
        return {
            "resolved_sections": len(resolved),
            "min_corroboration": min(counts),
            "mean_corroboration": round(sum(counts) / len(counts), 4),
            "thinly_corroborated_sections": len(thin),
            "thin_sections": thin,
            "well_corroborated": not thin,
        }

    def _assembly_flags(self, state: SessionState) -> Dict[str, Any]:
        """Phase 27: penalty flags voters raised on the WINNING content of each
        assembled section — the epistemic concerns that shipped with the answer.
        These were parsed and stored but never surfaced (inert). Aggregated here
        so a section that WON on score yet carries e.g. an unsupported_claim /
        logical_gap / missed_uncertainty flag is visible. Mechanical count of the
        council's own flags — never a CED judgement; audit-only, hidden from
        agents; scores/identities never exposed (only flag names + counts)."""
        assembled = state.assembled_answer
        empty = {"flagged_sections": [], "flags_by_section": {},
                 "serious_flag_count": 0, "clean": True}
        if assembled is None:
            return empty
        by_section: Dict[str, Dict[str, int]] = {}
        serious = 0
        for sec in assembled.sections:
            if sec.unresolved or not sec.selected_draft_id:
                continue
            counts: Dict[str, int] = {}
            for ss in state.section_scores_for(sec.section_name):
                if ss.draft_id != sec.selected_draft_id:
                    continue   # only flags on the content that WON this section
                for f in ss.penalty_flags:
                    counts[f.value] = counts.get(f.value, 0) + 1
            if counts:
                by_section[sec.section_name.value] = counts
                serious += sum(c for fv, c in counts.items()
                               if fv not in self.STYLISTIC_FLAG_VALUES)
        return {
            "flagged_sections": sorted(by_section),
            "flags_by_section": by_section,
            "serious_flag_count": serious,
            "clean": serious == 0,
        }

    def _weighting_audit(self, state: SessionState) -> Dict[str, Any]:
        """Phase 23 observability: report the aggregation mode and, when
        confidence-weighting is on, how many section winners it moved vs the
        plain mean — so its effect can be honestly evaluated (never hidden)."""
        if self.score_weighting == "uniform":
            return {"mode": "uniform", "sections_reweighted": 0}
        flips = 0
        for section in SECTION_ORDER:
            w = self._section_ranking(state, section, weighting="confidence")
            u = self._section_ranking(state, section, weighting="uniform")
            if w and u and w[0]["draft_id"] != u[0]["draft_id"]:
                flips += 1
        return {"mode": "confidence", "sections_reweighted": flips}

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

    def _fallback_section(self, state: SessionState, section: SectionName) -> AssembledSection:
        """Deterministically pick a real synthesis draft for a section that has no
        peer scores (fallback mode only). Content comes from an agent draft; CED
        only selects it mechanically (by stable draft_id), never fabricates it."""
        candidates = [d for d in state.section_drafts if d.section_text(section).strip()]
        if not candidates:
            return AssembledSection(
                section_name=section, selected_draft_id="", selected_author_agent_id="",
                content="", average_score=0.0, score_count=0, variance=0.0, unresolved=True)
        chosen = sorted(candidates, key=lambda d: d.draft_id)[0]
        return AssembledSection(
            section_name=section, selected_draft_id=chosen.draft_id,
            selected_author_agent_id=chosen.author_agent_id,
            content=chosen.section_text(section),
            average_score=0.0, score_count=0, variance=0.0, unresolved=False)

    def _cohesion_strengths(self, state: SessionState) -> Dict[str, float]:
        """Each draft's GLOBAL strength = mean of its per-section average scores
        across all five sections (peer-scored). Order-independent, deterministic —
        the anchor signal for coherence-aware assembly."""
        totals: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for section in SECTION_ORDER:
            for e in self._section_ranking(state, section):
                totals[e["draft_id"]] = totals.get(e["draft_id"], 0.0) + e["average_score"]
                counts[e["draft_id"]] = counts.get(e["draft_id"], 0) + 1
        return {d: totals[d] / counts[d] for d in totals}

    def _cohesive_pick(self, ranking: List[Dict[str, Any]],
                       strengths: Dict[str, float]) -> Dict[str, Any]:
        """Among the drafts within `cohesion_margin` of the section's top score,
        choose the globally strongest (coherent anchor); ties fall back to the
        original score ranking. Never selects a draft weaker than the winner by
        more than the margin — quality is preserved within a bounded band."""
        top = ranking[0]["average_score"]
        best_key, best = None, ranking[0]
        for pos, e in enumerate(ranking):
            if e["average_score"] < top - self.cohesion_margin:
                break   # ranking is score-descending → nothing further qualifies
            key = (-strengths.get(e["draft_id"], 0.0), pos)
            if best_key is None or key < best_key:
                best_key, best = key, e
        return best

    def assemble_sections(self, session_id: str) -> AssembledAnswer:
        """
        Section-by-section blind assembly: independently for each of the five
        sections, pick the draft with the highest average overall_score (with
        deterministic tie-breakers). CED never chooses winners semantically.
        With cohesion_margin > 0, near-tied sections prefer the globally strongest
        draft, pulling the answer toward a coherent single source (Phase 25).
        """
        state = self.get_session(session_id)
        drafts_by_id = {d.draft_id: d for d in state.section_drafts}
        strengths = self._cohesion_strengths(state) if self.cohesion_margin > 0 else {}
        self._cohesion_overrides = 0

        assembled_sections: List[AssembledSection] = []
        for section in SECTION_ORDER:
            ranking = self._section_ranking(state, section)
            if ranking:
                if self.cohesion_margin > 0:
                    entry = self._cohesive_pick(ranking, strengths)
                    if entry["draft_id"] != ranking[0]["draft_id"]:
                        self._cohesion_overrides += 1
                else:
                    entry = ranking[0]
                assembled_sections.append(
                    self._section_assembled(section, entry, drafts_by_id)
                )
            elif self.assembly_fallback:
                # No valid peer scores, but fallback enabled: use a real synthesis
                # draft's content (deterministic) so the answer is not empty. CED
                # still only mechanically selects an unscored draft — no fabrication.
                assembled_sections.append(self._fallback_section(state, section))
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
            # Distinct deterministic task_kind per evaluator round (not occurrence).
            rat_kind = (TaskKind.RATIFICATION_INITIAL if rounds == 1
                        else TaskKind.RATIFICATION_REVISION)
            move = self._dispatch(
                state, evaluator,
                role=AgentRole.FINAL_EVALUATOR,
                phase=DialogPhase.RATIFICATION,
                context={"assembled_draft": assembled.full_text()},
                extra_schema={"_epistemic_hint": epistemic_hint},
                task_kind=rat_kind, attempt_index=rounds - 1,
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
        self._capture_hybrid_shadow(state, final)
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
