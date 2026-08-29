"""Run one normal repository-native Socrates dialogue on OpenRouter Flex.

This is the ordinary CED lifecycle, not a benchmark or diagnostic. It uses the
GPT-5 Mini / OpenAI Flex route proven by the retained 4,096-token opening, the
exact task-derived CED structured-output schemas, and a phase-aware output
budget. Importing this module performs no network or credential access.

Example (PowerShell, from the repository root):

    py -3.12 scripts/run_socrates_live_v1.py "your question"

Invoking the command is the live action. It performs one fresh public endpoint
capability read and then the bounded CED calls; there is no baseline, retry,
fallback, second diagnostic, or approval stop inside the run.
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
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentMove,
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
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    PICODOLLARS_PER_USD,
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterRenderedTurnV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    dispatch_openrouter_one_live_inference_v1,
    openrouter_credential_is_present_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_COMPLETION_CEILING_USD_PER_MILLION_V1,
    REDUCED_MAX_INPUT_TOKENS_V1,
    REDUCED_MODEL_V1,
    REDUCED_PROMPT_CEILING_USD_PER_MILLION_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
    REDUCED_PROVIDER_SELECTOR_V1,
    REDUCED_REQUEST_CEILING_USD_V1,
    REDUCED_SEED_V1,
    WORKER_ALIASES_V1,
    WORKER_PROVIDER_IDS_V1,
    assert_reduced_flex_rendered_turn_v1,
    fetch_flex_endpoint_listing_once_v1,
    flex_profile_from_evidence_v1,
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
CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-normal-socrates-claim-store-v1"
)
RUN_ATTEMPT_LATCH_DIRECTORY = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-normal-socrates-run-attempt-v1"
)

NORMAL_RUN_SCHEMA_VERSION_V1 = "normal-socrates-openrouter-live-run/v1"
NORMAL_MODEL_V1 = REDUCED_MODEL_V1
NORMAL_PROVIDER_SELECTOR_V1 = REDUCED_PROVIDER_SELECTOR_V1
NORMAL_PROVIDER_DISPLAY_NAME_V1 = REDUCED_PROVIDER_DISPLAY_NAME_V1
NORMAL_LIVE_WORKERS_V1 = 2
NORMAL_LOGICAL_AGENTS_V1 = 4
NORMAL_MAXIMUM_CED_CALLS_V1 = 64
NORMAL_AUTOMATIC_RETRIES_V1 = 0

# The previous reduced run and its one diagnostic spent $0.00608825. A fresh
# ledger cannot know that history, so the normal run receives only the exact
# remainder of the unchanged cumulative $8 operator ceiling.
HARD_CUMULATIVE_SPEND_PICODOLLARS_V1 = 8 * PICODOLLARS_PER_USD
PRIOR_OBSERVED_SPEND_PICODOLLARS_V1 = 6_088_250_000
NORMAL_REMAINING_SPEND_PICODOLLARS_V1 = (
    HARD_CUMULATIVE_SPEND_PICODOLLARS_V1
    - PRIOR_OBSERVED_SPEND_PICODOLLARS_V1
)

# NOT YET RAISED, and the reason is worth recording where the numbers are.
#
# The Q5 council truncated six of its 97 calls, all GPT-5 Mini, which writes the
# most: five at 4_096 on evaluator turns and one at 8_192 on an initial response.
# Raising either figure breaks about twenty-six tests, because these envelopes
# are not free parameters - they feed endpoint validation
# (rejects_endpoint_below_synthesis_envelope), the phase-aware spend arithmetic,
# and profiles certified at exactly these sizes. Reverting the synthesis figure
# alone changed 43 failures to 44, so the coupling is in the two smaller
# envelopes, not the largest.
#
# So this is its own piece of work: re-certify the endpoints at the larger
# envelope, recompute the spend bounds, then move the numbers. Raising them
# without that leaves the economics asserting figures nobody has checked, which
# is worse than a 6% truncation rate that is at least visible in the evidence.
#
# Raised after the Q5 council truncated six of its 97 calls, all of them GPT-5
# Mini, which writes the most. A truncated completion is not a model failing to
# answer - it is us cutting the answer off mid-sentence and then recording a
# rejected move, so it is a harness artifact and must not be scored as data. The
# Q5 baselines had already shown the size: one answer ran to 12_676 tokens where
# a Q4 answer took about 4_000.
#
# The ceiling is not free. Every seat has its own max_completion_tokens, and a
# request equal to that ceiling leaves the model no room at all - which is
# exactly how a Qwen3 32B baseline was lost earlier, asked for 16_384 when 16_384
# was all it had. The synthesis budget therefore stays well under the smallest
# seat ceiling rather than reaching for it; see assert_output_budgets_fit_v1.
SHORT_OUTPUT_TOKENS_V1 = 4_096
REVISION_OUTPUT_TOKENS_V1 = 8_192
SYNTHESIS_OUTPUT_TOKENS_V1 = 16_384
NORMAL_MAXIMUM_OUTPUT_TOKENS_V1 = SYNTHESIS_OUTPUT_TOKENS_V1

NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1: Mapping[TaskKind, int] = {
    TaskKind.SOCRATIC_QUESTION: SHORT_OUTPUT_TOKENS_V1,
    TaskKind.INITIAL_RESPONSE: REVISION_OUTPUT_TOKENS_V1,
    TaskKind.ELENCHUS_OBJECTION: SHORT_OUTPUT_TOKENS_V1,
    TaskKind.REFLECTION_REVISION: REVISION_OUTPUT_TOKENS_V1,
    TaskKind.RECONSTRUCTION_PROPOSAL: REVISION_OUTPUT_TOKENS_V1,
    TaskKind.SYNTHESIS_DRAFT: SYNTHESIS_OUTPUT_TOKENS_V1,
    TaskKind.MOVE_SCORE: SHORT_OUTPUT_TOKENS_V1,
    TaskKind.SECTION_SCORE: SHORT_OUTPUT_TOKENS_V1,
    TaskKind.COUNCIL_RATIFICATION: SHORT_OUTPUT_TOKENS_V1,
    TaskKind.OBJECTION_VERIFICATION: SHORT_OUTPUT_TOKENS_V1,
}

DEFAULT_QUESTION_V1 = (
    "A company gives a new AI tool to teams whose managers voluntarily apply "
    "for it. Those teams also receive special training. Three months later "
    "they produce 18% more output than teams without the tool.\n\nThe CEO "
    "concludes:\n\"The AI tool caused an 18% productivity increase.\"\n\nIs "
    "that conclusion justified? What evidence or experimental design would "
    "distinguish the main competing explanations?"
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _usd_text(picodollars: int) -> str:
    value = Decimal(picodollars) / Decimal(PICODOLLARS_PER_USD)
    return format(value, "f")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_public_assistant_output_v1(value)
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_public_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_public_value(item) for item in value]
    return value


def _public_scalar(value: Any) -> Any:
    return getattr(value, "value", value)


def _ced_outcome_summary_v1(final: Any) -> Dict[str, Any]:
    """Separate orchestration return from CED ratification/release outcome."""

    return {
        "final_returned": final is not None,
        "synthesis_present": bool(getattr(final, "synthesis", None)),
        "ratified": getattr(final, "ratified", None),
        "ratification_status": _public_scalar(
            getattr(final, "ratification_status", None)
        ),
        "release_decision": _public_scalar(
            getattr(final, "release_decision", None)
        ),
        "governing_epistemic_status": _public_scalar(
            getattr(final, "governing_epistemic_status", None)
        ),
    }


def output_limit_for_task_v1(task: AgentTask) -> int:
    """Return the declared budget for one CED-owned task."""

    if type(task) is not AgentTask or task.task_kind is None:
        raise ContractValidationError("a CED task kind is required for output routing")
    try:
        return NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1[task.task_kind]
    except KeyError as exc:
        raise ContractValidationError(
            f"no normal-run output budget for {task.task_kind.value}"
        ) from exc


def build_normal_execution_policy_v1(
    output_limit_tokens: int,
) -> OpenRouterFrozenExecutionPolicyV1:
    """Build one member of the fixed phase-aware Flex policy family."""

    if output_limit_tokens not in {
        SHORT_OUTPUT_TOKENS_V1,
        REVISION_OUTPUT_TOKENS_V1,
        SYNTHESIS_OUTPUT_TOKENS_V1,
    }:
        raise ContractValidationError("normal-run output limit is not declared")
    return OpenRouterFrozenExecutionPolicyV1(
        model=NORMAL_MODEL_V1,
        provider_only=(NORMAL_PROVIDER_SELECTOR_V1,),
        provider_order=(NORMAL_PROVIDER_SELECTOR_V1,),
        output_limit_tokens=output_limit_tokens,
        temperature=None,
        seed=REDUCED_SEED_V1,
        max_price_prompt_usd_per_million=(
            REDUCED_PROMPT_CEILING_USD_PER_MILLION_V1
        ),
        max_price_completion_usd_per_million=(
            REDUCED_COMPLETION_CEILING_USD_PER_MILLION_V1
        ),
        max_price_request_usd=REDUCED_REQUEST_CEILING_USD_V1,
        bounded_timeout_seconds=120,
    )


def build_normal_policy_family_v1() -> Dict[int, OpenRouterFrozenExecutionPolicyV1]:
    return {
        limit: build_normal_execution_policy_v1(limit)
        for limit in (
            SHORT_OUTPUT_TOKENS_V1,
            REVISION_OUTPUT_TOKENS_V1,
            SYNTHESIS_OUTPUT_TOKENS_V1,
        )
    }


def derive_normal_call_budget_v1() -> Dict[str, int]:
    """Derive the exact two-worker maximum from current CED primitives."""

    fake = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(NORMAL_LIVE_WORKERS_V1):
        registry.register(
            ScriptedMockProvider(
                provider_id=f"normal_budget_worker_{index}",
                model_id=NORMAL_MODEL_V1,
            )
        )
    agents = [
        SocraticAgent(f"agent_{index}", fake)
        for index in range(NORMAL_LOGICAL_AGENTS_V1)
    ]
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

    state = ced.create_session("normal call-budget proof", "normal-budget-proof-v1")
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
                provider_id=(
                    f"normal_budget_worker_"
                    f"{spec.slot_index % NORMAL_LIVE_WORKERS_V1}"
                ),
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
    synthesis = len(
        ced.canonical_registry_task_specs(state, DialogPhase.SYNTHESIS)
    )
    cycles = ced.max_socratic_followups
    socratic_questions = opening + cycles * sum(
        spec.task_kind is TaskKind.SOCRATIC_QUESTION
        for spec in elenchus_per_cycle
    )
    objections = cycles * sum(
        spec.task_kind is TaskKind.ELENCHUS_OBJECTION
        for spec in elenchus_per_cycle
    )
    reflections = cycles * reflection_per_cycle
    deliberation = (
        socratic_questions
        + initial
        + objections
        + reflections
        + reconstruction
        + synthesis
    )
    move_scores = deliberation * (NORMAL_LIVE_WORKERS_V1 - 1)
    section_scores = (
        synthesis
        * len(SECTION_ORDER)
        * (NORMAL_LIVE_WORKERS_V1 - 1)
    )
    ratification = NORMAL_LIVE_WORKERS_V1
    total = deliberation + move_scores + section_scores + ratification
    breakdown = {
        "socratic_questions": socratic_questions,
        "initial_responses": initial,
        "elenchus_objections": objections,
        "reflections": reflections,
        "reconstruction": reconstruction,
        "synthesis": synthesis,
        "move_scores": move_scores,
        "section_scores": section_scores,
        "ratification": ratification,
        "homogeneous_objection_verification": 0,
        "ced_maximum": total,
    }
    expected = {
        "socratic_questions": 3,
        "initial_responses": 3,
        "elenchus_objections": 4,
        "reflections": 6,
        "reconstruction": 1,
        "synthesis": 4,
        "move_scores": 21,
        "section_scores": 20,
        "ratification": 2,
        "homogeneous_objection_verification": 0,
        "ced_maximum": 64,
    }
    if breakdown != expected:
        raise ContractValidationError(
            f"normal structural call budget drifted: {breakdown!r}"
        )
    return breakdown


def conservative_phase_aware_session_bound_v1() -> Dict[str, Any]:
    """Conservatively price every structurally reachable call at 400k input."""

    calls = derive_normal_call_budget_v1()
    counts_by_limit = {
        SHORT_OUTPUT_TOKENS_V1: (
            calls["socratic_questions"]
            + calls["elenchus_objections"]
            + calls["move_scores"]
            + calls["section_scores"]
            + calls["ratification"]
            + calls["homogeneous_objection_verification"]
        ),
        REVISION_OUTPUT_TOKENS_V1: (
            calls["initial_responses"]
            + calls["reflections"]
            + calls["reconstruction"]
        ),
        SYNTHESIS_OUTPUT_TOKENS_V1: calls["synthesis"],
    }
    policies = build_normal_policy_family_v1()
    per_call = {
        limit: conservative_turn_cost_bound_v1(
            policies[limit], REDUCED_MAX_INPUT_TOKENS_V1
        )
        for limit in counts_by_limit
    }
    total = sum(
        counts_by_limit[limit] * per_call[limit]
        for limit in counts_by_limit
    )
    return {
        "calls_by_output_limit": counts_by_limit,
        "per_call_bound_picodollars": per_call,
        "maximum_per_call_picodollars": max(per_call.values()),
        "structural_session_bound_picodollars": total,
    }


def assert_normal_static_contract_v1() -> Dict[str, Any]:
    """Prove schemas, task coverage, policy parity, calls, and spend offline."""

    assert_ced_structured_schema_parity_v1()
    if set(NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1) != set(
        SUPPORTED_CED_TASK_KINDS_V1
    ):
        raise ContractValidationError(
            "normal output policy differs from exact CED schema task coverage"
        )
    if NORMAL_AUTOMATIC_RETRIES_V1 != 0:
        raise ContractValidationError("normal run must retain zero retries")
    calls = derive_normal_call_budget_v1()
    if calls["ced_maximum"] != NORMAL_MAXIMUM_CED_CALLS_V1:
        raise ContractValidationError("normal call ceiling drifted")

    policies = build_normal_policy_family_v1()
    envelope = policies[NORMAL_MAXIMUM_OUTPUT_TOKENS_V1]
    fixed = envelope.model_dump(
        mode="json", exclude={"output_limit_tokens", "policy_id"}
    )
    for policy in policies.values():
        if policy.model_dump(
            mode="json", exclude={"output_limit_tokens", "policy_id"}
        ) != fixed:
            raise ContractValidationError(
                "phase-aware policies differ beyond output_limit_tokens"
            )
        if policy.automatic_retries != 0:
            raise ContractValidationError("phase-aware policy enabled retries")

    spend = conservative_phase_aware_session_bound_v1()
    if spend["structural_session_bound_picodollars"] != 3_552_256_000_000:
        raise ContractValidationError("normal phase-aware P19 arithmetic drifted")
    if spend["maximum_per_call_picodollars"] != 66_384_000_000:
        raise ContractValidationError("normal maximum per-call bound drifted")
    if (
        spend["structural_session_bound_picodollars"]
        > NORMAL_REMAINING_SPEND_PICODOLLARS_V1
    ):
        raise ContractValidationError(
            "normal structural bound exceeds remaining operator ceiling"
        )
    return {"calls": calls, "spend": spend, "policies": policies}


def normal_run_attempt_manifest_v1() -> Dict[str, Any]:
    """Endpoint/question-independent identity for one bounded invocation."""

    policies = build_normal_policy_family_v1()
    return {
        "schema_version": "normal-socrates-live-run-attempt/v1",
        "run_schema_version": NORMAL_RUN_SCHEMA_VERSION_V1,
        "scope": "one caller-supplied normal Socrates question",
        "model": NORMAL_MODEL_V1,
        "provider_selector": NORMAL_PROVIDER_SELECTOR_V1,
        "live_workers": NORMAL_LIVE_WORKERS_V1,
        "logical_agents": NORMAL_LOGICAL_AGENTS_V1,
        "policy_ids_by_output_limit": {
            str(limit): policy.policy_id
            for limit, policy in sorted(policies.items())
        },
        "output_limit_by_task_kind": {
            kind.value: limit
            for kind, limit in sorted(
                NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1.items(),
                key=lambda item: item[0].value,
            )
        },
        "maximum_live_calls": NORMAL_MAXIMUM_CED_CALLS_V1,
        "automatic_retries": NORMAL_AUTOMATIC_RETRIES_V1,
        "hard_cumulative_spend_picodollars": (
            HARD_CUMULATIVE_SPEND_PICODOLLARS_V1
        ),
        "prior_observed_spend_picodollars": (
            PRIOR_OBSERVED_SPEND_PICODOLLARS_V1
        ),
        "remaining_spend_picodollars": NORMAL_REMAINING_SPEND_PICODOLLARS_V1,
    }


def normal_run_attempt_id_v1() -> str:
    return "szornormalrunattemptv1_" + _sha256_text(
        canonical_json(normal_run_attempt_manifest_v1())
    )


def consume_normal_run_attempt_v1(
    directory: Path = RUN_ATTEMPT_LATCH_DIRECTORY,
) -> Dict[str, Any]:
    """Atomically consume the one normal invocation under the $8 envelope."""

    attempt_id = normal_run_attempt_id_v1()
    target_directory = Path(directory).resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{attempt_id}.consumed.json"
    value = {
        "run_attempt_id": attempt_id,
        "manifest": normal_run_attempt_manifest_v1(),
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
            "normal Socrates live invocation already consumed the remaining "
            "session authorization"
        ) from exc
    return {
        "run_attempt_id": attempt_id,
        "manifest": value["manifest"],
        "consumed_utc": value["consumed_utc"],
        "latch_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _policy_for_task_factory_v1(
    policies: Mapping[int, OpenRouterFrozenExecutionPolicyV1],
) -> Callable[[AgentTask], OpenRouterFrozenExecutionPolicyV1]:
    def select(task: AgentTask) -> OpenRouterFrozenExecutionPolicyV1:
        return policies[output_limit_for_task_v1(task)]

    return select


def _normal_predispatch_guard_v1(
    task: Optional[AgentTask], rendered: OpenRouterRenderedTurnV1
) -> None:
    if type(task) is not AgentTask:
        raise ContractValidationError("normal CED pre-dispatch task is required")
    expected_limit = output_limit_for_task_v1(task)
    assert_reduced_flex_rendered_turn_v1(
        rendered,
        expected_output_limit_tokens=expected_limit,
    )
    body = json.loads(rendered.canonical_body_json)
    if body.get("response_format") != ced_structured_response_format_v1(task):
        raise ContractValidationError(
            "provider response schema differs from the exact CED task schema"
        )


def build_normal_manifest_v1(
    *,
    question: str,
    profile: OpenRouterEndpointCapabilityProfileV1,
    policies: Mapping[int, OpenRouterFrozenExecutionPolicyV1],
    static_contract: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": NORMAL_RUN_SCHEMA_VERSION_V1,
        "question_sha256": _sha256_text(question),
        "model": NORMAL_MODEL_V1,
        "provider_selector": NORMAL_PROVIDER_SELECTOR_V1,
        "profile_id": profile.profile_id,
        "policy_ids_by_output_limit": {
            str(limit): policy.policy_id
            for limit, policy in sorted(policies.items())
        },
        "output_limit_by_task_kind": {
            kind.value: limit
            for kind, limit in sorted(
                NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1.items(),
                key=lambda item: item[0].value,
            )
        },
        "live_workers": NORMAL_LIVE_WORKERS_V1,
        "logical_agents": NORMAL_LOGICAL_AGENTS_V1,
        "ced_configuration": {
            "shadow_scoring_mode": ShadowScoringMode.ALL_PHASES.value,
            "phase_retry": False,
            "max_socratic_followups": 2,
            "ratification_repair": "block",
            "tree_expansions": 0,
            "ai_learning": False,
        },
        "baseline_calls": 0,
        "maximum_live_calls": NORMAL_MAXIMUM_CED_CALLS_V1,
        "automatic_retries": NORMAL_AUTOMATIC_RETRIES_V1,
        "prior_observed_spend_picodollars": (
            PRIOR_OBSERVED_SPEND_PICODOLLARS_V1
        ),
        "hard_cumulative_spend_picodollars": (
            HARD_CUMULATIVE_SPEND_PICODOLLARS_V1
        ),
        "remaining_spend_picodollars": NORMAL_REMAINING_SPEND_PICODOLLARS_V1,
        "structural_call_budget": dict(static_contract["calls"]),
        "phase_aware_spend_bound": dict(static_contract["spend"]),
    }


@dataclass
class PreparedNormalLiveRunV1:
    question: str
    session_id: str
    endpoint_evidence: Any
    profile: OpenRouterEndpointCapabilityProfileV1
    policies: Dict[int, OpenRouterFrozenExecutionPolicyV1]
    manifest: Dict[str, Any]
    authorization: OpenRouterLiveTestSessionAuthorizationV1
    ledger: OpenRouterSessionLedgerV1
    adapters: Tuple[SocratesLiveOpenRouterAdapter, ...]
    ced: CEDOrchestrator


def prepare_normal_live_run_v1(
    question: str,
    endpoint_listing_bytes: bytes,
    *,
    claim_directory: Path = CLAIM_STORE,
    dispatch: Optional[Callable[..., Any]] = None,
) -> PreparedNormalLiveRunV1:
    """Build the exact live runtime from fresh endpoint bytes, without a POST."""

    if not isinstance(question, str) or not question.strip():
        raise ContractValidationError("normal Socrates question must be nonblank")
    static_contract = assert_normal_static_contract_v1()
    evidence = validate_flex_endpoint_listing_v1(endpoint_listing_bytes)
    if evidence.context_length != REDUCED_MAX_INPUT_TOKENS_V1:
        raise ContractValidationError(
            "exact Flex endpoint context differs from the 400,000-token P19 bound"
        )
    if (
        evidence.max_prompt_tokens_observed is not None
        and evidence.max_prompt_tokens_observed > REDUCED_MAX_INPUT_TOKENS_V1
    ):
        raise ContractValidationError(
            "exact Flex endpoint prompt maximum exceeds the P19 input bound"
        )
    if evidence.maximum_output_tokens < NORMAL_MAXIMUM_OUTPUT_TOKENS_V1:
        raise ContractValidationError(
            "exact Flex endpoint cannot admit the 16,384-token synthesis envelope"
        )
    profile = flex_profile_from_evidence_v1(evidence)
    policies = dict(static_contract["policies"])
    manifest = build_normal_manifest_v1(
        question=question,
        profile=profile,
        policies=policies,
        static_contract=static_contract,
    )
    manifest_digest = _sha256_text(canonical_json(manifest))
    session_id = f"normal-socrates-live-v1-{manifest_digest[:32]}"
    envelope = policies[NORMAL_MAXIMUM_OUTPUT_TOKENS_V1]
    spend = static_contract["spend"]
    authorization = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Normal Socrates live invocation under the retained cumulative "
            "$8.00 ceiling; CED only, no baseline, no retry, no fallback. "
            "The bound policy is the 16,384-token envelope and task policies "
            "may only reduce output_limit_tokens."
        ),
        policy_id=envelope.policy_id or "",
        profile_id=profile.profile_id or "",
        model=NORMAL_MODEL_V1,
        provider_selector=NORMAL_PROVIDER_SELECTOR_V1,
        maximum_calls=NORMAL_MAXIMUM_CED_CALLS_V1,
        maximum_total_spend_picodollars=(
            NORMAL_REMAINING_SPEND_PICODOLLARS_V1
        ),
        maximum_per_call_spend_picodollars=(
            spend["maximum_per_call_picodollars"]
        ),
        session_id=session_id,
    )
    ledger = OpenRouterSessionLedgerV1(authorization)
    policy_factory = _policy_for_task_factory_v1(policies)
    projector = make_worker_payload_projector_v1()
    adapters = tuple(
        SocratesLiveOpenRouterAdapter(
            provider_id=provider_id,
            policy=envelope,
            profile=profile,
            ledger=ledger,
            claim_directory=claim_directory,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            dispatch=dispatch,
            response_format_factory=ced_structured_response_format_v1,
            structured_output_validator=validate_ced_structured_output_v1,
            task_execution_policy_factory=policy_factory,
            outbound_task_state_projector=projector,
            pre_dispatch_guard=_normal_predispatch_guard_v1,
            worker_alias=alias,
            expose_model_identity_to_worker=False,
            expected_returned_models=(NORMAL_MODEL_V1,),
            expected_provider_display_names=(NORMAL_PROVIDER_DISPLAY_NAME_V1,),
            ced_parse_repair_attempts=0,
        )
        for provider_id, alias in zip(
            WORKER_PROVIDER_IDS_V1[:NORMAL_LIVE_WORKERS_V1],
            WORKER_ALIASES_V1[:NORMAL_LIVE_WORKERS_V1],
            strict=True,
        )
    )
    registry = CouncilProviderRegistry(provider_timeout_seconds=125.0)
    for adapter in adapters:
        registry.register(adapter)
    fake = FakeProvider()
    agents = [
        SocraticAgent(f"agent_{index}", fake)
        for index in range(NORMAL_LOGICAL_AGENTS_V1)
    ]
    ced = CEDOrchestrator(
        agents,
        fake,
        registry=registry,
        shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
        phase_retry=False,
        max_socratic_followups=2,
        ratification_repair="block",
        tree_expansions=0,
        ai_learning=False,
    )
    return PreparedNormalLiveRunV1(
        question=question,
        session_id=session_id,
        endpoint_evidence=evidence,
        profile=profile,
        policies=policies,
        manifest=manifest,
        authorization=authorization,
        ledger=ledger,
        adapters=adapters,
        ced=ced,
    )


def _write_once_json_v1(path: Path, value: Mapping[str, Any]) -> str:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
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
            f"write-once normal-run artifact already exists: {target}"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def run_socrates(
    question: str = DEFAULT_QUESTION_V1,
    *,
    output_path: Optional[Path] = None,
    endpoint_fetch: Callable[..., Any] = fetch_flex_endpoint_listing_once_v1,
    dispatch: Optional[Callable[..., Any]] = None,
    claim_directory: Path = CLAIM_STORE,
    attempt_directory: Path = RUN_ATTEMPT_LATCH_DIRECTORY,
) -> Dict[str, Any]:
    """Execute one bounded normal live dialogue and persist its public record."""

    assert_normal_static_contract_v1()
    requested_target = (
        Path(output_path).resolve() if output_path is not None else None
    )
    if requested_target is not None and requested_target.exists():
        raise ContractValidationError(
            f"write-once normal-run artifact already exists: {requested_target}"
        )
    if dispatch is None and not openrouter_credential_is_present_v1():
        raise ContractValidationError("OPENROUTER_API_KEY is absent or placeholder")

    run_attempt = consume_normal_run_attempt_v1(attempt_directory)
    fetched = endpoint_fetch(bounded_timeout_seconds=30)
    if fetched.http_status != 200:
        raise ContractValidationError(
            f"fresh exact-endpoint GET failed with HTTP {fetched.http_status}"
        )
    prepared = prepare_normal_live_run_v1(
        question,
        fetched.raw_response_body,
        claim_directory=claim_directory,
        dispatch=dispatch or dispatch_openrouter_one_live_inference_v1,
    )
    target = requested_target or (
        BRANCH_RUN_DIRECTORY
        / f"normal_socrates_live_run_{prepared.session_id[-32:]}.json"
    ).resolve()
    if target.exists():
        raise ContractValidationError(
            f"write-once normal-run artifact already exists: {target}"
        )
    ready, warning = prepared.ced.registry.assess_readiness()
    if not ready:
        raise ContractValidationError(
            f"normal CED registry is not ready: {warning}"
        )

    started = time.perf_counter()
    error: Optional[str] = None
    final: Any = None
    try:
        final = asyncio.run(
            prepared.ced.run_registry_session(
                question, session_id=prepared.session_id
            )
        )
    except Exception as exc:  # retain one bounded run failure; never retry
        error = f"{type(exc).__name__}: {exc}"[:1000]
    latency_ms = round((time.perf_counter() - started) * 1000, 3)

    try:
        state: Any = prepared.ced.get_session(prepared.session_id)
    except KeyError:
        state = None
    turns = [
        row
        for adapter in prepared.adapters
        for row in adapter.observability_rows()
    ]
    if error is not None:
        run_status = "STOPPED_WITH_ERROR"
    elif prepared.ledger.fatal_failure is not None:
        run_status = "STOPPED_FATAL"
    else:
        run_status = "ORCHESTRATION_RETURNED"
    committed = prepared.ledger.committed_picodollars
    result: Dict[str, Any] = {
        "schema_version": NORMAL_RUN_SCHEMA_VERSION_V1,
        "status": run_status,
        "question": question,
        "session_id": prepared.session_id,
        "run_attempt": run_attempt,
        "manifest": prepared.manifest,
        "endpoint_fetch": {
            "http_status": fetched.http_status,
            "latency_ms": fetched.latency_ms,
        },
        "endpoint_evidence": prepared.endpoint_evidence.model_dump(
            mode="json", exclude_none=False
        ),
        "profile": prepared.profile.model_dump(mode="json", exclude_none=False),
        "authorization": prepared.authorization.model_dump(
            mode="json", exclude_none=False
        ),
        "turns": turns,
        "calls_consumed": prepared.ledger.calls_consumed,
        "maximum_live_calls": prepared.authorization.maximum_calls,
        "observed_cost_picodollars": prepared.ledger.observed_picodollars,
        "observed_cost_usd": _usd_text(prepared.ledger.observed_picodollars),
        "settled_cost_picodollars": prepared.ledger.settled_picodollars,
        "unsettled_reserved_picodollars": (
            prepared.ledger.unsettled_reserved_picodollars
        ),
        "authorized_session_ceiling_picodollars": (
            NORMAL_REMAINING_SPEND_PICODOLLARS_V1
        ),
        "committed_cost_picodollars": committed,
        "remaining_after_run_picodollars": max(
            0, NORMAL_REMAINING_SPEND_PICODOLLARS_V1 - committed
        ),
        "latency_ms": latency_ms,
        "fatal_failure": prepared.ledger.fatal_failure,
        "error": error,
        "ced_outcome": _ced_outcome_summary_v1(final),
        "final": (
            final.model_dump(mode="json", exclude_none=False)
            if hasattr(final, "model_dump")
            else None
        ),
        "state": (
            state.model_dump(mode="json", exclude_none=False)
            if hasattr(state, "model_dump")
            else None
        ),
    }
    result = _sanitize_public_value(result)
    artifact_sha256 = _write_once_json_v1(target, result)
    result["artifact_path"] = str(target.resolve())
    result["artifact_sha256"] = artifact_sha256
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded normal Socrates dialogue on GPT-5 Mini/Flex"
    )
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION_V1)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    result = run_socrates(args.question, output_path=args.out)
    print(
        json.dumps(
            {
                "status": result["status"],
                "session_id": result["session_id"],
                "calls_consumed": result["calls_consumed"],
                "observed_cost_usd": result["observed_cost_usd"],
                "ced_outcome": result["ced_outcome"],
                "artifact_path": result["artifact_path"],
                "artifact_sha256": result["artifact_sha256"],
                "error": result["error"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "ORCHESTRATION_RETURNED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
