"""S7B: operator grants, a one-shot HTTPS transport, and the JIT limit client.

Three additive pieces, and nothing else:

* **Operator grants.**  S7A froze the *shape* of operator authority but shipped
  only synthetic fixtures.  A live run needs real grants that bind the operator's
  actual declared values, so this module builds them from explicit inputs and
  never invents a number.

* **A one-shot HTTPS transport.**  The repository's general provider adapter uses
  ``aiohttp`` with ``json=body``, which re-serializes and therefore cannot prove
  that the bytes registered are the bytes sent.  A live shadow observation needs
  that proof, so this transport writes exact registered bytes over
  ``http.client`` and captures the raw response before anything interprets it.

* **The JIT model-limit client.**  One GET, no retry, raw bytes preserved for the
  frozen S7A parser to judge.

The dispatch budget is enforced by a process-wide latch rather than by
convention: the second attempt raises before a socket is opened.  Failing closed
on the second call is the whole point; a duplicate inference is a real charge
and an unrepeatable scientific event.

Credential handling: the bearer value is read at the dispatch boundary, used for
one header, and never returned, stored, logged, hashed, or bound into any
identity.  Only ``PRESENT``/``ABSENT`` ever leaves this module.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id

OPENROUTER_OPERATOR_PRICE_GRANT_SCHEMA_V1 = (
    "socrateszero-openrouter-operator-price-grant/v1"
)
OPENROUTER_OPERATOR_TOTAL_GRANT_SCHEMA_V1 = (
    "socrateszero-openrouter-operator-total-grant/v1"
)
OPENROUTER_CLAIM_STORE_GRANT_SCHEMA_V1 = (
    "socrateszero-openrouter-claim-store-grant/v1"
)
OPENROUTER_LIVE_TRANSPORT_REGISTRATION_SCHEMA_V1 = (
    "socrateszero-openrouter-live-transport-registration/v1"
)
OPENROUTER_LIVE_TRANSPORT_COMPLETION_SCHEMA_V1 = (
    "socrateszero-openrouter-live-transport-completion/v1"
)

#: The exact claim this experiment may make about the claim store.  It is
#: deliberately narrower than "rollback-proof": the property holds only under a
#: declared operator trust model, and the label says so out loud.
OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1 = (
    "TRUSTED_DURABLE_NON_ROLLBACK_UNDER_DECLARED_OPERATOR_TRUST_MODEL"
)

#: Threats the declared model covers.  The physical store must actually resist
#: these, and the offline test matrix proves each one.
FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1: Tuple[str, ...] = (
    "PROCESS_CRASH",
    "ORDINARY_PROCESS_RESTART",
    "ACCIDENTAL_DUPLICATE_EXECUTION",
    "CONCURRENT_DUPLICATE_CONSUMPTION",
)

#: Threats the declared model explicitly excludes.  Ordinary local storage does
#: not defeat any of these, and pretending otherwise would be the exact
#: overclaim the phase forbids.
FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1: Tuple[str, ...] = (
    "MALICIOUS_LOCAL_ADMINISTRATOR",
    "DELIBERATE_FILESYSTEM_ROLLBACK",
    "VM_OR_SNAPSHOT_ROLLBACK",
    "BACKUP_RESTORE_ACROSS_CONSUMPTION_BOUNDARY",
)

OPENROUTER_LIVE_API_HOST_V1 = "openrouter.ai"
OPENROUTER_LIVE_INFERENCE_PATH_V1 = "/api/v1/chat/completions"
OPENROUTER_MODEL_DETAIL_PATH_V1 = "/api/v1/model/openai/gpt-4.1-mini"
#: The documented first-party endpoint listing.  S7B guessed the endpoint slug
#: and the router matched nothing; this is the surface that states the real ones.
OPENROUTER_MODEL_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/openai/gpt-4.1-mini/endpoints"
)
OPENROUTER_CREDENTIAL_VARIABLE_V1 = "OPENROUTER_API_KEY"

#: Response bytes above this are refused rather than buffered without limit.
OPENROUTER_MAX_LIVE_RESPONSE_BYTES_V1 = 4 * 1024 * 1024

#: Endpoint listings for the two families the multi-model experiment adds. Each
#: is its own pinned class, so a typo in a slug cannot silently become a request
#: to some other model.
OPENROUTER_CLAUDE_SONNET_5_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/anthropic/claude-sonnet-5/endpoints"
)
OPENROUTER_GEMINI_3_7_FLASH_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/google/gemini-3.7-flash/endpoints"
)

#: The catalog listing, used only to discover exact model slugs before they are
#: pinned above.  A slug cannot be pinned without first being read from the
#: provider, and guessing one is what produced the S7B routing refusal.
OPENROUTER_MODELS_CATALOG_PATH_V1 = "/api/v1/models"

#: The two open-weight families the operator added to the council.  Both slugs
#: were read from the catalog listing above, not guessed.
OPENROUTER_QWEN3_235B_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/qwen/qwen3-235b-a22b-2507/endpoints"
)
OPENROUTER_LLAMA_4_MAVERICK_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/meta-llama/llama-4-maverick/endpoints"
)

#: Low-cost council candidates.  ``qwen3-32b`` is the operator's exact slug.
#: The operator's Seat C slug ``llama-4-scout-17b-16e-instruct`` is absent from
#: the catalog; ``llama-4-scout`` is the same model under OpenRouter's canonical
#: slug and is pinned here as an identified alternative, not a substitution.
OPENROUTER_QWEN3_32B_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/qwen/qwen3-32b/endpoints"
)
OPENROUTER_LLAMA_4_SCOUT_ENDPOINTS_PATH_V1 = (
    "/api/v1/models/meta-llama/llama-4-scout/endpoints"
)

#: The only request targets this phase may ever open, paired with the only
#: dispatch class allowed to use each.  Anything else is refused before a socket.
FROZEN_OPENROUTER_PERMITTED_TARGETS_V1 = {
    "jit_metadata_get": ("GET", OPENROUTER_MODEL_DETAIL_PATH_V1),
    "live_inference_post": ("POST", OPENROUTER_LIVE_INFERENCE_PATH_V1),
    "jit_endpoints_get": ("GET", OPENROUTER_MODEL_ENDPOINTS_PATH_V1),
    "claude_sonnet_5_endpoints_get": (
        "GET",
        OPENROUTER_CLAUDE_SONNET_5_ENDPOINTS_PATH_V1,
    ),
    "gemini_3_7_flash_endpoints_get": (
        "GET",
        OPENROUTER_GEMINI_3_7_FLASH_ENDPOINTS_PATH_V1,
    ),
    "models_catalog_get": ("GET", OPENROUTER_MODELS_CATALOG_PATH_V1),
    "qwen3_235b_endpoints_get": (
        "GET",
        OPENROUTER_QWEN3_235B_ENDPOINTS_PATH_V1,
    ),
    "llama_4_maverick_endpoints_get": (
        "GET",
        OPENROUTER_LLAMA_4_MAVERICK_ENDPOINTS_PATH_V1,
    ),
    "qwen3_32b_endpoints_get": ("GET", OPENROUTER_QWEN3_32B_ENDPOINTS_PATH_V1),
    "llama_4_scout_endpoints_get": (
        "GET",
        OPENROUTER_LLAMA_4_SCOUT_ENDPOINTS_PATH_V1,
    ),
}


class _FrozenShadowContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str, label: str) -> str:
    if not isinstance(value, str) or value.strip() != value or not value:
        raise ContractValidationError(f"{label} must be exact nonblank text")
    return value


# --------------------------------------------------------------- grants -----


class OpenRouterOperatorPriceGrantV1(_FrozenShadowContractV1):
    """An operator's explicit authorization of the three price ceilings.

    Content addressed over the exact decimal strings the operator supplied, so a
    grant cannot be reused to authorize different numbers.
    """

    schema_version: Literal[
        OPENROUTER_OPERATOR_PRICE_GRANT_SCHEMA_V1
    ] = OPENROUTER_OPERATOR_PRICE_GRANT_SCHEMA_V1
    operator_statement: str = Field(min_length=1)
    prompt_usd_per_million_tokens: str = Field(min_length=1)
    completion_usd_per_million_tokens: str = Field(min_length=1)
    request_usd: str = Field(min_length=1)
    grant_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def refuse_non_string_money(cls, data):
        if isinstance(data, dict):
            for field in (
                "prompt_usd_per_million_tokens",
                "completion_usd_per_million_tokens",
                "request_usd",
            ):
                value = data.get(field)
                if value is not None and type(value) is not str:
                    raise ContractValidationError(
                        f"{field} must be a decimal string, not "
                        f"{type(value).__name__}: float money is not authority"
                    )
        return data

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOperatorPriceGrantV1":
        expected = stable_contract_id(
            "szoroperatorpricegrantv1",
            self.model_dump(mode="json", exclude={"grant_id"}),
        )
        if self.grant_id not in (None, expected):
            raise ContractValidationError("operator price grant ID mismatch")
        object.__setattr__(self, "grant_id", expected)
        return self


class OpenRouterOperatorTotalSpendGrantV1(_FrozenShadowContractV1):
    """An operator's explicit total-spend ceiling for exactly one call."""

    schema_version: Literal[
        OPENROUTER_OPERATOR_TOTAL_GRANT_SCHEMA_V1
    ] = OPENROUTER_OPERATOR_TOTAL_GRANT_SCHEMA_V1
    operator_statement: str = Field(min_length=1)
    max_total_spend_usd: str = Field(min_length=1)
    max_spend_picodollars: int = Field(ge=0)
    grant_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def refuse_non_string_money(cls, data):
        if isinstance(data, dict):
            value = data.get("max_total_spend_usd")
            if value is not None and type(value) is not str:
                raise ContractValidationError(
                    "max_total_spend_usd must be a decimal string: float money "
                    "is not authority"
                )
        return data

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOperatorTotalSpendGrantV1":
        expected = stable_contract_id(
            "szoroperatortotalgrantv1",
            self.model_dump(mode="json", exclude={"grant_id"}),
        )
        if self.grant_id not in (None, expected):
            raise ContractValidationError("operator total-spend grant ID mismatch")
        object.__setattr__(self, "grant_id", expected)
        return self


