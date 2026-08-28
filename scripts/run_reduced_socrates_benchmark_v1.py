"""Run the explicitly approved reduced Socrates benchmark, once and locally.

Live scope is frozen to three direct GPT-5 Mini baselines (Q1/Q2/Q3) and one
four-seat homogeneous GPT-5 Mini CED session (Q2).  The heterogeneous arms,
other model families, Q1/Q3 councils, retries, and any spend above $8 are not
authorized.  Hidden evaluator keys live in a separate module that is imported
only after collection has closed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    AgentTask,
    DialogPhase,
    SECTION_ORDER,
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    FakeProvider,
    ScriptedMockProvider,
)
from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
    SUPPORTED_CED_TASK_KINDS_V1,
    assert_ced_structured_schema_parity_v1,
    ced_structured_response_format_v1,
    validate_ced_structured_output_v1,
)
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
    build_turn_user_content_v1,
    execute_bounded_text_turn_v1,
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterDynamicTurnRequestV1,
    OpenRouterRenderedTurnV1,
    OpenRouterSessionLedgerV1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    dispatch_openrouter_one_live_inference_v1,
    openrouter_credential_is_present_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1,
    REDUCED_MAX_CALLS_V1,
    REDUCED_MAX_INPUT_TOKENS_V1,
    REDUCED_MODEL_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
    WORKER_ALIASES_V1,
    WORKER_PROVIDER_IDS_V1,
    build_reduced_flex_policy_v1,
    build_reduced_session_authorization_v1,
    fetch_flex_endpoint_listing_once_v1,
    flex_profile_from_evidence_v1,
    make_hidden_evaluator_guard_v1,
    make_worker_payload_projector_v1,
    validate_flex_endpoint_listing_v1,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BRANCH_RUN_DIRECTORY = (
    REPOSITORY_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs"
)
DEFAULT_COLLECTION_PATH = BRANCH_RUN_DIRECTORY / "reduced_benchmark_collection_v1.json"
DEFAULT_EVALUATION_PATH = BRANCH_RUN_DIRECTORY / "reduced_benchmark_evaluation_v1.json"
DEFAULT_REPORT_PATH = BRANCH_RUN_DIRECTORY / "REDUCED_SOCRATES_BENCHMARK_REPORT.md"
CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-reduced-benchmark-claim-store-v1"
)
RUN_ATTEMPT_LATCH_DIRECTORY = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-reduced-benchmark-run-attempt-v1"
)

BENCHMARK_SCHEMA_VERSION_V1 = "reduced-socrates-live-benchmark/v1"
MODEL_V1 = "openai/gpt-5-mini"
PROVIDER_SELECTOR_V1 = "openai/flex"
MAXIMUM_LIVE_CALLS_V1 = 151
MAXIMUM_CED_CALLS_V1 = 148
MAXIMUM_BASELINE_CALLS_V1 = 3
HARD_TOTAL_SPEND_USD_V1 = "8.00"
AUTOMATIC_RETRIES_V1 = 0
OUTPUT_LIMIT_TOKENS_V1 = 1024
EVALUATOR_MODULE_NAME_V1 = (
    "backend.dialogues.socrates_zero.reduced_benchmark_evaluation_v1"
)
PUBLIC_FORBIDDEN_PROVIDER_VALUES_V1: Tuple[str, ...] = (
    "EVALUATOR-ONLY KEY",
    "Correct answer:",
    EVALUATOR_MODULE_NAME_V1,
)
OPERATOR_APPROVAL_STATEMENT_V1 = (
    "Approved reduced benchmark: at most 151 live calls, zero retries, "
    "and at most $8.00 total session spend. Prior $655.40 authorization void."
)
APPROVED_QUESTION_SHA256_V1: Dict[str, str] = {
    "Q1": "07af0cae3894d35d7c5e1e7410624ea9bf4ec397935897260beff0c7d57551fd",
    "Q2": "1726f5eed7d420c512e247b9f984830315c9641c72ef1f9a6d55fe606d782ce4",
    "Q3": "a52d7fca4e2babc9428a413edaa08d4b26cc140c32d83851e43948a584bfd941",
}
APPROVED_CED_SOURCE_SHA256_V1 = (
    "2f0396e6248db54f8985c643a69b0429f354110e6536c1edc699dcf3b9ff4a43"
)

PUBLIC_QUESTIONS_V1: Tuple[Tuple[str, str, str], ...] = (
    (
        "Q1",
        "Formal logic",
        "Every reviewer who signs a report without checking the evidence violates "
        "procedure. No reviewer who violates procedure may chair the final hearing. "
        "Mira chaired the final hearing and signed the report. Every signer either "
        "checked the evidence or signed without checking it.\n\nMust Mira have "
        "checked the evidence? Explain why.",
    ),
    (
        "Q2",
        "Causal reasoning",
        "A company gives a new AI tool to teams whose managers voluntarily apply "
        "for it. Those teams also receive special training. Three months later "
        "they produce 18% more output than teams without the tool.\n\nThe CEO "
        "concludes:\n\"The AI tool caused an 18% productivity increase.\"\n\nIs "
        "that conclusion justified? What evidence or experimental design would "
        "distinguish the main competing explanations?",
    ),
    (
        "Q3",
        "Epistemic restraint",
        "At 18:12 Omar's admin token was used from workstation M to delete a file. "
        "CCTV shows Omar somewhere else from 18:05 to 18:20. Priya was logged into "
        "workstation M around the deletion time. Admin tokens can be copied and used "
        "by another person.\n\nWho deleted the file, and what can actually be "
        "concluded from the available evidence?",
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    return value


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_public_assistant_output_v1(value)
    if isinstance(value, Mapping):
        return {str(key): _sanitize_public_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_public_value(item) for item in value]
    return value


def _write_once(path: Path, value: Any) -> str:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ContractValidationError(f"write-once artifact already exists: {target}")
    if target.suffix.lower() == ".md":
        encoded = str(value).encode("utf-8")
    else:
        encoded = (
            json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            + "\n"
        ).encode("utf-8")
    try:
        with target.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractValidationError(
            f"write-once artifact already exists: {target}"
        ) from exc
    return _sha256_bytes(encoded)


def assert_approved_static_inputs_v1() -> None:
    """Refuse if any question or the frozen CED implementation has drifted."""
    observed_questions = {
        qid: _sha256_text(question)
        for qid, _title, question in PUBLIC_QUESTIONS_V1
    }
    if observed_questions != APPROVED_QUESTION_SHA256_V1:
        raise ContractValidationError(
            "approved reduced-benchmark question bytes have drifted"
        )
    ced_source = REPOSITORY_ROOT / "backend" / "dialogues" / "ced.py"
    observed_ced = _sha256_bytes(ced_source.read_bytes())
    if observed_ced != APPROVED_CED_SOURCE_SHA256_V1:
        raise ContractValidationError(
            "approved frozen CED source bytes have drifted"
        )


def stable_run_attempt_manifest_v1() -> Dict[str, Any]:
    """Endpoint-independent identity for the one operator-approved run attempt."""
    return {
        "schema_version": "reduced-socrates-run-attempt/v1",
        "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION_V1,
        "operator_statement": OPERATOR_APPROVAL_STATEMENT_V1,
        "question_sha256": dict(APPROVED_QUESTION_SHA256_V1),
        "ced_source_sha256": APPROVED_CED_SOURCE_SHA256_V1,
        "conditions": {
            "baselines": ["Q1", "Q2", "Q3"],
            "homogeneous_ced": ["Q2"],
            "seats": 4,
            "model": MODEL_V1,
            "provider_selector": PROVIDER_SELECTOR_V1,
        },
        "maximum_live_calls": MAXIMUM_LIVE_CALLS_V1,
        "hard_total_spend_usd": HARD_TOTAL_SPEND_USD_V1,
        "automatic_retries": AUTOMATIC_RETRIES_V1,
    }


def stable_run_attempt_id_v1() -> str:
    return "szorreducedrunattemptv1_" + _sha256_text(
        canonical_json(stable_run_attempt_manifest_v1())
    )


def consume_stable_run_attempt_latch_v1(
    directory: Path = RUN_ATTEMPT_LATCH_DIRECTORY,
) -> Dict[str, Any]:
    """Atomically burn the only approved run attempt before any network action."""
    attempt_id = stable_run_attempt_id_v1()
    target_directory = Path(directory).resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{attempt_id}.consumed.json"
    value = {
        "run_attempt_id": attempt_id,
        "manifest": stable_run_attempt_manifest_v1(),
        "consumed_utc": _utc_now(),
    }
    encoded = (canonical_json(value) + "\n").encode("utf-8")
    try:
        with target.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractValidationError(
            "approved reduced-benchmark run attempt was already consumed; "
            "a rerun requires new explicit operator authorization"
        ) from exc
    return {
        "run_attempt_id": attempt_id,
        "latch_path": str(target),
        "latch_sha256": _sha256_bytes(encoded),
        "consumed_utc": value["consumed_utc"],
    }


def baseline_response_format_v1() -> Dict[str, Any]:
    """Strict normal-answer schema; deliberately not the CED move contract."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "reduced_benchmark_direct_answer_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["conclusion", "reasoning", "uncertainty", "confidence"],
                "properties": {
                    "conclusion": {"type": "string", "minLength": 1},
                    "reasoning": {"type": "string", "minLength": 1},
                    "uncertainty": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    }


