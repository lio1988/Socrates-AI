"""Public, local-only observation bridge for the canonical CED registry session.

This module deliberately owns no dialogue decisions.  It observes one isolated
``CEDOrchestrator.run_registry_session`` invocation and projects a small,
versioned, append-only public record.  Provider data, task logs, scores, model
identity and the unreleased final candidate never cross this boundary.
"""

from __future__ import annotations

import asyncio
import copy
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, Iterable, List, Optional, Sequence

from backend.dialogues.ced import (
    CanonicalRegistryApplicationOutcome,
    CEDOrchestrator,
)
from backend.dialogues.live_providers import build_council
from backend.dialogues.models import AgentMove, DialogPhase, FinalResponse, SessionState
from backend.dialogues.provider_registry import ScriptedMockProvider
from backend.dialogues.socratic import CommitmentRecord, live_commitments
from socrates.rendering import (
    NormalRenderResult,
    render_normal_response,
    sanitize_normal_text,
)


PUBLIC_EVENT_SCHEMA = "socrates.public-council.v1"
PUBLIC_RUN_PREFIX = "ced_"
MAX_RETAINED_RUNS = 32

PHASE_ORDER = (
    DialogPhase.OPENING,
    DialogPhase.INITIAL_RESPONSE,
    DialogPhase.ELENCHUS,
    DialogPhase.REFLECTION,
    DialogPhase.RECONSTRUCTION,
    DialogPhase.SYNTHESIS,
    DialogPhase.RATIFICATION,
)
PHASE_LABELS = {
    DialogPhase.OPENING: "Opening question",
    DialogPhase.INITIAL_RESPONSE: "Initial positions",
    DialogPhase.ELENCHUS: "Elenchus",
    DialogPhase.REFLECTION: "Reflection",
    DialogPhase.RECONSTRUCTION: "Reconstruction",
    DialogPhase.SYNTHESIS: "Synthesis",
    DialogPhase.RATIFICATION: "Ratification",
}
ROLE_LABELS = {
    "socrates": "Socrates",
    "elenchus_critic": "Elenchus critic",
    "empiricist": "Empiricist",
    "maieutic_reconstructor": "Maieutic reconstructor",
    "synthesizer": "Synthesizer",
    "reflector": "Reflector",
    "final_evaluator": "Final evaluator",
}
COUNCIL_ALIASES = ("Aletheia", "Logos", "Praxis", "Metis")

# Only these canonical move fields are public display material.  Unknown keys
# are ignored, never recursively serialized as a convenience.
_PUBLIC_MOVE_FIELDS = (
    "question",
    "critique_summary",
    "weak_assumptions",
    "logic_gaps",
    "contradictions",
    "factual_claims",
    "evidence_quality",
    "documentation_gaps",
    "key_insights",
    "synthesis_draft",
    "unresolved_tensions",
    "reason_for_revision",
    "revised_position",
    "integrated_critiques",
    "stronger_position",
    "remaining_weaknesses",
    "core_answer",
    "crucial_stress_test",
    "blind_spots",
    "nuance",
    "final_verdict",
)
_PUBLIC_NESTED_MOVE_FIELDS = {
    "factual_claims": ("claim", "status", "notes"),
}
_WINDOWS_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:\\(?:[^\s<>:\"|?*]+\\)*[^\s<>:\"|?*]*)"
)
_FILE_URI = re.compile(r"(?i)\bfile:///?[^\s]+")
_UNIX_PRIVATE_PATH = re.compile(
    r"(?<![A-Za-z0-9])/(?:Users|home|tmp|var/tmp|private|mnt|workspace)/[^\s]+"
)
_HEADING = re.compile(r"(?m)^##\s+([^\r\n]+)\s*$")
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,96}$")


def _safe_text(value: Any, *, limit: int = 16_000) -> str:
    if not isinstance(value, str):
        return ""
    text = sanitize_normal_text(value)
    text = _WINDOWS_PATH.sub("[REDACTED PATH]", text)
    text = _FILE_URI.sub("[REDACTED PATH]", text)
    text = _UNIX_PRIVATE_PATH.sub("[REDACTED PATH]", text)
    return text[:limit]


def project_public_text(value: Any, *, limit: int = 16_000) -> str:
    """Return text safe for the browser-visible public council surface."""

    return _safe_text(value, limit=limit)


def _safe_identifier(value: Any, *, fallback: str = "public_item") -> str:
    if not isinstance(value, str):
        return fallback
    value = value[:128]
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value) else fallback