class OpenRouterClaimStoreGrantV1(_FrozenShadowContractV1):
    """An operator's attestation about one exact claim-store location.

    The grant records the trust model *and its exclusions* together, so the
    artifact can never present the store as stronger than it is.  The excluded
    threats are part of the content-addressed identity: a grant that quietly
    dropped them would be a different grant.
    """

    schema_version: Literal[
        OPENROUTER_CLAIM_STORE_GRANT_SCHEMA_V1
    ] = OPENROUTER_CLAIM_STORE_GRANT_SCHEMA_V1
    operator_statement: str = Field(min_length=1)
    claim_store_id: str = Field(pattern=r"^szorclaimstorev1_[0-9a-f]{64}$")
    trust_model: Literal[
        OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1
    ] = OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1
    threats_included: Tuple[str, ...]
    threats_excluded: Tuple[str, ...]
    cryptographic_anti_rollback: Literal[False] = False
    outside_repository: bool
    outside_temporary_directory: bool
    grant_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterClaimStoreGrantV1":
        if self.threats_included != FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1:
            raise ContractValidationError(
                "claim-store grant does not carry the declared included threats"
            )
        if self.threats_excluded != FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1:
            raise ContractValidationError(
                "claim-store grant does not carry the declared excluded threats"
            )
        if not self.outside_repository or not self.outside_temporary_directory:
            raise ContractValidationError(
                "the claim store must live outside the repository and outside "
                "temporary directories"
            )
        expected = stable_contract_id(
            "szorclaimstoregrantv1",
            self.model_dump(mode="json", exclude={"grant_id"}),
        )
        if self.grant_id not in (None, expected):
            raise ContractValidationError("claim-store grant ID mismatch")
        object.__setattr__(self, "grant_id", expected)
        return self