def _sample_schema_tasks_v1() -> Tuple[AgentTask, ...]:
    common = dict(session_id="schema-proof", agent_id="Alpha", question="public q")
    return (
        AgentTask(role=AgentRole.SOCRATES, phase=DialogPhase.OPENING,
                  task_kind=TaskKind.SOCRATIC_QUESTION, **common),
        AgentTask(role=AgentRole.SOCRATES, phase=DialogPhase.ELENCHUS,
                  task_kind=TaskKind.SOCRATIC_QUESTION, **common),
        AgentTask(role=AgentRole.SYNTHESIZER, phase=DialogPhase.INITIAL_RESPONSE,
                  task_kind=TaskKind.INITIAL_RESPONSE, **common),
        AgentTask(role=AgentRole.ELENCHUS_CRITIC,
                  phase=DialogPhase.INITIAL_RESPONSE,
                  task_kind=TaskKind.INITIAL_RESPONSE, **common),
        AgentTask(role=AgentRole.EMPIRICIST,
                  phase=DialogPhase.INITIAL_RESPONSE,
                  task_kind=TaskKind.INITIAL_RESPONSE, **common),
        AgentTask(role=AgentRole.ELENCHUS_CRITIC, phase=DialogPhase.ELENCHUS,
                  task_kind=TaskKind.ELENCHUS_OBJECTION, **common),
        AgentTask(role=AgentRole.EMPIRICIST, phase=DialogPhase.ELENCHUS,
                  task_kind=TaskKind.ELENCHUS_OBJECTION, **common),
        AgentTask(role=AgentRole.REFLECTOR, phase=DialogPhase.REFLECTION,
                  task_kind=TaskKind.REFLECTION_REVISION, **common),
        AgentTask(role=AgentRole.MAIEUTIC_RECONSTRUCTOR,
                  phase=DialogPhase.RECONSTRUCTION,
                  task_kind=TaskKind.RECONSTRUCTION_PROPOSAL, **common),
        AgentTask(role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
                  task_kind=TaskKind.SYNTHESIS_DRAFT, **common),
        AgentTask(role=AgentRole.FINAL_EVALUATOR, phase=DialogPhase.SYNTHESIS,
                  task_kind=TaskKind.MOVE_SCORE, **common),
        AgentTask(role=AgentRole.FINAL_EVALUATOR, phase=DialogPhase.SYNTHESIS,
                  task_kind=TaskKind.SECTION_SCORE, **common),
        AgentTask(role=AgentRole.FINAL_EVALUATOR, phase=DialogPhase.RATIFICATION,
                  task_kind=TaskKind.COUNCIL_RATIFICATION, **common),
        AgentTask(role=AgentRole.FINAL_EVALUATOR, phase=DialogPhase.ELENCHUS,
                  task_kind=TaskKind.OBJECTION_VERIFICATION, **common),
    )


