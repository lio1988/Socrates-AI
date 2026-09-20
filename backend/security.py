"""Access boundary for a single-operator, same-origin application."""

import base64
import binascii
import hmac
import ipaddress
import os
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse


LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
MAX_BODY_BYTES = 65536
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
}


class AccessBoundary:
    def __init__(self, app, *, password, allowed_hosts):
        self.app = app
        self.password = password.encode("utf-8")
        self.allowed_hosts = allowed_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.update(SECURITY_HEADERS)
            await send(message)

        async def refuse(status, detail):
            headers = {"WWW-Authenticate": 'Basic realm="Socrates", charset="UTF-8"'} if status == 401 else {}
            await JSONResponse({"detail": detail}, status_code=status, headers=headers)(scope, receive, secure_send)

        headers = Headers(scope=scope)
        if any(len(headers.getlist(name)) > 1 for name in ("host", "origin", "authorization", "content-length")):
            await refuse(400, "Ambiguous request headers.")
            return
        host = headers.get("host", "")
        try:
            parsed = urlsplit("http://" + host)
            valid_host = parsed.hostname in self.allowed_hosts and not (
                parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            )
            parsed.port
        except ValueError:
            valid_host = False
        if not valid_host:
            await refuse(400, "Host is not allowed.")
            return
        try:
            local = ipaddress.ip_address((scope.get("client") or ("",))[0]).is_loopback
        except ValueError:
            local = False
        if not self.password and not local:
            await refuse(403, "Remote access requires an access password.")
            return
        if self.password:
            if not local and scope.get("scheme") != "https":
                await refuse(403, "Remote access requires HTTPS.")
                return
            authorization = headers.get("authorization", "").split(" ", 1)
            credential = b""
            if len(authorization) == 2 and authorization[0].lower() == "basic":
                try:
                    credential = base64.b64decode(authorization[1], validate=True)
                except (ValueError, binascii.Error):
                    credential = b""
            if not hmac.compare_digest(credential, b"socrates:" + self.password):
                await refuse(401, "Authentication required.")
                return
        origin = headers.get("origin")
        expected_origin = scope.get("scheme", "http") + "://" + host
        if (origin is not None and origin != expected_origin) or headers.get("sec-fetch-site") == "cross-site":
            await refuse(403, "Cross-origin access is not allowed.")
            return
        try:
            length = int(headers.get("content-length", "0"))
            if length < 0:
                raise ValueError
        except ValueError:
            await refuse(400, "Invalid content length.")
            return
        if length > MAX_BODY_BYTES:
            await refuse(413, "Request body is too large.")
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                await refuse(413, "Request body is too large.")
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, secure_send)


def access_settings():
    password = os.getenv("SOCRATES_ACCESS_PASSWORD", "")
    hosts = frozenset(host.strip().lower() for host in os.getenv(
        "SOCRATES_ALLOWED_HOSTS", "localhost,127.0.0.1,::1"
    ).split(",") if host.strip())
    if not hosts or any("*" in host or "/" in host for host in hosts):
        raise ValueError("SOCRATES_ALLOWED_HOSTS requires explicit hostnames.")
    if password and (len(password) < 32 or any(marker in password.lower() for marker in ("your-", "changeme", "placeholder"))):
        raise ValueError("SOCRATES_ACCESS_PASSWORD must be a non-placeholder password of at least 32 characters.")
    if not hosts.issubset(LOCAL_HOSTS) and not password:
        raise ValueError("Non-local hosts require SOCRATES_ACCESS_PASSWORD.")
    return {"password": password, "allowed_hosts": hosts}