def build_openrouter_claim_store_grant_v1(
    claim_directory: Path,
    *,
    operator_statement: str,
    repository_root: Path,
) -> OpenRouterClaimStoreGrantV1:
    """Build the live claim-store grant, checking the location claims itself.

    ``outside_repository`` and ``outside_temporary_directory`` are *measured*
    here rather than asserted by the caller: a grant should not be able to claim
    a property of a path that the path does not have.
    """
    from .openrouter_live_safety_closure_v1 import openrouter_claim_store_id_v1

    resolved = Path(claim_directory).resolve(strict=False)
    repo = Path(repository_root).resolve(strict=False)
    outside_repo = repo not in resolved.parents and resolved != repo
    lowered = resolved.as_posix().casefold()
    temp_markers = ("/temp/", "/tmp/", "/appdata/local/temp/")
    outside_temp = not any(marker in lowered + "/" for marker in temp_markers)
    return OpenRouterClaimStoreGrantV1(
        operator_statement=_nonblank(operator_statement, "operator statement"),
        claim_store_id=openrouter_claim_store_id_v1(resolved),
        threats_included=FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1,
        threats_excluded=FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1,
        outside_repository=outside_repo,
        outside_temporary_directory=outside_temp,
    )


# ------------------------------------------------------------ credential -----


