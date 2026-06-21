"""
Argumentation Framework v0.1 -- Abstract Dung layer (read-only, non-mutating)
============================================================================

A thin, deterministic Abstract Argumentation Framework (Dung 1995) built *over*
the existing :class:`EpistemicGraph`. It computes **grounded** acceptability
labels (IN / OUT / UNDEC) for claims and never mutates graph or claim state.

Scope lock (v0.1):
  * Arguments are CLAIMS ONLY -- ``graph.claims`` excluding REJECTED claims.
    Evidence nodes (``NodeType.EVIDENCE``) and any other non-claim node are
    NOT arguments.
  * Attacks are CLAIM-TO-CLAIM ONLY:
      - ``CONTRADICTS`` -> symmetric attack (both directions),
      - ``FALSIFIES``   -> directed attack (falsifier ``src`` -> falsified ``dst``),
    and ONLY when *both* endpoints are argument (claim) ids. An edge touching a
    non-claim node (e.g. an evidence node) is ignored.
  * ``SUPPORTS`` (and every other edge type) is ignored at the abstract level.
  * Semantics: grounded only (unique, skeptical, deterministic).

These labels are *structural*: they describe defensibility under attack, not the
truth of a claim, and they are independent of the Evidence Layer status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple

from .claim import Claim
from .epistemic_state import EpistemicState
from .epistemic_graph import EpistemicGraph, EdgeType


class ArgLabel(str, Enum):
    IN = "IN"
    OUT = "OUT"
    UNDEC = "UNDEC"


_NOTE = "Abstract argumentation labels are structural, not truth guarantees."

# Only these edge types are treated as attacks at the abstract level.
_SYMMETRIC_ATTACK = EdgeType.CONTRADICTS   # both directions
_DIRECTED_ATTACK = EdgeType.FALSIFIES      # src (falsifier) -> dst (falsified)


@dataclass
class AbstractAF:
    """An abstract AF = (arguments, attacks) extracted from an EpistemicGraph.

    ``arguments`` are sorted claim ids; ``attacks`` is a de-duplicated set of
    ``(attacker, target)`` claim-id pairs. The two index maps are convenience
    look-ups with sorted values.
    """

    arguments: List[str]
    attacks: Set[Tuple[str, str]]
    attackers_by: Dict[str, List[str]] = field(default_factory=dict)
    attacked_by: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ArgumentationLabeling:
    """Read-only result of grounded labeling. Deterministic and JSON-ready."""

    labels: Dict[str, ArgLabel]
    grounded_extension: List[str]
    attackers_by_claim: Dict[str, List[str]]
    attacked_by_claim: Dict[str, List[str]]
    semantics: str = "grounded"
    note: str = _NOTE

    def to_dict(self) -> dict:
        return {
            "semantics": self.semantics,
            "labels": {cid: lbl.value for cid, lbl in self.labels.items()},
            "grounded_extension": list(self.grounded_extension),
            "attackers_by_claim": {k: list(v) for k, v in self.attackers_by_claim.items()},
            "attacked_by_claim": {k: list(v) for k, v in self.attacked_by_claim.items()},
            "note": self.note,
        }


def argument_ids(graph: EpistemicGraph) -> List[str]:
    """Argument set = claim ids excluding REJECTED claims, sorted (deterministic).

    Non-claim nodes (evidence, questions, ...) are never arguments because they
    do not live in ``graph.claims``.
    """
    return sorted(
        cid
        for cid, claim in graph.claims.items()
        if claim.state != EpistemicState.REJECTED
    )


def build_af_from_graph(graph: EpistemicGraph) -> AbstractAF:
    """Build the Abstract AF from the graph applying the v0.1 scope lock.

    Read-only: inspects ``graph.claims`` and ``graph.edges`` and returns a new
    AF object. The graph is never modified.
    """
    args = argument_ids(graph)
    args_set = set(args)

    attacks: Set[Tuple[str, str]] = set()
    for edge in graph.edges.values():
        # Claim-to-claim only: both endpoints must be argument (claim) ids.
        # This drops edges that touch evidence nodes or REJECTED claims.
        if edge.src not in args_set or edge.dst not in args_set:
            continue
        if edge.edge_type == _SYMMETRIC_ATTACK:
            attacks.add((edge.src, edge.dst))
            attacks.add((edge.dst, edge.src))
        elif edge.edge_type == _DIRECTED_ATTACK:
            attacks.add((edge.src, edge.dst))
        # SUPPORTS and all other edge types are ignored in Abstract Dung v0.1.

    attackers_by: Dict[str, Set[str]] = {a: set() for a in args}
    attacked_by: Dict[str, Set[str]] = {a: set() for a in args}
    for attacker, target in attacks:
        attackers_by[target].add(attacker)
        attacked_by[attacker].add(target)

    return AbstractAF(
        arguments=args,
        attacks=attacks,
        attackers_by={a: sorted(attackers_by[a]) for a in args},
        attacked_by={a: sorted(attacked_by[a]) for a in args},
    )


def grounded_labeling(af: AbstractAF) -> ArgumentationLabeling:
    """Compute the grounded labeling via the standard monotone fixpoint.

      IN    : every attacker is OUT  (vacuously true when unattacked)
      OUT   : at least one attacker is IN
      UNDEC : otherwise

    Deterministic: arguments are processed in sorted order and all output lists
    are sorted. Self-attacking and mutually-attacking arguments settle at UNDEC.
    """
    labels: Dict[str, ArgLabel] = {a: ArgLabel.UNDEC for a in af.arguments}

    changed = True
    while changed:
        changed = False
        for a in af.arguments:  # af.arguments is already sorted
            if labels[a] != ArgLabel.UNDEC:
                continue
            attackers = af.attackers_by[a]
            if all(labels[b] == ArgLabel.OUT for b in attackers):
                labels[a] = ArgLabel.IN
                changed = True
            elif any(labels[b] == ArgLabel.IN for b in attackers):
                labels[a] = ArgLabel.OUT
                changed = True

    grounded = [a for a in af.arguments if labels[a] == ArgLabel.IN]
    return ArgumentationLabeling(
        labels={a: labels[a] for a in af.arguments},
        grounded_extension=grounded,
        attackers_by_claim=dict(af.attackers_by),
        attacked_by_claim=dict(af.attacked_by),
    )


def label_graph(graph: EpistemicGraph) -> ArgumentationLabeling:
    """Convenience: build the AF from the graph and return its grounded labeling.

    Pure read-only entry point for callers that just want the labels.
    """
    return grounded_labeling(build_af_from_graph(graph))
