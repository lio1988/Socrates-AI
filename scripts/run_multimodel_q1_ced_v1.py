"""Q2d: one exactly authorized heterogeneous Socrates/CED dialogue.

The three frozen seats are GPT-5 Mini on ``openai/flex``, Gemini 3.7 Flash on
``google-vertex/global``, and GPT-4.1 Mini on ``azure/swedencentral``.  Each
seat keeps its endpoint-specific model, selector, output parameter, schema,
price ceilings, and identity checks.

Q2d is fail-closed around one canonical protocol manifest.  Exact bytes,
SHA-256, reconstructed payload, a write-once attempt latch, and every
pre-dispatch guard must all agree before a request can cross the wire. The
runner verifies the retained evaluator-key digest offline, but never sends
the key in a provider request, writes it into the collection artifact, or scores
its own collection.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import weakref
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

import pydantic
import pydantic_core

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_multimodel_q1_v1 as q1
import scripts.run_socrates_live_v1 as normal
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
    safe_public_exception_code_v1,
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.protocol_authorization_v1 import (
    AuthorizedProtocolAttemptCapabilityV1,
    AuthorizedProtocolReceiptV1,
    assert_authorized_protocol_attempt_consumed_v1,
    assert_exact_authorized_protocol_v1,
    bind_authorized_protocol_attempt_v1,
    consume_authorized_protocol_attempt_v1,
)
from backend.dialogues.socrates_zero.openrouter_request_bounds_v1 import (
    EstimatorUnsupportedError,
    RequestBoundError,
    assert_request_within_bounds_v1,
    build_refusal_receipt_v1,
    measure_request_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    FROZEN_LIVE_SEMANTIC_HEADERS_V1,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1,
    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1,
    OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1,
    OPENROUTER_DISPATCH_LATCH_V1,
)
from backend.dialogues.models import AgentRole, AgentTask, DialogPhase, TaskKind
from backend.dialogues.reasoning_prompts import build_reasoning_system_prompt
from backend.dialogues.role_assignment import assign_primary_roles, stable_hash

CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero\openrouter-multimodel-q1-ced-v1"
)
RUN_ATTEMPT_LATCH_DIRECTORY_V1 = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero\openrouter-q2d-run-attempt-v1"
)
Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/"
    "runs/q2d_live_run_v1"
)
Q2D_RESULT_ARTIFACT_NAME_V1 = "q2d_ethics_council_v1.json"
Q2D_DISPATCH_EVIDENCE_DIRECTORY_NAME_V1 = "dispatch_evidence_v1"
Q2D_RUN_DIRECTORY_V1 = q1.RUNS / "q2d_live_run_v1"

Q2D_PROTOCOL_SCHEMA_VERSION_V1 = "socrates-q2d-freeze/v1"
Q2D_SESSION_ID_V1 = "q2d-ced-hetero-v1"
Q2D_LOGICAL_AGENTS_V1 = 3
# 107 before rule_on_round_objections_v1; the eight added calls rule on the
# four elenchus objections, two independent peers each.
Q2D_MAXIMUM_CED_CALLS_V1 = 115
#: Same protocol with rule_on_round_objections_v1 switched off, so the control
#: arm and the treatment arm run identical code and differ by one flag.
Q2D_MAXIMUM_CED_CALLS_CONTROL_V1 = 107
Q2D_PRIOR_OBSERVED_SPEND_PICODOLLARS_V1 = 651_915_000_000

Q2D_RUNTIME_SCRIPT_FILES_V1: Tuple[str, ...] = (
    "scripts/q2_ethics_question_v1.py",
    "scripts/score_q2_ethics_v1.py",
    "scripts/run_hard_logic_live_test_v1.py",
    "scripts/run_multimodel_q1_ced_v1.py",
    "scripts/run_multimodel_q1_v1.py",
    "scripts/run_reduced_socrates_benchmark_v1.py",
    "scripts/run_socrates_live_v1.py",
)
Q2D_RUNTIME_REPOSITORY_CONTROL_FILES_V1: Tuple[str, ...] = (
    ".gitattributes",
)

Q2D_TRUST_MODEL_V1 = "trusted_local_code_no_malicious_in_process_reflection"


def _q2d_implementation_files_v1(repository_root: Path) -> Tuple[str, ...]:
    """Conservatively lock every dialogue module plus the live script roots."""

    dialogue_root = repository_root / "backend" / "dialogues"
    dialogue_files = {
        path.relative_to(repository_root).as_posix()
        for path in dialogue_root.rglob("*.py")
        if path.is_file()
    }
    return tuple(
        sorted(
            dialogue_files
            | set(Q2D_RUNTIME_SCRIPT_FILES_V1)
            | set(Q2D_RUNTIME_REPOSITORY_CONTROL_FILES_V1)
        )
    )


def _q2d_frozen_attempt_directory_v1() -> Path:
    """Return the runner-owned latch directory; callers cannot override it."""

    if not isinstance(RUN_ATTEMPT_LATCH_DIRECTORY_V1, Path):
        raise ContractValidationError("Q2d frozen attempt directory drifted")
    return RUN_ATTEMPT_LATCH_DIRECTORY_V1


def _assert_q2d_live_host_v1() -> None:
    """The frozen local state paths are Windows-only production boundaries."""

    if os.name != "nt":
        raise ContractValidationError(
            "Q2d live execution requires the frozen Windows local-state paths"
        )


def _assert_fresh_q2d_process_dispatch_latch_v1() -> None:
    """Refuse a reused process before the unique protocol attempt is consumed."""

    used = OPENROUTER_DISPATCH_LATCH_V1.count("live_inference_post")
    if type(used) is not int or used != 0:
        raise ContractValidationError(
            "Q2d live execution requires a fresh inference-dispatch process"
        )


def _q2d_production_claim_store_v1() -> Path:
    """Resolve the frozen claim store only on its authorized live host."""

    _assert_q2d_live_host_v1()
    if not isinstance(CLAIM_STORE, Path):
        raise ContractValidationError("Q2d frozen claim store drifted")
    try:
        if not CLAIM_STORE.is_absolute():
            raise ContractValidationError("Q2d frozen claim store is not absolute")
        return CLAIM_STORE.resolve(strict=False)
    except (OSError, ValueError) as exc:
        raise ContractValidationError("Q2d frozen claim store is invalid") from exc


def _fsync_directory_best_effort_v1(directory: Path) -> None:
    """Durably publish a newly created entry where directory fsync exists."""

    try:
        descriptor = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _write_exclusive_fsynced_bytes_v1(path: Path, payload: bytes) -> None:
    """Create one artifact exactly once, flush it, and never overwrite it."""

    if not isinstance(path, Path) or not isinstance(payload, bytes):
        raise ContractValidationError("Q2d exclusive artifact arguments are invalid")
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory_best_effort_v1(path.parent)
    except FileExistsError as exc:
        raise ContractValidationError(
            f"Q2d write-once artifact already exists: {path.name}"
        ) from exc
    except OSError as exc:
        raise ContractValidationError(
            f"Q2d artifact could not be written: {path.name}"
        ) from exc


def _create_q2d_run_directory_v1() -> Path:
    """Atomically claim the frozen result boundary before one-shot authority."""

    directory = Q2D_RUN_DIRECTORY_V1
    if not isinstance(directory, Path):
        raise ContractValidationError("Q2d frozen run directory drifted")
    try:
        directory.mkdir(exist_ok=False)
        (directory / Q2D_DISPATCH_EVIDENCE_DIRECTORY_NAME_V1).mkdir(
            exist_ok=False
        )
        _fsync_directory_best_effort_v1(directory)
        _fsync_directory_best_effort_v1(directory.parent)
    except FileExistsError as exc:
        raise ContractValidationError("Q2d frozen run directory already exists") from exc
    except OSError as exc:
        raise ContractValidationError("Q2d frozen run directory is unavailable") from exc
    return directory


def _q2d_runtime_environment_v1() -> Dict[str, str]:
    """Versions whose exact schema rendering is part of this authorization."""

    return {
        "python_implementation": sys.implementation.name,
        "python_version": ".".join(str(value) for value in sys.version_info[:3]),
        "pydantic_version": pydantic.__version__,
        "pydantic_core_version": pydantic_core.__version__,
    }

#: The three output envelopes the CED task router can ask for.
OUTPUT_ENVELOPES_V1: Tuple[int, ...] = (
    normal.SHORT_OUTPUT_TOKENS_V1,
    normal.REVISION_OUTPUT_TOKENS_V1,
    normal.SYNTHESIS_OUTPUT_TOKENS_V1,
)

#: Wire parameters the frozen Flex guard forbids, kept identical here.
FORBIDDEN_WIRE_PARAMETERS_V1: Tuple[str, ...] = (
    "temperature",
    "reasoning",
    "reasoning_effort",
    "include_reasoning",
    "tools",
    "tool_choice",
)

#: A **local experiment prompt budget**, in tokens. It is not a provider
#: limit and is deliberately unrelated to one.
#:
#: Provenance of what it replaced: the previous 65,536 was Gemini's
#: `data.endpoints[0].max_completion_tokens` — an *output* field for one
#: seat — used as an input bound for all three, then enforced by comparing
#: characters against it.
#:
#: This value is a local budget with two jobs: it is what
#: `conservative_turn_cost_bound_v1` reserves against, and it caps how much
#: accumulated dialogue one turn may carry. It is independent of every
#: endpoint's context window (400,000 / 1,048,576 / 1,047,576 tokens) and of
#: every endpoint's output limit; the context window is checked separately
#: and always applies as well.
#:
#: This 131,072-token value is inherited unchanged from Q2c.  Its historical
#: selection used the then-declared 64-call ceiling; Q2d now derives the true
#: 107-call topology and prices it honestly at $5.18420480 incremental.  It is
#: not reduced to manufacture compliance with the earlier $5 ceiling.
#:
#: It gives 77% headroom over the scale-faithful Q2b reconstruction (74,156
#: tokens upper bound). A later turn that exceeds it is refused locally, at no
#: provider cost, with a privacy-safe receipt.
EXPERIMENT_PROMPT_BUDGET_TOKENS_V1 = 393_216

#: The cost-reservation call sites take a token count. Same value, same unit.
DECLARED_MAX_INPUT_TOKENS_V1 = EXPERIMENT_PROMPT_BUDGET_TOKENS_V1


def build_seat_policy_v1(
    key: str, output_limit_tokens: int
) -> OpenRouterFrozenExecutionPolicyV1:
    """One seat's execution policy at one declared output envelope."""

    if output_limit_tokens not in OUTPUT_ENVELOPES_V1:
        raise ContractValidationError("CED output envelope is not declared")
    spec = q1.FAMILIES_V1[key]
    if spec["output_field"] not in ("max_tokens", "max_completion_tokens"):
        raise ContractValidationError(
            f"{key}: unknown endpoint output-limit field {spec['output_field']!r}"
        )
    return OpenRouterFrozenExecutionPolicyV1(
        model=spec["model"],
        provider_only=(spec["selector"],),
        provider_order=(spec["selector"],),
        output_limit_tokens=output_limit_tokens,
        temperature=None,
        seed=normal.REDUCED_SEED_V1,
        max_price_prompt_usd_per_million=spec["prompt_ceiling"],
        max_price_completion_usd_per_million=spec["completion_ceiling"],
        max_price_request_usd="0",
        bounded_timeout_seconds=120,
    )


def build_seat_policy_family_v1(
    key: str,
) -> Dict[int, OpenRouterFrozenExecutionPolicyV1]:
    return {limit: build_seat_policy_v1(key, limit) for limit in OUTPUT_ENVELOPES_V1}


def output_limit_for_seat_task_v1(key: str, task: Any) -> int:
    """Return the frozen task envelope with one evidence-backed exception.

    Q2c proved that GPT-5 Mini exhausted the 4,096-token elenchus envelope
    before it could finish a valid visible JSON payload.  No other seat/task
    pair receives a larger envelope: Gemini's failed Socratic turn stopped
    normally and violated the provider-side structured-output contract.
    """

    if key not in dict(q1.COUNCIL_SEATS_V1).values():
        raise ContractValidationError(f"unknown Q2d council seat {key!r}")
    if type(task) is not normal.AgentTask or task.task_kind is None:
        raise ContractValidationError("a CED task kind is required for seat routing")
    if (
        key == "gpt_5_mini"
        and task.task_kind is normal.TaskKind.ELENCHUS_OBJECTION
    ):
        return normal.REVISION_OUTPUT_TOKENS_V1
    return normal.output_limit_for_task_v1(task)


def seat_policy_for_task_factory_v1(
    key: str,
    policies: Dict[int, OpenRouterFrozenExecutionPolicyV1],
) -> Callable[[Any], OpenRouterFrozenExecutionPolicyV1]:
    """Select from one seat's frozen family using the same Q2d router."""

    def select(task: Any) -> OpenRouterFrozenExecutionPolicyV1:
        limit = output_limit_for_seat_task_v1(key, task)
        try:
            return policies[limit]
        except KeyError as exc:
            raise ContractValidationError(
                f"{key}: no declared policy for {limit} output tokens"
            ) from exc

    return select