def _read_bearer_credential_v1() -> Optional[str]:
    """The single place this process reads the credential.

    One read site keeps the secret surface auditable, and lets offline tests
    supply a fake without going anywhere near the real environment variable -
    which the acquisition tripwire rightly treats as a credential access.
    """
    value = os.environ.get(OPENROUTER_CREDENTIAL_VARIABLE_V1)
    if not isinstance(value, str) or value.strip() == "":
        return None
    return value


def openrouter_credential_is_present_v1() -> bool:
    """Whether the canonical credential exists.  The value never leaves here."""
    return _read_bearer_credential_v1() is not None


# ------------------------------------------------------------- transport -----


class OpenRouterLiveTransportRegistrationV1(_FrozenShadowContractV1):
    """The exact bytes and target a dispatch is permitted to send."""

    schema_version: Literal[
        OPENROUTER_LIVE_TRANSPORT_REGISTRATION_SCHEMA_V1
    ] = OPENROUTER_LIVE_TRANSPORT_REGISTRATION_SCHEMA_V1
    dispatch_class: Literal[
        "jit_metadata_get",
        "live_inference_post",
        "jit_endpoints_get",
        "claude_sonnet_5_endpoints_get",
        "gemini_3_7_flash_endpoints_get",
        "models_catalog_get",
        "qwen3_235b_endpoints_get",
        "llama_4_maverick_endpoints_get",
        "qwen3_32b_endpoints_get",
        "llama_4_scout_endpoints_get",
    ]
    method: Literal["POST", "GET"]
    host: Literal[OPENROUTER_LIVE_API_HOST_V1] = OPENROUTER_LIVE_API_HOST_V1
    path: str = Field(min_length=1)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(ge=0)
    #: The authorized non-secret headers, name and value.  Authorization is not
    #: one of them and never becomes one: it is a dispatch-only secret.
    semantic_headers: Tuple[Tuple[str, str], ...]
    semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bounded_timeout_seconds: int = Field(gt=0, le=120)
    registration_id: Optional[str] = None

    @property
    def semantic_header_names(self) -> Tuple[str, ...]:
        return tuple(name for name, _ in self.semantic_headers)

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveTransportRegistrationV1":
        if any(name.lower() == "authorization" for name, _ in self.semantic_headers):
            raise ContractValidationError(
                "the Authorization header is never semantic evidence"
            )
        permitted = FROZEN_OPENROUTER_PERMITTED_TARGETS_V1.get(self.dispatch_class)
        if permitted is None or (self.method, self.path) != permitted:
            raise ContractValidationError(
                f"{self.dispatch_class} may only address "
                f"{permitted[0]} {permitted[1]}"
                if permitted
                else "unknown dispatch class"
            )
        if _header_evidence_digest_v1(self.semantic_headers) != (
            self.semantic_headers_sha256
        ):
            raise ContractValidationError(
                "semantic header digest does not describe the headers"
            )
        expected = stable_contract_id(
            "szorlivetransportregistrationv1",
            self.model_dump(mode="json", exclude={"registration_id"}),
        )
        if self.registration_id not in (None, expected):
            raise ContractValidationError("transport registration ID mismatch")
        object.__setattr__(self, "registration_id", expected)
        return self


