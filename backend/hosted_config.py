"""The deployment contract, decided from configuration and never from a request.

Two questions decide almost everything about how this application must behave:
is it running on a developer's loopback interface, or is it serving a public
origin? Every earlier guard answered that per request, from the client address
and the URL scheme. That is fine for refusing an individual call and useless for
refusing a *deployment*: a misconfigured public preview would look correct until
the first user typed a credential into plain HTTP.

So the answer is made once, at startup, from explicit environment values, and
the process refuses to start when the combination is unsafe. Nothing here reads
a header, a query string or a body. A caller cannot argue its way into hosted
mode, and cannot argue its way out of one either.

The rules deliberately fail closed and stay small. This is a deployment
contract, not a configuration framework.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Tuple
from urllib.parse import urlsplit


class DeploymentMode(str, Enum):
    """Where this process believes it is running."""

    #: Loopback only. Plain HTTP is acceptable because nothing leaves the host.
    LOCAL_DEVELOPMENT = "local_development"
    #: A real public origin. HTTPS is mandatory and HSTS becomes meaningful.
    HOSTED_PREVIEW = "hosted_preview"


class HostedConfigError(RuntimeError):
    """An unsafe or incoherent deployment configuration.

    Raised at startup so a bad combination never reaches a user. The message
    names the setting, never its value: an origin is harmless, but this class
    also guards settings that could grow to hold something that is not.
    """


ENVIRONMENT_PREFIX = "SOCRATES_"

#: Single-process public-preview defaults. They are not distributed production
#: controls, and the readiness endpoint says so when more than one worker is
#: declared.
DEFAULT_MAX_ACTIVE_BYOK_RUNS_GLOBAL = 2
DEFAULT_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT = 1
DEFAULT_BYOK_PREFLIGHTS_PER_10_MIN = 10
DEFAULT_BYOK_EXECUTIONS_PER_HOUR = 4

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise HostedConfigError(f"{name} must be a boolean flag")


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise HostedConfigError(f"{name} must be a whole number") from None
    if value <= 0:
        raise HostedConfigError(f"{name} must be greater than zero")
    return value


def _normalized_origin(raw: str) -> str:
    """Return an exact ``scheme://host[:port]`` origin, or refuse.

    A wildcard, a path, a query, a fragment or credentials in the authority all
    mean the operator has not actually decided what the origin is, and an origin
    nobody has decided cannot be compared against.
    """
    candidate = raw.strip()
    if not candidate:
        raise HostedConfigError("SOCRATES_PUBLIC_ORIGIN must not be blank")
    if "*" in candidate:
        raise HostedConfigError("SOCRATES_PUBLIC_ORIGIN must not be a wildcard")
    split = urlsplit(candidate)
    if split.scheme not in {"http", "https"}:
        raise HostedConfigError("SOCRATES_PUBLIC_ORIGIN must name http or https")
    if not split.netloc:
        raise HostedConfigError("SOCRATES_PUBLIC_ORIGIN must include a host")
    if split.path not in {"", "/"} or split.query or split.fragment:
        raise HostedConfigError(
            "SOCRATES_PUBLIC_ORIGIN must be an origin, not a URL with a path"
        )
    if "@" in split.netloc:
        raise HostedConfigError("SOCRATES_PUBLIC_ORIGIN must not carry credentials")
    return f"{split.scheme}://{split.netloc}"


@dataclass(frozen=True)
class HostedConfig:
    """What this process is allowed to do, decided once."""

    mode: DeploymentMode
    public_origin: Optional[str]
    enable_byok: bool
    enable_operator_normal_live: bool
    trust_proxy: bool
    trusted_proxy_hosts: Tuple[str, ...]
    workers: int
    run_root: Optional[str]
    max_active_byok_runs_global: int
    max_active_byok_runs_per_client: int
    byok_preflights_per_10_min: int
    byok_executions_per_hour: int

    @property
    def is_hosted(self) -> bool:
        return self.mode is DeploymentMode.HOSTED_PREVIEW

    @property
    def https_required(self) -> bool:
        """Hosted BYOK never travels over plain HTTP."""
        return self.is_hosted

    @property
    def may_emit_hsts(self) -> bool:
        """HSTS is a promise only an HTTPS origin can keep.

        Emitting it from a loopback development server would pin ``localhost``
        to HTTPS in the developer's browser, which is a hard thing to undo and
        an easy thing to do by accident.
        """
        return self.is_hosted and bool(
            self.public_origin and self.public_origin.startswith("https://")
        )

    @property
    def single_process_limits_are_sufficient(self) -> bool:
        """The limiter lives in this process's memory and nowhere else."""
        return self.workers == 1


