# BYOK hosting and security requirements — v1

Preparation only. Nothing here has been deployed, and this document does not
authorize a deployment.

## What BYOK actually promises

In BYOK mode the user's OpenRouter key necessarily exists, temporarily, in
their password input, in their browser's memory, and in the body of the
same-origin execution request. That request is the whole point: it is how the
key reaches the server that will spend it. Any claim of `API_KEYS_IN_BROWSER = 0`
would be false.

The promises the implementation does keep:

- the key is not persisted in browser storage (`localStorage`, `sessionStorage`,
  IndexedDB, cookies, Cache API are never written with it);
- the key is not placed in a URL, query string or fragment;
- the key is not rendered outside its own password input;
- the key is not sent through SSE;
- the key is not returned in any API response;
- the key is not written to run artifacts;
- the key is not written to application or access logs;
- the key is not shared across runs or users;
- the key's references are released when the run reaches a terminal state.

The truthful user-facing sentence, used verbatim in the UI:

> Your OpenRouter key is used only for this council run. It is not written to
> browser storage, Socrates run artifacts or public logs. It is held temporarily
> in server memory and released when the run ends.

**No cryptographic zeroization is claimed.** `RunScopedCredential.release()`
drops this object's reference and marks the wrapper released; CPython reclaims
the string when nothing else holds it. Immutable copies are not provably
overwritten, and the code says so where it lives.

Browser password managers may ignore `autocomplete="off"`. The application
cannot guarantee third-party password-manager behaviour and does not claim to.

## The deployment contract

As of the public-preparation checkpoint these requirements are enforced at
startup by `backend/hosted_config.py`, not inferred per request. The declared
`SOCRATES_PUBLIC_ORIGIN` *is* the mode: absent means `LOCAL_DEVELOPMENT`, set
means `HOSTED_PREVIEW`, blank is refused. A caller cannot argue its way between
the two, because the decision was made before the first request arrived.

The process refuses to start on hosted BYOK without an `https://` origin, a
wildcard origin, an origin carrying a path or credentials, an unsupported
scheme, proxy trust with no named proxy, a per-client cap above the global cap,
or a malformed flag or limit. Multiple workers are reported by `/ready` as
`degraded` rather than refused: the process can serve, it simply cannot honour
the documented in-memory limits.

See `docs/deployment-render-v1.md` for the concrete variable values.

## Required hosting configuration

| Requirement | Why |
| --- | --- |
| HTTPS mandatory for hosted BYOK | The request body carries a user credential. `_require_byok_transport_security` fails closed on non-loopback plain HTTP. |
| Same-origin UI and API | One FastAPI process serves `web/` and `/api`. A split origin would force CORS with credentials or a second trust boundary. |
| No CORS middleware, no wildcard origin | None is installed. A cross-origin `Origin` header is refused with 403. |
| Trusted proxy disabled by default | `X-Forwarded-For` and `X-Forwarded-Proto` are not read. A limiter keyed on a caller-supplied header is not a limiter. Enabling proxy trust must be an explicit, bounded configuration naming the known proxy. |
| One application worker for the first preview | Rate limits are per-process, in-memory. A second worker gets its own counters. |
| Source authorization before provider construction | `verify_production_normal_live_source_authorization_v1` runs at preflight and again immediately before runtime construction. |
| No server-key fallback for BYOK | The BYOK dispatch path never reads `OPENROUTER_API_KEY`. It is a separate transport entry point that takes the credential as an argument. |
| Ephemeral filesystem tolerated | Run artifacts are written under the run root. On an ephemeral host they vanish on restart; canonical artifacts that must survive have to be copied off-host. |
| Process restart kills active runs | A crash loses the in-memory credential. The run fails; it must never resume under a different credential. |
| Health endpoint reveals nothing | `/api/council/health` returns a fixed shape with no secrets, no paths and no version detail beyond the mode. |
| Private repository stays private | Nothing in the deployed artifact should expose the source repository. |

## Security headers

Applied by one middleware in `backend/local_ced_app.py`:

- `Content-Security-Policy` — `default-src 'self'`, `script-src 'self'`,
  `style-src 'self'`, `connect-src 'self'`, `object-src 'none'`,
  `base-uri 'none'`, `form-action 'none'`, `frame-ancestors 'none'`.
  **No `unsafe-inline` and no `unsafe-eval`.** The UI has no inline script, no
  inline style and no inline event handler, so none is needed.
- `Referrer-Policy: no-referrer`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Permissions-Policy` — camera, microphone, geolocation, payment and the rest
  disabled.
- `Strict-Transport-Security` — **only** when the request genuinely arrived over
  TLS on a non-loopback host. Asserting HSTS from a loopback dev server would
  pin `localhost` to HTTPS in the developer's browser.
- `Cache-Control: no-store` on preflight, execute and run-status responses.

Request bodies are bounded at 64 KiB (`MAX_REQUEST_BODY_BYTES`); a larger
declared `Content-Length` is refused with 413 before any route runs.

## Rate limiting and capacity

Server constants in `backend/dialogues/byok_live.py`, never browser input:

| Limit | Default |
| --- | --- |
| Active BYOK runs per client | 1 |
| Active BYOK runs globally | 2 |
| BYOK preflights per client per 10 minutes | 10 |
| BYOK executions per client per hour | 4 |
| Distinct tracked clients before eviction | 4096 |

Excess requests return HTTP 429 with a bounded `Retry-After`. There is no queue:
a queue would hold a user's credential while they wait.

Client identity is the direct connection address. **These limits are
single-process preview protection.** They reset on restart, and a multi-instance
deployment needs a shared external limiter before scale-out.

## Resource bounds

| Store | Bound |
| --- | --- |
| Preflight store | 32 entries, 900 s non-sliding TTL, one-use |
| Retained runs in memory | 32, terminal runs trimmed first |
| Rate-limit client tables | 4096 distinct clients, least-recently-inserted evicted |
| Rate-limit marks per client | Pruned to the active window on every check |
| Request body | 64 KiB |
| Credential | One per run, in one closure, released in `finally` |

No unbounded list or dictionary is introduced. Canonical run artifacts stay on
disk under the existing policy and never contain a credential.

## Public error vocabulary

Finite and sanitized. Callers see one of: invalid request; preflight expired;
preflight already consumed; source build not authorized; capacity temporarily
reached; the supplied OpenRouter key was rejected; provider unavailable;
council completed with unresolved release; run failed safely.

Never exposed: any key fragment, the request body, the `Authorization` header,
a raw OpenRouter response, a raw exception, a filesystem path, Git or
source-authorization internals, provider account metadata, or hidden CED state.

## What is deliberately still open

- **Per-attempt semantic parse outcomes.** The gap between structured-output
  validation and governing `VerificationRecord` creation is still unobservable.
  It lives in `backend/dialogues/ced.py`, a frozen-core file, and is a separate
  observability-only task.
- **Shared rate limiting.** Required before more than one application worker.
- **Deployment.** Not performed.
- **A controlled BYOK live run.** Not performed, and not authorized here.
