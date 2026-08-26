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
