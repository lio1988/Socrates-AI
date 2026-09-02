# Hosted preview on Render — preparation only

Nothing here has been deployed, and this document does not authorize a
deployment. It records the smallest path from the current checkpoint to a
single-service public preview, so the decision to deploy is a decision and not
an improvisation.

## Shape

```
public HTTPS origin
  → Render web service (one instance, one worker)
      → FastAPI
          ├── static Socrates UI      (same origin)
          ├── /api/council/*          (same origin)
          └── SSE                     (same origin)
      → canonical CED
      → OpenRouter
```

One origin, on purpose. BYOK sends a user credential in a request body; a split
frontend and backend would mean either CORS with credentials or a second trust
boundary, and neither is worth what it buys here.

## Service settings

| Setting | Value |
| --- | --- |
| Service type | Python web service |
| Build command | `pip install -r requirements.txt` |
| Start command | `python -B -m uvicorn backend.local_ced_app:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health check path | `/health` |
| Instances | 1 |
| Workers | 1 |
| Repository | **private** |

`--host 0.0.0.0` binds inside the container only; the platform terminates TLS
and is the sole public ingress. `-B` keeps the process from writing bytecode
beside authorized sources, which the source verifier refuses.

Docker is deliberately not introduced. It would add a build surface without
changing what runs, and the plain Python path is already reproducible.

## Environment

Set these on the service. None of them is a secret; the one real secret,
`OPENROUTER_API_KEY`, **must not be set at all** for a BYOK-only preview — its
absence is what makes an accidental operator-funded charge impossible.

| Variable | Preview value | Why |
| --- | --- | --- |
| `SOCRATES_PUBLIC_ORIGIN` | `https://<your-domain>` | Declares hosted mode. Absent means local development. Blank is refused. |
| `SOCRATES_ENABLE_BYOK` | `1` | The public funding model. |
| `SOCRATES_ENABLE_OPERATOR_NORMAL_LIVE` | `0` | Operator-funded live is not a public control. |
| `SOCRATES_TRUST_PROXY` | `0` | Forwarded headers are caller-controlled until a specific proxy is named. |
| `SOCRATES_WORKERS` | `1` | Readiness degrades above one: the limiter is in-process. |
| `SOCRATES_RUN_ROOT` | leave unset unless a disk is attached | See persistence below. |
| `SOCRATES_MAX_ACTIVE_BYOK_RUNS_GLOBAL` | `2` | Preview capacity. |
| `SOCRATES_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT` | `1` | |
| `SOCRATES_BYOK_PREFLIGHTS_PER_10_MIN` | `10` | |
| `SOCRATES_BYOK_EXECUTIONS_PER_HOUR` | `4` | |

The process refuses to start on an unsafe combination — hosted BYOK without an
`https://` origin, a wildcard origin, an origin carrying a path, proxy trust
with no named proxy, a per-client cap above the global cap. That refusal is the
point: a misconfigured preview should never reach a user's credential.

## Persistence

Render's filesystem is ephemeral. Run artifacts written under the run root
vanish on restart or redeploy.

- For a preview that only needs to *work*, leave `SOCRATES_RUN_ROOT` unset.
- For a preview whose artifacts must survive, attach a persistent disk and
  point `SOCRATES_RUN_ROOT` at its mount.
- Either way, artifacts are not a backup. Anything that must be kept has to be
  copied off the host deliberately.

A restart kills active BYOK runs. The credential dies with the process and the
run fails; it must never resume under a different key.

## Health and readiness

- `GET /health` → `{"status":"ok"}`. Liveness only.
- `GET /ready` → `{"status":"ok","mode":"hosted_preview"}`, or `503` with
  finite reason codes such as `in_memory_limits_need_one_worker`.

Neither reveals source hashes, Git identities, authorization ids, filesystem
paths, provider accounts or key material. Both are unauthenticated, so
everything they say is public by construction.

## Before the first public link

- [ ] Repository is private.
- [ ] `OPENROUTER_API_KEY` is **not** set on the service.
- [ ] `SOCRATES_PUBLIC_ORIGIN` matches the real domain exactly, `https://`.
- [ ] `/ready` returns `ok`, not `degraded`.
- [ ] HTTPS is live and the certificate resolves for the custom domain.
- [ ] A BYOK run has been exercised against the deployed origin with a
      dedicated key carrying a small account spending limit.
- [ ] Logs contain no credential, no `Authorization` header, no execute body.

## What this preview is not

One instance with in-process limits. It is not distributed, not
highly-available, and not protected against a determined abuser. A second
worker or a second instance needs a shared external limiter first; until then
the documented rate limits are the only thing standing between the preview and
a queue of strangers, and they reset on restart.