def _seat_index(seat_id: str) -> Optional[int]:
    match = re.search(r"(\d+)$", seat_id or "")
    return int(match.group(1)) if match else None


def _seat_alias(seat_id: str) -> str:
    index = _seat_index(seat_id)
    if index is not None and 0 <= index < len(COUNCIL_ALIASES):
        return COUNCIL_ALIASES[index]
    return "Council member"


def _public_seat(seat_id: str, role: Optional[str]) -> Dict[str, Any]:
    seat_id = _safe_identifier(seat_id, fallback="council_seat")
    return {
        "seat_id": seat_id,
        "alias": _seat_alias(seat_id),
        "role": role,
        "role_label": ROLE_LABELS.get(role or "", "Awaiting role"),
    }


def project_public_seat_identities(seat_ids: Sequence[str]) -> List[Dict[str, str]]:
    """Project stable public identities without provider/model topology."""

    return [
        {
            "seat_id": _safe_identifier(seat_id),
            "alias": _seat_alias(seat_id),
        }
        for seat_id in seat_ids
    ]


def _phase_payload(phase: DialogPhase, round_index: int = 0) -> Dict[str, Any]:
    return {
        "id": phase.value,
        "label": PHASE_LABELS[phase],
        "index": PHASE_ORDER.index(phase),
        "round": int(round_index),
    }


def _flatten_public_value(
    value: Any,
    *,
    allowed_mapping_fields: Sequence[str] = (),
) -> List[str]:
    if isinstance(value, str):
        text = _safe_text(value)
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, (list, tuple)):
        out: List[str] = []
        for item in value[:24]:
            out.extend(
                _flatten_public_value(
                    item,
                    allowed_mapping_fields=allowed_mapping_fields,
                )
            )
        return out
    if isinstance(value, dict):
        # Nested objects fail closed. Only explicitly public schema fields may
        # contribute display text; unknown values are never recursively
        # serialized merely because their parent field is public.
        out: List[str] = []
        for key in allowed_mapping_fields:
            if key in value:
                out.extend(_flatten_public_value(value[key]))
        return out
    return []


def project_public_move(move: AgentMove) -> Dict[str, Any]:
    """Project one already-accepted canonical move through a strict allowlist."""

    content = move.content if isinstance(move.content, dict) else {}
    fragments: List[str] = []
    headline = ""
    for key in _PUBLIC_MOVE_FIELDS:
        if key not in content:
            continue
        values = _flatten_public_value(
            content[key],
            allowed_mapping_fields=_PUBLIC_NESTED_MOVE_FIELDS.get(key, ()),
        )
        if not headline and values:
            headline = values[0]
        if values:
            label = key.replace("_", " ").capitalize()
            fragments.append(f"{label}: " + " · ".join(values))
    confidence = float(move.confidence)
    return {
        "move_id": _safe_identifier(move.move_id, fallback="accepted_move"),
        "seat_id": _safe_identifier(move.agent_id, fallback="council_seat"),
        "alias": _seat_alias(move.agent_id),
        "role": move.role.value,
        "role_label": ROLE_LABELS.get(move.role.value, move.role.value),
        "phase": move.phase.value,
        "task_kind": move.task_kind.value if move.task_kind is not None else None,
        "status": "accepted",
        "confidence": confidence,
        "confidence_label": (
            "High" if confidence >= 0.75 else "Moderate" if confidence >= 0.5 else "Low"
        ),
        "headline": headline,
        "display_text": _safe_text("\n".join(fragments)),
    }


def project_commitments(history: Sequence[CommitmentRecord]) -> List[Dict[str, Any]]:
    """Project the exact ledger and compute current records from that universe."""

    current_ids = {record.commitment_id for record in live_commitments(history)}
    return [
        {
            "commitment_id": _safe_identifier(record.commitment_id, fallback="commitment"),
            "cycle": int(record.cycle),
            "claim": _safe_text(record.claim),
            "status": record.status.value,
            "target_commitment_id": (
                _safe_identifier(record.target_commitment_id, fallback="commitment")
                if record.target_commitment_id is not None else None
            ),
            "is_current": record.commitment_id in current_ids,
        }
        for record in history
    ]


