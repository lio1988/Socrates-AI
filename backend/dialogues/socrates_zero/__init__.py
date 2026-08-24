"""Runtime-inert SocratesZero research surface.

Importing this package has no runtime side effects and does not enable search.
It exposes immutable contracts, the explicit fixed-rotation baseline strategy,
and deterministic legal-action machinery. The default CED path remains the
only execution path.
"""

from .contracts import (
    SEARCH_CONTRACT_SCHEMA_VERSION,
    ActionGenerator,
    ActionKind,
    ActionParameter,
    ActionPrior,
    ActionStatistics,
    ActionTargetKind,
    BudgetExceeded,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    MoveHistoryRef,
    ObservationRef,
    PolicyContextEntry,
    PolicyPrior,
    RoleHistoryRef,
    SearchBudget,
    SearchConstitution,
    SearchReceipt,
    SearchResult,
    SearchState,
    SearchStrategy,
    SearchTerminationReason,
    SemanticArtifactRef,
    TerminalStatus,
    ValueEstimator,
    canonical_json,
    stable_contract_id,
    validate_action_references,
)
from .baseline import (
    FIXED_ROTATION_BASELINE_ADAPTER_VERSION,
    FixedRotationBaselineAdapter,
    FixedRotationBaselineStrategy,
)
from .constitution import (
    LEGAL_ACTION_GENERATOR_VERSION,
    LEGAL_ACTION_VOCABULARY_VERSION,
    CEDSearchConstitution,
    DeterministicLegalActionGenerator,
)

SOCRATES_ZERO_ENABLED_ENV = "SOCRATES_ZERO_ENABLED"
SOCRATES_ZERO_DEFAULT_ENABLED = False

__all__ = [
    "SEARCH_CONTRACT_SCHEMA_VERSION",
    "FIXED_ROTATION_BASELINE_ADAPTER_VERSION",
    "LEGAL_ACTION_GENERATOR_VERSION",
    "LEGAL_ACTION_VOCABULARY_VERSION",
    "SOCRATES_ZERO_DEFAULT_ENABLED",
    "SOCRATES_ZERO_ENABLED_ENV",
    "ActionGenerator",
    "ActionKind",
    "ActionParameter",
    "ActionPrior",
    "ActionStatistics",
    "ActionTargetKind",
    "BudgetExceeded",
    "BudgetUsage",
    "ContractValidationError",
    "CEDSearchConstitution",
    "DeterministicLegalActionGenerator",
    "FixedRotationBaselineAdapter",
    "FixedRotationBaselineStrategy",
    "LegalAction",
    "MoveHistoryRef",
    "ObservationRef",
    "PolicyContextEntry",
    "PolicyPrior",
    "RoleHistoryRef",
    "SearchBudget",
    "SearchConstitution",
    "SearchReceipt",
    "SearchResult",
    "SearchState",
    "SearchStrategy",
    "SearchTerminationReason",
    "SemanticArtifactRef",
    "TerminalStatus",
    "ValueEstimator",
    "canonical_json",
    "stable_contract_id",
    "validate_action_references",
]