#: Where construction evidence for a locally refused request is kept. Raw
#: prompt text never goes here: a refused CED prompt holds the whole
#: dialogue, and archiving it would open a raw-prompt store outside the
#: evidence boundary this branch has kept throughout.
REFUSAL_RECEIPT_DIRECTORY_V1 = q1.RUNS / "refusal_receipts"

#: Context window in tokens for each seat's exact endpoint, read from that
#: endpoint's own retained listing rather than assumed.
SEAT_CONTEXT_WINDOW_TOKENS_V1: Dict[str, int] = {
    "gpt_5_mini": 400_000,
    "gemini_3_7_flash_standard": 1_048_576,
    "gemini_3_7_flash": 1_048_576,
    "gpt_4_1_mini": 1_047_576,
    # Read from the OpenRouter model catalogue rather than assumed. Both weak
    # seats cap completions at 16_384, which is exactly the synthesis budget:
    # asking either for 16_384 output tokens leaves it no headroom at all, and
    # a Qwen3 32B baseline given that budget ran to the cap and returned
    # truncated, unparseable JSON. That sample was excluded as an artifact of
    # our ceiling rather than scored as a failure of the model.
    "qwen3_32b": 131_072,
    "llama_4_maverick": 1_048_576,
    "llama_4_scout": 1_048_576,
    "qwen3_235b": 262_144,
}

#: The most a seat will produce in one completion, from the OpenRouter catalogue.
#: A phase budget equal to one of these is not a budget: it asks the model for
#: everything it can emit and leaves nothing for the answer to finish in. That is
#: how a Qwen3 32B baseline was lost - asked for 16_384 output tokens when 16_384
#: was its ceiling, it ran to the cap and returned truncated, unparseable JSON,
#: and the sample had to be excluded as our artifact rather than scored.
SEAT_COMPLETION_CEILING_TOKENS_V1: Dict[str, int] = {
    "gpt_5_mini": 128_000,
    "gemini_3_7_flash_standard": 65_536,
    "gemini_3_7_flash": 65_536,
    "gpt_4_1_mini": 32_768,
    "qwen3_32b": 16_384,
    "llama_4_maverick": 16_384,
    "llama_4_scout": 16_384,
}

#: Room a phase budget must leave below the tightest seat ceiling.
OUTPUT_BUDGET_HEADROOM_TOKENS_V1 = 4_096


def assert_output_budgets_fit_v1(seat_keys) -> Dict[str, int]:
    """Refuse a plan whose phase budgets crowd the tightest seat's ceiling.

    Twice now a run was spoiled by asking a model for as many tokens as it can
    emit: once in the Q5 council, where six GPT-5 Mini calls were cut off and
    recorded as rejected moves, and once in a Qwen3 32B baseline that had to be
    thrown out entirely. Both were invisible until the evidence was read
    afterwards. This makes the same mistake refuse to start.
    """

    ceilings = {}
    for key in seat_keys:
        ceiling = SEAT_COMPLETION_CEILING_TOKENS_V1.get(key)
        if ceiling is None:
            raise ContractValidationError(
                f"{key}: no recorded completion ceiling; a phase budget cannot "
                "be justified against an unknown limit"
            )
        ceilings[key] = ceiling
    tightest = min(ceilings.values())
    largest = max(OUTPUT_ENVELOPES_V1)
    if largest + OUTPUT_BUDGET_HEADROOM_TOKENS_V1 > tightest:
        raise ContractValidationError(
            f"output budget {largest} leaves under "
            f"{OUTPUT_BUDGET_HEADROOM_TOKENS_V1} tokens below the tightest seat "
            f"ceiling {tightest}; a request that reaches a model's ceiling is a "
            "truncated answer waiting to happen"
        )
    return ceilings


def assert_input_within_bound_v1(
    key: str, body: Dict[str, Any], reserved_output_tokens: int
) -> Dict[str, Any]:
    """Bound one rendered request, never comparing across units.

    Returns the measurement so a refusal can record what it saw.
    """

    context_window = SEAT_CONTEXT_WINDOW_TOKENS_V1.get(key)
    if context_window is None:
        raise ContractValidationError(f"{key}: no recorded endpoint context window")
    selector = q1.FAMILIES_V1[key]["selector"]
    try:
        measurement = measure_request_v1(
            body,
            reserved_output_tokens=reserved_output_tokens,
            context_window_tokens=context_window,
            provider_selector=selector,
        )
    except EstimatorUnsupportedError as exc:
        raise ContractValidationError(f"{key}: {exc}") from exc
    try:
        assert_request_within_bounds_v1(
            measurement, max_prompt_tokens=EXPERIMENT_PROMPT_BUDGET_TOKENS_V1
        )
    except RequestBoundError as exc:
        _persist_refusal_receipt_v1(key, body, measurement, exc)
        raise ContractValidationError(f"{key}: {exc}") from exc
    return measurement.as_record()


