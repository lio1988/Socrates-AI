# Stable branch memory — OpenRouter acquisition adapter controls v0

## Starting checkpoint

- Parent branch:
  `feature/socrates-zero-external-provider-authorization-gate-v0`.
- Fork HEAD: `03bc740fa73939e5942e9ed1c1674d3e165147b5`.
- Current branch: `feature/socrates-zero-provider-adapter-controls-v0`.
- Protected untracked files: `scripts/live_dialogue.py.bak` and the malformed
  root filename beginning `ocratic_followup_mandate`.

## Frozen decision and candidate

- Phase 8.5B decision: `PROVIDER-ADAPTER HARDENING REQUIRED`.
- Provider: OpenRouter.
- Existing production adapter:
  `backend.dialogues.openrouter_provider.OpenRouterProviderAdapter`.
- Exact canned research model: `openai/gpt-4.1-mini`.
- Live selection remains rejected; this branch grants no call authority.

## Primary hypothesis

A separate acquisition-only adapter can deterministically render exact bytes
from `AcquisitionSemanticRequest`, freeze adapter-owned controls, and emit
complete immutable canned response evidence without credentials, external
transport, production integration or canonical application.

## Non-negotiable invariants

- Activity remains `0/0/0/0/0/0` for
  network/credential/provider/model/tool/CED application.
- The production OpenRouter adapter and provider registry remain unchanged.
- Acquisition Contract v0 and every sealed historical artifact remain unchanged.
- The adapter is additive, offline-only, canned-only, default-disabled,
  non-governing and produces only `UNADMITTED` evidence.
- No aggregate runs before the pre-result freeze commit.
- Pricing is truthful: use trusted repository evidence or mark the live-model
  price `NOT ESTABLISHED`; synthetic prices may test arithmetic only.
- Protected untracked files are never touched or staged.

## Repository-backed control audit

Frozen before implementation:

- logical router/provider ID: `openrouter`;
- exact candidate model: `openai/gpt-4.1-mini`;
- logical output-token cap: `256`;
- canned total timeout: `5000 ms`;
- application/adapter/local retries: `0`;
- SDK retry status: `NOT_APPLICABLE` because the audited production path uses
  direct `aiohttp`, not a provider SDK;
- stream: `false`; tools: explicit empty set; temperature: `0`; seed:
  `PROVEN_UNSUPPORTED` and omitted;
- logical endpoint intent:
  `https://openrouter.ai:443/api/v1/chat/completions`, `POST`, JSON, redirects
  disabled, environment proxies disabled, TLS required, no alternate endpoint;
- attribution headers: absent; Authorization is always out of band and forbidden
  in this phase.

## Frozen unresolved controls

Repository source does not establish:

- an OpenRouter-supported provider-route field;
- an OpenRouter-supported upstream-fallback-disable field;
- the OpenRouter wire spelling/enforcement of an output-token cap;
- a tokenizer or fixed provider chat-framing overhead for authoritative billed
  input-token bounds;
- a trusted, attributable price for the exact candidate model/route;
- an exactly pinned `aiohttp` version or real endpoint/cancellation enforcement.

These remain `NOT_ESTABLISHED`. The implementation may prove payload-byte bounds
and synthetic arithmetic mechanics, but must not relabel either as live token or
cost authority. Under the frozen hypothesis, accepting any unresolved mandatory
control falsifies the candidate.

## Input and pricing truth rules

- `FULL_REQUEST_UTF8_BYTE_COUNT_V0` may record `B = len(body_bytes)` as a
  deterministic client-payload-only upper bound and `B + 256` as a payload-only
  total. It is not an authoritative billed-input bound without trusted framing
  evidence.
- Live-model pricing status is `NOT_ESTABLISHED`; maximum live cost is typed
  unknown, never zero.
- A separate `SYNTHETIC_TEST_ONLY` record may validate integer ceiling and
  overflow arithmetic but carries no provider/model/live authority.