class OpenRouterLiveTransportCompletionV1(_FrozenShadowContractV1):
    """What one dispatch actually produced, before any interpretation."""

    schema_version: Literal[
        OPENROUTER_LIVE_TRANSPORT_COMPLETION_SCHEMA_V1
    ] = OPENROUTER_LIVE_TRANSPORT_COMPLETION_SCHEMA_V1
    registration_id: str = Field(min_length=1)
    dispatch_attempted: Literal[True] = True
    local_dispatch_count: Literal[1] = 1
    retry_count: Literal[0] = 0
    completed: bool
    http_status: Optional[int] = None
    response_body_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    response_body_length: Optional[int] = Field(default=None, ge=0)
    response_header_count: Optional[int] = Field(default=None, ge=0)
    response_header_evidence_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    failure_class: Optional[str] = None
    completion_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveTransportCompletionV1":
        if self.completed and self.http_status is None:
            raise ContractValidationError("a completed dispatch carries a status")
        if not self.completed and self.failure_class is None:
            raise ContractValidationError(
                "an incomplete dispatch must name its failure class"
            )
        expected = stable_contract_id(
            "szorlivetransportcompletionv1",
            self.model_dump(mode="json", exclude={"completion_id"}),
        )
        if self.completion_id not in (None, expected):
            raise ContractValidationError("transport completion ID mismatch")
        object.__setattr__(self, "completion_id", expected)
        return self


@dataclass(frozen=True)
class OpenRouterRawHttpResultV1:
    """Raw evidence from one dispatch.  Not a contract; not persisted as-is."""

    registration: OpenRouterLiveTransportRegistrationV1
    dispatched_body: bytes
    completion: OpenRouterLiveTransportCompletionV1
    raw_response_body: bytes
    response_headers: Tuple[Tuple[str, str], ...]


class OpenRouterDispatchBudgetExceeded(ContractValidationError):
    """Raised before a second network dispatch of the same class is opened."""


class _DispatchLatch:
    """A process-wide one-shot latch per dispatch class.

    Deliberately not resettable from this module.  A caller that wants a second
    live call must obtain new authorization in a new phase, which is a human
    decision, not a function call.
    """

    def __init__(self) -> None:
        self._used: dict[str, int] = {}

    def count(self, kind: str) -> int:
        return self._used.get(kind, 0)

    def claim(self, kind: str, limit: int) -> None:
        used = self._used.get(kind, 0)
        if used >= limit:
            raise OpenRouterDispatchBudgetExceeded(
                f"{kind} budget of {limit} already consumed; "
                "a further request requires new explicit authorization"
            )
        self._used[kind] = used + 1


OPENROUTER_DISPATCH_LATCH_V1 = _DispatchLatch()