def _persist_refusal_receipt_v1(
    key: str, body: Dict[str, Any], measurement: Any, exc: Any
) -> None:
    """Keep construction evidence for a refused request, never its content.

    Q2b's refusals kept only a digest, which made the defect impossible to
    reproduce. The fix is not to archive the prompt: a refused CED prompt holds
    the entire dialogue, and storing it would open a raw-prompt archive outside
    the evidence boundary this branch has kept throughout. The receipt records
    the digest, the sizes, the estimator and the limits.
    """

    spec = q1.FAMILIES_V1[key]
    try:
        REFUSAL_RECEIPT_DIRECTORY_V1.mkdir(parents=True, exist_ok=True)
        receipt = build_refusal_receipt_v1(
            seat=key,
            model=spec["model"],
            phase=str(body.get("__phase", "")) or "unknown",
            task_kind="unknown",
            body=body,
            measurement=measurement,
            error=exc,
            source_artifact_references=(spec.get("evidence_file")
                                        or spec.get("evidence_path")
                                        or spec.get("retained_profile"),),
            refused_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        target = REFUSAL_RECEIPT_DIRECTORY_V1 / (
            f"refusal_{key}_{receipt['canonical_body_sha256'][:16]}.json"
        )
        target.write_text(canonical_json(receipt), encoding="utf-8")
    except OSError:
        pass  # evidence retention must never itself break a run


def assert_exact_seat_output_parameter_v1(
    key: str, body: Dict[str, Any], expected_limit: int
) -> None:
    """Require exactly one endpoint-native output parameter, never both."""

    expected_field = q1.FAMILIES_V1[key]["output_field"]
    output_fields = {"max_tokens", "max_completion_tokens"}
    present = {field for field in output_fields if field in body}
    if present != {expected_field}:
        raise ContractValidationError(
            f"{key}: output parameter set drifted: {sorted(present)}"
        )
    if body.get(expected_field) != expected_limit:
        raise ContractValidationError(f"{key}: rendered output bound drifted")


_COUNCIL_USER_PREFIX_V1 = (
    "You are one bounded Socratic council provider. Return exactly one JSON "
    "object and no markdown. Do not invent protocol authority.\n"
)


def _reject_q2d_duplicate_keys_v1(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    """Reject parser-differential JSON instead of silently keeping one key."""

    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError(
                f"Q2d rendered JSON contains duplicate key: {key}"
            )
        result[key] = value
    return result


def _reject_q2d_nonfinite_constant_v1(value: str) -> None:
    raise ContractValidationError(
        f"Q2d rendered JSON contains non-finite constant: {value}"
    )


def _load_strict_q2d_json_object_v1(text: str, *, label: str) -> Dict[str, Any]:
    """Parse strict JSON with no duplicate keys or non-standard numbers."""

    if type(text) is not str:
        raise ContractValidationError(f"{label} must be a JSON string")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_q2d_duplicate_keys_v1,
            parse_constant=_reject_q2d_nonfinite_constant_v1,
        )
    except ContractValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{label} is not strict JSON") from exc
    if type(value) is not dict:
        raise ContractValidationError(f"{label} must be a JSON object")
    return value


_Q2D_SYNTHETIC_EVALUATOR_TASKS_V1 = frozenset(
    {
        TaskKind.MOVE_SCORE,
        TaskKind.SECTION_SCORE,
        TaskKind.COUNCIL_RATIFICATION,
        TaskKind.OBJECTION_VERIFICATION,
    }
)


_Q2D_ORDINARY_DELIBERATION_TASKS_V1 = frozenset(
    {
        TaskKind.SOCRATIC_QUESTION,
        TaskKind.INITIAL_RESPONSE,
        TaskKind.ELENCHUS_OBJECTION,
        TaskKind.REFLECTION_REVISION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
        TaskKind.SYNTHESIS_DRAFT,
    }
)

_Q2D_SEAT_IDENTIFIED_EVALUATOR_TASKS_V1 = frozenset(
    {
        TaskKind.MOVE_SCORE,
        TaskKind.SECTION_SCORE,
        TaskKind.COUNCIL_RATIFICATION,
    }
)

_Q2D_TASK_PHASES_AND_ROLES_V1 = {
    TaskKind.SOCRATIC_QUESTION: (
        frozenset({DialogPhase.OPENING, DialogPhase.ELENCHUS}),
        frozenset({AgentRole.SOCRATES}),
    ),
    TaskKind.INITIAL_RESPONSE: (
        frozenset({DialogPhase.INITIAL_RESPONSE}),
        frozenset(
            {
                AgentRole.ELENCHUS_CRITIC,
                AgentRole.EMPIRICIST,
                AgentRole.SYNTHESIZER,
            }
        ),
    ),
    TaskKind.ELENCHUS_OBJECTION: (
        frozenset({DialogPhase.ELENCHUS}),
        frozenset({AgentRole.ELENCHUS_CRITIC, AgentRole.EMPIRICIST}),
    ),
    TaskKind.REFLECTION_REVISION: (
        frozenset({DialogPhase.REFLECTION}),
        frozenset({AgentRole.REFLECTOR}),
    ),
    TaskKind.RECONSTRUCTION_PROPOSAL: (
        frozenset({DialogPhase.RECONSTRUCTION}),
        frozenset({AgentRole.MAIEUTIC_RECONSTRUCTOR}),
    ),
    TaskKind.SYNTHESIS_DRAFT: (
        frozenset({DialogPhase.SYNTHESIS}),
        frozenset({AgentRole.SYNTHESIZER}),
    ),
    TaskKind.MOVE_SCORE: (
        frozenset(
            {
                DialogPhase.OPENING,
                DialogPhase.INITIAL_RESPONSE,
                DialogPhase.ELENCHUS,
                DialogPhase.REFLECTION,
                DialogPhase.RECONSTRUCTION,
                DialogPhase.SYNTHESIS,
            }
        ),
        frozenset({AgentRole.FINAL_EVALUATOR}),
    ),
    TaskKind.SECTION_SCORE: (
        frozenset({DialogPhase.SYNTHESIS}),
        frozenset({AgentRole.FINAL_EVALUATOR}),
    ),
    TaskKind.COUNCIL_RATIFICATION: (
        frozenset({DialogPhase.RATIFICATION}),
        frozenset({AgentRole.FINAL_EVALUATOR}),
    ),
    TaskKind.OBJECTION_VERIFICATION: (
        frozenset({DialogPhase.ELENCHUS}),
        frozenset({AgentRole.FINAL_EVALUATOR}),
    ),
}


def _q2d_reachable_schema_tasks_v1() -> Dict[str, AgentTask]:
    """One deterministic task for every reachable Q2d response-schema shape."""

    specs = [
        ("socratic.opening", TaskKind.SOCRATIC_QUESTION,
         DialogPhase.OPENING, AgentRole.SOCRATES),
        ("socratic.followup", TaskKind.SOCRATIC_QUESTION,
         DialogPhase.ELENCHUS, AgentRole.SOCRATES),
        ("initial.elenchus_critic", TaskKind.INITIAL_RESPONSE,
         DialogPhase.INITIAL_RESPONSE, AgentRole.ELENCHUS_CRITIC),
        ("initial.empiricist", TaskKind.INITIAL_RESPONSE,
         DialogPhase.INITIAL_RESPONSE, AgentRole.EMPIRICIST),
        ("initial.synthesizer", TaskKind.INITIAL_RESPONSE,
         DialogPhase.INITIAL_RESPONSE, AgentRole.SYNTHESIZER),
        ("elenchus.critic", TaskKind.ELENCHUS_OBJECTION,
         DialogPhase.ELENCHUS, AgentRole.ELENCHUS_CRITIC),
        ("elenchus.empiricist", TaskKind.ELENCHUS_OBJECTION,
         DialogPhase.ELENCHUS, AgentRole.EMPIRICIST),
        ("reflection", TaskKind.REFLECTION_REVISION,
         DialogPhase.REFLECTION, AgentRole.REFLECTOR),
        ("reconstruction", TaskKind.RECONSTRUCTION_PROPOSAL,
         DialogPhase.RECONSTRUCTION, AgentRole.MAIEUTIC_RECONSTRUCTOR),
        ("synthesis", TaskKind.SYNTHESIS_DRAFT,
         DialogPhase.SYNTHESIS, AgentRole.SYNTHESIZER),
        ("move_score.opening", TaskKind.MOVE_SCORE,
         DialogPhase.OPENING, AgentRole.FINAL_EVALUATOR),
        ("move_score.initial_response", TaskKind.MOVE_SCORE,
         DialogPhase.INITIAL_RESPONSE, AgentRole.FINAL_EVALUATOR),
        ("move_score.elenchus", TaskKind.MOVE_SCORE,
         DialogPhase.ELENCHUS, AgentRole.FINAL_EVALUATOR),
        ("move_score.reflection", TaskKind.MOVE_SCORE,
         DialogPhase.REFLECTION, AgentRole.FINAL_EVALUATOR),
        ("move_score.reconstruction", TaskKind.MOVE_SCORE,
         DialogPhase.RECONSTRUCTION, AgentRole.FINAL_EVALUATOR),
        ("move_score.synthesis", TaskKind.MOVE_SCORE,
         DialogPhase.SYNTHESIS, AgentRole.FINAL_EVALUATOR),
        ("section_score", TaskKind.SECTION_SCORE,
         DialogPhase.SYNTHESIS, AgentRole.FINAL_EVALUATOR),
        ("ratification", TaskKind.COUNCIL_RATIFICATION,
         DialogPhase.RATIFICATION, AgentRole.FINAL_EVALUATOR),
        ("objection_verification", TaskKind.OBJECTION_VERIFICATION,
         DialogPhase.ELENCHUS, AgentRole.FINAL_EVALUATOR),
    ]
    return {
        label: AgentTask(
            task_id=f"q2d_schema_{label.replace('.', '_')}",
            session_id=Q2D_SESSION_ID_V1,
            agent_id="q2d_schema_probe",
            role=role,
            phase=phase,
            question="Q2d frozen response-schema probe",
            task_kind=kind,
        )
        for label, kind, phase, role in specs
    }


def _q2d_reachable_response_schema_sha256_v1() -> Dict[str, str]:
    return {
        label: hashlib.sha256(
            canonical_json(normal.ced_structured_response_format_v1(task)).encode(
                "utf-8"
            )
        ).hexdigest()
        for label, task in _q2d_reachable_schema_tasks_v1().items()
    }


def _q2d_ordinary_schedule_signatures_v1() -> frozenset[tuple[Any, ...]]:
    """Derive every ordinary task signature reachable in the fixed session."""

    fake = normal.FakeProvider()
    agents = [
        normal.SocraticAgent(f"agent_{index}", fake)
        for index in range(Q2D_LOGICAL_AGENTS_V1)
    ]
    ced = normal.CEDOrchestrator(
        agents,
        fake,
        shadow_scoring_mode=normal.ShadowScoringMode.ALL_PHASES,
        phase_retry=True,
        max_socratic_followups=2,
        ratification_repair="block",
        tree_expansions=0,
        ai_learning=False,
    )
    state = ced.create_session(
        "Q2d schedule seal", session_id=Q2D_SESSION_ID_V1
    )
    signatures: set[tuple[Any, ...]] = set()

    def add_specs(phase: DialogPhase, round_number: int) -> tuple[Any, ...]:
        specs = ced.canonical_registry_task_specs(
            state, phase, round_index=round_number
        )
        signatures.update(
            (
                round_number,
                spec.phase,
                spec.task_kind,
                spec.agent_id,
                spec.role,
            )
            for spec in specs
        )
        return specs

    add_specs(DialogPhase.OPENING, 0)
    initial_specs = add_specs(DialogPhase.INITIAL_RESPONSE, 0)
    add_specs(DialogPhase.ELENCHUS, 0)
    add_specs(DialogPhase.ELENCHUS, 1)
    add_specs(DialogPhase.RECONSTRUCTION, 0)
    add_specs(DialogPhase.RECONSTRUCTION, 1)
    add_specs(DialogPhase.SYNTHESIS, 0)
    add_specs(DialogPhase.SYNTHESIS, 1)
    for round_number in (0, 1):
        signatures.update(
            (
                round_number,
                DialogPhase.REFLECTION,
                TaskKind.REFLECTION_REVISION,
                spec.agent_id,
                AgentRole.REFLECTOR,
            )
            for spec in initial_specs
        )
    return frozenset(signatures)


def _assert_q2d_seat_task_mapping_v1(key: str, task: AgentTask) -> None:
    """Bind each reachable Q2d task to its exact physical council seat.

    Deliberation tasks carry the stable logical agent id, while registry
    scoring and ratification tasks carry the voter provider id. Objection
    verification is the intentional exception: CED uses ``agent_id`` for the
    target claim id and sends the same task to independent peer adapters.
    """

    # A second attempt is admitted; a third is not.
    #
    # The line this protocol has to hold is not "never ask twice". Asking the
    # same interlocutor again is the elenchus itself: an answer that changes on
    # the second asking has shown it was opinion rather than knowledge, and the
    # inconsistency is the finding. What must never happen is *discarding* - a
    # failure quietly replaced by a success and only the success recorded.
    #
    # So the admitted attempt is bounded and, above all, kept: CED reroutes the
    # failed slot ONCE and every attempt stays in the task log, so the second
    # answer can never erase the first. That the reroute goes to a distinct seat
    # buys independence, not permission; re-asking the silent seat would be
    # equally legitimate and would tell us something this run could not - whether
    # Gemini's empty answer was noise or a stable refusal.
    #
    # Refusing it cost a whole dialectic. In the opener experiment Gemini
    # returned {"content": {}} on the elenchus Socratic turn - 956 tokens, seven
    # required fields absent, no question. With no question there is nothing for
    # REFLECTION to answer, so the cycle ended: one silent response from one seat
    # in one turn truncated every remaining round. That is the failure mode the
    # rescue was written for, disabled by a flag that made no distinction
    # between repeating a question and hiding the answer to it.
    if type(task.attempt_index) is not int or task.attempt_index not in (0, 1, 2):
        raise ContractValidationError(
            "Q2d admits three attempts: ignorance, betrayal, non-conformance"
        )
    if type(task.round_number) is not int:
        raise ContractValidationError("Q2d task round is not reachable")

    seat_keys = [seat_key for _alias, seat_key in q1.COUNCIL_SEATS_V1]
    try:
        seat_index = seat_keys.index(key)
    except ValueError as exc:
        raise ContractValidationError(f"unknown Q2d council seat {key!r}") from exc
    if seat_index >= Q2D_LOGICAL_AGENTS_V1 or seat_index >= len(
        normal.WORKER_PROVIDER_IDS_V1
    ):
        raise ContractValidationError("Q2d seat topology drifted")

    kind = task.task_kind
    shape = _Q2D_TASK_PHASES_AND_ROLES_V1.get(kind)
    if shape is None:
        raise ContractValidationError(
            f"Q2d task kind is not reachable in the frozen protocol: {kind!r}"
        )
    allowed_phases, allowed_roles = shape
    if task.phase not in allowed_phases or task.role not in allowed_roles:
        raise ContractValidationError(
            "Q2d task phase/role relationship is not reachable in the frozen protocol"
        )

    if kind in _Q2D_ORDINARY_DELIBERATION_TASKS_V1:
        expected_agent_id = f"agent_{seat_index}"
        if task.agent_id != expected_agent_id:
            raise ContractValidationError(
                f"{key}: deliberation task is not bound to {expected_agent_id}"
            )
        signature = (
            task.round_number,
            task.phase,
            kind,
            task.agent_id,
            task.role,
        )
        if signature not in _q2d_ordinary_schedule_signatures_v1():
            raise ContractValidationError(
                "Q2d ordinary task schedule signature is not reachable"
            )
        return
    if kind in _Q2D_SEAT_IDENTIFIED_EVALUATOR_TASKS_V1:
        expected_provider_id = normal.WORKER_PROVIDER_IDS_V1[seat_index]
        if task.agent_id != expected_provider_id:
            raise ContractValidationError(
                f"{key}: evaluator task is not bound to {expected_provider_id}"
            )
        if task.round_number != 0:
            raise ContractValidationError(
                "Q2d evaluator task schedule signature is not reachable"
            )
        return
    if kind is TaskKind.OBJECTION_VERIFICATION:
        if type(task.agent_id) is not str or not task.agent_id:
            raise ContractValidationError(
                "Q2d objection verification target claim id is absent"
            )
        if task.round_number != 0:
            raise ContractValidationError(
                "Q2d objection-verification schedule signature is not reachable"
            )
        return
    raise ContractValidationError("Q2d task routing contract is incomplete")


def _expected_q2d_primary_role_v1(task: AgentTask) -> AgentRole:
    """Reconstruct the CED-owned primary role for every reachable Q2d task."""

    if task.task_kind in _Q2D_SYNTHETIC_EVALUATOR_TASKS_V1:
        return AgentRole.FINAL_EVALUATOR
    logical_agent_ids = [
        f"agent_{index}" for index in range(Q2D_LOGICAL_AGENTS_V1)
    ]
    roles = assign_primary_roles(logical_agent_ids, Q2D_SESSION_ID_V1)
    try:
        return roles[task.agent_id]
    except KeyError as exc:
        raise ContractValidationError(
            "Q2d rendered state names an unknown logical agent"
        ) from exc


def _assert_q2d_task_body_binding_v1(task: AgentTask, body: Dict[str, Any]) -> None:
    """Bind the rendered messages to the exact CED task being authorized."""

    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ContractValidationError("Q2d rendered messages drifted")
    system, user = messages
    if (
        not isinstance(system, dict)
        or set(system) != {"content", "role"}
        or system.get("role") != "system"
        or system.get("content")
        != build_reasoning_system_prompt(
            task.role, task.phase, task.task_kind, model=None
        )
    ):
        raise ContractValidationError("Q2d rendered system message drifted")
    if (
        not isinstance(user, dict)
        or set(user) != {"content", "role"}
        or user.get("role") != "user"
        or not isinstance(user.get("content"), str)
        or not user["content"].startswith(_COUNCIL_USER_PREFIX_V1)
    ):
        raise ContractValidationError("Q2d rendered user message drifted")
    payload_text = user["content"][len(_COUNCIL_USER_PREFIX_V1) :]
    payload = _load_strict_q2d_json_object_v1(
        payload_text, label="Q2d rendered user payload"
    )
    if payload_text != json.dumps(payload, ensure_ascii=False, sort_keys=True):
        raise ContractValidationError(
            "Q2d rendered user payload is not the exact producer serialization"
        )
    if set(payload) != {
        "agent_state",
        "response_contract",
        "task",
    }:
        raise ContractValidationError("Q2d rendered user payload shape drifted")
    projector = normal.make_worker_payload_projector_v1()
    projected_task, _unused_state = projector(
        task.model_dump(mode="json", exclude_none=True), {}
    )
    if payload.get("task") != projected_task:
        raise ContractValidationError("Q2d rendered task differs from CED task")
    if payload.get("response_contract") != {
        "format": "json_object",
        "required": ["content", "confidence"],
        "content_must_be_object": True,
    }:
        raise ContractValidationError("Q2d response-contract message drifted")
    state = payload.get("agent_state")
    if not isinstance(state, dict) or set(state) != {
        "agent_id",
        "assigned_role",
        "has_submitted",
        "primary_role",
        "round_number",
    }:
        raise ContractValidationError("Q2d rendered agent state drifted")
    expected_primary_role = _expected_q2d_primary_role_v1(task)
    if (
        state.get("agent_id") != projected_task.get("agent_id")
        or state.get("assigned_role") != projected_task.get("role")
        or state.get("round_number") != 0
        or state.get("has_submitted") is not False
        or state.get("primary_role") != expected_primary_role.value
    ):
        raise ContractValidationError("Q2d rendered agent state/task binding drifted")


def _seat_predispatch_guard_v1(
    key: str,
    *,
    protocol_path: Path,
    protocol_receipt: AuthorizedProtocolReceiptV1,
    expected_protocol_payload: Dict[str, Any],
    attempt_capability: AuthorizedProtocolAttemptCapabilityV1,
    builder_scope: object,
) -> Callable[..., None]:
    """Per-seat body-byte guard with exact protocol and endpoint constants."""

    _assert_registered_q2d_builder_scope_v1(builder_scope)
    spec = q1.FAMILIES_V1[key]
    expected_provider = {
        "allow_fallbacks": False,
        "max_price": {
            "completion": spec["completion_ceiling"],
            "prompt": spec["prompt_ceiling"],
            "request": "0",
        },
        "only": [spec["selector"]],
        "order": [spec["selector"]],
        "require_parameters": True,
    }

    def guard(task: Optional[Any], rendered: Any) -> None:
        # Capturing the exact bound scope keeps its weak identity live for the
        # duration of every adapter guard. A historical latch is evidence only;
        # it cannot stand in for this process-local builder authority.
        _assert_registered_q2d_builder_scope_v1(builder_scope)
        fresh_expected = build_q2d_protocol_payload_v1(
            expected_protocol_payload.get("question_name", "q2"),
            expected_protocol_payload.get("mid_round_objection_rulings", True),
        )
        if fresh_expected != expected_protocol_payload:
            raise ContractValidationError(
                "Q2d implementation, retained evidence, or local execution "
                "boundary drifted after authorization"
            )
        fresh_receipt = assert_exact_authorized_protocol_v1(
            protocol_path=protocol_path,
            authorized_sha256=protocol_receipt.authorized_sha256,
            expected_schema_version=Q2D_PROTOCOL_SCHEMA_VERSION_V1,
            expected_payload=fresh_expected,
        )
        if fresh_receipt.as_record() != protocol_receipt.as_record():
            raise ContractValidationError(
                "Q2d protocol receipt drifted after builder authorization"
            )
        assert_authorized_protocol_attempt_consumed_v1(
            capability=attempt_capability,
            receipt=protocol_receipt,
            attempt_directory=_q2d_frozen_attempt_directory_v1(),
            session_id=Q2D_SESSION_ID_V1,
            expected_builder=builder_scope,
        )
        if type(task) is not normal.AgentTask:
            raise ContractValidationError("CED pre-dispatch task is required")
        question_text, _question_sha = _question_v1(
            expected_protocol_payload.get("question_name", "q2")
        )
        if task.session_id != Q2D_SESSION_ID_V1:
            raise ContractValidationError("Q2d task session_id drifted")
        if task.question != question_text:
            raise ContractValidationError("Q2d task question drifted")
        _assert_q2d_seat_task_mapping_v1(key, task)
        if type(rendered) is not normal.OpenRouterRenderedTurnV1:
            raise ContractValidationError("exact rendered-turn contract is required")
        expected_limit = output_limit_for_seat_task_v1(key, task)
        try:
            normal.OpenRouterRenderedTurnV1.model_validate(
                rendered.model_dump(mode="json")
            )
        except Exception as exc:
            raise ContractValidationError("Q2d rendered-turn seal drifted") from exc
        body = _load_strict_q2d_json_object_v1(
            rendered.canonical_body_json, label="Q2d rendered wire body"
        )
        if rendered.canonical_body_json != canonical_json(body):
            raise ContractValidationError("Q2d rendered wire body is not canonical")
        _assert_q2d_task_body_binding_v1(task, body)
        messages = body.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            raise ContractValidationError("Q2d rendered messages drifted")
        expected_turn = OpenRouterDynamicTurnRequestV1(
            system_prompt=messages[0].get("content", "")
            if isinstance(messages[0], dict)
            else "",
            user_content=messages[1].get("content", "")
            if isinstance(messages[1], dict)
            else "",
            role_seat=str(getattr(task.role, "value", task.role) or "unknown"),
            dialogue_id=str(task.session_id),
            turn_id=str(task.task_id),
            dialogue_phase=str(
                getattr(task.phase, "value", task.phase) or "unknown"
            ),
            prior_state_digest=None,
        )
        if rendered.turn_content_id != expected_turn.turn_content_id:
            raise ContractValidationError("Q2d rendered turn-content identity drifted")
        expected_headers_sha256 = hashlib.sha256(
            canonical_json(dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1)).encode("utf-8")
        ).hexdigest()
        if rendered.semantic_headers_sha256 != expected_headers_sha256:
            raise ContractValidationError("Q2d semantic-header identity drifted")
        expected_output_field = spec["output_field"]
        expected_body_keys = {
            "messages",
            "model",
            "provider",
            "response_format",
            "seed",
            "stream",
            expected_output_field,
        }
        if set(body) != expected_body_keys:
            raise ContractValidationError("Q2d rendered wire body field set drifted")
        if rendered.policy_id != build_seat_policy_v1(key, expected_limit).policy_id:
            raise ContractValidationError(f"{key}: rendered policy identity drifted")
        if rendered.profile_id != q1.load_profile_v1(key).profile_id:
            raise ContractValidationError(f"{key}: rendered profile identity drifted")
        assert_input_within_bound_v1(
            key, body, reserved_output_tokens=expected_limit
        )
        if body.get("model") != spec["model"]:
            raise ContractValidationError(f"{key}: rendered model drifted")
        # Which key carries the output bound is an endpoint property, not a
        # global one: the Flex endpoints use `max_tokens`, Azure uses
        # `max_completion_tokens`, and sending the wrong one under
        # `require_parameters` is what refused the S7C route.
        assert_exact_seat_output_parameter_v1(key, body, expected_limit)
        if body.get("seed") != normal.REDUCED_SEED_V1:
            raise ContractValidationError(f"{key}: rendered seed drifted")
        for forbidden in FORBIDDEN_WIRE_PARAMETERS_V1:
            if forbidden in body:
                raise ContractValidationError(
                    f"{key}: forbidden wire parameter emitted: {forbidden}"
                )
        if body.get("provider") != expected_provider:
            raise ContractValidationError(f"{key}: rendered provider controls drifted")
        if body.get("stream") is not False:
            raise ContractValidationError(f"{key}: rendered stream control drifted")
        if body.get("response_format") != normal.ced_structured_response_format_v1(task):
            raise ContractValidationError(
                f"{key}: response schema differs from the exact CED task schema"
            )

    return guard


