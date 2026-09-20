# Security and deployment boundary

Socrates AI is a single-operator research application, not a multi-tenant service.
A public source repository does not require a publicly accessible backend.

## Local operation

Run `python main.py` and open `http://127.0.0.1:8000/`. The default listener is
loopback-only, forwarded headers are disabled by that entrypoint, and the
application refuses non-loopback peers when no access password is configured.
Use the served frontend, not a `file://` copy. Host validation and same-origin
checks protect the local service from foreign browser origins and DNS rebinding.
The local mode trusts other processes and users on the same computer.

## Remote operation

Before exposing any interface or tunnel, configure both:

- `SOCRATES_ACCESS_PASSWORD`: a randomly generated password of at least 32
  characters; store it only in a secret manager or ignored local `.env`.
- `SOCRATES_ALLOWED_HOSTS`: comma-separated exact hostnames, without scheme,
  port or wildcards. Non-local hostnames require an access password.

All routes, including the frontend, health, docs, dialog controls and exports,
require HTTP Basic authentication when a password is set. The username is
`socrates`. This password is separate from all model-provider API keys. Browsers
can use their native login prompt. All authenticated operators share the same
session store; there is no per-user ownership or tenant isolation.

Use HTTPS, a firewall and an authenticated ingress. Do not expose the backend
port directly. Configure proxy trust narrowly, strip client-supplied forwarded
headers at the proxy, and set the access password even if the proxy connects
from loopback. Never treat a proxy's loopback address as proof of end-user
identity. External HTTP requests are refused; a TLS-terminating proxy must
provide a trusted HTTPS scheme or enforce TLS and authentication itself.

The app bounds request bodies to 64 KiB, active dialogs to two and stored sessions
to 100 per worker. Running sessions cannot be deleted to evade the active limit.
Delete finished sessions explicitly when storage fills. Use one worker for this
in-memory application. Ingress still needs rate limits, connection/body-read
timeouts and provider-side spending limits. These are not implemented by a
per-worker session count. Provider HTTP calls have bounded timeouts but some
calls remain synchronous and can block the event loop.

## Secrets and maintenance

Never commit credentials, `.env` variants, private keys or private run artifacts.
`.env.example` is the only allowed example environment file and must contain
placeholders. Ignore rules do not remove already-tracked files or Git history.

GitHub secret scanning and push protection are enabled on the repository.
The Security workflow adds Gitleaks, dependency auditing and offline boundary
tests when the workflow is published. Gitleaks exceptions cover exact synthetic
test credentials and protocol identifiers, not whole directories. Do not
silence a new finding without reviewing it. Branch rules must separately require
these checks if merges should be blocked; adding a workflow alone does not do so.

To update and verify a local environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend_security.test.cjs
```

Dependency minimums include fixes for
[aiohttp's response parser](https://github.com/aio-libs/aiohttp/security/advisories/GHSA-cq5v-8q36-5273)
and [AnyIO's TLS hostname handling](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6).
Dependency auditing must be repeated over time; an audit is not a permanent
guarantee or a locked dependency resolution.

If a real key is published, revoke it at its provider and replace it locally.
Deleting a line or making a repository private does not revoke a key or erase
copies, forks, caches and historical commits. Report security defects privately
through GitHub's security reporting facilities when available; never include a
credential in an issue, PR, screenshot or chat.
