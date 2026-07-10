"""Final governed self-revision facade with preflighted transactions.

This is the recommended integration surface. It inherits the safe registry-
reloading operations from ``GovernedSelfRevisionSystem`` but wires the
transaction coordinator that enforces causal isolation before any journal or
Identity write.
"""

from __future__ import annotations

from pathlib import Path

from .governed_system import GovernedSelfRevisionSystem as _BaseSystem
from .identity_registry import IdentityRegistry
from .revision_evidence import RevisionEvidenceRegistry
from .revision_registry_governed import SelfRevisionRegistry
from .revision_transaction_governed import SelfRevisionTransactionCoordinator


class GovernedSelfRevisionSystem(_BaseSystem):
    """Single safe integration API for evidence-bound self-revision."""

    @classmethod
    def from_root(cls, root: Path | str) -> "GovernedSelfRevisionSystem":
        root_path = Path(root)
        identity = IdentityRegistry(root_path / "identity")
        evidence = RevisionEvidenceRegistry(root_path / "evidence")
        lifecycle = SelfRevisionRegistry(root_path / "lifecycle")
        transactions = SelfRevisionTransactionCoordinator(
            identity,
            lifecycle,
            root_path / "transactions",
        )
        return cls(identity, evidence, lifecycle, transactions)


__all__ = ["GovernedSelfRevisionSystem"]
