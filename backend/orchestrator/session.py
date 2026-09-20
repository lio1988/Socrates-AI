"""Dialog session state + manager + small conversion helpers.

Holds all 15-rule per-session state (Rule 15: each engine independently
managed). Extracted from main.py.
"""

from __future__ import annotations

import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import HTTPException

from socrates_ai import (
    DialogManager, DialogConfig, DialogMode, DialogSpeed, SummaryMode,
)
from backend.storage.models import *
from backend.constitution_guard import ConstitutionGuard, ConstitutionViolationError
from backend.orchestrator.convergence import compute_convergence


class EnhancedDialogSession:
    """
    Full session state implementing all 15 Constitution rules.
    Each engine is independently managed (Rule 15).
    """

    def __init__(self, session_id: str, config: DialogConfig, api_keys: dict):
        self.session_id       = session_id
        self.config           = config
        self.api_keys         = api_keys
        self.status           = "initialized"
        self.created_at       = datetime.now()
        self.current_round    = 0
        self._paused          = asyncio.Event()
        self._paused.set()    # starts unpaused
        self._stop_requested  = False

        # ── Rule 1: Socratic rotation tracking ──────────────────────────
        self.available_models:    List[str] = list(api_keys.keys())
        self.socratic_rotation:   List[str] = []  # history of who was Socrates
        self.rounds_as_socrates:  Dict[str, int] = {m: 0 for m in self.available_models}
        self.current_socrates:    str = ""

        # ── Dialogue history ─────────────────────────────────────────────
        self.history:       List[DialogTurnResponse] = []
        self.scores:        Dict[str, int] = {m: 0 for m in self.available_models}

        # ── Rule 6: Claims store ─────────────────────────────────────────
        self.claims:        List[Claim] = []

        # ── Rule 7: Contradiction Graph ──────────────────────────────────
        self.contradiction_graph: ContradictionGraphData = ContradictionGraphData()

        # ── Rule 8: Knowledge Graph ──────────────────────────────────────
        self.knowledge_graph: KnowledgeGraphData = KnowledgeGraphData()

        # ── Rule 9: Consensus Memory ─────────────────────────────────────
        self.consensus_memory:    ConsensusMemoryData = ConsensusMemoryData()
        self._prev_conclusion_count: int = 0

        # ── Rule 3: Elenchus history ─────────────────────────────────────
        self.elenchus_history:    List[ElenchusResult] = []

        # ── Rule 5: Reflection history ───────────────────────────────────
        self.reflection_history:  List[ReflectionStep] = []

        # ── Rule 10: Complexity ──────────────────────────────────────────
        self.complexity:          Optional[ComplexityAssessment] = None
        self.enforced_rounds:     int = config.rounds

        # ── Rule 11: Convergence ─────────────────────────────────────────
        self.convergence_score:   float = 0.0
        self.consensus_stable:    bool  = False

        # ── Rule 12+13: Synthesis ────────────────────────────────────────
        self.synthesis_result:    Optional[SynthesisResult] = None
        self.synthesis_domain:    Optional[Domain]          = None

        # ── Rule 14: Evolution log ───────────────────────────────────────
        self.evolution_log:       List[EvolutionEntry] = []

        # ── Constitution Guard log ────────────────────────────────────────
        self.constitution_violations: List[str] = []

        # ── Injected questions (mid-dialogue) ────────────────────────────
        self.pending_injection:   Optional[str] = None

        # ── Dialog manager (from socrates_ai) ────────────────────────────
        self.manager:             Optional[DialogManager] = None

    # ── Rotation helpers (Rule 1) ────────────────────────────────────────────

    def next_socrates(self) -> str:
        """
        Rule 1: Select next Socrates using round-robin rotation.
        Explicitly avoids permanent authority.
        """
        idx = len(self.socratic_rotation) % len(self.available_models)
        model = self.available_models[idx]
        try:
            ConstitutionGuard.assert_socratic_rotation(
                model,
                self.current_socrates or None,
                self.rounds_as_socrates,
                self.enforced_rounds,
            )
        except ConstitutionViolationError as exc:
            self._log_violation(exc)
            # Force pick next in rotation
            idx = (idx + 1) % len(self.available_models)
            model = self.available_models[idx]

        self.current_socrates = model
        self.socratic_rotation.append(model)
        self.rounds_as_socrates[model] = self.rounds_as_socrates.get(model, 0) + 1
        return model

    # ── Convergence update (Rule 11) ─────────────────────────────────────────

    def update_convergence(self) -> None:
        self.convergence_score, self.consensus_stable = compute_convergence(
            self.consensus_memory,
            self.elenchus_history,
            self._prev_conclusion_count,
        )
        self._prev_conclusion_count = len(self.consensus_memory.verified_conclusions)

    # ── Constitution violation logger ────────────────────────────────────────

    def _log_violation(self, exc: ConstitutionViolationError) -> None:
        entry = f"[R{self.current_round}] Rule {exc.rule}: {exc.description}"
        self.constitution_violations.append(entry)
        self.evolution_log.append(EvolutionEntry(
            component="reasoning_policy",
            change=f"Violation detected: {entry}",
            reason="Automatic Constitution enforcement",
            round=self.current_round,
        ))

    def to_status_response(self) -> DialogStatusResponse:
        rotation_info = None
        if self.available_models:
            nxt_idx = len(self.socratic_rotation) % len(self.available_models)
            rotation_info = SocraticRotationInfo(
                rotation_order=self.socratic_rotation,
                current_socrates=self.current_socrates,
                next_socrates=self.available_models[nxt_idx],
                rounds_as_socrates=self.rounds_as_socrates,
            )
        return DialogStatusResponse(
            session_id=self.session_id,
            topic=self.config.topic,
            rounds_planned=self.enforced_rounds,
            rounds_completed=self.current_round,
            mode=self.config.mode.value,
            status=self.status,
            complexity=self.complexity,
            convergence_score=self.convergence_score,
            consensus_stable=self.consensus_stable,
            socratic_rotation=rotation_info,
            history=self.history,
            scores=self.scores,
            constitution_violations=self.constitution_violations,
        )