def _header_evidence_digest_v1(headers: Tuple[Tuple[str, str], ...]) -> str:
    from .contracts import canonical_json

    payload = canonical_json([[name.lower(), value] for name, value in headers])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dispatch_once_v1(
    *,
    kind: str,
    method: str,
    path: str,
    body: Optional[bytes],
    semantic_headers: Mapping[str, str],
    bounded_timeout_seconds: int,
    bearer_credential: str,
    limit: int = 1,
) -> OpenRouterRawHttpResultV1:
    """Send exactly one request and capture raw evidence.  Never retries.

    The latch is claimed *before* the socket is opened, so a crash mid-flight
    still consumes the budget.  Under-execution is the safe direction: a second
    attempt could double-charge and would destroy the one-shot claim.
    """
    # One sealing step.  ``sealed_body`` is the object whose digest is recorded
    # and the object handed to the client: there is no second serialization
    # between identity and the socket, so they cannot diverge.
    sealed_body: Optional[bytes] = None if body is None else bytes(body)
    ordered_headers = tuple(sorted((str(k), str(v)) for k, v in semantic_headers.items()))
    registration = OpenRouterLiveTransportRegistrationV1(
        dispatch_class=kind,
        method=method,
        path=path,
        body_sha256=hashlib.sha256(sealed_body or b"").hexdigest(),
        body_length=len(sealed_body or b""),
        semantic_headers=ordered_headers,
        semantic_headers_sha256=_header_evidence_digest_v1(ordered_headers),
        bounded_timeout_seconds=bounded_timeout_seconds,
    )
    OPENROUTER_DISPATCH_LATCH_V1.claim(kind, limit)

    headers = dict(ordered_headers)
    # Injected at the boundary only; never recorded anywhere below.
    headers["Authorization"] = f"Bearer {bearer_credential}"

    connection = http.client.HTTPSConnection(
        OPENROUTER_LIVE_API_HOST_V1,
        timeout=bounded_timeout_seconds,
        context=ssl.create_default_context(),
    )
    try:
        connection.request(method, path, body=sealed_body, headers=headers)
        response = connection.getresponse()
        raw = response.read(OPENROUTER_MAX_LIVE_RESPONSE_BYTES_V1 + 1)
        if len(raw) > OPENROUTER_MAX_LIVE_RESPONSE_BYTES_V1:
            raise ContractValidationError("live response exceeded the byte cap")
        response_headers = tuple(
            (str(name), str(value)) for name, value in response.getheaders()
        )
        completion = OpenRouterLiveTransportCompletionV1(
            registration_id=registration.registration_id or "",
            completed=True,
            http_status=int(response.status),
            response_body_sha256=hashlib.sha256(raw).hexdigest(),
            response_body_length=len(raw),
            response_header_count=len(response_headers),
            response_header_evidence_sha256=_header_evidence_digest_v1(
                response_headers
            ),
        )
        return OpenRouterRawHttpResultV1(
            registration=registration,
            dispatched_body=sealed_body or b"",
            completion=completion,
            raw_response_body=raw,
            response_headers=response_headers,
        )
    except Exception as exc:  # noqa: BLE001 - every failure is evidence, not a retry
        completion = OpenRouterLiveTransportCompletionV1(
            registration_id=registration.registration_id or "",
            completed=False,
            failure_class=type(exc).__name__,
        )
        return OpenRouterRawHttpResultV1(
            registration=registration,
            dispatched_body=sealed_body or b"",
            completion=completion,
            raw_response_body=b"",
            response_headers=(),
        )
    finally:
        connection.close()
        headers.clear()


def fetch_openrouter_model_detail_v1(
    *, bounded_timeout_seconds: int = 30
) -> OpenRouterRawHttpResultV1:
    """The single permitted first-party model-limit GET.  No retry."""
    credential = _read_bearer_credential_v1()
    if credential is None:
        raise ContractValidationError("credential absent; no request may be made")
    return _dispatch_once_v1(
        kind="jit_metadata_get",
        method="GET",
        path=OPENROUTER_MODEL_DETAIL_PATH_V1,
        body=None,
        semantic_headers={"Accept": "application/json"},
        bounded_timeout_seconds=bounded_timeout_seconds,
        bearer_credential=credential,
    )


def fetch_openrouter_family_endpoints_v1(
    *, dispatch_class: str, bounded_timeout_seconds: int = 30
) -> OpenRouterRawHttpResultV1:
    """One bounded GET of a pinned family endpoint listing.  No retry.

    The class selects the path from the frozen target table, so a caller cannot
    reach an arbitrary model listing by passing a crafted string.
    """
    permitted = FROZEN_OPENROUTER_PERMITTED_TARGETS_V1.get(dispatch_class)
    if permitted is None or permitted[0] != "GET":
        raise ContractValidationError(
            f"{dispatch_class!r} is not a permitted metadata GET class"
        )
    credential = _read_bearer_credential_v1()
    if credential is None:
        raise ContractValidationError("credential absent; no request may be made")
    return _dispatch_once_v1(
        kind=dispatch_class,
        method="GET",
        path=permitted[1],
        body=None,
        semantic_headers={"Accept": "application/json"},
        bounded_timeout_seconds=bounded_timeout_seconds,
        bearer_credential=credential,
    )