def conservative_ced_bound_v1() -> Dict[str, Any]:
    """Compatibility name for the topology-aware Q2d reservation."""

    return conservative_q2d_bound_v1()


def derive_q2d_call_plan_v1(mid_round_rulings: bool = True) -> Dict[str, Any]:
    """Derive the exact reachable three-provider Q2d call ceiling offline.

    The old 64-call value belongs to the two-worker homogeneous topology.  Q2d
    has three independent provider/model seats, mapped one-to-one to exactly
    three logical agents, so each accepted move or draft
    has two peer evaluators and every mapped objection can have two independent
    verifiers.  The fixed session ID freezes role rotation before pricing.
    """

    if stable_hash(Q2D_SESSION_ID_V1) % Q2D_LOGICAL_AGENTS_V1 != 1:
        raise ContractValidationError("Q2d fixed session role offset drifted")

    fake = normal.FakeProvider()
    agents = [
        normal.SocraticAgent(f"agent_{index}", fake)
        for index in range(Q2D_LOGICAL_AGENTS_V1)
    ]
    ced = normal.CEDOrchestrator(
        agents,
        fake,
        shadow_scoring_mode=normal.ShadowScoringMode.ALL_PHASES,
        phase_retry=True,
        max_socratic_followups=2,
        ratification_repair="block",
        tree_expansions=0,
        ai_learning=False,
    )
    state = ced.create_session("Q2d offline schedule", session_id=Q2D_SESSION_ID_V1)

    seat_keys = tuple(key for _alias, key in q1.COUNCIL_SEATS_V1)
    assert_output_budgets_fit_v1(seat_keys)
    if len(seat_keys) != Q2D_LOGICAL_AGENTS_V1 or len(set(seat_keys)) != len(
        seat_keys
    ):
        raise ContractValidationError(
            "Q2d requires exactly one distinct physical seat per logical agent"
        )
    agent_to_seat = {
        f"agent_{index}": seat_keys[index]
        for index in range(Q2D_LOGICAL_AGENTS_V1)
    }
    scheduled: list[tuple[str, TaskKind, DialogPhase, AgentRole]] = []

    def append_specs(phase: DialogPhase, round_index: int) -> tuple[Any, ...]:
        specs = ced.canonical_registry_task_specs(
            state, phase, round_index=round_index
        )
        scheduled.extend(
            (spec.agent_id, spec.task_kind, spec.phase, spec.role)
            for spec in specs
        )
        return specs

    append_specs(DialogPhase.OPENING, 0)
    initial_specs = append_specs(DialogPhase.INITIAL_RESPONSE, 0)
    append_specs(DialogPhase.ELENCHUS, 0)
    scheduled.extend(
        (
            spec.agent_id,
            TaskKind.REFLECTION_REVISION,
            DialogPhase.REFLECTION,
            AgentRole.REFLECTOR,
        )
        for spec in initial_specs
    )
    append_specs(DialogPhase.ELENCHUS, 1)
    scheduled.extend(
        (
            spec.agent_id,
            TaskKind.REFLECTION_REVISION,
            DialogPhase.REFLECTION,
            AgentRole.REFLECTOR,
        )
        for spec in initial_specs
    )
    append_specs(DialogPhase.RECONSTRUCTION, 1)
    synthesis_specs = append_specs(DialogPhase.SYNTHESIS, 1)

    # Two positions in this schedule are structurally privileged and neither
    # rotates, which the role rotation hides because rotation is complete when
    # measured by role rather than by position.
    #
    # The opening Socratic turn is the only one that precedes all content: no
    # seat has spoken, and its question sets the direction every other seat then
    # searches in. Across five Q4 runs it was always Gemini, and its question
    # already named the symmetric profiles and set responsiveness aside - after
    # which GPT-4.1 Mini, which alone calls the impossibility false in two draws
    # of three, produced the correct proof five times out of five.
    #
    # The reconstruction turn occurs exactly once, so it cannot rotate at all;
    # it was GPT-5 Mini in every run.
    #
    # Both follow from seat order through the fixed session offset. That is a
    # legitimate design, but it was invisible: it had to be reconstructed from
    # dispatch timestamps. Deriving it here puts it in the authorized payload,
    # so every run states who held the privileged chairs instead of leaving it
    # to be inferred.
    privileged_positions: Dict[str, Optional[str]] = {
        "opening_socratic_question": None,
        "maieutic_reconstruction": None,
    }
    for agent_id, _kind, phase, role in scheduled:
        if (
            phase is DialogPhase.OPENING
            and role is AgentRole.SOCRATES
            and privileged_positions["opening_socratic_question"] is None
        ):
            privileged_positions["opening_socratic_question"] = agent_to_seat[agent_id]
        if (
            phase is DialogPhase.RECONSTRUCTION
            and privileged_positions["maieutic_reconstruction"] is None
        ):
            privileged_positions["maieutic_reconstruction"] = agent_to_seat[agent_id]
    if None in privileged_positions.values():
        raise ContractValidationError(
            f"Q2d privileged positions could not be derived: {privileged_positions}"
        )

    calls_by_seat_cap: Dict[str, Dict[int, int]] = {
        key: {limit: 0 for limit in OUTPUT_ENVELOPES_V1} for key in seat_keys
    }
    deliberation_by_seat = {key: 0 for key in seat_keys}
    objections_by_seat = {key: 0 for key in seat_keys}
    syntheses_by_seat = {key: 0 for key in seat_keys}

    for slot, (agent_id, kind, phase, role) in enumerate(scheduled):
        seat = agent_to_seat[agent_id]
        task = AgentTask(
            task_id=f"q2d_plan_{slot}",
            session_id=Q2D_SESSION_ID_V1,
            agent_id=agent_id,
            role=role,
            phase=phase,
            question="Q2d offline schedule",
            task_kind=kind,
            slot_index=slot,
        )
        limit = output_limit_for_seat_task_v1(seat, task)
        calls_by_seat_cap[seat][limit] += 1
        deliberation_by_seat[seat] += 1
        if kind is TaskKind.ELENCHUS_OBJECTION:
            objections_by_seat[seat] += 1
        if kind is TaskKind.SYNTHESIS_DRAFT:
            syntheses_by_seat[seat] += 1

    deliberation_calls = len(scheduled)
    providers = len(seat_keys)
    peer_count = providers - 1
    move_score_calls = deliberation_calls * peer_count
    section_score_calls = len(synthesis_specs) * len(normal.SECTION_ORDER) * peer_count
    ratification_calls = providers

    # Every move is evaluated by all provider seats except its authoring seat.
    for key in seat_keys:
        calls_by_seat_cap[key][normal.SHORT_OUTPUT_TOKENS_V1] += (
            deliberation_calls - deliberation_by_seat[key]
        )
        calls_by_seat_cap[key][normal.SHORT_OUTPUT_TOKENS_V1] += (
            len(normal.SECTION_ORDER)
            * (len(synthesis_specs) - syntheses_by_seat[key])
        )
        calls_by_seat_cap[key][normal.SHORT_OUTPUT_TOKENS_V1] += 1

    # Worst case: all four non-Socratic elenchus moves plus one critical
    # ratification objection from each provider are mapped.  Each is checked by
    # the two model-distinct peers, never by its raiser.
    objections_with_ratification = {
        key: objections_by_seat[key] + 1 for key in seat_keys
    }
    objection_count = sum(objections_with_ratification.values())
    for key in seat_keys:
        calls_by_seat_cap[key][normal.SHORT_OUTPUT_TOKENS_V1] += (
            objection_count - objections_with_ratification[key]
        )
    verification_calls = objection_count * peer_count

    # rule_on_round_objections_v1 rules on each elenchus objection while the
    # dialogue can still read the reason, using the same independence rule as
    # the governing pass: every seat whose model differs from the raiser. The
    # ratification objections are excluded because they are raised after the
    # last round, when no reader is left.
    round_objection_count = (
        sum(objections_by_seat.values()) if mid_round_rulings else 0
    )
    for key in seat_keys:
        calls_by_seat_cap[key][normal.SHORT_OUTPUT_TOKENS_V1] += (
            round_objection_count - objections_by_seat[key]
        )
    round_ruling_calls = round_objection_count * peer_count if mid_round_rulings else 0

    # Phase rescue is conditional, so it never appears in the deterministic
    # schedule above - which means without explicit headroom the process latch
    # would cut a run at exactly the moment a rescue was needed.
    #
    # The bound: a rescue reroutes only failed slots, once per phase. Worst case
    # every deliberation slot fails once, giving one reroute each, and each
    # rescued move that is accepted is peer-scored by the two seats that did not
    # author it. Nothing else can fire.
    # Two further attempts per slot, not one: the first repeats the question to
    # the same seat, because a first failure may be simple misunderstanding; the
    # second passes it to a different seat, because a second failure is no
    # longer that.
    rescue_reroutes = deliberation_calls * 2
    rescue_scores = rescue_reroutes * peer_count
    phase_rescue_headroom = rescue_reroutes + rescue_scores

    stage_calls = {
        "deliberation": deliberation_calls,
        "phase_rescue_headroom": phase_rescue_headroom,
        "move_scores": move_score_calls,
        "section_scores": section_score_calls,
        "ratification": ratification_calls,
        "objection_verification": verification_calls,
        "round_objection_rulings": round_ruling_calls,
    }
    maximum_calls = sum(stage_calls.values())
    expected_calls = (
        Q2D_MAXIMUM_CED_CALLS_V1 if mid_round_rulings
        else Q2D_MAXIMUM_CED_CALLS_CONTROL_V1
    ) + phase_rescue_headroom
    if maximum_calls != expected_calls:
        raise ContractValidationError(
            f"Q2d call-plan drift: {maximum_calls} != {expected_calls}"
        )

    return {
        "session_id": Q2D_SESSION_ID_V1,
        "logical_agents": Q2D_LOGICAL_AGENTS_V1,
        "logical_agent_to_seat": agent_to_seat,
        "seat_mapping": "one_logical_agent_per_physical_model",
        "maximum_calls": maximum_calls,
        "stage_calls": stage_calls,
        "deliberation_authored_by_seat": deliberation_by_seat,
        "elenchus_objections_by_seat": objections_by_seat,
        "privileged_positions": privileged_positions,
        "synthesis_drafts_by_seat": syntheses_by_seat,
        "calls_by_seat_and_output_limit": {
            key: {str(limit): counts[limit] for limit in OUTPUT_ENVELOPES_V1}
            for key, counts in calls_by_seat_cap.items()
        },
    }


