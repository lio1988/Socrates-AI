r"""
No-key connectivity diagnostic for the Anthropic API network path.

Checks DNS + TCP + TLS reachability to api.anthropic.com (and a neutral host for
comparison), plus library/cert sanity. It makes **NO API call**, sends **NO API
key**, and reveals **no secrets** — it is a transport-layer reachability probe
only (TLS handshake, no HTTP request body).

Run it in the SAME shell where the live smoke failed (authoritative):

    .\.venv\Scripts\python.exe scripts\diagnose_connectivity.py

Reading the result:
  - api.anthropic.com FAILs but the neutral host is OK  -> Anthropic-specific block
    (firewall / proxy / DNS policy).
  - BOTH fail                                           -> general egress blocked
    (no internet / port 443 blocked).
  - TLS fails but TCP is OK                             -> cert / proxy-MITM issue.
  - A set HTTPS_PROXY usually means the SDK must be told to use it.
"""

from __future__ import annotations

import os
import platform
import socket
import ssl
import sys

HOSTS = [("api.anthropic.com", 443), ("pypi.org", 443)]   # target + neutral baseline
TIMEOUT = 10.0


def _dns(host: str):
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True, ", ".join(sorted({i[4][0] for i in infos}))
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _tcp(host: str, port: int):
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True, "connected"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _tls(host: str, port: int):
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
                subj = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))
                return True, (f"{tls.version()} | CN={subj.get('commonName', '?')} | "
                              f"issuer={issuer.get('organizationName', '?')} | "
                              f"expires {cert.get('notAfter', '?')}")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    print("=" * 72)
    print("  NO-KEY CONNECTIVITY DIAGNOSTIC — Anthropic API path")
    print("  (no API call · no key · no secrets · TLS handshake only)")
    print("=" * 72)
    print(f"  python {sys.version.split()[0]} | {platform.system()} {platform.release()}")
    proxies = [v for v in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
               if os.environ.get(v) or os.environ.get(v.lower())]
    print(f"  proxy env set : {proxies or 'none'}    (values not shown)")
    print("-" * 72)

    results = {}
    for host, port in HOSTS:
        print(f"  {host}:{port}")
        for label, fn in (("DNS", lambda: _dns(host)),
                          ("TCP", lambda: _tcp(host, port)),
                          ("TLS", lambda: _tls(host, port))):
            ok, info = fn()
            results[(host, label)] = ok
            print(f"    {label} : {'OK  ' if ok else 'FAIL'} {info}")
        print()

    api_ok = all(results.get(("api.anthropic.com", x)) for x in ("DNS", "TCP", "TLS"))
    neutral_ok = all(results.get(("pypi.org", x)) for x in ("DNS", "TCP", "TLS"))
    print("-" * 72)
    if api_ok:
        print("  VERDICT: network path to api.anthropic.com is OPEN at the transport layer.")
        print("  If the live smoke still fails, suspect a shell-specific proxy/env in the")
        print("  terminal where you run it, or a transient issue — re-run the smoke.")
    elif neutral_ok:
        print("  VERDICT: api.anthropic.com is BLOCKED but general internet works ->")
        print("  Anthropic-specific firewall / proxy / DNS policy. Try another network,")
        print("  a VPN, or configure the proxy the SDK should use.")
    else:
        print("  VERDICT: general egress appears blocked (neither host reachable) ->")
        print("  no internet / port 443 blocked in this environment.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