def fetch_openrouter_model_endpoints_v1(
    *, bounded_timeout_seconds: int = 30
) -> OpenRouterRawHttpResultV1:
    """One bounded GET of the documented endpoint listing.  No retry."""
    credential = _read_bearer_credential_v1()
    if credential is None:
        raise ContractValidationError("credential absent; no request may be made")
    return _dispatch_once_v1(
        kind="jit_endpoints_get",
        method="GET",
        path=OPENROUTER_MODEL_ENDPOINTS_PATH_V1,
        body=None,
        semantic_headers={"Accept": "application/json"},
        bounded_timeout_seconds=bounded_timeout_seconds,
        bearer_credential=credential,
    )


def dispatch_openrouter_one_live_inference_v1(
    *,
    body_bytes: bytes,
    semantic_headers: Mapping[str, str],
    bounded_timeout_seconds: int,
    process_dispatch_limit: int = 1,
) -> OpenRouterRawHttpResultV1:
    """One inference POST.  No retry, ever.

    ``process_dispatch_limit`` is the process-wide ceiling on how many inference
    dispatches this interpreter may ever make. It defaults to **1**, which is the
    scientific pilot's behaviour and must stay the default: a lone call should
    never be able to become two by accident.

    A bounded session raises it to its own authorized call cap. That is not a
    weakening — the ceiling still exists, is still enforced before a socket
    opens, and is still a number the operator authorized. What protects a
    *specific* turn from being dispatched twice is its single-use claim, not this
    counter.

    The caller must have consumed that claim already; this function does not
    check it, because the claim store is the authority and a second check here
    would only invite a second code path to the same decision.
    """
    credential = _read_bearer_credential_v1()
    if credential is None:
        raise ContractValidationError("credential absent; no request may be made")
    if not isinstance(body_bytes, (bytes, bytearray)) or not body_bytes:
        raise ContractValidationError("inference dispatch requires exact body bytes")
    return _dispatch_once_v1(
        kind="live_inference_post",
        method="POST",
        path=OPENROUTER_LIVE_INFERENCE_PATH_V1,
        body=bytes(body_bytes),
        semantic_headers=semantic_headers,
        bounded_timeout_seconds=bounded_timeout_seconds,
        bearer_credential=credential,
        limit=int(process_dispatch_limit),
    )


__all__ = [
    "FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1",
    "FROZEN_OPENROUTER_PERMITTED_TARGETS_V1",
    "FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1",
    "OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1",
    "OPENROUTER_CREDENTIAL_VARIABLE_V1",
    "OPENROUTER_DISPATCH_LATCH_V1",
    "OPENROUTER_LIVE_API_HOST_V1",
    "OPENROUTER_LIVE_INFERENCE_PATH_V1",
    "OPENROUTER_MODEL_DETAIL_PATH_V1",
    "OpenRouterClaimStoreGrantV1",
    "OpenRouterDispatchBudgetExceeded",
    "OpenRouterLiveTransportCompletionV1",
    "OpenRouterLiveTransportRegistrationV1",
    "OpenRouterOperatorPriceGrantV1",
    "OpenRouterOperatorTotalSpendGrantV1",
    "OpenRouterRawHttpResultV1",
    "build_openrouter_claim_store_grant_v1",
    "dispatch_openrouter_one_live_inference_v1",
    "fetch_openrouter_model_detail_v1",
    "fetch_openrouter_family_endpoints_v1",
    "fetch_openrouter_model_endpoints_v1",
    "openrouter_credential_is_present_v1",
]