def conservative_q2d_bound_v1(mid_round_rulings: bool = True) -> Dict[str, Any]:
    """Price the exact fixed-session call plan at frozen endpoint ceilings."""

    plan = derive_q2d_call_plan_v1(mid_round_rulings)
    seat_totals: Dict[str, int] = {}
    per_call: Dict[str, Dict[str, int]] = {}
    maximum_per_call = 0
    for key, counts in plan["calls_by_seat_and_output_limit"].items():
        seat_total = 0
        per_call[key] = {}
        for limit_text, call_count in counts.items():
            limit = int(limit_text)
            bound = normal.conservative_turn_cost_bound_v1(
                policy=build_seat_policy_v1(key, limit),
                max_input_tokens=DECLARED_MAX_INPUT_TOKENS_V1,
            )
            per_call[key][limit_text] = bound
            seat_total += call_count * bound
            maximum_per_call = max(maximum_per_call, bound)
        seat_totals[key] = seat_total
    total = sum(seat_totals.values())
    return {
        "maximum_calls": plan["maximum_calls"],
        "seat_total_picodollars": seat_totals,
        "per_call_picodollars": per_call,
        "total_picodollars": total,
        "maximum_per_call_picodollars": maximum_per_call,
        "prior_observed_picodollars": Q2D_PRIOR_OBSERVED_SPEND_PICODOLLARS_V1,
        "required_cumulative_picodollars": (
            Q2D_PRIOR_OBSERVED_SPEND_PICODOLLARS_V1 + total
        ),
    }


_Q2D_BUILDER_SCOPE_REGISTRY_V1: weakref.WeakSet[object] = weakref.WeakSet()
_Q2D_BUILDER_SCOPE_REGISTRY_LOCK_V1 = Lock()


class _Q2DAuthorizedBuilderScopeV1:
    """Opaque scope issued only by the Q2d council factory."""

    __slots__ = ("__weakref__",)

    def __new__(cls) -> "_Q2DAuthorizedBuilderScopeV1":
        raise TypeError("Q2d builder scopes can only be issued by the live factory")


def _issue_and_bind_q2d_builder_scope_v1(
    capability: AuthorizedProtocolAttemptCapabilityV1,
) -> _Q2DAuthorizedBuilderScopeV1:
    """Issue, register, and bind one protocol-specific live builder scope."""

    scope = object.__new__(_Q2DAuthorizedBuilderScopeV1)
    with _Q2D_BUILDER_SCOPE_REGISTRY_LOCK_V1:
        _Q2D_BUILDER_SCOPE_REGISTRY_V1.add(scope)
    try:
        bind_authorized_protocol_attempt_v1(
            capability=capability,
            builder=scope,
        )
    except Exception:
        with _Q2D_BUILDER_SCOPE_REGISTRY_LOCK_V1:
            _Q2D_BUILDER_SCOPE_REGISTRY_V1.discard(scope)
        raise
    return scope


def _assert_registered_q2d_builder_scope_v1(scope: object) -> None:
    """Reject generic or externally reconstructed builder authority."""

    if type(scope) is not _Q2DAuthorizedBuilderScopeV1:
        raise ContractValidationError("Q2d builder scope provenance is invalid")
    with _Q2D_BUILDER_SCOPE_REGISTRY_LOCK_V1:
        registered = scope in _Q2D_BUILDER_SCOPE_REGISTRY_V1
    if not registered:
        raise ContractValidationError("Q2d builder scope was not issued by the factory")


class _Q2DRegistryReadinessViewV1:
    """Immutable readiness-only projection; never exposes live adapters."""

    __slots__ = ("__ready", "__warning")

    def __init__(self, ready: bool, warning: Optional[str]) -> None:
        self.__ready = bool(ready)
        self.__warning = warning

    def assess_readiness(self) -> Tuple[bool, Optional[str]]:
        return self.__ready, self.__warning


class _Q2DOneShotRunStateV1:
    """Shared consumption state so even a shallow wrapper copy cannot replay."""

    __slots__ = ("lock", "started")

    def __init__(self) -> None:
        self.lock = Lock()
        self.started = False

    def consume(self) -> None:
        with self.lock:
            if self.started:
                raise ContractValidationError(
                    "Q2d authorized dialogue already started"
                )
            self.started = True


class Q2DAuthorizedCouncilV1:
    """One-shot facade over the authorized Q2d orchestrator.

    The raw CED and mutable adapters never cross the builder boundary. Starting
    the dialogue consumes this facade before the delegate can return or raise,
    so a failed first trajectory cannot be replayed through the same authority.
    """

    __slots__ = (
        "__adapters",
        "__ced",
        "__question_name",
        "__registry_view",
        "__run_state",
    )

    def __init__(
        self,
        adapters: Tuple[SocratesLiveOpenRouterAdapter, ...],
        ced: Any,
        *,
        question_name: str = "q2",
    ) -> None:
        if len(adapters) != Q2D_LOGICAL_AGENTS_V1:
            raise ContractValidationError("Q2d authorized council seat count drifted")
        if getattr(ced, "registry", None) is None:
            raise ContractValidationError("Q2d authorized council registry is absent")
        ready, warning = ced.registry.assess_readiness()
        self.__adapters = adapters
        self.__ced = ced
        self.__registry_view = _Q2DRegistryReadinessViewV1(ready, warning)
        self.__run_state = _Q2DOneShotRunStateV1()
        self.__question_name = question_name

    @property
    def registry(self) -> _Q2DRegistryReadinessViewV1:
        """The registry readiness surface required before the sole run."""

        return self.__registry_view

    async def run_registry_session(self, question: str, *, session_id: str) -> Any:
        """Start the exact authorized dialogue once, consuming before delegate."""

        expected_question, _question_sha = _question_v1(self.__question_name)
        if session_id != Q2D_SESSION_ID_V1 or question != expected_question:
            raise ContractValidationError(
                "Q2d authorized council run identity drifted"
            )
        self.__run_state.consume()
        return await self.__ced.run_registry_session(
            question, session_id=session_id
        )

    def observability_rows(self) -> Tuple[Dict[str, Any], ...]:
        """Return detached terminal-accounting rows from the three live seats."""

        return tuple(
            dict(row)
            for adapter in self.__adapters
            for row in adapter.observability_rows()
        )


def _build_heterogeneous_council_core_v1(
    ledger: OpenRouterSessionLedgerV1,
    *,
    claim_directory: Path,
    dispatch: Optional[Callable[..., Any]] = None,
    protocol_path: Path,
    protocol_receipt: AuthorizedProtocolReceiptV1,
    expected_protocol_payload: Dict[str, Any],
    attempt_capability: AuthorizedProtocolAttemptCapabilityV1,
) -> Q2DAuthorizedCouncilV1:
    """Private construction seam used by the fixed live factory and offline tests."""

    if (
        len(q1.COUNCIL_SEATS_V1) != Q2D_LOGICAL_AGENTS_V1
        or len({key for _alias, key in q1.COUNCIL_SEATS_V1})
        != Q2D_LOGICAL_AGENTS_V1
    ):
        raise ContractValidationError(
            "Q2d live topology requires one distinct model seat per logical agent"
        )
    fresh_expected = build_q2d_protocol_payload_v1(
        expected_protocol_payload.get("question_name", "q2"),
        expected_protocol_payload.get("mid_round_objection_rulings", True),
    )
    if fresh_expected != expected_protocol_payload:
        raise ContractValidationError(
            "Q2d implementation or local execution boundary drifted before construction"
        )
    fresh_receipt = assert_exact_authorized_protocol_v1(
        protocol_path=protocol_path,
        authorized_sha256=protocol_receipt.authorized_sha256,
        expected_schema_version=Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=expected_protocol_payload,
    )
    if fresh_receipt.as_record() != protocol_receipt.as_record():
        raise ContractValidationError("Q2d builder protocol receipt drifted")
    builder_scope = _issue_and_bind_q2d_builder_scope_v1(attempt_capability)
    assert_authorized_protocol_attempt_consumed_v1(
        capability=attempt_capability,
        receipt=protocol_receipt,
        attempt_directory=_q2d_frozen_attempt_directory_v1(),
        session_id=Q2D_SESSION_ID_V1,
        expected_builder=builder_scope,
    )

    projector = normal.make_worker_payload_projector_v1()
    adapters: list[SocratesLiveOpenRouterAdapter] = []
    for index, (alias, key) in enumerate(q1.COUNCIL_SEATS_V1):
        spec = q1.FAMILIES_V1[key]
        profile: OpenRouterEndpointCapabilityProfileV1 = q1.load_profile_v1(key)
        family = build_seat_policy_family_v1(key)
        adapters.append(
            SocratesLiveOpenRouterAdapter(
                provider_id=normal.WORKER_PROVIDER_IDS_V1[index],
                policy=family[normal.SYNTHESIS_OUTPUT_TOKENS_V1],
                profile=profile,
                ledger=ledger,
                claim_directory=claim_directory,
                max_input_tokens=DECLARED_MAX_INPUT_TOKENS_V1,
                dispatch=dispatch,
                response_format_factory=normal.ced_structured_response_format_v1,
                structured_output_validator=normal.validate_ced_structured_output_v1,
                task_execution_policy_factory=seat_policy_for_task_factory_v1(
                    key, family
                ),
                outbound_task_state_projector=projector,
                pre_dispatch_guard=_seat_predispatch_guard_v1(
                    key,
                    protocol_path=protocol_path,
                    protocol_receipt=protocol_receipt,
                    expected_protocol_payload=expected_protocol_payload,
                    attempt_capability=attempt_capability,
                    builder_scope=builder_scope,
                ),
                worker_alias=alias,
                expose_model_identity_to_worker=False,
                expected_returned_models=(spec["model"],),
                expected_provider_display_names=spec["provider_display"],
                ced_parse_repair_attempts=0,
            )
        )
    registry = normal.CouncilProviderRegistry(provider_timeout_seconds=125.0)
    for adapter in adapters:
        registry.register(adapter)
    fake = normal.FakeProvider()
    agents = [
        normal.SocraticAgent(f"agent_{index}", fake)
        for index in range(Q2D_LOGICAL_AGENTS_V1)
    ]
    ced = normal.CEDOrchestrator(
        agents,
        fake,
        registry=registry,
        shadow_scoring_mode=normal.ShadowScoringMode.ALL_PHASES,
        phase_retry=True,
        max_socratic_followups=2,
        ratification_repair="block",
        tree_expansions=0,
        ai_learning=False,
    )
    if len(adapters) != len(agents) or len(
        {adapter.provider_id for adapter in adapters}
    ) != len(adapters):
        raise ContractValidationError(
            "Q2d live topology does not provide unique physical quorum identities"
        )
    ced.mid_round_objection_rulings_v1 = bool(
        expected_protocol_payload.get("mid_round_objection_rulings", True)
    )
    return Q2DAuthorizedCouncilV1(
        tuple(adapters),
        ced,
        question_name=expected_protocol_payload.get("question_name", "q2"),
    )


