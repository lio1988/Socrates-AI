"""
Deliberation Tree Search — search as a policy-improvement operator.

The AlphaGo insight, transplanted: the council's one-shot drafts are the raw
policy; blind peer scores are the value estimates; this tree spends a bounded
revision budget on the most promising drafts (UCB selection) so the candidate
pool handed to blind assembly is *at least as strong* as the one-shot pool.

This module is PURE MECHANISM: no LLM calls, no provider access, no network,
no keys. CED orchestrates the actual revision + scoring calls and feeds the
results in; the tree only does selection math and bookkeeping.

Invariants (see docs/deliberation_tree/ARCHITECTURE.md):
  - Scores are the council's REAL peer scores — never fabricated here.
    A draft whose scores all failed stays unscored (own_score=None) and can
    never be reported as the best node.
  - The tree is CED-owned: nothing in it is ever shown to agents.
  - Selection math is deterministic (stable tie-break by node_id).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Default exploration constant for UCB1 selection. With per-session budgets
#: of 1-6 expansions this mostly decides how quickly a second-best draft gets
#: one revision; it is deliberately modest.
DEFAULT_EXPLORATION = 0.5

#: Peer scores live on a 0-10 scale; Q is normalized by this for UCB.
SCORE_SCALE = 10.0


@dataclass
class TreeNode:
    """One synthesis draft in the deliberation tree (identified by draft_id)."""
    node_id: str
    parent_id: Optional[str]
    depth: int                        # 1 = original council draft
    own_score: Optional[float]        # real mean peer score; None = unscored
    expansions: int = 0               # times selected for revision
    visits: int = 0                   # subtree size counted in value_sum
    value_sum: float = 0.0            # own + descendants' real scores
    children: List[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        """Backed-up mean of real scores in this subtree (0.0 when unscored)."""
        return self.value_sum / self.visits if self.visits > 0 else 0.0


class DeliberationTree:
    """Bounded UCB tree over synthesis drafts (flat frontier: every node is
    directly selectable — no descending re-selection at these tiny budgets)."""

    def __init__(self, exploration: float = DEFAULT_EXPLORATION) -> None:
        if exploration < 0:
            raise ValueError(f"exploration must be >= 0, got {exploration!r}")
        self.exploration = float(exploration)
        self.nodes: Dict[str, TreeNode] = {}
        self.total_expansions = 0     # selections made (budget actually spent)

    # ── Construction ─────────────────────────────────────────────────────────

    def add_root_draft(self, draft_id: str, score: Optional[float]) -> TreeNode:
        """Register one original council draft as a depth-1 node."""
        if draft_id in self.nodes:
            raise ValueError(f"duplicate node {draft_id!r}")
        node = TreeNode(node_id=draft_id, parent_id=None, depth=1, own_score=score)
        if score is not None:
            node.visits = 1
            node.value_sum = float(score)
        self.nodes[draft_id] = node
        return node

    def attach(self, parent_id: str, child_id: str,
               score: Optional[float]) -> TreeNode:
        """Add a revision of `parent_id` with its REAL mean peer score (None if
        every peer score failed) and back the score up the ancestor chain."""
        if parent_id not in self.nodes:
            raise KeyError(f"unknown parent {parent_id!r}")
        if child_id in self.nodes:
            raise ValueError(f"duplicate node {child_id!r}")
        parent = self.nodes[parent_id]
        child = TreeNode(node_id=child_id, parent_id=parent_id,
                         depth=parent.depth + 1, own_score=score)
        if score is not None:
            child.visits = 1
            child.value_sum = float(score)
        self.nodes[child_id] = child
        parent.children.append(child_id)
        if score is not None:                      # mean backup (real scores only)
            anc = parent
            while anc is not None:
                anc.visits += 1
                anc.value_sum += float(score)
                anc = self.nodes.get(anc.parent_id) if anc.parent_id else None
        return child

    # ── Selection (UCB1, deterministic) ───────────────────────────────────────

    def _ucb(self, node: TreeNode) -> float:
        q = node.mean_value / SCORE_SCALE
        u = self.exploration * math.sqrt(
            math.log(1.0 + self.total_expansions) / (1.0 + node.expansions))
        return q + u

    def select(self) -> str:
        """Pick the node to revise next: highest UCB, tie-broken by node_id.
        Counts as one expansion of that node (spent even if the revision later
        fails — a repeatedly failing branch must not monopolize selection)."""
        if not self.nodes:
            raise RuntimeError("select() on an empty tree")
        best = min(self.nodes.values(),
                   key=lambda n: (-self._ucb(n), n.node_id))
        best.expansions += 1
        self.total_expansions += 1
        return best.node_id

    # ── Results (mechanical, CED-owned) ───────────────────────────────────────

    def best_node(self) -> Optional[TreeNode]:
        """Highest REAL own score; ties → shallower depth → node_id. Unscored
        nodes can never win (no fabrication)."""
        scored = [n for n in self.nodes.values() if n.own_score is not None]
        if not scored:
            return None
        return min(scored, key=lambda n: (-n.own_score, n.depth, n.node_id))

    def best_root_score(self) -> Optional[float]:
        roots = [n.own_score for n in self.nodes.values()
                 if n.depth == 1 and n.own_score is not None]
        return max(roots) if roots else None

    def amplification_gain(self) -> float:
        """How much the search improved on the one-shot policy: (best revision
        own score) - (best original own score), floored at 0.0 because assembly
        works on a superset pool and can simply ignore weaker revisions."""
        root = self.best_root_score()
        best = self.best_node()
        if root is None or best is None:
            return 0.0
        return max(0.0, float(best.own_score) - float(root))

    def improvement_pairs(
        self, min_margin: float = 1.0,
    ) -> List[Tuple[str, str, float]]:
        """(child_id, parent_id, margin) where a revision beat the draft it
        revised by >= min_margin real peer-score points — future preference
        pairs for the Teacher Loop (train the policy on the search's output)."""
        pairs: List[Tuple[str, str, float]] = []
        for node in sorted(self.nodes.values(), key=lambda n: n.node_id):
            if node.parent_id is None or node.own_score is None:
                continue
            parent = self.nodes[node.parent_id]
            if parent.own_score is None:
                continue
            margin = float(node.own_score) - float(parent.own_score)
            if margin >= min_margin:
                pairs.append((node.node_id, node.parent_id, round(margin, 4)))
        return pairs

    def audit(self) -> Dict[str, Any]:
        """Mechanical summary for the CED-owned audit (hidden from agents)."""
        best = self.best_node()
        return {
            "enabled": True,
            "exploration": self.exploration,
            "node_count": len(self.nodes),
            "root_count": sum(1 for n in self.nodes.values() if n.depth == 1),
            "revision_count": sum(1 for n in self.nodes.values() if n.depth > 1),
            "max_depth": max((n.depth for n in self.nodes.values()), default=0),
            "total_expansions": self.total_expansions,
            "best_draft_id": best.node_id if best else None,
            "best_own_score": round(best.own_score, 4) if best else None,
            "best_root_score": (round(self.best_root_score(), 4)
                                if self.best_root_score() is not None else None),
            "amplification_gain": round(self.amplification_gain(), 4),
            "improvement_pairs": [
                {"child": c, "parent": p, "margin": m}
                for c, p, m in self.improvement_pairs()
            ],
        }
