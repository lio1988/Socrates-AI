"""Runtime tripwires for the acquisition-only experiment boundary.

This module is deliberately separate from the canned runtime.  It imports the
external seams that the experiment must prove it never crosses, but importing
the module is inert: patches exist only inside :class:`AcquisitionBoundaryTripwireV0`.

The authoritative builders and write-once publishers query the active harness
directly.  They do not accept a caller-supplied "zero" attestation.
"""

from __future__ import annotations

import builtins
import contextvars
import http.client
import importlib
import os
import socket
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, Sequence
from unittest.mock import patch


class AcquisitionBoundaryViolation(AssertionError):
    """Raised immediately when an acquisition experiment crosses a forbidden seam."""


@dataclass(frozen=True)
class AcquisitionBoundaryHitV0:
    ordinal: int
    category: str
    seam: str


@dataclass(frozen=True)
class AcquisitionBoundaryTripwireSnapshotV0:
    external_network_attempts: int
    credential_access_attempts: int
    live_provider_calls: int
    provider_sdk_calls: int
    model_executions: int
    tool_calls: int
    canonical_application_calls: int
    hits: tuple[AcquisitionBoundaryHitV0, ...]

    @property
    def total_forbidden_attempts(self) -> int:
        return sum(
            (
                self.external_network_attempts,
                self.credential_access_attempts,
                self.live_provider_calls,
                self.provider_sdk_calls,
                self.model_executions,
                self.tool_calls,
                self.canonical_application_calls,
            )
        )


_ACTIVE_TRIPWIRE: contextvars.ContextVar[
    Optional["AcquisitionBoundaryTripwireV0"]
] = contextvars.ContextVar("socrates_zero_acquisition_boundary_tripwire_v0", default=None)

_SECRET_ENV_MARKERS = (
    "API_KEY",
    "APIKEY",
    "AUTH_TOKEN",
    "BEARER_TOKEN",
    "CLIENT_SECRET",
    "CREDENTIAL",
    "PASSWORD",
    "PRIVATE_KEY",
    "PROVIDER_SECRET",
    "SECRET_KEY",
)
_SECRET_ENV_EXACT = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "NVIDIA_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    }
)
_CREDENTIAL_PATH_MARKERS = frozenset(
    {
        ".aws",
        ".azure",
        ".env",
        ".gcloud",
        ".ssh",
        "auth.json",
        "credentials",
        "credentials.json",
        "keyring",
        "netrc",
        "secrets",
        "secrets.json",
        "token.json",
    }
)


def _is_secret_environment_key(key: object) -> bool:
    text = str(key).upper()
    return text in _SECRET_ENV_EXACT or any(marker in text for marker in _SECRET_ENV_MARKERS)


def _is_credential_path(value: object) -> bool:
    if isinstance(value, int):
        return False
    try:
        path = Path(os.fspath(value))
    except TypeError:
        return False
    lowered = tuple(part.lower() for part in path.parts)
    name = path.name.lower()
    if name.endswith((".key", ".pem", ".p12", ".pfx")):
        return True
    return any(
        part in _CREDENTIAL_PATH_MARKERS
        or "credential" in part
        or part.startswith(".env")
        for part in lowered
    )


