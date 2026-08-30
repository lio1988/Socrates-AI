"""Thin ordinary-user surfaces over the canonical Socrates CED engine.

``prepare`` is offline and creates no runtime.  ``execute`` and ``run`` require
an explicit confirmation and delegate the dialogue itself to
``CEDOrchestrator.run_registry_session``.
"""

from .planning import (
    DEFAULT_NORMAL_SEATS,
    NormalCallPlan,
    NormalPlanningError,
    derive_normal_call_plan,
    price_normal_call_plan,
)
from .rendering import NormalRenderResult, render_normal_response
from .runtime import (
    DEFAULT_RUN_ROOT,
    DEFAULT_STANDING_CAP_USD,
    NormalAccounting,
    NormalAuthorizationError,
    NormalIntegrityError,
    NormalPreflight,
    NormalResult,
    NormalRunCollisionError,
    NormalRuntime,
    execute,
    prepare,
    run,
)

__all__ = [
    "DEFAULT_NORMAL_SEATS",
    "DEFAULT_RUN_ROOT",
    "DEFAULT_STANDING_CAP_USD",
    "NormalCallPlan",
    "NormalAccounting",
    "NormalAuthorizationError",
    "NormalIntegrityError",
    "NormalPlanningError",
    "NormalPreflight",
    "NormalRenderResult",
    "NormalResult",
    "NormalRunCollisionError",
    "NormalRuntime",
    "derive_normal_call_plan",
    "execute",
    "price_normal_call_plan",
    "prepare",
    "render_normal_response",
    "run",
]
