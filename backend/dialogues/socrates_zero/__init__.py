"""SocratesZero research surface.

Importing this package has no runtime side effects and does not enable search.
The default CED path remains the fixed-rotation baseline.
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

SOCRATES_ZERO_ENABLED_ENV = "SOCRATES_ZERO_ENABLED"
SOCRATES_ZERO_DEFAULT_ENABLED = False

__all__ = [
    "SEARCH_CONTRACT_SCHEMA_VERSION",
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