class AcquisitionBoundaryTripwireV0:
    """Patch forbidden seams, count every attempted crossing, and abort at once."""

    def __init__(self) -> None:
        self._counts = {
            "external_network_attempts": 0,
            "credential_access_attempts": 0,
            "live_provider_calls": 0,
            "provider_sdk_calls": 0,
            "model_executions": 0,
            "tool_calls": 0,
            "canonical_application_calls": 0,
        }
        self._hits: list[AcquisitionBoundaryHitV0] = []
        self._patchers: list[Any] = []
        self._token: Optional[contextvars.Token[Optional[AcquisitionBoundaryTripwireV0]]] = None

    @property
    def active(self) -> bool:
        return _ACTIVE_TRIPWIRE.get() is self

    @property
    def hits(self) -> tuple[AcquisitionBoundaryHitV0, ...]:
        return tuple(self._hits)

    def snapshot(self) -> AcquisitionBoundaryTripwireSnapshotV0:
        return AcquisitionBoundaryTripwireSnapshotV0(
            **self._counts,
            hits=tuple(self._hits),
        )

    def _abort(self, category: str, seam: str) -> None:
        self._counts[category] += 1
        hit = AcquisitionBoundaryHitV0(
            ordinal=len(self._hits) + 1,
            category=category,
            seam=seam,
        )
        self._hits.append(hit)
        raise AcquisitionBoundaryViolation(
            f"forbidden acquisition boundary crossed: {category}:{seam}"
        )

    def _forbidden(self, category: str, seam: str):
        def fail(*_args: object, **_kwargs: object) -> None:
            self._abort(category, seam)

        return fail

    def _patch(self, target: object, attribute: str, replacement: object) -> None:
        patcher = patch.object(target, attribute, replacement)
        patcher.start()
        self._patchers.append(patcher)

    def _patch_module_attribute(
        self,
        module: ModuleType,
        dotted_owner: Sequence[str],
        attribute: str,
        category: str,
        seam: str,
    ) -> None:
        owner: object = module
        for name in dotted_owner:
            owner = getattr(owner, name)
        if hasattr(owner, attribute):
            self._patch(owner, attribute, self._forbidden(category, seam))

    def _install_network_tripwires(self) -> None:
        original_socket_connect = socket.socket.connect
        original_socket_send = socket.socket.send
        original_socket_sendall = socket.socket.sendall

        def called_from(function_name: str) -> bool:
            frame = sys._getframe(1)
            while frame is not None:
                if frame.f_code.co_name == function_name:
                    return True
                frame = frame.f_back
            return False

        def guarded_socket_connect(
            sock: socket.socket, address: object
        ) -> object:
            # CPython's Windows event loop bootstraps its private wakeup pair
            # through ``socket._fallback_socketpair``.  This is local runtime
            # plumbing, not an acquisition network attempt.
            if called_from("_fallback_socketpair"):
                return original_socket_connect(sock, address)
            self._abort("external_network_attempts", "socket.socket.connect")

        def guarded_socket_send(
            sock: socket.socket, data: object, *args: object, **kwargs: object
        ) -> object:
            if called_from("_write_to_self"):
                return original_socket_send(sock, data, *args, **kwargs)
            self._abort("external_network_attempts", "socket.socket.send")

        def guarded_socket_sendall(
            sock: socket.socket, data: object, *args: object, **kwargs: object
        ) -> object:
            if called_from("_write_to_self"):
                return original_socket_sendall(sock, data, *args, **kwargs)
            self._abort("external_network_attempts", "socket.socket.sendall")

        for owner, attribute, seam in (
            (socket, "create_connection", "socket.create_connection"),
            (socket, "getaddrinfo", "socket.getaddrinfo"),
            (socket.socket, "connect_ex", "socket.socket.connect_ex"),
            (urllib.request, "urlopen", "urllib.request.urlopen"),
            (urllib.request.OpenerDirector, "open", "urllib.request.OpenerDirector.open"),
            (http.client.HTTPConnection, "connect", "http.client.HTTPConnection.connect"),
            (http.client.HTTPConnection, "request", "http.client.HTTPConnection.request"),
            (http.client.HTTPSConnection, "connect", "http.client.HTTPSConnection.connect"),
        ):
            self._patch(
                owner,
                attribute,
                self._forbidden("external_network_attempts", seam),
            )
        self._patch(socket.socket, "connect", guarded_socket_connect)
        self._patch(socket.socket, "send", guarded_socket_send)
        self._patch(socket.socket, "sendall", guarded_socket_sendall)

        optional_http_seams = (
            ("requests.sessions", ("Session",), "request", "requests.Session.request"),
            ("requests.sessions", ("Session",), "send", "requests.Session.send"),
            ("httpx", ("Client",), "request", "httpx.Client.request"),
            ("httpx", ("Client",), "send", "httpx.Client.send"),
            ("httpx", ("AsyncClient",), "request", "httpx.AsyncClient.request"),
            ("httpx", ("AsyncClient",), "send", "httpx.AsyncClient.send"),
            ("aiohttp", ("ClientSession",), "_request", "aiohttp.ClientSession._request"),
        )
        for module_name, owner_path, attribute, seam in optional_http_seams:
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue
            self._patch_module_attribute(
                module,
                owner_path,
                attribute,
                "external_network_attempts",
                seam,
            )

    def _install_credential_tripwires(self) -> None:
        original_getenv = os.getenv
        original_environment_get = type(os.environ).get
        original_environment_getitem = type(os.environ).__getitem__
        original_open = builtins.open
        original_path_open = Path.open
        original_path_read_bytes = Path.read_bytes
        original_path_read_text = Path.read_text

        def getenv(key: object, default: object = None) -> object:
            if _is_secret_environment_key(key):
                self._abort("credential_access_attempts", f"os.getenv:{key}")
            return original_getenv(key, default)

        def environment_get(environment: object, key: object, default: object = None) -> object:
            if _is_secret_environment_key(key):
                self._abort("credential_access_attempts", f"os.environ.get:{key}")
            return original_environment_get(environment, key, default)

        def environment_getitem(environment: object, key: object) -> object:
            if _is_secret_environment_key(key):
                self._abort("credential_access_attempts", f"os.environ.__getitem__:{key}")
            return original_environment_getitem(environment, key)

        def guarded_open(file: object, *args: object, **kwargs: object):
            if _is_credential_path(file):
                self._abort("credential_access_attempts", f"open:{file}")
            return original_open(file, *args, **kwargs)

        def guarded_path_open(path: Path, *args: object, **kwargs: object):
            if _is_credential_path(path):
                self._abort("credential_access_attempts", f"Path.open:{path}")
            return original_path_open(path, *args, **kwargs)

        def guarded_read_bytes(path: Path) -> bytes:
            if _is_credential_path(path):
                self._abort("credential_access_attempts", f"Path.read_bytes:{path}")
            return original_path_read_bytes(path)

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if _is_credential_path(path):
                self._abort("credential_access_attempts", f"Path.read_text:{path}")
            return original_path_read_text(path, *args, **kwargs)

        self._patch(os, "getenv", getenv)
        self._patch(type(os.environ), "get", environment_get)
        self._patch(type(os.environ), "__getitem__", environment_getitem)
        self._patch(builtins, "open", guarded_open)
        self._patch(Path, "open", guarded_path_open)
        self._patch(Path, "read_bytes", guarded_read_bytes)
        self._patch(Path, "read_text", guarded_read_text)

        try:
            keyring = importlib.import_module("keyring")
        except ImportError:
            keyring = None
        if keyring is not None and hasattr(keyring, "get_password"):
            self._patch(
                keyring,
                "get_password",
                self._forbidden("credential_access_attempts", "keyring.get_password"),
            )

    def _install_provider_model_and_ced_tripwires(self) -> None:
        seam_specs = (
            (
                "backend.dialogues.provider_registry",
                ("CouncilProviderRegistry",),
                "run_adapter",
                "live_provider_calls",
                "CouncilProviderRegistry.run_adapter",
            ),
            (
                "backend.dialogues.provider_registry",
                ("CouncilProviderRegistry",),
                "gather_council_round",
                "live_provider_calls",
                "CouncilProviderRegistry.gather_council_round",
            ),
            (
                "backend.dialogues.provider_registry",
                ("BaseProviderAdapter",),
                "generate_agent_move",
                "provider_sdk_calls",
                "BaseProviderAdapter.generate_agent_move",
            ),
            (
                "backend.dialogues.offline_provider_adapter",
                ("OfflineProviderAdapter",),
                "generate_agent_move",
                "provider_sdk_calls",
                "OfflineProviderAdapter.generate_agent_move",
            ),
            (
                "backend.dialogues.offline_provider_adapter",
                ("CannedResponseTransport",),
                "send",
                "provider_sdk_calls",
                "CannedResponseTransport.send",
            ),
            (
                "backend.dialogues.offline_provider_adapter",
                ("ScriptedOfflineTransport",),
                "send",
                "provider_sdk_calls",
                "ScriptedOfflineTransport.send",
            ),
            (
                "backend.dialogues.live_providers",
                ("LiveAnthropicAdapter",),
                "generate_agent_move",
                "model_executions",
                "LiveAnthropicAdapter.generate_agent_move",
            ),
            (
                "backend.dialogues.live_providers",
                ("LiveAnthropicAdapter",),
                "_produce_raw_text",
                "model_executions",
                "LiveAnthropicAdapter._produce_raw_text",
            ),
            (
                "backend.dialogues.openrouter_provider",
                ("OpenRouterProviderAdapter",),
                "generate_agent_move",
                "model_executions",
                "OpenRouterProviderAdapter.generate_agent_move",
            ),
            (
                "backend.dialogues.openrouter_provider",
                ("OpenRouterProviderAdapter",),
                "_request",
                "provider_sdk_calls",
                "OpenRouterProviderAdapter._request",
            ),
            (
                "backend.dialogues.nvidia_nim_provider",
                ("LiveNvidiaNIMAdapter",),
                "generate_agent_move",
                "model_executions",
                "LiveNvidiaNIMAdapter.generate_agent_move",
            ),
            (
                "backend.dialogues.providers",
                ("FakeProvider",),
                "complete",
                "model_executions",
                "FakeProvider.complete",
            ),
            (
                "backend.dialogues.providers",
                ("_UnimplementedProvider",),
                "complete",
                "model_executions",
                "LLMProvider.complete",
            ),
            (
                "backend.dialogues.agent",
                ("SocraticAgent",),
                "execute",
                "model_executions",
                "SocraticAgent.execute",
            ),
            (
                "backend.dialogues.ced_canonical_successor",
                ("CanonicalSuccessorEnvironmentV0",),
                "apply_observation",
                "canonical_application_calls",
                "CanonicalSuccessorEnvironmentV0.apply_observation",
            ),
        )
        for module_name, owner_path, attribute, category, seam in seam_specs:
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue
            self._patch_module_attribute(
                module,
                owner_path,
                attribute,
                category,
                seam,
            )

        for attribute in (
            "Popen",
            "call",
            "check_call",
            "check_output",
            "run",
        ):
            self._patch(
                subprocess,
                attribute,
                self._forbidden("tool_calls", f"subprocess.{attribute}"),
            )

    def __enter__(self) -> "AcquisitionBoundaryTripwireV0":
        if self._token is not None:
            raise RuntimeError("acquisition boundary tripwire is already active")
        self._token = _ACTIVE_TRIPWIRE.set(self)
        try:
            self._install_network_tripwires()
            self._install_credential_tripwires()
            self._install_provider_model_and_ced_tripwires()
        except BaseException:
            self._stop_patches()
            token = self._token
            self._token = None
            if token is not None:
                _ACTIVE_TRIPWIRE.reset(token)
            raise
        return self

    def _stop_patches(self) -> None:
        while self._patchers:
            self._patchers.pop().stop()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self._stop_patches()
        token = self._token
        self._token = None
        if token is not None:
            _ACTIVE_TRIPWIRE.reset(token)
        if self._hits and exc_type is None:
            first = self._hits[0]
            raise AcquisitionBoundaryViolation(
                "acquisition tripwire recorded forbidden attempts; "
                f"first={first.category}:{first.seam} total={len(self._hits)}"
            )
        return False

    def assert_clean(self) -> AcquisitionBoundaryTripwireSnapshotV0:
        if not self.active:
            raise AcquisitionBoundaryViolation(
                "an active acquisition boundary tripwire is required"
            )
        snapshot = self.snapshot()
        if snapshot.total_forbidden_attempts or snapshot.hits:
            raise AcquisitionBoundaryViolation(
                "acquisition boundary tripwire is not clean"
            )
        return snapshot

    def assert_artifact_counters(self, counters: object) -> None:
        snapshot = self.assert_clean()
        names = (
            "external_network_attempts",
            "credential_access_attempts",
            "live_provider_calls",
            "provider_sdk_calls",
            "model_executions",
            "tool_calls",
            "canonical_application_calls",
        )
        actual = {name: getattr(counters, name, None) for name in names}
        observed = {name: getattr(snapshot, name) for name in names}
        if actual != observed:
            raise AcquisitionBoundaryViolation(
                "artifact tripwire counters differ from instrumented boundary "
                f"evidence: artifact={actual!r} observed={observed!r}"
            )


def active_acquisition_boundary_tripwire_v0() -> AcquisitionBoundaryTripwireV0:
    harness = _ACTIVE_TRIPWIRE.get()
    if harness is None or not harness.active:
        raise AcquisitionBoundaryViolation(
            "authoritative acquisition work requires an active boundary tripwire"
        )
    return harness


def require_clean_acquisition_boundary_tripwire_v0() -> AcquisitionBoundaryTripwireSnapshotV0:
    """Return live instrumented evidence; never accept caller-supplied counters."""

    return active_acquisition_boundary_tripwire_v0().assert_clean()


def assert_acquisition_artifact_tripwires_v0(counters: object) -> None:
    """Cross-check an artifact's zero claims against the active instrumentation."""

    active_acquisition_boundary_tripwire_v0().assert_artifact_counters(counters)


__all__ = [
    "AcquisitionBoundaryHitV0",
    "AcquisitionBoundaryTripwireSnapshotV0",
    "AcquisitionBoundaryTripwireV0",
    "AcquisitionBoundaryViolation",
    "active_acquisition_boundary_tripwire_v0",
    "assert_acquisition_artifact_tripwires_v0",
    "require_clean_acquisition_boundary_tripwire_v0",
]
