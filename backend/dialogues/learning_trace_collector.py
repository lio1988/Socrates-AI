"""
Phase 26D — CED Learning Trace Collector.

This module wires Phase 26C's learning foundation to *finished* CED session state
without changing the orchestrator's reasoning/scoring/ratification semantics.
It is deliberately opt-in and post-run:

    dataset = collect_learning_dataset(session_state, registry=ced.registry)

No provider calls, no training, no fine-tuning, no prompt mutation, no hidden-audit
leakage. It reads CED-owned state after execution and builds sanitized traces that
future DPO/RLHF/RLAIF/reward/distillation pipelines can consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .learning_foundation import (
    LearningDataset,
    LearningSignalKind,
    LearningTrace,
    SocratesConstitution,
    assess_training_eligibility,
    sanitize_public_payload,
)
from .models import (
    AgentMove,
    AgentRole,
    AgentTask,
    CouncilRatification,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    RatificationVerdict,
    SessionState,
    TaskLogEntry,
    TaskKind,
)
from .provider_registry import CouncilProviderRegistry


@dataclass(frozen=True)
class ProviderMeta:
    provider_id: str
    provider_family: str = "unknown"
    model: str = "unknown"
    provider_name: str = ""


def infer_provider_family(provider_id: str = "", provider_name: str = "", model: str = "") -> str:
    text = " ".join([provider_id or "", provider_name or "", model or ""]).lower()
    if "nvidia" in text or "nim" in text or "nemotron" in text:
        return "nvidia"
    if "anthropic" in text or "claude" in text:
        return "anthropic"
    if "openai" in text or "gpt" in text:
        return "openai"
    if "gemini" in text or "google" in text:
        return "google"
    if "mock" in text or "scripted" in text or "fake" in text:
        return "mock"
    return "unknown"


def provider_catalog(registry: Optional[CouncilProviderRegistry]) -> Dict[str, ProviderMeta]:
    """Return provider metadata from a registry without calling any provider."""
    if registry is None:
        return {}
    catalog: Dict[str, ProviderMeta] = {}
    for adapter in registry.all_adapters():
        provider_id = getattr(adapter, "provider_id", "unknown")
        model = getattr(adapter, "model", None) or "mock"
        provider_name = getattr(adapter, "provider_name", "") or ""
        catalog[provider_id] = ProviderMeta(
            provider_id=provider_id,
            provider_family=infer_provider_family(provider_id, provider_name, model),
            model=model,
            provider_name=provider_name,
        )
    return catalog


def _meta_for(provider_id: Optional[str], catalog: Dict[str, ProviderMeta]) -> ProviderMeta:
    if provider_id and provider_id in catalog:
        return catalog[provider_id]
    return ProviderMeta(
        provider_id=provider_id or "unknown",
        provider_family=infer_provider_family(provider_id or ""),
        model="unknown",
    )


def _task_from_log(state: SessionState, entry: TaskLogEntry) -> AgentTask:
    """Reconstruct the public task identity needed for learning traces."""
    return AgentTask(
        task_id=entry.task_id,
        session_id=state.session_id,
        agent_id=entry.agent_id,
        role=entry.assigned_role,
        phase=entry.phase,
        question=state.question,
        # Keep context intentionally empty unless debug_context was explicitly
        # enabled upstream; LearningTrace sanitization still drops hidden fields.
        context=sanitize_public_payload(entry.debug_context or {}),
        output_schema={"_role": entry.schema_name or entry.assigned_role.value},
        round_number=entry.round_index,
        task_kind=entry.task_kind,
        slot_index=entry.slot_index,
        attempt_index=entry.attempt_index,
    )


def _response_from_move(entry: TaskLogEntry, move: Optional[AgentMove]) -> ProviderResponse:
    """Create a ProviderResponse-shaped record from persisted CED state."""
    status = entry.provider_status or (ProviderStatus.OK if move is not None else ProviderStatus.UNAVAILABLE)
    return ProviderResponse(
        provider_id=entry.provider_id or (move.provider_id if move else "unknown"),
        agent_id=entry.agent_id,
        status=status,
        parsed_move=move if status == ProviderStatus.OK else None,
        error_message=None if status == ProviderStatus.OK else f"provider status {status.value}",
    )


def _final_answer_payload(state: SessionState) -> Optional[Dict[str, Any]]:
    final = state.final_response
    if final is None:
        return None
    return sanitize_public_payload({
        "ratified": final.ratified,
        "ratification_status": final.ratification_status,
        "epistemic_status": final.epistemic_status.value if hasattr(final.epistemic_status, "value") else str(final.epistemic_status),
        "answer": final.answer,
        "blocking_objections": list(final.blocking_objections),
        "unresolved_sections": [s.value if hasattr(s, "value") else str(s) for s in final.unresolved_sections],
    })


def _winner_sections(state: SessionState, move: Optional[AgentMove]) -> List[str]:
    if move is None or state.assembled_answer is None:
        return []
    winners: List[str] = []
    draft_id = f"draft_{move.move_id}"
    for section in state.assembled_answer.sections:
        if section.selected_draft_id == draft_id:
            winners.append(section.section_name.value if hasattr(section.section_name, "value") else str(section.section_name))
    return winners


def _failed_sections(state: SessionState, move: Optional[AgentMove]) -> List[str]:
    if move is None or state.assembled_answer is None:
        return []
    draft_id = f"draft_{move.move_id}"
    failed: List[str] = []
    for section in state.assembled_answer.sections:
        if section.unresolved and section.selected_draft_id == draft_id:
            failed.append(section.section_name.value if hasattr(section.section_name, "value") else str(section.section_name))
    return failed


def collect_task_traces(
    state: SessionState,
    *,
    registry: Optional[CouncilProviderRegistry] = None,
    constitution: Optional[SocratesConstitution] = None,
    include_raw_text: bool = False,
) -> List[LearningTrace]:
    """
    Convert CED task_log entries into LearningTrace records. Linked successful
    moves become eligible candidates if the constitution allows them; failed tasks
    remain trace-only.
    """
    policy = constitution or SocratesConstitution.default()
    catalog = provider_catalog(registry)
    moves_by_id = {m.move_id: m for m in state.moves}
    final_payload = _final_answer_payload(state)
    traces: List[LearningTrace] = []

    for entry in state.task_log:
        move = moves_by_id.get(entry.move_id or "") if entry.move_id else None
        task = _task_from_log(state, entry)
        response = _response_from_move(entry, move)
        meta = _meta_for(response.provider_id, catalog)
        trace = LearningTrace.from_provider_response(
            task,
            response,
            provider_family=meta.provider_family,
            model=meta.model,
            include_raw_text=include_raw_text,
            final_answer=final_payload,
            winner_sections=_winner_sections(state, move),
            failed_sections=_failed_sections(state, move),
            metadata={
                "collector": "phase_26d",
                "source": "task_log",
                "provider_name": meta.provider_name,
                "move_id": move.move_id if move else None,
                "context_hash": entry.context_hash,
            },
            constitution=policy,
        )
        traces.append(trace)
    return traces


def _trace_for_verdict(
    state: SessionState,
    verdict: RatificationVerdict,
    *,
    catalog: Dict[str, ProviderMeta],
    constitution: SocratesConstitution,
) -> LearningTrace:
    provider_id = verdict.provider_id or verdict.agent_id
    meta = _meta_for(provider_id, catalog)
    task = AgentTask(
        task_id=verdict.task_id or verdict.ratification_id,
        session_id=state.session_id,
        agent_id=verdict.agent_id,
        role=AgentRole.FINAL_EVALUATOR,
        phase=DialogPhase.RATIFICATION,
        question=state.question,
        task_kind=TaskKind.COUNCIL_RATIFICATION,
    )
    response = ProviderResponse(
        provider_id=provider_id,
        agent_id=verdict.agent_id,
        status=verdict.provider_status,
        parsed_move=AgentMove(
            move_id=verdict.move_id or verdict.ratification_id,
            task_id=task.task_id,
            agent_id=verdict.agent_id,
            role=AgentRole.FINAL_EVALUATOR,
            phase=DialogPhase.RATIFICATION,
            content=sanitize_public_payload(verdict.model_dump(mode="json", exclude_none=True)),
            confidence=verdict.confidence,
        ) if verdict.provider_status == ProviderStatus.OK else None,
    )
    trace = LearningTrace.from_provider_response(
        task,
        response,
        provider_family=meta.provider_family,
        model=meta.model,
        ratification_vote=verdict.model_dump(mode="json", exclude_none=True),
        final_answer=_final_answer_payload(state),
        metadata={"collector": "phase_26d", "source": "council_ratification"},
        constitution=constitution,
    )
    trace.signal_kind = LearningSignalKind.RATIFICATION
    trace.eligibility = assess_training_eligibility(trace, constitution)
    return trace


def collect_ratification_traces(
    state: SessionState,
    *,
    registry: Optional[CouncilProviderRegistry] = None,
    constitution: Optional[SocratesConstitution] = None,
) -> List[LearningTrace]:
    policy = constitution or SocratesConstitution.default()
    catalog = provider_catalog(registry)
    rat: Optional[CouncilRatification] = state.council_ratification
    if rat is None:
        return []
    return [_trace_for_verdict(state, v, catalog=catalog, constitution=policy) for v in rat.verdicts]


def collect_score_traces(
    state: SessionState,
    *,
    registry: Optional[CouncilProviderRegistry] = None,
    constitution: Optional[SocratesConstitution] = None,
) -> List[LearningTrace]:
    """Collect score records as trace-only learning signals for future reward work."""
    policy = constitution or SocratesConstitution.default()
    catalog = provider_catalog(registry)
    traces: List[LearningTrace] = []

    for index, score in enumerate(state.micro_scores):
        provider_id = score.provider_id or score.voter_agent_id
        meta = _meta_for(provider_id, catalog)
        trace = LearningTrace(
            signal_kind=LearningSignalKind.PEER_SCORE,
            session_id=state.session_id,
            task_id=f"score:{score.output_id}:{score.voter_agent_id}:{index}",
            question=state.question,
            provider_id=provider_id,
            provider_family=meta.provider_family,
            model=meta.model,
            agent_id=score.voter_agent_id,
            role=AgentRole.FINAL_EVALUATOR.value,
            phase=score.phase.value,
            task_kind=TaskKind.MOVE_SCORE.value,
            status=score.provider_status.value,
            content=sanitize_public_payload({
                "output_id": score.output_id,
                "author_agent_id": score.author_agent_id,
                "voter_agent_id": score.voter_agent_id,
                "rubric_name": score.rubric_name,
                "score_breakdown": score.score_breakdown.model_dump(mode="json"),
                "overall_score": score.overall_score,
                "justification": score.justification,
                "penalty_flags": [f.value if hasattr(f, "value") else str(f) for f in score.penalty_flags],
            }),
            confidence=score.confidence,
            metadata={"collector": "phase_26d", "source": "micro_score"},
        )
        trace.eligibility = assess_training_eligibility(trace, policy)
        traces.append(trace)

    for card in state.draft_scorecards:
        for index, score in enumerate(card.section_scores):
            provider_id = score.provider_id or card.voter_agent_id
            meta = _meta_for(provider_id, catalog)
            trace = LearningTrace(
                signal_kind=LearningSignalKind.PEER_SCORE,
                session_id=state.session_id,
                task_id=f"section_score:{card.draft_id}:{score.section_name.value}:{card.voter_agent_id}:{index}",
                question=state.question,
                provider_id=provider_id,
                provider_family=meta.provider_family,
                model=meta.model,
                agent_id=card.voter_agent_id,
                role=AgentRole.FINAL_EVALUATOR.value,
                phase=DialogPhase.SYNTHESIS.value,
                task_kind=TaskKind.SECTION_SCORE.value,
                status=score.provider_status.value,
                content=sanitize_public_payload({
                    "draft_id": card.draft_id,
                    "section_name": score.section_name.value,
                    "author_agent_id": score.author_agent_id,
                    "voter_agent_id": score.voter_agent_id,
                    "score_breakdown": score.score_breakdown.model_dump(mode="json"),
                    "overall_score": score.overall_score,
                    "justification": score.justification,
                    "penalty_flags": [f.value if hasattr(f, "value") else str(f) for f in score.penalty_flags],
                }),
                confidence=score.confidence,
                metadata={"collector": "phase_26d", "source": "section_score"},
            )
            trace.eligibility = assess_training_eligibility(trace, policy)
            traces.append(trace)
    return traces


def collect_learning_dataset(
    state: SessionState,
    *,
    registry: Optional[CouncilProviderRegistry] = None,
    constitution: Optional[SocratesConstitution] = None,
    include_scores: bool = True,
    include_ratification: bool = True,
    include_raw_text: bool = False,
) -> LearningDataset:
    """
    Build a LearningDataset from a finished or partial SessionState.

    This is safe to call after successful sessions and fallback/quorum-failed
    sessions. Failed tasks are preserved as trace-only signals; eligible exports
    remain governed by SocratesConstitution.
    """
    policy = constitution or SocratesConstitution.default()
    dataset = LearningDataset(constitution=policy)
    for trace in collect_task_traces(
        state, registry=registry, constitution=policy, include_raw_text=include_raw_text,
    ):
        dataset.add_trace(trace)
    if include_ratification:
        for trace in collect_ratification_traces(state, registry=registry, constitution=policy):
            dataset.add_trace(trace)
    if include_scores:
        for trace in collect_score_traces(state, registry=registry, constitution=policy):
            dataset.add_trace(trace)
    return dataset


def learning_export_summary(dataset: LearningDataset) -> Dict[str, Any]:
    """Small audit summary suitable for FinalResponse.audit_summary later."""
    by_kind: Dict[str, int] = {}
    eligible = 0
    for trace in dataset.traces:
        by_kind[trace.signal_kind.value] = by_kind.get(trace.signal_kind.value, 0) + 1
        if trace.eligibility and trace.eligibility.eligible:
            eligible += 1
    return {
        "trace_count": len(dataset.traces),
        "eligible_trace_count": eligible,
        "preference_count": len(dataset.preferences),
        "eval_count": len(dataset.evals),
        "signals": by_kind,
        "constitution_version": dataset.constitution.version,
    }