def structured_schema_manifest_v1() -> Dict[str, Any]:
    rows = []
    variants = set()
    for task in _sample_schema_tasks_v1():
        response_format = ced_structured_response_format_v1(task)
        variant = (
            f"{task.task_kind.value}:{task.phase.value}:{task.role.value}"
        )
        variants.add(task.task_kind)
        rows.append(
            {
                "variant": variant,
                "response_format_sha256": _sha256_text(canonical_json(response_format)),
            }
        )
    supported = set(SUPPORTED_CED_TASK_KINDS_V1)
    if variants != supported:
        raise ContractValidationError(
            "structured schema sample coverage differs from supported CED task kinds"
        )
    baseline = baseline_response_format_v1()
    return {
        "ced_variants": sorted(rows, key=lambda row: row["variant"]),
        "baseline_response_format_sha256": _sha256_text(canonical_json(baseline)),
    }


def derive_reduced_call_budget_v1() -> Dict[str, Any]:
    """Derive and lock the exact 4-seat structural maximum from CED primitives."""
    seats = 4
    fake = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(seats):
        registry.register(
            ScriptedMockProvider(
                provider_id=f"seat_{index}", model_id=MODEL_V1
            )
        )
    agents = [SocraticAgent(f"agent_{index}", fake) for index in range(seats)]
    ced = CEDOrchestrator(agents, fake, registry=registry)

    signature = inspect.signature(CEDOrchestrator.__init__)
    expected_defaults = {
        "shadow_scoring_mode": ShadowScoringMode.ALL_PHASES,
        "ratification_repair": "block",
        "phase_retry": False,
        "max_socratic_followups": 2,
        "ai_learning": False,
        "tree_expansions": 0,
    }
    for name, expected in expected_defaults.items():
        if signature.parameters[name].default != expected:
            raise ContractValidationError(f"CED default drifted for {name}")

    state = ced.create_session("offline structural budget proof", "budget-proof-v1")
    initial_specs = ced.canonical_registry_task_specs(
        state, DialogPhase.INITIAL_RESPONSE
    )
    for spec in initial_specs:
        state.moves.append(
            AgentMove(
                task_id=f"budget-{spec.slot_index}",
                agent_id=spec.agent_id,
                role=spec.role,
                phase=DialogPhase.INITIAL_RESPONSE,
                content={"commitments": [f"claim {spec.slot_index}"]},
                task_kind=TaskKind.INITIAL_RESPONSE,
                provider_id=f"seat_{spec.slot_index}",
            )
        )

    opening = len(ced.canonical_registry_task_specs(state, DialogPhase.OPENING))
    initial = len(initial_specs)
    elenchus_per_cycle = ced.canonical_registry_task_specs(
        state, DialogPhase.ELENCHUS
    )
    reflection_per_cycle = len(
        ced.canonical_registry_task_specs(state, DialogPhase.REFLECTION)
    )
    reconstruction = len(
        ced.canonical_registry_task_specs(state, DialogPhase.RECONSTRUCTION)
    )
    synthesis = len(ced.canonical_registry_task_specs(state, DialogPhase.SYNTHESIS))
    followup_cycles = ced.max_socratic_followups
    socratic_questions = opening + followup_cycles * sum(
        spec.task_kind is TaskKind.SOCRATIC_QUESTION for spec in elenchus_per_cycle
    )
    elenchus_objections = followup_cycles * sum(
        spec.task_kind is TaskKind.ELENCHUS_OBJECTION for spec in elenchus_per_cycle
    )
    reflections = followup_cycles * reflection_per_cycle
    deliberation = (
        socratic_questions
        + initial
        + elenchus_objections
        + reflections
        + reconstruction
        + synthesis
    )
    move_scores = deliberation * (seats - 1)
    section_scores = synthesis * len(SECTION_ORDER) * (seats - 1)
    ratification = seats
    # Model-level independence excludes all peer seats when every seat has the
    # exact same authoritative model id, so objection verification schedules 0.
    homogeneous_verification = 0
    ced_total = deliberation + move_scores + section_scores + ratification
    breakdown = {
        "socratic_questions": socratic_questions,
        "initial_responses": initial,
        "elenchus_objections": elenchus_objections,
        "reflections": reflections,
        "reconstruction": reconstruction,
        "synthesis": synthesis,
        "move_scores": move_scores,
        "section_scores": section_scores,
        "ratification": ratification,
        "homogeneous_objection_verification": homogeneous_verification,
        "ced_maximum": ced_total,
        "baselines": MAXIMUM_BASELINE_CALLS_V1,
        "total_maximum": ced_total + MAXIMUM_BASELINE_CALLS_V1,
    }
    expected = {
        "socratic_questions": 3,
        "initial_responses": 3,
        "elenchus_objections": 4,
        "reflections": 6,
        "reconstruction": 1,
        "synthesis": 4,
        "move_scores": 63,
        "section_scores": 60,
        "ratification": 4,
        "homogeneous_objection_verification": 0,
        "ced_maximum": 148,
        "baselines": 3,
        "total_maximum": 151,
    }
    if breakdown != expected:
        raise ContractValidationError(
            f"reduced structural call budget drifted: {breakdown!r}"
        )
    return breakdown