def build_heterogeneous_council_v1(
    ledger: OpenRouterSessionLedgerV1,
    *,
    protocol_path: Path,
    protocol_receipt: AuthorizedProtocolReceiptV1,
    expected_protocol_payload: Dict[str, Any],
    attempt_capability: AuthorizedProtocolAttemptCapabilityV1,
) -> Q2DAuthorizedCouncilV1:
    """Build the production council with frozen claim and dispatch boundaries."""

    _assert_q2d_live_host_v1()
    evidence_directory = (
        Q2D_RUN_DIRECTORY_V1 / Q2D_DISPATCH_EVIDENCE_DIRECTORY_NAME_V1
    )
    if not evidence_directory.is_dir():
        raise ContractValidationError(
            "Q2d frozen dispatch-evidence directory is not acquired"
        )
    return _build_heterogeneous_council_core_v1(
        ledger,
        claim_directory=_q2d_production_claim_store_v1(),
        dispatch=error_retaining_dispatch_v1(
            evidence_directory,
            normal.dispatch_openrouter_one_live_inference_v1,
        ),
        protocol_path=protocol_path,
        protocol_receipt=protocol_receipt,
        expected_protocol_payload=expected_protocol_payload,
        attempt_capability=attempt_capability,
    )


def classify_q2c_failure_v1(
    turn: Dict[str, Any], finish_evidence: Dict[str, Any]
) -> str:
    """Classify the two Q2c rejections from retained, non-inferred evidence."""

    usage = finish_evidence.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    completion_details = usage.get("completion_tokens_details")
    completion_details = (
        completion_details if isinstance(completion_details, dict) else {}
    )
    if (
        turn.get("model") == "openai/gpt-5-mini"
        and turn.get("task_kind") == TaskKind.ELENCHUS_OBJECTION.value
        and turn.get("completion_tokens") == normal.SHORT_OUTPUT_TOKENS_V1
        and usage.get("completion_tokens") == normal.SHORT_OUTPUT_TOKENS_V1
        and finish_evidence.get("finish_reason") == "length"
        and completion_details.get("reasoning_tokens") == 3_264
        and turn.get("ced_rejection_reason") == "json parse failed"
    ):
        return "completion_envelope_exhausted_before_valid_visible_payload"
    if (
        turn.get("model") == "google/gemini-3.7-flash"
        and turn.get("task_kind") == TaskKind.SOCRATIC_QUESTION.value
        and finish_evidence.get("finish_reason") == "stop"
        and turn.get("provider_structured_output_valid") is False
        and turn.get("ced_rejection_reason")
        == "schema validation failed: epistemic_marker is required"
    ):
        return "provider_structured_output_contract_violation"
    return "unclassified_retained_failure"


_SAFE_FINISH_REASONS_V1 = frozenset(
    {"stop", "length", "content_filter", "tool_calls", "error"}
)
_SAFE_NATIVE_FINISH_REASONS_V1 = frozenset(
    {
        "STOP",
        "MAX_TOKENS",
        "SAFETY",
        "RECITATION",
        "OTHER",
        "stop",
        "length",
        "max_output_tokens",
        "error",
    }
)
_SAFE_STRING_PROVIDER_ERROR_CODES_V1 = frozenset(
    {
        "engine_overloaded",
        "provider_error",
        "rate_limit_exceeded",
        "upstream_error",
    }
)
_SAFE_TRANSPORT_FAILURE_CLASSES_V1 = frozenset(
    {
        "ConnectionError",
        "ConnectionResetError",
        "HTTPException",
        "OSError",
        "RemoteDisconnected",
        "SSLError",
        "TimeoutError",
    }
)


def _safe_finish_value_v1(value: Any, allowed: frozenset[str]) -> Optional[str]:
    if value is None:
        return None
    if type(value) is str and value in allowed:
        return value
    return "unrecognized"


def _safe_provider_error_code_v1(value: Any) -> Any:
    if type(value) is int and value >= 0:
        return value
    if type(value) is str and value in _SAFE_STRING_PROVIDER_ERROR_CODES_V1:
        return value
    return "unrecognized" if value is not None else None


def assert_q2d_dispatch_evidence_contract_v1(receipt: Dict[str, Any]) -> None:
    """Validate both field names and every provider-controlled value domain."""

    required = {
        "body_length",
        "body_sha256",
        "finish_reason",
        "model_requested",
        "native_finish_reason",
        "provider_error_class",
        "provider_error_code",
        "response_body_length",
        "response_body_sha256",
        "schema_version",
        "transport_failure_class",
        "usage",
    }
    if type(receipt) is not dict or set(receipt) != required:
        raise ContractValidationError("Q2d dispatch evidence field set drifted")
    if receipt.get("schema_version") != "socrates-q2d-dispatch-evidence/v1":
        raise ContractValidationError("Q2d dispatch evidence schema drifted")
    for field in ("body_sha256", "response_body_sha256"):
        value = receipt.get(field)
        if (
            type(value) is not str
            or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)
        ):
            raise ContractValidationError(f"Q2d evidence {field} is not SHA-256")
    for field in ("body_length", "response_body_length"):
        if type(receipt.get(field)) is not int or receipt[field] < 0:
            raise ContractValidationError(f"Q2d evidence {field} is invalid")
    allowed_models = {
        q1.FAMILIES_V1[key]["model"] for _alias, key in q1.COUNCIL_SEATS_V1
    } | {"unrecognized_model"}
    if receipt.get("model_requested") not in allowed_models:
        raise ContractValidationError("Q2d evidence model value is unsafe")
    finish = receipt.get("finish_reason")
    if not (
        finish is None
        or (type(finish) is str and finish in _SAFE_FINISH_REASONS_V1)
        or finish == "unrecognized"
    ):
        raise ContractValidationError("Q2d evidence finish reason is unsafe")
    native_finish = receipt.get("native_finish_reason")
    if not (
        native_finish is None
        or (
            type(native_finish) is str
            and native_finish in _SAFE_NATIVE_FINISH_REASONS_V1
        )
        or native_finish == "unrecognized"
    ):
        raise ContractValidationError("Q2d evidence native finish reason is unsafe")
    if receipt.get("provider_error_class") not in (
        None,
        "provider_error_envelope",
    ):
        raise ContractValidationError("Q2d evidence provider error class is unsafe")
    code = receipt.get("provider_error_code")
    if not (
        code is None
        or (type(code) is int and code >= 0)
        or (
            type(code) is str
            and (
                code in _SAFE_STRING_PROVIDER_ERROR_CODES_V1
                or code == "unrecognized"
            )
        )
    ):
        raise ContractValidationError("Q2d evidence provider error code is unsafe")
    transport = receipt.get("transport_failure_class")
    if not (
        transport is None
        or (
            type(transport) is str
            and (
                transport in _SAFE_TRANSPORT_FAILURE_CLASSES_V1
                or transport == "unrecognized"
            )
        )
    ):
        raise ContractValidationError("Q2d evidence transport class is unsafe")
    usage = receipt.get("usage")
    if type(usage) is not dict or not set(usage).issubset(
        {"completion_tokens", "prompt_tokens", "reasoning_tokens", "total_tokens"}
    ):
        raise ContractValidationError("Q2d evidence usage shape is unsafe")
    if any(type(value) is not int or value < 0 for value in usage.values()):
        raise ContractValidationError("Q2d evidence usage value is unsafe")