# ============================================================================
# SECTION 8: SESSION MANAGER
# ============================================================================

class DialogSessionManager:
    """Thread-safe in-memory session store (Rule 15: independent module)"""

    def __init__(self):
        self._sessions: Dict[str, EnhancedDialogSession] = {}

    def create(self, session_id: str, config: DialogConfig, api_keys: dict) -> EnhancedDialogSession:
        if session_id in self._sessions:
            raise HTTPException(409, "Session already exists.")
        if len(self._sessions) >= 100:
            raise HTTPException(429, "Session storage is full. Delete completed sessions first.")
        active = sum(session.status not in {"completed", "stopped", "error"} for session in self._sessions.values())
        if active >= 2:
            raise HTTPException(429, "At most two dialogs may run at once.")
        session = EnhancedDialogSession(session_id, config, api_keys)
        session.manager = DialogManager(config, api_keys)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[EnhancedDialogSession]:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> EnhancedDialogSession:
        session = self.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
        return session

    def delete(self, session_id: str) -> bool:
        session = self.get(session_id)
        if session is not None and session.status not in {"completed", "stopped", "error"}:
            raise HTTPException(409, "Stop the dialog and wait for completion before deleting it.")
        return self._sessions.pop(session_id, None) is not None

    def list_all(self) -> List[dict]:
        return [
            {
                "session_id": s.session_id,
                "topic": s.config.topic,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "rounds_planned": s.enforced_rounds,
                "rounds_completed": s.current_round,
                "convergence_score": s.convergence_score,
                "consensus_stable": s.consensus_stable,
                "constitution_violations": len(s.constitution_violations),
            }
            for s in self._sessions.values()
        ]


session_manager = DialogSessionManager()


# ============================================================================
# SECTION 9: HELPERS
# ============================================================================

def is_real_api_key(value: str | None) -> bool:
    """Return True only for non-empty, non-placeholder API keys.

    This keeps /health and the live pipeline from treating example .env values
    such as xai-your-grok-key-here as real providers.
    """
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False

    lowered = stripped.lower()
    placeholder_markers = (
        "your-",
        "placeholder",
        "changeme",
        "example",
        "key-here",
        "...",
    )
    return not any(marker in lowered for marker in placeholder_markers)


def get_api_keys() -> dict:
    keys = {
        "claude":  os.getenv("ANTHROPIC_API_KEY", ""),
        "grok":    os.getenv("XAI_API_KEY", ""),
        "gemini":  os.getenv("GOOGLE_API_KEY", ""),
        "chatgpt": os.getenv("OPENAI_API_KEY", ""),
    }
    return {k: v.strip() for k, v in keys.items() if is_real_api_key(v)}


def speed_to_model(s: DialogSpeedEnum) -> DialogSpeed:
    return {
        DialogSpeedEnum.VERY_SLOW: DialogSpeed.VERY_SLOW,
        DialogSpeedEnum.SLOW:      DialogSpeed.SLOW,
        DialogSpeedEnum.NORMAL:    DialogSpeed.NORMAL,
        DialogSpeedEnum.FAST:      DialogSpeed.FAST,
        DialogSpeedEnum.VERY_FAST: DialogSpeed.VERY_FAST,
    }[s]


def mode_to_model(m: DialogModeEnum) -> DialogMode:
    return {
        DialogModeEnum.SOCRATIC:  DialogMode.SOCRATIC,
        DialogModeEnum.DEBATE:    DialogMode.DEBATE,
        DialogModeEnum.CONSENSUS: DialogMode.CONSENSUS,
    }[m]


def summary_to_model(s: SummaryModeEnum) -> SummaryMode:
    return {
        SummaryModeEnum.NONE:  SummaryMode.NONE,
        SummaryModeEnum.EVERY: SummaryMode.EVERY,
        SummaryModeEnum.HALF:  SummaryMode.HALF,
    }[s]


def generate_session_id() -> str:
    return f"dialog_{uuid.uuid4().hex[:12]}"