def build_benchmark_authorization_manifest_v1(policy, profile) -> Dict[str, Any]:
    assert_approved_static_inputs_v1()
    budget = derive_reduced_call_budget_v1()
    schemas = structured_schema_manifest_v1()
    payload = {
        "schema_version": BENCHMARK_SCHEMA_VERSION_V1,
        "operator_statement": OPERATOR_APPROVAL_STATEMENT_V1,
        "conditions": {
            "baselines": ["Q1", "Q2", "Q3"],
            "homogeneous_ced": ["Q2"],
            "seats": 4,
            "heterogeneous_ced": [],
        },
        "questions": [
            {"question_id": qid, "question_sha256": _sha256_text(question)}
            for qid, _title, question in PUBLIC_QUESTIONS_V1
        ],
        "model": MODEL_V1,
        "provider_selector": PROVIDER_SELECTOR_V1,
        "policy_id": policy.policy_id,
        "profile_id": profile.profile_id,
        "maximum_live_calls": MAXIMUM_LIVE_CALLS_V1,
        "hard_total_spend_usd": HARD_TOTAL_SPEND_USD_V1,
        "automatic_retries": AUTOMATIC_RETRIES_V1,
        "sampling": {
            "temperature": None,
            "seed": 0,
            "reasoning_settings": "omitted",
        },
        "call_budget": budget,
        "ced_source_sha256": APPROVED_CED_SOURCE_SHA256_V1,
        "structured_schemas": schemas,
    }
    digest = _sha256_text(canonical_json(payload))
    return {**payload, "benchmark_authorization_manifest_sha256": digest}


