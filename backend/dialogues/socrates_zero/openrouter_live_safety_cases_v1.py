"""Frozen offline cases for OpenRouter live-safety closure v1.

This module is deliberately declarative and import-inert.  It names every
positive, adversarial, cross-request and metamorphic obligation predeclared in
Sections 35--40 of the S7A protocol without performing I/O or evaluating the
runtime contracts.  The evaluator owns probe dispatch; this module owns the
immutable inputs, expectations and content identities.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id


OPENROUTER_LIVE_SAFETY_CASE_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-case/v1"
)
OPENROUTER_LIVE_SAFETY_CASE_SET_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-case-set/v1"
)
OPENROUTER_LIVE_SAFETY_THRESHOLDS_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-thresholds/v1"
)


class _FrozenLiveSafetyCaseContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterLiveSafetyCaseFamilyV1(str, Enum):
    P17 = "P17"
    P19 = "P19"
    AUTHORIZATION = "AUTHORIZATION"
    METAMORPHIC = "METAMORPHIC"


class OpenRouterLiveSafetyCaseKindV1(str, Enum):
    POSITIVE = "POSITIVE"
    ADVERSARIAL = "ADVERSARIAL"


class OpenRouterLiveSafetyExpectedOutcomeV1(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class OpenRouterLiveSafetyHazardV1(str, Enum):
    """Forbidden acceptances measured independently of expectation matching."""

    HEURISTIC_P17_AUTHORITY = "HEURISTIC_P17_AUTHORITY"
    BYTE_TO_TOKEN_SUBSTITUTION = "BYTE_TO_TOKEN_SUBSTITUTION"
    INCOMPLETE_CHARGE_COVERAGE = "INCOMPLETE_CHARGE_COVERAGE"
    REQUEST_FEE_OMISSION_TO_ZERO = "REQUEST_FEE_OMISSION_TO_ZERO"
    HIDDEN_MONETARY_TERM = "HIDDEN_MONETARY_TERM"
    CROSS_REQUEST_SUBSTITUTION = "CROSS_REQUEST_SUBSTITUTION"
    AUTHORIZATION_REUSE = "AUTHORIZATION_REUSE"
    CONSUMPTION_ROLLBACK = "CONSUMPTION_ROLLBACK"
    CREDENTIAL_LEAKAGE = "CREDENTIAL_LEAKAGE"
    TEST_FIXTURE_PROMOTION = "TEST_FIXTURE_PROMOTION"


class OpenRouterLiveSafetyCaseV1(_FrozenLiveSafetyCaseContractV1):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_CASE_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_CASE_SCHEMA_V1
    case_id: str = Field(min_length=1)
    family: OpenRouterLiveSafetyCaseFamilyV1
    kind: OpenRouterLiveSafetyCaseKindV1
    description: str = Field(min_length=1)
    probe: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    expected_outcome: OpenRouterLiveSafetyExpectedOutcomeV1
    expected_failure_code: Optional[str] = None
    requirement_tags: Tuple[str, ...]
    hazards: Tuple[OpenRouterLiveSafetyHazardV1, ...] = ()
    case_fingerprint: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveSafetyCaseV1":
        positive = self.kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE
        accepted = (
            self.expected_outcome
            is OpenRouterLiveSafetyExpectedOutcomeV1.ACCEPTED
        )
        if positive != accepted:
            raise ContractValidationError(
                "live-safety case kind disagrees with expected outcome"
            )
        if accepted != (self.expected_failure_code is None):
            raise ContractValidationError(
                "live-safety expected outcome disagrees with failure code"
            )
        if not self.requirement_tags:
            raise ContractValidationError("a live-safety case must cover a requirement")
        if len(set(self.requirement_tags)) != len(self.requirement_tags):
            raise ContractValidationError("live-safety requirement tags must be unique")
        if tuple(sorted(self.requirement_tags)) != self.requirement_tags:
            raise ContractValidationError("live-safety requirement tags must be sorted")
        if any(not tag.startswith("S") or "." not in tag for tag in self.requirement_tags):
            raise ContractValidationError("invalid live-safety requirement tag")
        if len(set(self.hazards)) != len(self.hazards):
            raise ContractValidationError("live-safety hazards must be unique")
        if tuple(sorted(self.hazards, key=lambda value: value.value)) != self.hazards:
            raise ContractValidationError("live-safety hazards must be sorted")
        expected = stable_contract_id(
            "szorlivesafetycasev1",
            {
                "case_id": self.case_id,
                "family": self.family.value,
                "kind": self.kind.value,
                "description": self.description,
                "probe": self.probe,
                "expected_outcome": self.expected_outcome.value,
                "expected_failure_code": self.expected_failure_code,
                "requirement_tags": self.requirement_tags,
                "hazards": tuple(value.value for value in self.hazards),
            },
        )
        if self.case_fingerprint not in (None, expected):
            raise ContractValidationError("live-safety case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


class OpenRouterLiveSafetyCaseSetV1(_FrozenLiveSafetyCaseContractV1):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_CASE_SET_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_CASE_SET_SCHEMA_V1
    family: Optional[OpenRouterLiveSafetyCaseFamilyV1] = None
    cases: Tuple[OpenRouterLiveSafetyCaseV1, ...]
    case_set_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveSafetyCaseSetV1":
        ids = tuple(case.case_id for case in self.cases)
        if not ids:
            raise ContractValidationError("live-safety case set cannot be empty")
        if len(set(ids)) != len(ids):
            raise ContractValidationError("live-safety case IDs must be unique")
        if ids != tuple(sorted(ids)):
            raise ContractValidationError("live-safety cases must be in stable order")
        if self.family is not None and any(
            case.family is not self.family for case in self.cases
        ):
            raise ContractValidationError("case-set family disagrees with a case")
        expected = stable_contract_id(
            "szorlivesafetycasesetv1",
            {
                "family": self.family.value if self.family is not None else "ALL",
                "case_fingerprints": tuple(
                    case.case_fingerprint for case in self.cases
                ),
            },
        )
        if self.case_set_id not in (None, expected):
            raise ContractValidationError("live-safety case-set ID mismatch")
        object.__setattr__(self, "case_set_id", expected)
        return self


def _case(
    case_id: str,
    family: OpenRouterLiveSafetyCaseFamilyV1,
    kind: OpenRouterLiveSafetyCaseKindV1,
    description: str,
    probe: str,
    tags: Tuple[str, ...],
    failure: Optional[str] = None,
    hazards: Tuple[OpenRouterLiveSafetyHazardV1, ...] = (),
) -> OpenRouterLiveSafetyCaseV1:
    return OpenRouterLiveSafetyCaseV1(
        case_id=case_id,
        family=family,
        kind=kind,
        description=description,
        probe=probe,
        expected_outcome=(
            OpenRouterLiveSafetyExpectedOutcomeV1.ACCEPTED
            if kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE
            else OpenRouterLiveSafetyExpectedOutcomeV1.REJECTED
        ),
        expected_failure_code=failure,
        requirement_tags=tuple(sorted(tags)),
        hazards=tuple(sorted(hazards, key=lambda value: value.value)),
    )


_P = OpenRouterLiveSafetyCaseKindV1.POSITIVE
_X = OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL
_P17 = OpenRouterLiveSafetyCaseFamilyV1.P17
_P19 = OpenRouterLiveSafetyCaseFamilyV1.P19
_AUTH = OpenRouterLiveSafetyCaseFamilyV1.AUTHORIZATION
_META = OpenRouterLiveSafetyCaseFamilyV1.METAMORPHIC
_H = OpenRouterLiveSafetyHazardV1


FROZEN_OPENROUTER_P17_CASES_V1: Tuple[OpenRouterLiveSafetyCaseV1, ...] = tuple(
    sorted(
        (
            _case("orp17v1-p01-valid-trusted-limit-proof", _P17, _P, "A trusted exact-model limit proves a conservative input bound.", "P17_VALID_TRUSTED_LIMIT", ("S35.1",)),
            _case("orp17v1-p02-valid-jit-limit-record", _P17, _P, "A structurally fresh exact-model JIT record is sufficient.", "P17_VALID_JIT_RECORD", ("S35.2",)),
            _case("orp17v1-x01-byte-length-as-token-bound", _P17, _X, "Request byte length is not token authority.", "P17_BYTE_LENGTH", ("S36.1",), "P17_METHOD_NOT_AUTHORITATIVE", (_H.BYTE_TO_TOKEN_SUBSTITUTION,)),
            _case("orp17v1-x02-character-count-as-token-bound", _P17, _X, "Character count is not token authority.", "P17_CHARACTER_COUNT", ("S36.2",), "P17_METHOD_NOT_AUTHORITATIVE", (_H.HEURISTIC_P17_AUTHORITY,)),
            _case("orp17v1-x03-chars-per-token-heuristic", _P17, _X, "A chars/token estimate is not token authority.", "P17_CHARS_PER_TOKEN", ("S36.3",), "P17_METHOD_NOT_AUTHORITATIVE", (_H.HEURISTIC_P17_AUTHORITY,)),
            _case("orp17v1-x04-tokenizer-family-as-exact", _P17, _X, "A tokenizer family label is not an exact tokenizer.", "P17_TOKENIZER_FAMILY", ("S36.4",), "P17_TOKENIZER_BINDING_INCOMPLETE", (_H.HEURISTIC_P17_AUTHORITY,)),
            _case("orp17v1-x05-tokenizer-version-absent", _P17, _X, "Tokenizer implementation version is absent.", "P17_TOKENIZER_VERSION_ABSENT", ("S36.5",), "P17_TOKENIZER_BINDING_INCOMPLETE"),
            _case("orp17v1-x06-tokenizer-data-identity-absent", _P17, _X, "Tokenizer data/vocabulary identity is absent.", "P17_TOKENIZER_DATA_ABSENT", ("S36.6",), "P17_TOKENIZER_BINDING_INCOMPLETE"),
            _case("orp17v1-x07-model-tokenizer-authority-absent", _P17, _X, "The model-to-tokenizer authority is absent.", "P17_MODEL_TOKENIZER_AUTHORITY_ABSENT", ("S36.7",), "P17_TOKENIZER_BINDING_INCOMPLETE"),
            _case("orp17v1-x08-chat-framing-unbounded", _P17, _X, "Chat/message framing is not bounded.", "P17_CHAT_FRAMING_UNBOUNDED", ("S36.8",), "P17_FRAMING_NOT_BOUNDED"),
            _case("orp17v1-x09-wrong-model", _P17, _X, "The limit record names another model.", "P17_WRONG_MODEL", ("S36.9",), "P17_MODEL_MISMATCH"),
            _case("orp17v1-x10-sibling-request", _P17, _X, "The limit record is bound to a sibling request.", "P17_SIBLING_REQUEST", ("S36.10",), "P17_REQUEST_MISMATCH"),
            _case("orp17v1-x11-malformed-limit", _P17, _X, "A malformed token limit is refused.", "P17_MALFORMED_LIMIT", ("S36.11",), "P17_LIMIT_INVALID"),
            _case("orp17v1-x12-negative-limit", _P17, _X, "A negative token limit is refused.", "P17_NEGATIVE_LIMIT", ("S36.11",), "P17_LIMIT_INVALID"),
            _case("orp17v1-x13-zero-limit", _P17, _X, "A zero token limit is invalid for this request.", "P17_ZERO_LIMIT", ("S36.12",), "P17_LIMIT_INVALID"),
            _case("orp17v1-x14-ambiguous-limit-kind", _P17, _X, "An ambiguous semantic limit class is refused.", "P17_AMBIGUOUS_LIMIT_KIND", ("S36.13",), "P17_LIMIT_KIND_AMBIGUOUS"),
            _case("orp17v1-x15-untrusted-source", _P17, _X, "An untrusted source cannot establish the bound.", "P17_UNTRUSTED_SOURCE", ("S36.14",), "P17_SOURCE_UNTRUSTED"),
            _case("orp17v1-x16-source-digest-mismatch", _P17, _X, "A source digest mismatch invalidates the record.", "P17_SOURCE_DIGEST_MISMATCH", ("S36.15",), "P17_SOURCE_DIGEST_MISMATCH"),
            _case("orp17v1-x17-stale-jit-record", _P17, _X, "A stale JIT record is refused when freshness is required.", "P17_STALE_JIT_RECORD", ("S36.16",), "P17_NOT_JIT_FRESH"),
            _case("orp17v1-x18-output-bound-as-input", _P17, _X, "The output bound cannot stand for the input bound.", "P17_OUTPUT_BOUND_SUBSTITUTION", ("S36.17",), "P17_METHOD_NOT_AUTHORITATIVE", (_H.HEURISTIC_P17_AUTHORITY,)),
        ),
        key=lambda case: case.case_id,
    )
)


FROZEN_OPENROUTER_P19_CASES_V1: Tuple[OpenRouterLiveSafetyCaseV1, ...] = tuple(
    sorted(
        (
            _case("orp19v1-p01-complete-price-policy", _P19, _P, "Prompt, completion and request ceilings are complete.", "P19_COMPLETE_PRICE_POLICY", ("S35.3",)),
            _case("orp19v1-p02-explicit-zero-request-fee", _P19, _P, "An explicit request_usd of zero is a real bound.", "P19_EXPLICIT_ZERO_REQUEST_FEE", ("S35.4",)),
            _case("orp19v1-p03-positive-request-fee-once", _P19, _P, "A positive request fee is added exactly once.", "P19_POSITIVE_REQUEST_FEE_ONCE", ("S35.5",)),
            _case("orp19v1-p04-text-only-non-applicability", _P19, _P, "Exact text-only bytes prove image/audio non-applicability.", "P19_TEXT_ONLY_MODALITY", ("S35.6",)),
            _case("orp19v1-p05-complete-cost-bound", _P19, _P, "All applicable classes yield a complete exact cost bound.", "P19_COMPLETE_COST_BOUND", ("S35.7",)),
            _case("orp19v1-p06-cost-equals-total-ceiling", _P19, _P, "Equality at the operator total-spend ceiling passes.", "P19_COST_EQUALS_TOTAL_CEILING", ("S35.8", "S37.15")),
            _case("orp19v1-x01-request-fee-absent", _P19, _X, "An omitted request fee leaves coverage incomplete.", "P19_REQUEST_FEE_ABSENT", ("S37.1",), "PRICE_POLICY_INCOMPLETE", (_H.INCOMPLETE_CHARGE_COVERAGE, _H.REQUEST_FEE_OMISSION_TO_ZERO)),
            _case("orp19v1-x02-request-fee-none", _P19, _X, "Explicit None is not an authoritative zero.", "P19_REQUEST_FEE_NONE", ("S37.2",), "PRICE_POLICY_INCOMPLETE", (_H.INCOMPLETE_CHARGE_COVERAGE, _H.REQUEST_FEE_OMISSION_TO_ZERO)),
            _case("orp19v1-x03-request-fee-malformed", _P19, _X, "A malformed request fee is refused.", "P19_REQUEST_FEE_MALFORMED", ("S37.3",), "PRICE_COMPONENT_INVALID"),
            _case("orp19v1-x04-request-fee-negative", _P19, _X, "A negative request fee is refused.", "P19_REQUEST_FEE_NEGATIVE", ("S37.4",), "PRICE_COMPONENT_INVALID"),
            _case("orp19v1-x05-request-fee-float", _P19, _X, "Binary-float request-fee authority is refused.", "P19_REQUEST_FEE_FLOAT", ("S37.5",), "PRICE_COMPONENT_INVALID"),
            _case("orp19v1-x06-prompt-ceiling-absent", _P19, _X, "The prompt ceiling is mandatory.", "P19_PROMPT_CEILING_ABSENT", ("S37.6",), "PRICE_POLICY_INCOMPLETE", (_H.INCOMPLETE_CHARGE_COVERAGE,)),
            _case("orp19v1-x07-completion-ceiling-absent", _P19, _X, "The completion ceiling is mandatory.", "P19_COMPLETION_CEILING_ABSENT", ("S37.7",), "PRICE_POLICY_INCOMPLETE", (_H.INCOMPLETE_CHARGE_COVERAGE,)),
            _case("orp19v1-x08-applicable-charge-unbounded", _P19, _X, "No applicable charge class may remain unbounded.", "P19_APPLICABLE_CHARGE_UNBOUNDED", ("S37.8",), "PRICE_POLICY_INCOMPLETE", (_H.INCOMPLETE_CHARGE_COVERAGE,)),
            _case("orp19v1-x09-media-false-non-applicability", _P19, _X, "A media request cannot inherit text-only non-applicability.", "P19_MEDIA_FALSE_NON_APPLICABILITY", ("S37.9",), "MODALITY_PROOF_MISMATCH", (_H.INCOMPLETE_CHARGE_COVERAGE,)),
            _case("orp19v1-x10-arithmetic-overflow", _P19, _X, "Cost arithmetic overflow is refused.", "P19_ARITHMETIC_OVERFLOW", ("S37.10",), "COST_ARITHMETIC_INVALID"),
            _case("orp19v1-x11-price-policy-id-mismatch", _P19, _X, "A mutated price-policy identity is refused.", "P19_PRICE_POLICY_ID_MISMATCH", ("S37.11",), "PRICE_POLICY_MISMATCH"),
            _case("orp19v1-x12-sibling-overlay-substitution", _P19, _X, "A sibling live overlay cannot stand for this request.", "P19_SIBLING_OVERLAY", ("S37.12",), "REQUEST_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
            _case("orp19v1-x13-without-p17", _P19, _X, "P19 cannot be authoritative without P17.", "P19_WITHOUT_P17", ("S37.13",), "P17_NOT_ESTABLISHED"),
            _case("orp19v1-x14-without-total-spend-ceiling", _P19, _X, "A cost bound cannot authorize without a total-spend ceiling.", "P19_WITHOUT_TOTAL_SPEND", ("S37.14",), "TOTAL_SPEND_CEILING_MISSING"),
            _case("orp19v1-x15-one-picodollar-over-total", _P19, _X, "One picodollar over the total ceiling fails.", "P19_ONE_PICODOLLAR_OVER", ("S37.16",), "COST_EXCEEDS_TOTAL_SPEND_CEILING"),
            _case("orp19v1-x16-hidden-term-omitted-from-formula", _P19, _X, "Arithmetic cannot contain a term omitted from the formula.", "P19_HIDDEN_TERM_FORMULA", ("S37.17",), "FORMULA_COMPONENT_MISMATCH", (_H.HIDDEN_MONETARY_TERM,)),
            _case("orp19v1-x17-formula-term-omitted-from-arithmetic", _P19, _X, "The rendered formula cannot contain an unsummed term.", "P19_HIDDEN_TERM_ARITHMETIC", ("S37.18",), "FORMULA_COMPONENT_MISMATCH", (_H.HIDDEN_MONETARY_TERM,)),
            _case("orp19v1-x18-test-fixture-promoted", _P19, _X, "A test monetary fixture cannot become production authority.", "P19_TEST_FIXTURE_PROMOTION", ("S37.19",), "TEST_FIXTURE_NOT_AUTHORIZED", (_H.TEST_FIXTURE_PROMOTION,)),
        ),
        key=lambda case: case.case_id,
    )
)


FROZEN_OPENROUTER_AUTHORIZATION_CASES_V1: Tuple[OpenRouterLiveSafetyCaseV1, ...] = tuple(
    sorted(
        (
            _case("orauthv1-p01-fresh-authorization", _AUTH, _P, "A fresh exact authorization is usable.", "AUTH_FRESH", ("S35.9",)),
            _case("orauthv1-p02-first-consumption", _AUTH, _P, "The first consumption succeeds exactly once.", "AUTH_FIRST_CONSUMPTION", ("S35.10",)),
            _case("orauthv1-p03-synthetic-jit-preflight", _AUTH, _P, "A complete synthetic JIT preflight authorizes one call.", "AUTH_SYNTHETIC_PREFLIGHT", ("S35.11",)),
            _case("orauthv1-x01-reused", _AUTH, _X, "A consumed authorization cannot be reused.", "AUTH_REUSED", ("S38.1",), "AUTHORIZATION_ALREADY_CONSUMED", (_H.AUTHORIZATION_REUSE,)),
            _case("orauthv1-x02-request-a-applied-to-b", _AUTH, _X, "Authorization A cannot authorize request B.", "AUTH_WRONG_REQUEST", ("S38.2",), "AUTHORIZATION_REQUEST_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
            _case("orauthv1-x03-stale-p17", _AUTH, _X, "Authorization cannot bind stale P17 evidence.", "AUTH_STALE_P17", ("S38.3",), "AUTHORIZATION_P17_MISMATCH"),
            _case("orauthv1-x04-wrong-price-policy", _AUTH, _X, "Authorization cannot bind another price policy.", "AUTH_WRONG_PRICE_POLICY", ("S38.4",), "AUTHORIZATION_PRICE_POLICY_MISMATCH"),
            _case("orauthv1-x05-wrong-total-spend", _AUTH, _X, "Authorization cannot bind another total-spend ceiling.", "AUTH_WRONG_TOTAL_SPEND", ("S38.5",), "AUTHORIZATION_TOTAL_SPEND_MISMATCH"),
            _case("orauthv1-x06-dispatch-cap-greater-than-one", _AUTH, _X, "An authorization dispatch cap greater than one is invalid.", "AUTH_DISPATCH_CAP_GT_ONE", ("S38.6",), "AUTHORIZATION_DISPATCH_CAP_INVALID"),
            _case("orauthv1-x07-ced-enabled", _AUTH, _X, "CED authority must remain disabled.", "AUTH_CED_ENABLED", ("S38.7",), "CED_AUTHORITY_ENABLED"),
            _case("orauthv1-x08-s5-mapper-absent", _AUTH, _X, "The S5 mapper identity is mandatory.", "AUTH_S5_MAPPER_ABSENT", ("S38.8",), "S5_MAPPER_UNAVAILABLE"),
            _case("orauthv1-x09-s6-integration-absent", _AUTH, _X, "The S6 integration identity is mandatory.", "AUTH_S6_INTEGRATION_ABSENT", ("S38.9",), "S6_INTEGRATION_UNAVAILABLE"),
            _case("orauthv1-x10-credential-value-embedded", _AUTH, _X, "Credential values may not enter authorization.", "AUTH_CREDENTIAL_VALUE", ("S38.10",), "CREDENTIAL_VALUE_FORBIDDEN", (_H.CREDENTIAL_LEAKAGE,)),
            _case("orauthv1-x11-id-mutation", _AUTH, _X, "Authorization identity mutation is refused.", "AUTH_ID_MUTATION", ("S38.11",), "AUTHORIZATION_ID_MISMATCH"),
            _case("orauthv1-x12-consumption-rollback", _AUTH, _X, "Under the attested trusted non-rollback store contract, consumption cannot be mutated back to freshness or reused while its claim persists; physical store realization is an S7B JIT fact.", "AUTH_CONSUMPTION_ROLLBACK", ("S38.12",), "CONSUMPTION_ROLLBACK", (_H.AUTHORIZATION_REUSE, _H.CONSUMPTION_ROLLBACK)),
            _case("orcrossv1-x01-a-p17-with-b-request", _AUTH, _X, "P17 A plus request B fails.", "CROSS_P17_A_REQUEST_B", ("S39.1",), "AUTHORIZATION_REQUEST_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
            _case("orcrossv1-x02-a-price-with-b-request", _AUTH, _X, "Price policy A plus request B fails.", "CROSS_PRICE_A_REQUEST_B", ("S39.2",), "AUTHORIZATION_PRICE_POLICY_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
            _case("orcrossv1-x03-a-cost-with-b-authorization", _AUTH, _X, "Cost bound A plus authorization B fails.", "CROSS_COST_A_AUTH_B", ("S39.3",), "AUTHORIZATION_COST_BOUND_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
            _case("orcrossv1-x04-a-authorization-with-b-transport", _AUTH, _X, "Authorization A plus transport B fails.", "CROSS_AUTH_A_TRANSPORT_B", ("S39.4",), "AUTHORIZATION_TRANSPORT_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
            _case("orcrossv1-x05-a-consumption-with-b-request", _AUTH, _X, "Consumption A plus request B fails.", "CROSS_CONSUMPTION_A_REQUEST_B", ("S39.5",), "AUTHORIZATION_REQUEST_MISMATCH", (_H.CROSS_REQUEST_SUBSTITUTION,)),
        ),
        key=lambda case: case.case_id,
    )
)


FROZEN_OPENROUTER_METAMORPHIC_CASES_V1: Tuple[OpenRouterLiveSafetyCaseV1, ...] = tuple(
    sorted(
        (
            _case("ormetav1-p01-deterministic-evaluator-rebuild", _META, _P, "The frozen semantic evaluation rebuild is deterministic.", "META_DETERMINISTIC_REBUILD", ("S35.12",)),
            _case("ormetav1-p02-same-inputs-same-ids", _META, _P, "Equal semantic safety inputs produce equal IDs.", "META_SAME_INPUTS_SAME_IDS", ("S40.1",)),
            _case("ormetav1-p03-equivalent-price-text", _META, _P, "Canonical-equivalent decimal text yields equal monetary authority.", "META_EQUIVALENT_PRICE_TEXT", ("S40.2",)),
            _case("ormetav1-p04-one-picodollar-changes-policy", _META, _P, "One picodollar changes the relevant policy identity.", "META_ONE_PICODOLLAR_POLICY", ("S40.3",)),
            _case("ormetav1-p05-request-byte-change-invalidates", _META, _P, "A request-byte change invalidates old P17 and authorization.", "META_REQUEST_BYTES_INVALIDATE", ("S40.4",)),
            _case("ormetav1-p06-request-component-changes-identity", _META, _P, "Adding max_price.request changes request identity.", "META_REQUEST_COMPONENT_IDENTITY", ("S40.5",)),
            _case("ormetav1-p07-none-to-zero-changes-policy", _META, _P, "None to explicit zero changes policy identity and coverage.", "META_NONE_TO_ZERO", ("S40.6",)),
            _case("ormetav1-p08-model-change-invalidates-p17", _META, _P, "Changing the exact model invalidates P17 evidence.", "META_MODEL_INVALIDATES_P17", ("S40.7",)),
            _case("ormetav1-p09-consumption-not-fresh-replay", _META, _P, "Consumption cannot replay as a fresh authorization.", "META_CONSUMPTION_NOT_FRESH", ("S40.8",)),
        ),
        key=lambda case: case.case_id,
    )
)


FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1: Tuple[OpenRouterLiveSafetyCaseV1, ...] = tuple(
    sorted(
        FROZEN_OPENROUTER_P17_CASES_V1
        + FROZEN_OPENROUTER_P19_CASES_V1
        + FROZEN_OPENROUTER_AUTHORIZATION_CASES_V1
        + FROZEN_OPENROUTER_METAMORPHIC_CASES_V1,
        key=lambda case: case.case_id,
    )
)

FROZEN_OPENROUTER_P17_CASE_SET_V1 = OpenRouterLiveSafetyCaseSetV1(
    family=_P17, cases=FROZEN_OPENROUTER_P17_CASES_V1
)
FROZEN_OPENROUTER_P19_CASE_SET_V1 = OpenRouterLiveSafetyCaseSetV1(
    family=_P19, cases=FROZEN_OPENROUTER_P19_CASES_V1
)
FROZEN_OPENROUTER_AUTHORIZATION_CASE_SET_V1 = OpenRouterLiveSafetyCaseSetV1(
    family=_AUTH, cases=FROZEN_OPENROUTER_AUTHORIZATION_CASES_V1
)
FROZEN_OPENROUTER_METAMORPHIC_CASE_SET_V1 = OpenRouterLiveSafetyCaseSetV1(
    family=_META, cases=FROZEN_OPENROUTER_METAMORPHIC_CASES_V1
)
FROZEN_OPENROUTER_LIVE_SAFETY_CASE_SET_V1 = OpenRouterLiveSafetyCaseSetV1(
    cases=FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
)

OPENROUTER_P17_CASE_SET_ID_V1 = FROZEN_OPENROUTER_P17_CASE_SET_V1.case_set_id
OPENROUTER_P19_CASE_SET_ID_V1 = FROZEN_OPENROUTER_P19_CASE_SET_V1.case_set_id
OPENROUTER_AUTHORIZATION_CASE_SET_ID_V1 = (
    FROZEN_OPENROUTER_AUTHORIZATION_CASE_SET_V1.case_set_id
)
OPENROUTER_METAMORPHIC_CASE_SET_ID_V1 = (
    FROZEN_OPENROUTER_METAMORPHIC_CASE_SET_V1.case_set_id
)
OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1 = (
    FROZEN_OPENROUTER_LIVE_SAFETY_CASE_SET_V1.case_set_id
)


FROZEN_OPENROUTER_LIVE_SAFETY_REQUIREMENT_TAGS_V1: Tuple[str, ...] = tuple(
    sorted(
        tuple(f"S35.{index}" for index in range(1, 13))
        + tuple(f"S36.{index}" for index in range(1, 18))
        + tuple(f"S37.{index}" for index in range(1, 20))
        + tuple(f"S38.{index}" for index in range(1, 13))
        + tuple(f"S39.{index}" for index in range(1, 6))
        + tuple(f"S40.{index}" for index in range(1, 9))
    )
)


class OpenRouterLiveSafetyThresholdsV1(_FrozenLiveSafetyCaseContractV1):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_THRESHOLDS_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_THRESHOLDS_SCHEMA_V1
    required_total_cases: Literal[73] = 73
    required_positive_accepted: Literal[20] = 20
    required_adversarial_rejected: Literal[53] = 53
    required_p17_cases: Literal[20] = 20
    required_p17_positive_accepted: Literal[2] = 2
    required_p17_adversarial_rejected: Literal[18] = 18
    required_p19_cases: Literal[24] = 24
    required_p19_positive_accepted: Literal[6] = 6
    required_p19_adversarial_rejected: Literal[18] = 18
    required_authorization_cases: Literal[20] = 20
    required_authorization_positive_accepted: Literal[3] = 3
    required_authorization_adversarial_rejected: Literal[17] = 17
    required_metamorphic_cases: Literal[9] = 9
    required_metamorphic_holding: Literal[9] = 9
    required_requirement_tags_covered: Literal[73] = 73
    required_unexpected_results: Literal[0] = 0
    required_invalid_fixture_constructions: Literal[0] = 0
    required_guard_code_mismatches: Literal[0] = 0
    maximum_heuristic_p17_authority_accepted: Literal[0] = 0
    maximum_byte_to_token_substitutions_accepted: Literal[0] = 0
    maximum_incomplete_charge_coverage_accepted: Literal[0] = 0
    maximum_request_fee_omission_to_zero: Literal[0] = 0
    maximum_hidden_monetary_terms: Literal[0] = 0
    maximum_cross_request_substitutions_accepted: Literal[0] = 0
    maximum_authorization_reuse_accepted: Literal[0] = 0
    maximum_consumption_rollback_accepted: Literal[0] = 0
    maximum_credential_leakage_findings: Literal[0] = 0
    maximum_test_fixture_promotions: Literal[0] = 0
    maximum_external_activity: Literal[0] = 0
    required_s6_predecessor_surfaces_unchanged: Literal[8] = 8
    thresholds_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveSafetyThresholdsV1":
        expected = stable_contract_id(
            "szorlivesafetythresholdsv1",
            self.model_dump(mode="json", exclude={"thresholds_id"}),
        )
        if self.thresholds_id not in (None, expected):
            raise ContractValidationError("live-safety thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1 = OpenRouterLiveSafetyThresholdsV1()
OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1 = (
    FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1.thresholds_id
)


def _validate_frozen_inventory_v1() -> None:
    cases = FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
    expected_tags = set(FROZEN_OPENROUTER_LIVE_SAFETY_REQUIREMENT_TAGS_V1)
    actual_tags = {tag for case in cases for tag in case.requirement_tags}
    if len(cases) != 73:
        raise ContractValidationError("live-safety frozen case count changed")
    if actual_tags != expected_tags:
        raise ContractValidationError("live-safety numbered requirement coverage changed")
    if sum(case.kind is _P for case in cases) != 20:
        raise ContractValidationError("live-safety positive case count changed")
    if sum(case.kind is _X for case in cases) != 53:
        raise ContractValidationError("live-safety adversarial case count changed")


_validate_frozen_inventory_v1()


__all__ = [
    "FROZEN_OPENROUTER_AUTHORIZATION_CASES_V1",
    "FROZEN_OPENROUTER_AUTHORIZATION_CASE_SET_V1",
    "FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1",
    "FROZEN_OPENROUTER_LIVE_SAFETY_CASE_SET_V1",
    "FROZEN_OPENROUTER_LIVE_SAFETY_REQUIREMENT_TAGS_V1",
    "FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1",
    "FROZEN_OPENROUTER_METAMORPHIC_CASES_V1",
    "FROZEN_OPENROUTER_METAMORPHIC_CASE_SET_V1",
    "FROZEN_OPENROUTER_P17_CASES_V1",
    "FROZEN_OPENROUTER_P17_CASE_SET_V1",
    "FROZEN_OPENROUTER_P19_CASES_V1",
    "FROZEN_OPENROUTER_P19_CASE_SET_V1",
    "OPENROUTER_AUTHORIZATION_CASE_SET_ID_V1",
    "OPENROUTER_LIVE_SAFETY_CASE_SCHEMA_V1",
    "OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1",
    "OPENROUTER_LIVE_SAFETY_CASE_SET_SCHEMA_V1",
    "OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1",
    "OPENROUTER_LIVE_SAFETY_THRESHOLDS_SCHEMA_V1",
    "OPENROUTER_METAMORPHIC_CASE_SET_ID_V1",
    "OPENROUTER_P17_CASE_SET_ID_V1",
    "OPENROUTER_P19_CASE_SET_ID_V1",
    "OpenRouterLiveSafetyCaseFamilyV1",
    "OpenRouterLiveSafetyCaseKindV1",
    "OpenRouterLiveSafetyCaseSetV1",
    "OpenRouterLiveSafetyCaseV1",
    "OpenRouterLiveSafetyExpectedOutcomeV1",
    "OpenRouterLiveSafetyHazardV1",
    "OpenRouterLiveSafetyThresholdsV1",
]