def privacy_safe_dispatch_evidence_v1(
    directory: Path, inner: Callable[..., Any]
) -> Callable[..., Any]:
    """Retain only allowlisted metadata for bytes that crossed the wire.

    Historical raw artifacts are left untouched.  Q2d creates one canonical
    sidecar keyed by the request-body digest; neither request nor response text,
    headers, credentials, provider messages, or cost-detail subtrees are ever
    persisted.
    """

    def numeric(value: Any) -> Optional[int]:
        return value if type(value) is int and value >= 0 else None

    def dispatch(**kwargs: Any) -> Any:
        result = inner(**kwargs)
        body = kwargs.get("body_bytes")
        raw = getattr(result, "raw_response_body", None)
        if not isinstance(body, (bytes, bytearray)) or not isinstance(
            raw, (bytes, bytearray)
        ):
            return result
        body_bytes = bytes(body)
        response_bytes = bytes(raw)
        try:
            request = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            request = {}
        try:
            payload = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            payload = {}

        choices = payload.get("choices") if isinstance(payload, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else {}
        usage_raw = payload.get("usage") if isinstance(payload, dict) else None
        usage_raw = usage_raw if isinstance(usage_raw, dict) else {}
        completion_details = usage_raw.get("completion_tokens_details")
        completion_details = (
            completion_details if isinstance(completion_details, dict) else {}
        )
        usage = {
            "completion_tokens": numeric(usage_raw.get("completion_tokens")),
            "prompt_tokens": numeric(usage_raw.get("prompt_tokens")),
            "reasoning_tokens": numeric(completion_details.get("reasoning_tokens")),
            "total_tokens": numeric(usage_raw.get("total_tokens")),
        }
        usage = {key: value for key, value in usage.items() if value is not None}

        error = payload.get("error") if isinstance(payload, dict) else None
        error = error if isinstance(error, dict) else None
        provider_error_code = _safe_provider_error_code_v1(
            error.get("code") if error else None
        )
        completion = getattr(result, "completion", None)
        transport_failure = getattr(completion, "failure_class", None)
        transport_failure = (
            transport_failure
            if type(transport_failure) is str
            and transport_failure in _SAFE_TRANSPORT_FAILURE_CLASSES_V1
            else ("unrecognized" if transport_failure is not None else None)
        )

        requested_model = request.get("model") if isinstance(request, dict) else None
        allowed_models = {
            q1.FAMILIES_V1[key]["model"] for _alias, key in q1.COUNCIL_SEATS_V1
        }
        if requested_model not in allowed_models:
            requested_model = "unrecognized_model"

        body_sha256 = hashlib.sha256(body_bytes).hexdigest()
        receipt = {
            "schema_version": "socrates-q2d-dispatch-evidence/v1",
            "body_sha256": body_sha256,
            "body_length": len(body_bytes),
            "response_body_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "response_body_length": len(response_bytes),
            "model_requested": requested_model,
            "finish_reason": _safe_finish_value_v1(
                first.get("finish_reason") if isinstance(first, dict) else None,
                _SAFE_FINISH_REASONS_V1,
            ),
            "native_finish_reason": _safe_finish_value_v1(
                first.get("native_finish_reason")
                if isinstance(first, dict)
                else None,
                _SAFE_NATIVE_FINISH_REASONS_V1,
            ),
            "provider_error_class": (
                "provider_error_envelope" if error is not None else None
            ),
            "provider_error_code": provider_error_code,
            "transport_failure_class": transport_failure,
            "usage": usage,
        }
        assert_q2d_dispatch_evidence_contract_v1(receipt)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"dispatch_{body_sha256}.json"
        _write_exclusive_fsynced_bytes_v1(
            target, canonical_json(receipt).encode("utf-8")
        )
        return result

    return dispatch


def error_retaining_dispatch_v1(
    directory: Path, inner: Callable[..., Any]
) -> Callable[..., Any]:
    """Compatibility name for the privacy-safe Q2d evidence observer."""

    return privacy_safe_dispatch_evidence_v1(directory, inner)


def _public_audit_v1(audit: Any) -> Optional[Dict[str, Any]]:
    """Keep the CED audit fields that explain a non-proceeding outcome."""

    if not isinstance(audit, dict):
        return None
    keys = (
        "execution_mode",
        "proceeded",
        "quorum_failed",
        "blocked_phase",
        "warning",
        "provider_status_summary",
        "registry_phase_rounds",
        "task_log_count",
    )
    return {k: audit[k] for k in keys if k in audit}


def _question_v1(name: str) -> Tuple[str, str]:
    """Resolve any registered question through its pinned bundle.

    Adding a question is adding a bundle file, not editing this function. The
    bundle re-derives the question, rubric and evaluator-key digests from the
    module and refuses on drift, so the guarantee the old hard-coded constants
    gave is unchanged.
    """

    from scripts.question_bundles_v1 import (
        load_bundle_v1,
        load_question_module_v1,
    )

    bundle = load_bundle_v1(name)
    module = load_question_module_v1(name)
    return module.QUESTION_V1, bundle["question_sha256"]


def _legacy_question_v1(name: str) -> Tuple[str, str]:
    """Return (text, sha256) for the named question, checked before use.

    Q1 is the saturated logic question: all four families answered it correctly,
    so it cannot measure whether a council adds anything. Q2 is the ethics
    argument, which did spread them. Q2's evaluator key machine-checks its own
    countermodel, and a council is not worth buying if that check fails.
    """

    if name == "q1":
        return q1.QUESTION_V1, q1.QUESTION_SHA256_V1
    if name == "q5":
        # Q5 is Q4 with the symmetric profiles removed from the domain, which
        # inverts the verdict. The council proposed the restriction itself, and
        # the weight sits on two facts about the solution space - no satisfying
        # rule is monotone, and the least any of them departs from higher-total
        # is two profiles - because a verdict is guessable and the symmetry
        # proof is by now recalled rather than derived.
        import scripts.q5_ethics_question_v1 as q5

        if not q5.verify_key_v1()["key_is_sound"]:
            raise ContractValidationError("Q5 evaluator key failed its own check")
        return q5.QUESTION_V1, q5.QUESTION_SHA256_V1
    if name == "q4":
        # Q4 states a *true* impossibility and then draws an unjustified remedy
        # from it. Q3 was saturated - seven of nine baselines cleared 30/32 - so
        # Q4 is built with two dependent steps, the first of which punishes the
        # refutation reflex that Q2 and Q3 both rewarded.
        import scripts.q4_ethics_question_v1 as q4

        if not q4.verify_key_v1()["key_is_sound"]:
            raise ContractValidationError("Q4 evaluator key failed its own check")
        return q4.QUESTION_V1, q4.QUESTION_SHA256_V1
    if name == "q3":
        # Q3 is a *valid* moral argument that is nonetheless unsound, chosen
        # because Q2's oracle union beat its best single answer by only two
        # points — less than the sampling noise measured across fifteen draws.
        import scripts.q3_ethics_question_v1 as q3

        if not q3.verify_key_v1()["key_is_sound"]:
            raise ContractValidationError("Q3 evaluator key failed its own check")
        return q3.QUESTION_V1, q3.QUESTION_SHA256_V1
    if name != "q2":
        raise ContractValidationError(f"unknown question {name!r}")
    import scripts.q2_ethics_question_v1 as q2

    if not q2.verify_key_v1()["key_is_sound"]:
        raise ContractValidationError("Q2 evaluator key failed its own check")
    return q2.QUESTION_V1, q2.QUESTION_SHA256_V1


def _sha256_file_v1(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractValidationError(f"required Q2d file is unavailable: {path}") from exc


def build_q2d_protocol_payload_v1(
    question_name: str = "q2", mid_round_rulings: bool = True,
) -> Dict[str, Any]:
    """Reconstruct the complete authorization payload from local evidence.

    ``question_name`` selects the pinned question bundle. It defaults to "q2" so
    every existing caller and every retained artifact keeps its exact meaning;
    a different question yields a different payload, hence a different digest,
    hence its own operator approval — which is the point.
    """

    repository_root = Path(__file__).resolve().parents[1]
    q2b_path = q1.RUNS / "q2b_frozen_protocol_v1.json"
    try:
        q2b = json.loads(q2b_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractValidationError("Q2b frozen controls are unavailable") from exc
    frozen_controls = {
        "question_sha256": q2b.get("question_sha256"),
        "rubric_sha256": q2b.get("rubric_sha256"),
        "evaluator_key_sha256": q2b.get("evaluator_key_sha256"),
        "baseline_response_schema_sha256": q2b.get(
            "baseline_response_schema_sha256"
        ),
        "baseline_system_prompt_sha256": q2b.get("baseline_system_prompt_sha256"),
        "seat_profiles_sha256": q2b.get("seat_profiles_sha256"),
    }
    # The three question-specific digests now come from the pinned bundle, so a
    # second experimental question needs a bundle file rather than an edit here.
    from scripts.question_bundles_v1 import load_bundle_v1

    bundle = load_bundle_v1(question_name)
    if question_name != "q2":
        # A non-default question replaces exactly the three controls that are
        # question-specific. Seats, baseline schema and system prompt are shared
        # across questions and stay bound to the retained freeze.
        frozen_controls["question_sha256"] = bundle["question_sha256"]
        frozen_controls["rubric_sha256"] = bundle["rubric_sha256"]
        frozen_controls["evaluator_key_sha256"] = bundle["evaluator_key_sha256"]
    expected_frozen = {
        "question_sha256": bundle["question_sha256"] if question_name != "q2" else (
            "1b20ffe116ab1f78e9cd63fc5722c5b0383d71492e311977d19d6cc7f375f8ad"
        ),
        "rubric_sha256": bundle["rubric_sha256"] if question_name != "q2" else (
            "7f17f31b93c9d84e2a7b0d75e9364d5b97e85674e587a4094311af55fd9ef053"
        ),
        "evaluator_key_sha256": bundle["evaluator_key_sha256"]
        if question_name != "q2"
        else (
            "876a8e6d4c4fe6f8d3b5ec6601ed5a4072bc97ba0777d885268f36cedd0d3f04"
        ),
        "baseline_response_schema_sha256": (
            "f2c010d02342dc0caacbaa86a67da45cb30bbd748e6e1e9860e19e23adeed8dd"
        ),
        "baseline_system_prompt_sha256": (
            "71f162a22cb409bd82fb184ef2da16ba27ac89a0bc458b5ffbbf569b31e09372"
        ),
        "seat_profiles_sha256": (
            "ea99dc22ab428551effb58e6fa28b8f623b80676a89c4be38986a56b108bc079"
        ),
    }
    import scripts.q2_ethics_question_v1 as q2

    if not q2.verify_key_v1()["key_is_sound"]:
        raise ContractValidationError("Q2d evaluator key failed its machine check")
    rubric_payload = {
        "criteria": [
            {"name": name, "requirement": requirement, "points": points}
            for name, requirement, points in q2.CRITERIA_V1
        ],
        "maximum": q2.MAXIMUM_SCORE_V1,
        "error_flags": list(q2.ERROR_FLAGS_V1),
    }
    evaluator_key_payload = {
        "valid": q2.VALID_V1,
        "first_invalid_step": q2.FIRST_INVALID_STEP_V1,
        "diagnosis": q2.DIAGNOSIS_V1,
        "countermodel": q2.COUNTERMODEL_V1,
        "fallacy_fallacy": q2.FALLACY_FALLACY_V1,
    }
    recomputed_frozen = {
        "question_sha256": hashlib.sha256(
            q2.QUESTION_V1.encode("utf-8")
        ).hexdigest(),
        "rubric_sha256": hashlib.sha256(
            canonical_json(rubric_payload).encode("utf-8")
        ).hexdigest(),
        "evaluator_key_sha256": hashlib.sha256(
            canonical_json(evaluator_key_payload).encode("utf-8")
        ).hexdigest(),
        "baseline_response_schema_sha256": hashlib.sha256(
            canonical_json(q1.reduced.baseline_response_format_v1()).encode("utf-8")
        ).hexdigest(),
        "baseline_system_prompt_sha256": hashlib.sha256(
            q1.BASELINE_SYSTEM_PROMPT_V1.encode("utf-8")
        ).hexdigest(),
    }

    seat_profiles: Dict[str, Dict[str, Any]] = {}
    seat_profile_digest_payload: Dict[str, Dict[str, Any]] = {}
    retained_seats = q2b.get("seat_profiles")
    retained_seats = retained_seats if isinstance(retained_seats, dict) else {}
    # The retained Q2b evidence describes the default three seats. An alternative
    # seat set has no history to compare against, so its profile is taken from the
    # live endpoint configuration and the digest recomputed. Nothing checkable is
    # weakened: the post-authorization drift guards rebuild this payload and
    # compare, so an endpoint profile moving between approval and dispatch is
    # still caught. What is lost is the tie to historical evidence, which does
    # not exist for these seats.
    default_seats = q1.COUNCIL_SEAT_SET_NAME_V1 == "default"
    for alias, key in q1.COUNCIL_SEATS_V1:
        spec = q1.FAMILIES_V1[key]
        retained = retained_seats.get(alias)
        if default_seats and not isinstance(retained, dict):
            raise ContractValidationError(f"Q2d retained seat {alias} is absent")
        current_profile = q1.load_profile_v1(key)
        exact = {
            "family": key,
            "model": spec["model"],
            "selector": spec["selector"],
            "output_field": spec["output_field"],
            "profile_id": current_profile.profile_id,
            "evidence_sha256": current_profile.evidence_sha256,
        }
        for field in (
            "evidence_sha256",
            "model",
            "selector",
            "output_field",
            "profile_id",
        ):
            if default_seats and exact[field] != (retained or {}).get(field):
                raise ContractValidationError(
                    f"Q2d retained seat {alias} {field} drifted"
                )
        seat_profiles[alias] = exact
        seat_profile_digest_payload[alias] = {
            field: exact[field]
            for field in (
                "evidence_sha256",
                "model",
                "output_field",
                "profile_id",
                "selector",
            )
        }

    recomputed_frozen["seat_profiles_sha256"] = hashlib.sha256(
        canonical_json(seat_profile_digest_payload).encode("utf-8")
    ).hexdigest()
    if question_name != "q2":
        # A non-default question is frozen by its pinned bundle. load_bundle_v1
        # has already re-derived all three digests from the question module and
        # refused on drift, so recomputing them here in a second, subtly
        # different payload shape would test nothing and disagree by
        # construction. The shared controls below stay recomputed as before.
        for field in ("question_sha256", "rubric_sha256", "evaluator_key_sha256"):
            recomputed_frozen[field] = bundle[field]
    if not default_seats:
        # The seat set names itself in the payload, so a run under one seat set
        # cannot be mistaken for a run under another, and each gets its own
        # digest and its own one-shot authorization.
        frozen_controls["seat_profiles_sha256"] = recomputed_frozen[
            "seat_profiles_sha256"
        ]
        expected_frozen["seat_profiles_sha256"] = recomputed_frozen[
            "seat_profiles_sha256"
        ]
    if frozen_controls != expected_frozen or recomputed_frozen != expected_frozen:
        raise ContractValidationError("Q2d frozen control digests drifted")

    implementation_sha256 = {
        name: _sha256_file_v1(repository_root / name)
        for name in _q2d_implementation_files_v1(repository_root)
    }
    evidence_paths = {
        "q2b_protocol": q2b_path,
        "q2b_council_trajectory": q1.RUNS / "q2b_ethics_council_v1.json",
        "q2b_matched_baselines": q1.RUNS / "q2b_matched_baselines_v1.json",
        "q2b_scored_baselines": q1.RUNS / "q2b_scored_baselines_v1.json",
        "q2c_protocol_v1": q1.RUNS / "q2c_frozen_protocol_v1.json",
        "q2c_protocol_v2": q1.RUNS / "q2c_frozen_protocol_v2.json",
        "q2c_result": q1.RUNS / "q2c_ethics_council_v1.json",
        "q2c_finish_reasons": (
            q1.RUNS / "q1_condition_c_provider_errors" / "finish_reasons.jsonl"
        ),
        "attribution_correction_ledger": (
            q1.RUNS / "attribution_correction_ledger_v1.json"
        ),
        "protocol_nonconformance_ledger": (
            q1.RUNS / "protocol_nonconformance_ledger_v1.json"
        ),
    }
    evidence_sha256 = {
        name: _sha256_file_v1(path) for name, path in evidence_paths.items()
    }
    plan = derive_q2d_call_plan_v1(mid_round_rulings)
    bound = conservative_q2d_bound_v1(mid_round_rulings)
    return {
        "schema_version": Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        # The payload names its own question so the post-authorization drift
        # guards can rebuild exactly this payload without a threaded parameter.
        "question_name": question_name,
        # Names the arm, so the two conditions cannot be compared by accident and
        # each carries its own authorization.
        "mid_round_objection_rulings": mid_round_rulings,
        "kind": "Q2 topology-corrected heterogeneous CED reliability run",
        "execution_status": "offline_preflight_budget_authorization_required",
        "scientific_classification": (
            "new_protocol_exploratory_reliability_run_not_confirmatory_replication"
        ),
        "session_id": Q2D_SESSION_ID_V1,
        "attempt_latch": {
            "directory": str(_q2d_frozen_attempt_directory_v1()),
            "path_flavor": "windows_declared_absolute_path",
            "directory_control": "runner_owned_no_public_override",
            "consumption": "write_once_before_live_construction",
            "required_process_dispatch_class": "live_inference_post",
            "required_initial_process_dispatch_count": 0,
            "filesystem_trust_model": {
                "label": OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1,
                "threats_included": list(
                    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1
                ),
                "threats_excluded": list(
                    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1
                ),
            },
        },
        "local_execution_boundary": {
            "claim_store_declared": str(CLAIM_STORE),
            "claim_store_path_flavor": "windows_declared_absolute_path",
            "live_dispatch": "fixed_privacy_safe_openrouter_dispatch_v1",
            "local_code_threat_model": Q2D_TRUST_MODEL_V1,
            "claim_store_trust_model": {
                "label": OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1,
                "threats_included": list(
                    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1
                ),
                "threats_excluded": list(
                    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1
                ),
            },
        },
        "run_artifacts": {
            "run_directory": Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1,
            "result_artifact": (
                f"{Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1}/"
                f"{Q2D_RESULT_ARTIFACT_NAME_V1}"
            ),
            "dispatch_evidence_directory": (
                f"{Q2D_RUN_DIRECTORY_REPOSITORY_RELATIVE_V1}/"
                f"{Q2D_DISPATCH_EVIDENCE_DIRECTORY_NAME_V1}"
            ),
            "directory_acquisition": "atomic_mkdir_exist_ok_false",
            "file_creation": "exclusive_xb_flush_fsync_no_overwrite",
        },
        "question": question_name,
        "council_seat_set": q1.COUNCIL_SEAT_SET_NAME_V1,
        "runtime_environment": _q2d_runtime_environment_v1(),
        "reachable_response_schema_sha256": (
            _q2d_reachable_response_schema_sha256_v1()
        ),
        "frozen_controls": frozen_controls,
        "seat_profiles": seat_profiles,
        "prompt_token_estimator_id": "wire_utf8_byte_upper_bound_v1",
        "experiment_prompt_budget_tokens": EXPERIMENT_PROMPT_BUDGET_TOKENS_V1,
        "maximum_ced_calls": plan["maximum_calls"],
        "call_plan": plan,
        "topology_repair": {
            "q2b_q2c_logical_agents": 4,
            "q2b_q2c_physical_models": 3,
            "q2d_logical_agents": Q2D_LOGICAL_AGENTS_V1,
            "q2d_physical_models": len(q1.COUNCIL_SEATS_V1),
            "mapping": "one_logical_agent_per_physical_model",
            "reason": "unique_provider_quorum_and_one_to_one_authoring_identity",
        },
        "cost_bound": bound,
        "required_cumulative_spend_picodollars": bound[
            "required_cumulative_picodollars"
        ],
        "prior_operator_ceiling_picodollars": 5_000_000_000_000,
        "operator_approval_required": True,
        "retries": "same_seat_prohibited",
        "phase_rescue": "one_reroute_to_a_distinct_seat_per_failed_slot_recorded",
        "substitution": "prohibited",
        "failure_repairs": {
            "gemini_socratic_question": "no_change_provider_contract_violation",
            "gpt_5_mini_elenchus_objection": "output_limit_4096_to_8192",
        },
        "privacy_evidence": {
            "schema_version": "socrates-q2d-dispatch-evidence/v1",
            "raw_http_request_body_persisted": False,
            "raw_http_response_body_persisted": False,
            "sanitized_visible_assistant_output_persisted_in_main_artifact": True,
            "keyed_by": "body_sha256",
        },
        "implementation_sha256": implementation_sha256,
        "implementation_hash_closure": {
            "backend": "all_backend/dialogues_recursive_python_files",
            "scripts": list(Q2D_RUNTIME_SCRIPT_FILES_V1),
            "repository_controls": list(
                Q2D_RUNTIME_REPOSITORY_CONTROL_FILES_V1
            ),
            "ordering": "sorted_repository_relative_posix_paths",
        },
        "retained_evidence_sha256": evidence_sha256,
        "q2c_status": "incomplete_protocol_nonconformant_no_final_score",
        "live_calls_before_new_approval": 0,
    }


def run_condition_c_v1(
    question_name: str = "q2",
    *,
    protocol_path: Optional[Path] = None,
    authorized_protocol_sha256: Optional[str] = None,
    mid_round_rulings: bool = True,
) -> Dict[str, Any]:
    """Execute one exactly authorized Q2d dialogue and persist its record."""

    if question_name not in ("q2", "q3", "q4", "q5"):
        raise ContractValidationError(
            "authorization permits only the frozen Q2 or Q3 question"
        )
    if protocol_path is None or authorized_protocol_sha256 is None:
        raise ContractValidationError(
            "live Q2d execution requires an exact protocol path and approved digest"
        )

    # This is the first acquisition boundary.  It must run before a ledger,
    # claim, credential read, adapter, or dispatch exists.
    expected_protocol = build_q2d_protocol_payload_v1(
        question_name, mid_round_rulings
    )
    protocol_receipt = assert_exact_authorized_protocol_v1(
        protocol_path=protocol_path,
        authorized_sha256=authorized_protocol_sha256,
        expected_schema_version=Q2D_PROTOCOL_SCHEMA_VERSION_V1,
        expected_payload=expected_protocol,
    )
    _assert_fresh_q2d_process_dispatch_latch_v1()
    _assert_q2d_live_host_v1()
    run_directory = _create_q2d_run_directory_v1()
    out = run_directory / Q2D_RESULT_ARTIFACT_NAME_V1
    question_text, question_sha = _question_v1(question_name)
    call_plan = derive_q2d_call_plan_v1(mid_round_rulings)
    plan = conservative_q2d_bound_v1()
    print(f"=== council bound, question {question_name} ===")
    for key, value in plan["seat_total_picodollars"].items():
        print(f"  seat {q1.FAMILIES_V1[key]['label']:18s} ${q1._usd(value)} total")
    print(
        f"  {plan['maximum_calls']} calls total          "
        f"${q1._usd(plan['total_picodollars'])}"
    )

    session_id = Q2D_SESSION_ID_V1
    alpha_key = q1.COUNCIL_SEATS_V1[0][1]
    authorization = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Operator-authorized Q2d: one topology-corrected heterogeneous "
            "Socrates/CED reliability dialogue "
            "with GPT-5 Mini, Gemini 3.7 Flash, and GPT-4.1 Mini. Exact "
            f"protocol SHA-256 {protocol_receipt.authorized_sha256}. No baseline, "
            "no same-seat retry, no fallback, no substitution. A failed slot may "
            "be rerouted once to a distinct seat, and every attempt is recorded."
        ),
        policy_id=build_seat_policy_v1(
            alpha_key, normal.SYNTHESIS_OUTPUT_TOKENS_V1
        ).policy_id or "",
        profile_id=q1.load_profile_v1(alpha_key).profile_id or "",
        model="multi-model",
        provider_selector="multi-endpoint",
        maximum_calls=plan["maximum_calls"],
        maximum_total_spend_picodollars=plan["total_picodollars"],
        maximum_per_call_spend_picodollars=plan["maximum_per_call_picodollars"],
        session_id=session_id,
    )
    ledger = OpenRouterSessionLedgerV1(authorization)
    attempt_capability = consume_authorized_protocol_attempt_v1(
        receipt=protocol_receipt,
        attempt_directory=_q2d_frozen_attempt_directory_v1(),
        session_id=session_id,
    )
    council = build_heterogeneous_council_v1(
        ledger,
        protocol_path=protocol_path,
        protocol_receipt=protocol_receipt,
        expected_protocol_payload=expected_protocol,
        attempt_capability=attempt_capability,
    )
    ready, warning = council.registry.assess_readiness()
    if not ready:
        raise ContractValidationError(f"heterogeneous CED registry is not ready: {warning}")

    print(
        f"\n=== running {len(q1.COUNCIL_SEATS_V1)}-seat "
        "heterogeneous council ==="
    )
    for alias, key in q1.COUNCIL_SEATS_V1:
        print(f"  {alias}: {q1.FAMILIES_V1[key]['label']} ({q1.FAMILIES_V1[key]['selector']})")
    protocol_attempt = attempt_capability.as_record()
    started = time.perf_counter()
    error: Optional[str] = None
    final: Any = None
    try:
        final = asyncio.run(
            council.run_registry_session(question_text, session_id=session_id)
        )
    except Exception as exc:  # retain one bounded run failure; never retry
        error = safe_public_exception_code_v1(exc, context="orchestration")
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    turns = list(council.observability_rows())
    if error is not None:
        status = "STOPPED_WITH_ERROR"
    elif ledger.fatal_failure is not None:
        status = "STOPPED_FATAL"
    else:
        status = "ORCHESTRATION_RETURNED"
    record = {
        "schema_version": "socrates-q2d-heterogeneous-ced/v1",
        "condition": "Q2d_topology_corrected_heterogeneous_reliability_ced",
        "scientific_classification": (
            "new_protocol_exploratory_reliability_run_not_confirmatory_replication"
        ),
        "session_id": session_id,
        "question": question_name,
        "question_sha256": question_sha,
        "run_status": status,
        "error": error,
        "latency_ms": latency_ms,
        "council_seats": [
            {
                "alias": alias,
                "family": key,
                "model": q1.FAMILIES_V1[key]["model"],
                "provider_selector": q1.FAMILIES_V1[key]["selector"],
            }
            for alias, key in q1.COUNCIL_SEATS_V1
        ],
        "protocol_authorization": protocol_receipt.as_record(),
        "protocol_attempt": protocol_attempt,
        "session_authorization": authorization.model_dump(mode="json"),
        "call_plan": call_plan,
        "conservative_bound_usd": q1._usd(plan["total_picodollars"]),
        "calls_consumed": ledger.calls_consumed,
        "observed_cost_picodollars": ledger.observed_picodollars,
        "observed_cost_usd": q1._usd(ledger.observed_picodollars),
        "ledger_fatal_failure": ledger.fatal_failure,
        "outcome": normal._ced_outcome_summary_v1(final),
        # `_ced_outcome_summary_v1` reports *that* quorum failed, never why.
        # `_registry_fallback_final` puts the phase it blocked at, the warning
        # and the per-phase provider verdicts in `audit_summary`, and without
        # them a fully accepted trajectory that still fails quorum is
        # uninterpretable.
        "audit_summary": _public_audit_v1(getattr(final, "audit_summary", None)),
        "blocking_objections": [
            sanitize_public_assistant_output_v1(str(o))[:500]
            for o in (getattr(final, "blocking_objections", None) or [])
        ],
        "turns": turns,
    }
    _write_exclusive_fsynced_bytes_v1(
        out, canonical_json(record).encode("utf-8")
    )
    print(f"\n  status: {status}")
    if error:
        print(f"  error: {error}")
    print(f"  calls: {ledger.calls_consumed} | observed: ${q1._usd(ledger.observed_picodollars)}")
    print(f"  written: {out}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Q2d exactly-authorized heterogeneous CED")
    parser.add_argument(
        "--question",
        choices=("q2", "q3", "q4", "q5"),
        default="q2",
        help="Q2d authorizes only the frozen ethics question",
    )
    parser.add_argument(
        "--protocol-manifest",
        type=Path,
        default=q1.RUNS / "q2d_frozen_protocol_v1.json",
        help="canonical Q2d manifest whose exact digest was operator-approved",
    )
    parser.add_argument(
        "--execute-authorized-protocol-sha256",
        help="exact lowercase SHA-256 copied from the operator's approval",
    )
    parser.add_argument(
        "--mid-round-rulings",
        choices=("on", "off"),
        default="on",
        help=(
            "rule on each round's objections while the dialogue can still read "
            "them; 'off' is the control arm on identical code"
        ),
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="print the conservative bound and the rendered seat wire shapes only",
    )
    args = parser.parse_args()
    if args.plan_only:
        plan = conservative_q2d_bound_v1(args.mid_round_rulings == "on")
        for key, value in plan["seat_total_picodollars"].items():
            print(f"  seat {q1.FAMILIES_V1[key]['label']:18s} ${q1._usd(value)} total")
        print(
            f"  {plan['maximum_calls']} calls total          "
            f"${q1._usd(plan['total_picodollars'])}"
        )
        print(
            "  required cumulative                  "
            f"${q1._usd(plan['required_cumulative_picodollars'])}"
        )
        return 0
    if args.execute_authorized_protocol_sha256 is None:
        parser.error(
            "--execute-authorized-protocol-sha256 is required for live execution"
        )
    run_condition_c_v1(
        question_name=args.question,
        mid_round_rulings=(args.mid_round_rulings == "on"),
        protocol_path=args.protocol_manifest,
        authorized_protocol_sha256=args.execute_authorized_protocol_sha256,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
