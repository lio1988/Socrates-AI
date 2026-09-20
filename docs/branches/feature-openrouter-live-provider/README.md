# Branch: feature/openrouter-live-provider

Adds an opt-in strict OpenRouter adapter for the canonical `CouncilProviderRegistry` path.

The default Socrates-AI runtime remains offline/deterministic. Live OpenRouter use requires explicit environment configuration.

## Safety boundaries

- exact requested model ID is pinned;
- silent model substitution is rejected fail-closed;
- no fallback model is configured;
- API key comes from caller/environment only;
- no secrets are written to source, receipts, or logs;
- CED remains the sole protocol authority;
- provider output still passes the existing structured `AgentMove` validation path.