class _ProviderBodyCaptureV1:
    """Retain exact credential-free canonical bodies and their task identities."""

    def __init__(self) -> None:
        self._ordered: List[Tuple[str, str]] = []
        self._tasks_by_digest: Dict[str, AgentTask] = {}
        self._forbidden_guard = make_hidden_evaluator_guard_v1(
            forbidden_values=PUBLIC_FORBIDDEN_PROVIDER_VALUES_V1
        )

    def __call__(
        self, task: Optional[AgentTask], rendered: OpenRouterRenderedTurnV1
    ) -> None:
        self._forbidden_guard(task, rendered)
        body = rendered.canonical_body_json
        if _sha256_text(body) != rendered.body_sha256:
            raise ContractValidationError("pre-dispatch body capture digest mismatch")
        self._ordered.append((rendered.body_sha256, body))
        if task is not None:
            self._tasks_by_digest[rendered.body_sha256] = task

    def enrich_ced_records(self, records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for raw_record in records:
            record = dict(raw_record)
            task = self._tasks_by_digest.get(str(record.get("body_sha256") or ""))
            if task is None:
                out.append(record)
                continue
            record["task_kind"] = task.task_kind.value if task.task_kind else None
            # Prefer the adapter's validation of the exact raw assistant text.
            # The fallback exists only for early failure records created before
            # the adapter could attach its independent structured-output result.
            if record.get("provider_structured_output_valid") is None:
                assistant = record.get("assistant_output_sanitized")
                if not isinstance(assistant, str):
                    record["provider_structured_output_valid"] = False
                    record["provider_structured_output_error"] = (
                        record.get("failure_class") or "no_assistant_output"
                    )
                else:
                    try:
                        validate_ced_structured_output_v1(task, assistant)
                    except Exception as exc:  # evidence, never CED authority
                        record["provider_structured_output_valid"] = False
                        record["provider_structured_output_error"] = (
                            f"{type(exc).__name__}: {exc}"
                        )[:500]
                    else:
                        record["provider_structured_output_valid"] = True
                        record["provider_structured_output_error"] = None
            record["ced_parser_accepted"] = record.get("ced_move_accepted")
            out.append(record)
        return out

    def evidence_for_records(self, records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        expected = Counter(
            str(record.get("body_sha256"))
            for record in records
            if record.get("body_sha256")
        )
        retained: List[Dict[str, Any]] = []
        bodies: List[str] = []
        for digest, body in self._ordered:
            if expected[digest] <= 0:
                continue
            expected[digest] -= 1
            bodies.append(body)
            retained.append(
                {
                    "body_sha256": digest,
                    "body_length": len(body.encode("utf-8")),
                    "canonical_body": body,
                }
            )
        if any(expected.values()):
            raise ContractValidationError(
                "provider-body capture is incomplete for dispatched turn records"
            )
        exact_manifest = [
            {"body_sha256": row["body_sha256"], "body_length": row["body_length"]}
            for row in retained
        ]
        return {
            "provider_bound_bodies": bodies,
            "body_records": retained,
            "ordered_exact_body_manifest_sha256": _sha256_text(
                canonical_json(exact_manifest)
            ),
        }


class _FatalSessionDispatchV1:
    """Latch identity/retry failures so no later call can reach the socket."""

    def __init__(
        self,
        capture: _ProviderBodyCaptureV1,
        ledger: OpenRouterSessionLedgerV1,
        transport=dispatch_openrouter_one_live_inference_v1,
    ) -> None:
        self.capture = capture
        self.ledger = ledger
        self.transport = transport
        self.fatal_reason: Optional[str] = None

    def guard(self, task: Optional[AgentTask], rendered: OpenRouterRenderedTurnV1) -> None:
        fatal = self.fatal_reason or self.ledger.fatal_failure
        if fatal is not None:
            raise ContractValidationError(
                f"session stopped after fatal provider binding: {fatal}"
            )
        self.capture(task, rendered)

    def __call__(self, **kwargs):
        fatal = self.fatal_reason or self.ledger.fatal_failure
        if fatal is not None:
            raise ContractValidationError(
                f"session stopped after fatal provider binding: {fatal}"
            )
        result = self.transport(**kwargs)
        retry_count = getattr(result.completion, "retry_count", 0)
        if type(retry_count) is not int or retry_count != 0:
            self.fatal_reason = "transport_retry_observed"
            self.ledger.trip_fatal(self.fatal_reason)
            return result
        if result.completion.completed and result.completion.http_status == 200:
            try:
                payload = json.loads(result.raw_response_body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return result
            actual_model = payload.get("model") if isinstance(payload, Mapping) else None
            provider = payload.get("provider") if isinstance(payload, Mapping) else None
            if actual_model != REDUCED_MODEL_V1:
                self.fatal_reason = "returned_model_identity_mismatch"
            elif provider != REDUCED_PROVIDER_DISPLAY_NAME_V1:
                self.fatal_reason = "returned_provider_identity_mismatch"
            if self.fatal_reason is not None:
                self.ledger.trip_fatal(self.fatal_reason)
        return result


def _validate_baseline_output_v1(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not isinstance(text, str):
        return False, "no_assistant_content"
    try:
        value = json.loads(text)
    except ValueError:
        return False, "baseline_output_not_json"
    if not isinstance(value, Mapping):
        return False, "baseline_output_not_object"
    expected = {"conclusion", "reasoning", "uncertainty", "confidence"}
    if set(value) != expected:
        return False, "baseline_output_field_mismatch"
    if not all(isinstance(value[name], str) for name in ("conclusion", "reasoning", "uncertainty")):
        return False, "baseline_output_text_field_invalid"
    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return False, "baseline_confidence_invalid"
    if not 0 <= float(confidence) <= 1:
        return False, "baseline_confidence_out_of_range"
    return True, None


def _selected_flex_endpoint_record_v1(raw: bytes) -> Dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") if isinstance(payload, Mapping) else None
    endpoints = data.get("endpoints") if isinstance(data, Mapping) else None
    matches = [
        dict(item)
        for item in (endpoints or [])
        if isinstance(item, Mapping)
        and item.get("tag") == PROVIDER_SELECTOR_V1
        and item.get("model_id") == MODEL_V1
    ]
    if len(matches) != 1:
        raise ContractValidationError("cannot retain unique selected Flex endpoint")
    return matches[0]


def _run_baselines_v1(
    policy,
    profile,
    ledger,
    guard,
    dispatch,
    *,
    baselines: Optional[Dict[str, Any]] = None,
    records: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    baselines = {} if baselines is None else baselines
    records = [] if records is None else records
    response_format = baseline_response_format_v1()
    for qid, _title, question in PUBLIC_QUESTIONS_V1:
        turn = OpenRouterDynamicTurnRequestV1(
            system_prompt=(
                "Answer the user's problem directly and concisely. State the "
                "conclusion, the reasoning that supports it, and any relevant "
                "uncertainty or limitation. Do not mention a council or evaluator."
            ),
            user_content=question,
            role_seat="direct_baseline",
            dialogue_id=f"reduced-baseline-{qid.lower()}",
            turn_id=f"baseline-{qid.lower()}-1",
            dialogue_phase="baseline",
        )
        outcome = execute_bounded_text_turn_v1(
            policy=policy,
            profile=profile,
            ledger=ledger,
            claim_directory=CLAIM_STORE,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            turn=turn,
            response_format_override=response_format,
            expected_returned_models=(REDUCED_MODEL_V1,),
            expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
            pre_dispatch_guard=guard,
            dispatch=dispatch,
        )
        record = outcome.record.model_dump(mode="json", exclude_none=False)
        records.append(record)
        valid, validation_error = _validate_baseline_output_v1(outcome.assistant_text)
        baselines[qid] = {
            "assistant_output": (
                sanitize_public_assistant_output_v1(outcome.assistant_text)
                if isinstance(outcome.assistant_text, str)
                else None
            ),
            "provider_structured_output_valid": valid,
            "validation_error": validation_error,
            "failure_reason": outcome.failure_reason,
            "transport": record,
            "usage": {
                "prompt_tokens": record.get("prompt_tokens"),
                "completion_tokens": record.get("completion_tokens"),
                "observed_cost_picodollars": record.get("observed_cost_picodollars"),
                "observed_cost_usd_decimal": record.get("observed_cost_usd_decimal"),
            },
        }
        if ledger.fatal_failure is not None:
            raise ContractValidationError(
                "baseline dispatch tripped fatal session latch: "
                f"{ledger.fatal_failure}"
            )
    return baselines, records


def assert_runner_pre_network_gates_v1():
    """Prove frozen approval, call, spend, schema, route, and sampling gates."""
    assert_approved_static_inputs_v1()
    if MAXIMUM_LIVE_CALLS_V1 != REDUCED_MAX_CALLS_V1:
        raise ContractValidationError("runner and safety call ceilings differ")
    approved_spend_picos = int(
        Decimal(HARD_TOTAL_SPEND_USD_V1) * Decimal(10**12)
    )
    if approved_spend_picos != REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1:
        raise ContractValidationError("runner and safety spend ceilings differ")
    derive_reduced_call_budget_v1()
    assert_ced_structured_schema_parity_v1()
    policy = build_reduced_flex_policy_v1()
    if policy.model != MODEL_V1 or tuple(policy.provider_only) != (
        PROVIDER_SELECTOR_V1,
    ):
        raise ContractValidationError("reduced policy route differs from approval")
    if policy.output_limit_tokens != OUTPUT_LIMIT_TOKENS_V1:
        raise ContractValidationError("reduced output limit differs from approval")
    if policy.temperature is not None or policy.seed != 0:
        raise ContractValidationError("reduced sampling contract drifted")
    return policy


def _build_offline_ced_runtime_v1(
    *,
    policy,
    profile,
    ledger: OpenRouterSessionLedgerV1,
    fatal_dispatch: _FatalSessionDispatchV1,
    session_id: str,
    question: str,
) -> Dict[str, Any]:
    """Construct and smoke-test every CED component before any paid POST."""
    provider_aliases = dict(
        zip(WORKER_PROVIDER_IDS_V1, WORKER_ALIASES_V1, strict=True)
    )
    outbound_projector = make_worker_payload_projector_v1(
        provider_aliases=provider_aliases
    )
    adapters = [
        SocratesLiveOpenRouterAdapter(
            provider_id=provider_id,
            policy=policy,
            profile=profile,
            ledger=ledger,
            claim_directory=CLAIM_STORE,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            response_format_factory=ced_structured_response_format_v1,
            structured_output_validator=validate_ced_structured_output_v1,
            outbound_task_state_projector=outbound_projector,
            pre_dispatch_guard=fatal_dispatch.guard,
            worker_alias=alias,
            expose_model_identity_to_worker=False,
            expected_returned_models=(REDUCED_MODEL_V1,),
            expected_provider_display_names=(
                REDUCED_PROVIDER_DISPLAY_NAME_V1,
            ),
            ced_parse_repair_attempts=0,
            dispatch=fatal_dispatch,
        )
        for provider_id, alias in zip(
            WORKER_PROVIDER_IDS_V1, WORKER_ALIASES_V1, strict=True
        )
    ]
    if [adapter.worker_alias for adapter in adapters] != list(WORKER_ALIASES_V1):
        raise ContractValidationError("CED worker alias wiring drifted")
    if any(
        adapter.authoritative_model_id() != REDUCED_MODEL_V1
        for adapter in adapters
    ):
        raise ContractValidationError("CED authoritative model wiring drifted")

    registry = CouncilProviderRegistry(provider_timeout_seconds=125.0)
    for adapter in adapters:
        registry.register(adapter)
    ready, warning = registry.assess_readiness()
    if not ready:
        raise ContractValidationError(
            f"CED registry is not ready during offline wiring preflight: {warning}"
        )

    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{index}", fake) for index in range(4)]
    ced = CEDOrchestrator(agents, fake, registry=registry)
    preflight_state = ced.create_session(question, session_id=session_id)

    # Exercise the exact task/schema/projector seams with CED-owned tasks. This
    # is pure serialization: no claim, credential read, transport, or model call.
    projected_task_count = 0
    for phase in (
        DialogPhase.OPENING,
        DialogPhase.INITIAL_RESPONSE,
        DialogPhase.ELENCHUS,
        DialogPhase.REFLECTION,
        DialogPhase.RECONSTRUCTION,
        DialogPhase.SYNTHESIS,
    ):
        for spec in ced.canonical_registry_task_specs(preflight_state, phase):
            task = ced._build_registry_phase_task(  # exact production task builder
                preflight_state, phase, spec
            )
            ced_structured_response_format_v1(task)
            worker_content = build_turn_user_content_v1(
                task,
                preflight_state.agent_states[spec.agent_id],
                outbound_task_state_projector=outbound_projector,
            )
            if any(
                identity in worker_content
                for identity in (
                    REDUCED_MODEL_V1,
                    PROVIDER_SELECTOR_V1,
                    REDUCED_PROVIDER_DISPLAY_NAME_V1,
                )
            ):
                raise ContractValidationError(
                    "CED worker projection exposed authoritative route identity"
                )
            projected_task_count += 1
    if projected_task_count <= 0:
        raise ContractValidationError("CED wiring preflight produced no tasks")

    return {
        "adapters": adapters,
        "registry": registry,
        "ced": ced,
        "question": question,
        "session_id": session_id,
        "projected_task_count": projected_task_count,
        "registry_ready": ready,
    }


def _prepare_ced_then_consume_run_attempt_v1(
    *,
    policy,
    profile,
    ledger: OpenRouterSessionLedgerV1,
    fatal_dispatch: _FatalSessionDispatchV1,
    session_id: str,
    question: str,
    latch_directory: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Finish all fallible offline CED wiring, then burn the one-run latch."""
    runtime = _build_offline_ced_runtime_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        fatal_dispatch=fatal_dispatch,
        session_id=session_id,
        question=question,
    )
    latch = consume_stable_run_attempt_latch_v1(
        RUN_ATTEMPT_LATCH_DIRECTORY
        if latch_directory is None
        else latch_directory
    )
    return runtime, latch


def _snapshot_runtime_collection_v1(
    collection: Dict[str, Any],
    *,
    ledger: Optional[OpenRouterSessionLedgerV1],
    session: Any,
    capture: Optional[_ProviderBodyCaptureV1],
    fatal_dispatch: Optional[_FatalSessionDispatchV1],
    baseline_records: List[Dict[str, Any]],
    adapters: List[SocratesLiveOpenRouterAdapter],
    final: Any,
    state: Any,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw_turn_records = [
        row for adapter in adapters for row in adapter.observability_rows()
    ]
    turn_records = (
        capture.enrich_ced_records(raw_turn_records)
        if capture is not None
        else [dict(row) for row in raw_turn_records]
    )
    all_records = list(baseline_records) + turn_records
    homogeneous = collection.setdefault("homogeneous_q2", {})
    homogeneous.update(
        {
            "condition": "four homogeneous GPT-5 Mini CED seats on Q2 only",
            "worker_aliases": list(WORKER_ALIASES_V1),
            "provider_models": {
                provider_id: MODEL_V1 for provider_id in WORKER_PROVIDER_IDS_V1
            },
            "turns": _sanitize_public_value(turn_records),
            "calls_consumed": len(turn_records),
        }
    )
    if final is not None:
        homogeneous["final"] = _sanitize_public_value(
            final.model_dump(mode="json")
        )
    if state is not None:
        homogeneous["state"] = _sanitize_public_value(
            state.model_dump(mode="json")
        )
    if ledger is not None:
        collection["actual_live_calls"] = ledger.calls_consumed
        hard_ceiling = (
            session.maximum_total_spend_picodollars
            if session is not None
            else REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
        )
        collection["ledger"] = {
            "calls_consumed": ledger.calls_consumed,
            "settled_picodollars": ledger.settled_picodollars,
            "observed_picodollars": ledger.observed_picodollars,
            "unsettled_reserved_picodollars": ledger.unsettled_reserved_picodollars,
            "committed_picodollars": ledger.committed_picodollars,
            "fatal_failure": ledger.fatal_failure,
            "hard_ceiling_picodollars": hard_ceiling,
        }
    if capture is not None:
        collection["wire_evidence"] = capture.evidence_for_records(all_records)
    collection["fatal_session_stop"] = (
        (fatal_dispatch.fatal_reason if fatal_dispatch is not None else None)
        or (ledger.fatal_failure if ledger is not None else None)
    )
    collection["completed_utc"] = _utc_now()
    collection["evaluator_module_imported_during_collection"] = (
        EVALUATOR_MODULE_NAME_V1 in sys.modules
    )
    collection["collection_dispatch_closed"] = True
    return turn_records, all_records


def collect_reduced_benchmark_v1(
    endpoint_raw: Optional[bytes] = None,
    *,
    record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    collection = {} if record is None else record
    collection.update(
        {
            "schema_version": BENCHMARK_SCHEMA_VERSION_V1,
            "started_utc": _utc_now(),
            "operator_approval": OPERATOR_APPROVAL_STATEMENT_V1,
            "prior_655_40_authorization": "VOID_NOT_EXECUTED",
            "model": MODEL_V1,
            "provider_selector": PROVIDER_SELECTOR_V1,
            "maximum_live_calls": MAXIMUM_LIVE_CALLS_V1,
            "actual_live_calls": 0,
            "hard_total_spend_usd": HARD_TOTAL_SPEND_USD_V1,
            "automatic_retries": AUTOMATIC_RETRIES_V1,
            "sampling": {
                "temperature": None,
                "seed": 0,
                "reasoning_settings": "omitted",
            },
            "baselines": {},
            "homogeneous_q2": {
                "condition": "four homogeneous GPT-5 Mini CED seats on Q2 only",
                "worker_aliases": list(WORKER_ALIASES_V1),
                "provider_models": {
                    provider_id: MODEL_V1
                    for provider_id in WORKER_PROVIDER_IDS_V1
                },
                "turns": [],
                "calls_consumed": 0,
            },
            "collection_dispatch_closed": False,
        }
    )
    if EVALUATOR_MODULE_NAME_V1 in sys.modules:
        raise ContractValidationError(
            "hidden evaluator module was imported before live collection"
        )

    policy = None
    profile = None
    session = None
    ledger: Optional[OpenRouterSessionLedgerV1] = None
    capture: Optional[_ProviderBodyCaptureV1] = None
    fatal_dispatch: Optional[_FatalSessionDispatchV1] = None
    baseline_records: List[Dict[str, Any]] = []
    adapters: List[SocratesLiveOpenRouterAdapter] = []
    final = None
    state = None
    ced = None
    try:
        policy = assert_runner_pre_network_gates_v1()

        if endpoint_raw is None:
            fetched = fetch_flex_endpoint_listing_once_v1()
            endpoint_raw = fetched.raw_response_body
            collection["endpoint_http"] = {
                "http_status": fetched.http_status,
                "latency_ms": fetched.latency_ms,
                "body_sha256": _sha256_bytes(endpoint_raw),
                "body_length": len(endpoint_raw),
            }
        else:
            collection["endpoint_http"] = {
                "injected_offline_endpoint_evidence": True,
                "body_sha256": _sha256_bytes(endpoint_raw),
                "body_length": len(endpoint_raw),
            }
        collection["endpoint_raw_utf8"] = endpoint_raw.decode(
            "utf-8", errors="strict"
        )
        if collection["endpoint_http"].get("http_status", 200) != 200:
            raise ContractValidationError(
                "Flex endpoint capability GET returned HTTP "
                f"{collection['endpoint_http']['http_status']}"
            )
        endpoint_evidence = validate_flex_endpoint_listing_v1(endpoint_raw)
        selected_endpoint = _selected_flex_endpoint_record_v1(endpoint_raw)
        collection["selected_endpoint_record"] = selected_endpoint
        collection["endpoint_evidence"] = _json_value(endpoint_evidence)
        profile = flex_profile_from_evidence_v1(endpoint_evidence)
        collection["profile"] = profile.model_dump(mode="json")
        manifest = build_benchmark_authorization_manifest_v1(policy, profile)
        manifest_digest = manifest["benchmark_authorization_manifest_sha256"]
        session_id = f"reduced-socrates-benchmark-v1-{manifest_digest}"
        session = build_reduced_session_authorization_v1(
            policy, profile, session_id=session_id
        )
        if manifest_digest not in session.session_id:
            raise ContractValidationError(
                "session authorization is not manifest-bound"
            )
        collection["authorization_manifest"] = manifest
        collection["session_authorization"] = session.model_dump(mode="json")
        ledger = OpenRouterSessionLedgerV1(session)
        capture = _ProviderBodyCaptureV1()
        fatal_dispatch = _FatalSessionDispatchV1(capture, ledger)

        if not openrouter_credential_is_present_v1():
            raise ContractValidationError(
                "OpenRouter credential absent; no POST dispatched"
            )
        q2 = next(
            question
            for qid, _title, question in PUBLIC_QUESTIONS_V1
            if qid == "Q2"
        )
        # Construct and exercise every locally fallible CED wiring seam before
        # burning the one-run latch or permitting the first paid baseline POST.
        runtime, run_attempt_latch = _prepare_ced_then_consume_run_attempt_v1(
            policy=policy,
            profile=profile,
            ledger=ledger,
            fatal_dispatch=fatal_dispatch,
            session_id=session_id,
            question=q2,
        )
        adapters = runtime["adapters"]
        ced = runtime["ced"]
        collection["ced_offline_wiring_preflight"] = {
            "registry_ready": runtime["registry_ready"],
            "projected_task_count": runtime["projected_task_count"],
            "adapter_count": len(adapters),
            "completed_before_run_attempt_latch": True,
            "completed_before_first_post": True,
        }
        collection["run_attempt_latch"] = run_attempt_latch

        _run_baselines_v1(
            policy,
            profile,
            ledger,
            fatal_dispatch.guard,
            fatal_dispatch,
            baselines=collection["baselines"],
            records=baseline_records,
        )
        final = asyncio.run(
            ced.run_registry_session(q2, session_id=session_id)
        )
        state = ced.get_session(session_id)
        if ledger.fatal_failure is not None:
            raise ContractValidationError(
                f"CED dispatch tripped fatal session latch: {ledger.fatal_failure}"
            )

        _turn_records, all_records = _snapshot_runtime_collection_v1(
            collection,
            ledger=ledger,
            session=session,
            capture=capture,
            fatal_dispatch=fatal_dispatch,
            baseline_records=baseline_records,
            adapters=adapters,
            final=final,
            state=state,
        )
        if ledger.calls_consumed != len(all_records):
            raise ContractValidationError(
                "ledger call count differs from retained dispatched-turn records"
            )
        if ledger.calls_consumed > MAXIMUM_LIVE_CALLS_V1:
            raise ContractValidationError(
                "approved session call ceiling exceeded"
            )
        if len(collection["wire_evidence"]["provider_bound_bodies"]) != (
            ledger.calls_consumed
        ):
            raise ContractValidationError(
                "provider-bound body evidence count mismatch"
            )
        if collection["evaluator_module_imported_during_collection"]:
            raise ContractValidationError(
                "hidden evaluator imported during collection"
            )
        collection["result"] = "COLLECTION_COMPLETE"
        return collection
    except Exception as exc:
        if state is None and ced is not None and session is not None:
            try:
                state = ced.get_session(session.session_id)
            except Exception:
                state = None
        _snapshot_runtime_collection_v1(
            collection,
            ledger=ledger,
            session=session,
            capture=capture,
            fatal_dispatch=fatal_dispatch,
            baseline_records=baseline_records,
            adapters=adapters,
            final=final,
            state=state,
        )
        collection["result"] = "COLLECTION_FAILED_PARTIAL_OR_PREFLIGHT"
        collection["failure_class"] = type(exc).__name__
        collection["failure_message"] = sanitize_public_assistant_output_v1(
            str(exc)
        )[:1000]
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the approved reduced Socrates benchmark exactly once"
    )
    parser.add_argument(
        "--execute-approved",
        action="store_true",
        help="required acknowledgement of the already-approved 151-call/$8 session",
    )
    parser.add_argument("--collection-out", default=str(DEFAULT_COLLECTION_PATH))
    parser.add_argument("--evaluation-out", default=str(DEFAULT_EVALUATION_PATH))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    if not args.execute_approved:
        raise SystemExit(
            "REFUSING: pass --execute-approved only for the operator-approved "
            "151-call / $8.00 / zero-retry reduced session"
        )
    output_paths = [Path(args.collection_out), Path(args.evaluation_out), Path(args.report_out)]
    existing = [str(path.resolve()) for path in output_paths if path.exists()]
    if existing:
        raise SystemExit(f"REFUSING: write-once output exists: {existing}")

    collection: Dict[str, Any] = {}
    try:
        collect_reduced_benchmark_v1(record=collection)
    except Exception as exc:
        collection.setdefault("schema_version", BENCHMARK_SCHEMA_VERSION_V1)
        collection.setdefault("completed_utc", _utc_now())
        collection["result"] = "REDUCED_SOCRATES_BENCHMARK_FAILED"
        collection["failure_class"] = type(exc).__name__
        collection["failure_message"] = sanitize_public_assistant_output_v1(
            str(exc)
        )[:1000]
        collection["collection_dispatch_closed"] = True
        collection_sha = _write_once(Path(args.collection_out), collection)
        print(
            json.dumps(
                {
                    "result": collection["result"],
                    "actual_live_calls": collection.get("actual_live_calls", 0),
                    "fatal_session_stop": collection.get("fatal_session_stop"),
                    "failure_class": collection["failure_class"],
                    "failure_message": collection["failure_message"],
                    "collection_path": str(
                        Path(args.collection_out).resolve()
                    ),
                    "collection_sha256": collection_sha,
                    "evaluation_written": False,
                    "report_written": False,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    collection_sha = _write_once(Path(args.collection_out), collection)

    # No live function is reachable below this boundary. Hidden evaluator keys
    # are loaded only now, after collection and exact-body retention completed.
    from backend.dialogues.socrates_zero.reduced_benchmark_evaluation_v1 import (
        build_reduced_benchmark_evaluation_v1,
        render_reduced_benchmark_markdown_v1,
    )

    evaluation = build_reduced_benchmark_evaluation_v1(collection)
    evaluation["collection_artifact_sha256"] = collection_sha
    evaluation_sha = _write_once(Path(args.evaluation_out), evaluation)
    report = render_reduced_benchmark_markdown_v1(collection, evaluation)
    report_sha = _write_once(Path(args.report_out), report)
    print(
        json.dumps(
            {
                "result": "REDUCED_SOCRATES_BENCHMARK_COMPLETE",
                "actual_live_calls": collection["actual_live_calls"],
                "observed_cost_picodollars": collection["ledger"]["observed_picodollars"],
                "hard_total_spend_usd": HARD_TOTAL_SPEND_USD_V1,
                "collection_path": str(Path(args.collection_out).resolve()),
                "collection_sha256": collection_sha,
                "evaluation_path": str(Path(args.evaluation_out).resolve()),
                "evaluation_sha256": evaluation_sha,
                "report_path": str(Path(args.report_out).resolve()),
                "report_sha256": report_sha,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