def load_hosted_config(
    env: Optional[Mapping[str, str]] = None,
) -> HostedConfig:
    """Read and validate the deployment contract, or refuse to start."""

    source: Mapping[str, str] = os.environ if env is None else env

    raw_origin = source.get("SOCRATES_PUBLIC_ORIGIN")
    # Unset means local development. *Set and blank* means an operator meant to
    # declare an origin and did not, and silently demoting that to local
    # development is the kind of quiet fallback this contract exists to refuse.
    if raw_origin is not None and not raw_origin.strip():
        raise HostedConfigError("SOCRATES_PUBLIC_ORIGIN must not be blank")
    has_origin = raw_origin is not None
    public_origin = _normalized_origin(raw_origin) if has_origin else None
    # The declared origin *is* the mode. Nothing about a request can change it.
    mode = (
        DeploymentMode.HOSTED_PREVIEW if has_origin
        else DeploymentMode.LOCAL_DEVELOPMENT
    )

    enable_byok = _flag(source, "SOCRATES_ENABLE_BYOK", True)
    # Operator-funded live spends the operator's money, so a public deployment
    # has to opt into showing it rather than opt out.
    enable_operator = _flag(
        source, "SOCRATES_ENABLE_OPERATOR_NORMAL_LIVE", False
    )
    trust_proxy = _flag(source, "SOCRATES_TRUST_PROXY", False)
    raw_hosts = source.get("SOCRATES_TRUSTED_PROXY_HOSTS", "") or ""
    trusted_hosts = tuple(
        part.strip() for part in raw_hosts.split(",") if part.strip()
    )
    workers = _positive_int(source, "SOCRATES_WORKERS", 1)
    run_root = (source.get("SOCRATES_RUN_ROOT") or "").strip() or None

    config = HostedConfig(
        mode=mode,
        public_origin=public_origin,
        enable_byok=enable_byok,
        enable_operator_normal_live=enable_operator,
        trust_proxy=trust_proxy,
        trusted_proxy_hosts=trusted_hosts,
        workers=workers,
        run_root=run_root,
        max_active_byok_runs_global=_positive_int(
            source,
            "SOCRATES_MAX_ACTIVE_BYOK_RUNS_GLOBAL",
            DEFAULT_MAX_ACTIVE_BYOK_RUNS_GLOBAL,
        ),
        max_active_byok_runs_per_client=_positive_int(
            source,
            "SOCRATES_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT",
            DEFAULT_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT,
        ),
        byok_preflights_per_10_min=_positive_int(
            source,
            "SOCRATES_BYOK_PREFLIGHTS_PER_10_MIN",
            DEFAULT_BYOK_PREFLIGHTS_PER_10_MIN,
        ),
        byok_executions_per_hour=_positive_int(
            source,
            "SOCRATES_BYOK_EXECUTIONS_PER_HOUR",
            DEFAULT_BYOK_EXECUTIONS_PER_HOUR,
        ),
    )
    _refuse_unsafe_combinations(config)
    return config


def _refuse_unsafe_combinations(config: HostedConfig) -> None:
    """Every rule here describes a deployment that would look fine and not be.

    They are startup refusals rather than warnings because each one is a state
    a user could type a credential into before anyone noticed.
    """
    if config.is_hosted and config.enable_byok:
        assert config.public_origin is not None
        if not config.public_origin.startswith("https://"):
            raise HostedConfigError(
                "hosted BYOK requires an https SOCRATES_PUBLIC_ORIGIN"
            )
    if config.trust_proxy and not config.trusted_proxy_hosts:
        # A limiter keyed on a header any caller may set is not a limiter, and
        # proxy trust without a named proxy is exactly that.
        raise HostedConfigError(
            "SOCRATES_TRUST_PROXY requires SOCRATES_TRUSTED_PROXY_HOSTS"
        )
    if config.max_active_byok_runs_per_client > config.max_active_byok_runs_global:
        raise HostedConfigError(
            "per-client active BYOK runs cannot exceed the global cap"
        )


def readiness_report(config: HostedConfig) -> Tuple[str, Tuple[str, ...]]:
    """A finite status plus finite reason codes. Never a path or an identifier.

    Multiple workers are reported rather than refused: the process is genuinely
    able to serve, it simply cannot honour the documented limits, and a reader
    deserves to be told which of those two things is wrong.
    """
    reasons: list[str] = []
    if not config.single_process_limits_are_sufficient:
        reasons.append("in_memory_limits_need_one_worker")
    if config.is_hosted and not config.may_emit_hsts:
        reasons.append("hosted_origin_is_not_https")
    status = "ok" if not reasons else "degraded"
    return status, tuple(reasons)


__all__ = [
    "DEFAULT_BYOK_EXECUTIONS_PER_HOUR",
    "DEFAULT_BYOK_PREFLIGHTS_PER_10_MIN",
    "DEFAULT_MAX_ACTIVE_BYOK_RUNS_GLOBAL",
    "DEFAULT_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT",
    "DeploymentMode",
    "HostedConfig",
    "HostedConfigError",
    "load_hosted_config",
    "readiness_report",
]