def _public_sections(public_answer: str) -> List[Dict[str, str]]:
    matches = list(_HEADING.finditer(public_answer))
    if not matches:
        return ([{"id": "answer", "title": "Council answer", "content": public_answer}]
                if public_answer else [])
    sections: List[Dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(public_answer)
        title = _safe_text(match.group(1), limit=160)
        section_id = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or f"section_{index}"
        sections.append({
            "id": section_id,
            "title": title,
            "content": _safe_text(public_answer[start:end].strip()),
        })
    return sections


def project_normal_render(rendered: NormalRenderResult) -> Dict[str, Any]:
    """Publish only fields already authorized by the Normal renderer."""

    public_answer = _safe_text(rendered.public_answer)
    return {
        "outcome": rendered.outcome,
        "release_decision": rendered.release_decision,
        "governing_status": rendered.governing_epistemic_status,
        "notice": _safe_text(rendered.notice, limit=2_000),
        "answer_released": bool(rendered.candidate_authorized),
        "public_answer": public_answer,
        "sections": _public_sections(public_answer) if rendered.candidate_authorized else [],
    }


def project_final(final: FinalResponse) -> Dict[str, Any]:
    """Publish only what the governing normal renderer authorizes."""

    return project_normal_render(render_normal_response(final))


class _PublicEventStore:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._events: List[Dict[str, Any]] = []
        self._subscribers: set[asyncio.Queue] = set()
        self.terminal = False

    @property
    def events(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._events)

    def append(self, event_type: str, data: Dict[str, Any], *, terminal: bool = False) -> None:
        event = {
            "schema_version": PUBLIC_EVENT_SCHEMA,
            "run_id": self.run_id,
            "sequence": len(self._events),
            "type": event_type,
            "data": copy.deepcopy(data),
        }
        self._events.append(event)
        if terminal:
            self.terminal = True
        for queue in tuple(self._subscribers):
            queue.put_nowait(copy.deepcopy(event))

    async def subscribe(self, after_sequence: int = -1) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        # No await between snapshot and registration: an appender in this event
        # loop cannot create a replay gap.
        existing = [copy.deepcopy(event) for event in self._events
                    if event["sequence"] > after_sequence]
        terminal_at_snapshot = self.terminal
        self._subscribers.add(queue)
        try:
            for event in existing:
                yield event
            if terminal_at_snapshot:
                return
            while True:
                event = await queue.get()
                if event["sequence"] <= after_sequence:
                    if event["type"] in {"run.completed", "run.failed"}:
                        return
                    continue
                yield event
                if event["type"] in {"run.completed", "run.failed"}:
                    return
        finally:
            self._subscribers.discard(queue)


@dataclass
class LocalCouncilRun:
    run_id: str
    question: str
    status: str = "queued"
    provider_mode: str = ""
    ced: Optional[CEDOrchestrator] = None
    state: Optional[SessionState] = None
    final: Optional[FinalResponse] = None
    task: Optional[asyncio.Task] = field(default=None, repr=False)
    _store: _PublicEventStore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._store = _PublicEventStore(self.run_id)

    @property
    def events(self) -> List[Dict[str, Any]]:
        return self._store.events

    def emit(self, event_type: str, data: Dict[str, Any], *, terminal: bool = False) -> None:
        self._store.append(event_type, data, terminal=terminal)

    async def subscribe(self, after_sequence: int = -1) -> AsyncIterator[Dict[str, Any]]:
        async for event in self._store.subscribe(after_sequence):
            yield event

    def public_snapshot(self) -> Dict[str, Any]:
        events = self._store.events
        contributions = [event["data"]["move"] for event in events
                         if event["type"] == "move.accepted"]
        commitments: List[Dict[str, Any]] = []
        final: Optional[Dict[str, Any]] = None
        ratification: Optional[Dict[str, Any]] = None
        phases: List[Dict[str, Any]] = []
        for event in events:
            if event["type"] == "phase.started":
                phases.append(event["data"]["phase"])
            elif event["type"] == "commitments.snapshot":
                commitments = event["data"]["commitments"]
            elif event["type"] == "ratification.completed":
                ratification = event["data"]["ratification"]
            elif event["type"] == "run.completed":
                final = event["data"]["final"]
        return copy.deepcopy({
            "schema_version": PUBLIC_EVENT_SCHEMA,
            "run_id": self.run_id,
            "question": _safe_text(self.question, limit=8_000),
            "status": self.status,
            "phases": phases,
            "contributions": contributions,
            "commitments": commitments,
            "ratification": ratification,
            "final": final,
        })


class _CouncilObserver:
    """Temporary instance-level observation at canonical mutation seams."""

    def __init__(self, run: LocalCouncilRun) -> None:
        self.run = run
        self.ced = run.ced
        self._originals: Dict[str, Any] = {}
        self._ratification_attempts: Dict[str, int] = {}

    def _emit_safe(self, event_type: str, data_factory: Callable[[], Dict[str, Any]]) -> None:
        # Observability is subordinate to the canonical run.  A projector error
        # may hide an event, but can never change CED output or mutation order.
        try:
            self.run.emit(event_type, data_factory())
        except Exception:
            return

    def _ratification_seats(self, state: SessionState) -> List[Dict[str, Any]]:
        assert self.ced is not None
        healthy = self.ced._healthy_adapters()
        bindings = self.ced._session_adapter_bindings.get(state.session_id, {})
        seats: List[Dict[str, Any]] = []
        used: set[str] = set()
        for index, adapter in enumerate(healthy):
            logical = next((agent_id for agent_id, bound in bindings.items()
                            if bound is adapter and agent_id not in used), None)
            seat_id = logical or f"agent_{index}"
            used.add(seat_id)
            seats.append(_public_seat(seat_id, "final_evaluator"))
        return seats

    @contextmanager
    def installed(self):
        assert self.ced is not None
        ced = self.ced
        self._originals = {
            "prepare": ced._prepare_registry_phase,
            "apply": ced._apply_registry_response,
            "finalize": ced._finalize_registry_phase,
            "run_phase": ced._run_registry_phase,
            "ratify": ced.run_council_ratification,
        }

        def prepare(state: SessionState, phase: DialogPhase):
            specs = self._originals["prepare"](state, phase)
            self._emit_safe("phase.started", lambda: {
                "phase": _phase_payload(phase, state.round_number),
                "seats": [_public_seat(spec.agent_id, spec.role.value) for spec in specs],
            })
            return specs

        def apply(state, phase, task, response, dispatch):
            application = self._originals["apply"](
                state, phase, task, response, dispatch
            )
            if application.outcome is CanonicalRegistryApplicationOutcome.ACCEPTED:
                move = next((item for item in reversed(state.moves)
                             if item.move_id == application.accepted_move_id), None)
                if move is not None:
                    self._emit_safe("move.accepted", lambda: {"move": project_public_move(move)})
            else:
                self._emit_safe("operation.rejected", lambda: {
                    "phase": phase.value,
                    "seat_id": task.agent_id,
                    "code": "candidate_rejected",
                })
            return application

        def finalize(state, phase, responses, dispatch, effective_quorum):
            result = self._originals["finalize"](
                state, phase, responses, dispatch, effective_quorum
            )
            self._emit_safe("commitments.snapshot", lambda: {
                "commitments": project_commitments(ced.commitment_ledger(state))
            })
            return result

        async def run_phase(state, phase, timeout_seconds):
            result = await self._originals["run_phase"](
                state, phase, timeout_seconds
            )
            self._emit_safe("phase.completed", lambda: {
                "phase": _phase_payload(phase, state.round_number),
                "status": "completed" if result.proceed else "blocked",
            })
            return result

        async def ratify(state, timeout_seconds=None, round_index=0):
            attempt = self._ratification_attempts.get(state.session_id, 0)
            self._ratification_attempts[state.session_id] = attempt + 1
            self._emit_safe("phase.started", lambda: {
                "phase": _phase_payload(DialogPhase.RATIFICATION, attempt),
                "seats": self._ratification_seats(state),
            })
            result = await self._originals["ratify"](
                state, timeout_seconds, round_index
            )
            self._emit_safe("ratification.completed", lambda: {
                "ratification": {
                    "status": result.status.value,
                    "valid_verdicts": int(result.valid_verdicts),
                    "quorum": int(result.quorum),
                    "caveat_count": int(result.caveat_count),
                    "critical_block_count": int(result.critical_block_count),
                }
            })
            self._emit_safe("phase.completed", lambda: {
                "phase": _phase_payload(DialogPhase.RATIFICATION, attempt),
                "status": result.status.value,
            })
            return result

        ced._prepare_registry_phase = prepare
        ced._apply_registry_response = apply
        ced._finalize_registry_phase = finalize
        ced._run_registry_phase = run_phase
        ced.run_council_ratification = ratify
        try:
            yield
        finally:
            ced._prepare_registry_phase = self._originals["prepare"]
            ced._apply_registry_response = self._originals["apply"]
            ced._finalize_registry_phase = self._originals["finalize"]
            ced._run_registry_phase = self._originals["run_phase"]
            ced.run_council_ratification = self._originals["ratify"]


@contextmanager
def observe_public_council(run: LocalCouncilRun, ced: CEDOrchestrator):
    """Install the existing subordinate public observer for one Normal run."""

    run.ced = ced
    with _CouncilObserver(run).installed():
        yield


class LocalCouncilManager:
    """Own isolated local-mock CED runs and their public append-only streams."""

    def __init__(self, *, ced_factory: Optional[Callable[[], Any]] = None,
                 max_retained_runs: int = MAX_RETAINED_RUNS) -> None:
        self._ced_factory = ced_factory or (
            lambda: build_council(env={}, council_size=4)
        )
        self._runs: Dict[str, LocalCouncilRun] = {}
        self._lock = asyncio.Lock()
        self._max_retained_runs = max(1, int(max_retained_runs))

    @property
    def runs(self) -> Dict[str, LocalCouncilRun]:
        return dict(self._runs)

    def get_run(self, run_id: str) -> Optional[LocalCouncilRun]:
        return self._runs.get(run_id)

    def _new_run_id(self) -> str:
        return PUBLIC_RUN_PREFIX + secrets.token_hex(12)

    def _trim_terminal_runs(self) -> None:
        terminal = [run_id for run_id, run in self._runs.items()
                    if run.status in {"completed", "blocked", "failed"}]
        excess = len(self._runs) - self._max_retained_runs
        for run_id in terminal[:max(0, excess)]:
            self._runs.pop(run_id, None)

    @staticmethod
    def _assert_offline_ced(ced: Any, mode: str) -> CEDOrchestrator:
        if not isinstance(ced, CEDOrchestrator) or mode != "mock":
            raise RuntimeError("Local CED safety gate rejected the council configuration.")
        registry = ced.registry
        adapters = registry.all_adapters() if registry is not None else []
        if not adapters or not all(
            isinstance(adapter, ScriptedMockProvider)
            and getattr(adapter, "is_fake", False) is True
            for adapter in adapters
        ):
            raise RuntimeError("Local CED safety gate requires scripted offline providers.")
        return ced

    async def _reserve(self, question: str, run_id: Optional[str]) -> LocalCouncilRun:
        async with self._lock:
            candidate = run_id or self._new_run_id()
            if not _SAFE_RUN_ID.fullmatch(candidate):
                raise ValueError("Invalid local council run id.")
            if candidate in self._runs:
                raise ValueError("Local council run id already exists.")
            self._trim_terminal_runs()
            run = LocalCouncilRun(candidate, question)
            self._runs[candidate] = run
            return run

    async def start_run(self, question: str, *, run_id: Optional[str] = None) -> LocalCouncilRun:
        run = await self._reserve(question, run_id)
        run.task = asyncio.create_task(self._execute(run))
        return run

    async def run_to_completion(self, question: str, *, run_id: Optional[str] = None) -> LocalCouncilRun:
        run = await self._reserve(question, run_id)
        await self._execute(run)
        return run

    async def _execute(self, run: LocalCouncilRun) -> None:
        try:
            ced, mode = self._ced_factory()
            run.ced = self._assert_offline_ced(ced, mode)
            run.provider_mode = mode
            run.status = "running"
            run.emit("run.started", {
                "status": "running",
                "question": _safe_text(run.question, limit=8_000),
                "council_size": len(run.ced.agents),
            })
            observer = _CouncilObserver(run)
            with observer.installed():
                final = await run.ced.run_registry_session(
                    run.question, session_id=run.run_id
                )
            run.final = final
            run.state = run.ced.get_session(run.run_id)
            public_final = project_final(final)
            run.status = "completed" if public_final["answer_released"] else "blocked"
            run.emit("run.completed", {
                "status": run.status,
                "final": public_final,
            }, terminal=True)
        except asyncio.CancelledError:
            run.status = "failed"
            run.emit("run.failed", {
                "status": "failed",
                "message": "Local council run stopped during server shutdown.",
            }, terminal=True)
            raise
        except Exception:
            run.status = "failed"
            run.emit("run.failed", {
                "status": "failed",
                "message": "Local council run could not be completed.",
            }, terminal=True)

    async def shutdown(self) -> None:
        tasks = [run.task for run in self._runs.values()
                 if run.task is not None and not run.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


__all__ = [
    "PUBLIC_EVENT_SCHEMA",
    "LocalCouncilManager",
    "LocalCouncilRun",
    "project_commitments",
    "project_final",
    "project_normal_render",
    "project_public_seat_identities",
    "project_public_text",
    "project_public_move",
    "observe_public_council",
]
