# Branch: feature/openrouter-live-provider

Adds an opt-in strict OpenRouter adapter for the canonical
`CouncilProviderRegistry` path and the H1 Hybrid append-only shadow ledger.

The default Socrates-AI runtime remains offline/deterministic. Live OpenRouter use requires explicit environment configuration.

## CANONICAL EXECUTION RESTORATION

This branch also restores three pre-existing execution contracts exposed by
the live-provider integration audit:

- each logical agent is bound to one physical provider/model seat for the
  session, while the existing deterministic Socratic roles continue to rotate;
- OpenRouter exposes its exact namespaced model ID through the shared adapter
  `model` metadata contract;
- successfully parsed `AgentMove.confidence` is the typed source used by
  downstream score and ratification records.

These are parity fixes, not an epistemic architecture change. Council scoring,
ratification, `well_supported`, role definitions, prompts, thresholds, and
Devil's Advocate behavior are unchanged.

## H0 BASELINE FREEZE

The restored execution baseline is protected by:

- the normative H0.5 contract at
  `docs/HYBRID_V1_H0_5_PRESERVATION_CONTRACT.md`;
- two offline known-failure fixtures under
  `tests_dialogues/fixtures/known_failures/`;
- fixture-integrity tests that independently enumerate the unique benchmark
  answer and make no provider or network call.

The fixtures preserve only retained evidence. Missing provider prose, score
values, and clipped historical transcript sections are explicitly unavailable
and were not reconstructed.

## H1 HYBRID SHADOW

The explicitly injected H1 observer records deterministic, append-only
provenance after canonical finalization. It is disabled by default,
non-authoritative, failure-isolated, replayable, conflict-safe, and absent from
`SessionState`/`FinalResponse`. It changes no prompt, provider behavior, phase,
role, score, assembly, ratification, release, learning, OpenClaw, or Live View
authority. See `docs/HYBRID_V1_H1_SHADOW_IMPLEMENTATION.md`.

## Safety boundaries

- exact requested model ID is pinned;
- silent model substitution is rejected fail-closed;
- no fallback model is configured;
- API key comes from caller/environment only;
- no secrets are written to source, receipts, or logs;
- CED remains the sole protocol authority;
- provider output still passes the existing structured `AgentMove` validation path.
