"""Q7: a bipartite certificate problem generated before anyone was asked it.

Why this question exists.

Q5 and Q6 asked about fairness rules over score vectors. Both are small enough
to hold in the head, and both live in a literature a strong model may have read.
Q7 is deliberately outside that family and outside any literature: the instance
is generated from a seed string by a rule fixed in this file, and the first
candidate meeting eight structural constraints - also fixed in this file, before
any candidate was drawn - is the one used. There is no published answer to
recall, and the constraints were not adjusted afterwards to produce a prettier
instance.

What makes it hard is not arithmetic. A maximum matching on twelve plus twelve
vertices can be found by hand with patience. What cannot be done by patience
alone is *certifying* it: the answer is only worth anything if it comes with a
minimum vertex cover of the same size and a Hall-deficient set, and the
constraints below rule out every shortcut that would make those easy to guess.

The two counterfactuals are the point of the question. One absent edge, when
added, raises the maximum matching by exactly one; one present edge lies in some
maximum matching yet can be deleted without cost. A reader who has conflated

    this edge appears in a maximum matching

with

    this edge is necessary for every maximum matching

will get the second counterfactual wrong, and will get it wrong confidently.

The structural constraints, fixed before candidate selection:

  1. every left vertex has degree >= 2
  2. every right vertex has degree >= 2
  3. the maximum matching cardinality M is 10 or 11
  4. no vertex is unmatched in *every* maximum matching, so the deficiency is
     not pinned to one nameable vertex that could be spotted without work
  5. the smallest Hall-deficient left subset has size >= 4, so no two- or
     three-vertex obstruction can be seen at a glance
  6. at least one absent edge raises M by exactly 1
  7. at least one present edge lies in some maximum matching and can still be
     deleted without reducing M
  8. the graph has more than one maximum matching, so no answer is forced

Nothing in this file computes a certificate for scoring. The key is computed
twice, independently, in scripts/q7_verifier_a_v1.py and
scripts/q7_verifier_b_v1.py, and neither imports the other.
"""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

import scripts.q7_verifier_a_v1 as A
import scripts.q7_verifier_b_v1 as B

Edge = Tuple[str, str]

BASE_SEED_V1 = "SOCRATES_Q7_BLIND_BIPARTITE_CERTIFICATE_V1"

LEFT_V1: Tuple[str, ...] = tuple(f"L{i}" for i in range(1, 13))
RIGHT_V1: Tuple[str, ...] = tuple(f"R{i}" for i in range(1, 13))

#: How far the search may run before the instance is declared unreachable under
#: the declared rule. Fixed in advance so a fruitless search is a reported
#: failure rather than an invitation to loosen a constraint.
MAXIMUM_CANDIDATE_INDEX_V1 = 20000


# ----------------------------------------------------- deterministic bits ---


class _SeedStream:
    """An endless, reproducible byte stream keyed by one candidate seed.

    SHA256(seed || counter) blocks, concatenated. Unbiased small integers come
    from rejection sampling rather than a modulo, so the draw is uniform and the
    stream position depends only on the values drawn.
    """

    def __init__(self, seed: bytes) -> None:
        self._seed = seed
        self._counter = 0
        self._buffer = b""

    def byte(self) -> int:
        if not self._buffer:
            block = hashlib.sha256(
                self._seed + self._counter.to_bytes(4, "big")).digest()
            self._counter += 1
            self._buffer = block
        value, self._buffer = self._buffer[0], self._buffer[1:]
        return value

    def below(self, bound: int) -> int:
        limit = 256 - (256 % bound)
        while True:
            value = self.byte()
            if value < limit:
                return value % bound


def candidate_seed_v1(index: int) -> bytes:
    return hashlib.sha256(f"{BASE_SEED_V1}:{index}".encode("utf-8")).digest()


def generate_candidate_v1(index: int) -> List[Edge]:
    """The fixed edge-generation rule, in three declared stages.

    Stage 1 gives every left vertex two distinct neighbours. Stage 2 repairs any
    right vertex left below degree two. Stage 3 adds between four and eight
    further edges. Minimum degree is therefore structural rather than a matter
    of luck, which is what makes the search over candidates converge at all: a
    uniform 12x12 draw dense enough to keep every degree at two almost never
    leaves a deficiency to find.
    """
    stream = _SeedStream(candidate_seed_v1(index))
    edges: set = set()

    for l_index in range(12):
        chosen: set = set()
        while len(chosen) < 2:
            chosen.add(stream.below(12))
        for r_index in chosen:
            edges.add((l_index, r_index))

    for r_index in range(12):
        while sum(1 for (_l, r) in edges if r == r_index) < 2:
            edges.add((stream.below(12), r_index))

    extra = 4 + stream.below(5)
    added = 0
    while added < extra:
        pair = (stream.below(12), stream.below(12))
        if pair not in edges:
            edges.add(pair)
            added += 1

    return sorted(
        ((LEFT_V1[l], RIGHT_V1[r]) for l, r in edges),
        key=lambda e: (int(e[0][1:]), int(e[1][1:])),
    )


# ------------------------------------------------- the eight constraints ----


def _degrees(edges: Sequence[Edge]) -> Tuple[Dict[str, int], Dict[str, int]]:
    left = {v: 0 for v in LEFT_V1}
    right = {v: 0 for v in RIGHT_V1}
    for l_vertex, r_vertex in edges:
        left[l_vertex] += 1
        right[r_vertex] += 1
    return left, right


def _absent_edges(edges: Sequence[Edge]) -> List[Edge]:
    present = set(edges)
    return [(l, r) for l in LEFT_V1 for r in RIGHT_V1 if (l, r) not in present]


def evaluate_constraints_v1(edges: Sequence[Edge]) -> Dict[str, object]:
    """Every constraint, evaluated in cheap-first order and reported in full."""
    left_degree, right_degree = _degrees(edges)
    report: Dict[str, object] = {
        "c1_left_degree_at_least_two": min(left_degree.values()) >= 2,
        "c2_right_degree_at_least_two": min(right_degree.values()) >= 2,
    }
    if not (report["c1_left_degree_at_least_two"]
            and report["c2_right_degree_at_least_two"]):
        return report

    adjacency = A.build_adjacency_v1(edges, LEFT_V1, RIGHT_V1)
    size = A.matching_size_v1(adjacency, LEFT_V1)
    report["maximum_matching_size"] = size
    report["c3_matching_is_ten_or_eleven"] = size in (10, 11)
    if not report["c3_matching_is_ten_or_eleven"]:
        return report

    # 4. A vertex unmatched in every maximum matching would name the deficiency
    #    outright. Forcing a left vertex into the matching and asking whether M
    #    survives settles it for that vertex.
    always_unmatched = []
    for l_vertex in LEFT_V1:
        matched_somewhere = any(
            A.edge_is_in_some_maximum_matching_v1(adjacency, LEFT_V1, (l_vertex, r))
            for r in adjacency[l_vertex]
        )
        if not matched_somewhere:
            always_unmatched.append(l_vertex)
    report["left_vertices_unmatched_in_every_maximum_matching"] = always_unmatched
    report["c4_no_forced_unmatched_vertex"] = not always_unmatched
    if always_unmatched:
        return report

    # 5. Smallest Hall-deficient left subset, by exhaustive enumeration.
    smallest = None
    for subset_size in range(1, 13):
        for subset in combinations(LEFT_V1, subset_size):
            if len(A.neighbourhood_v1(adjacency, subset)) < subset_size:
                smallest = subset
                break
        if smallest is not None:
            break
    report["smallest_hall_witness"] = list(smallest) if smallest else None
    report["smallest_hall_witness_size"] = len(smallest) if smallest else None
    report["c5_smallest_hall_witness_at_least_four"] = (
        smallest is not None and len(smallest) >= 4)
    if not report["c5_smallest_hall_witness_at_least_four"]:
        return report

    raising = [e for e in _absent_edges(edges)
               if A.matching_size_with_edge_added_v1(adjacency, LEFT_V1, e) == size + 1]
    report["absent_edges_that_raise_m"] = raising
    report["c6_some_absent_edge_raises_m"] = bool(raising)
    if not raising:
        return report

    deletable = [
        e for e in edges
        if A.edge_is_in_some_maximum_matching_v1(adjacency, LEFT_V1, e)
        and A.matching_size_with_edge_deleted_v1(adjacency, LEFT_V1, e) == size
    ]
    report["edges_in_a_maximum_matching_that_are_not_necessary"] = deletable
    report["c7_some_edge_is_used_but_not_necessary"] = bool(deletable)
    if not deletable:
        return report

    report["maximum_matchings_counted_to_three"] = A.count_maximum_matchings_v1(
        adjacency, LEFT_V1, cap=3)
    report["c8_more_than_one_maximum_matching"] = (
        report["maximum_matchings_counted_to_three"] >= 2)
    return report


def satisfies_all_v1(report: Dict[str, object]) -> bool:
    keys = [k for k in report if k.startswith("c") and k[1].isdigit()]
    return len(keys) == 8 and all(report[k] for k in keys)


# ----------------------------------------------------- candidate selection --


def select_instance_v1(maximum_index: int = MAXIMUM_CANDIDATE_INDEX_V1
                       ) -> Dict[str, object]:
    """The first candidate meeting every constraint. No hand-picking anywhere."""
    for index in range(maximum_index):
        edges = generate_candidate_v1(index)
        report = evaluate_constraints_v1(edges)
        if satisfies_all_v1(report):
            return {
                "candidate_index": index,
                "seed_sha256": candidate_seed_v1(index).hex(),
                "edges": edges,
                "graph_sha256": graph_sha256_v1(edges),
                "constraints": report,
            }
    raise RuntimeError(
        f"no candidate below index {maximum_index} satisfies the declared "
        "constraints; the rule or the constraints would have to change, and "
        "that must be a recorded decision rather than a quiet retry"
    )


def graph_sha256_v1(edges: Sequence[Edge]) -> str:
    payload = json.dumps(
        {"left": list(LEFT_V1), "right": list(RIGHT_V1),
         "edges": [list(e) for e in edges]},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ------------------------------------------ the two counterfactual edges ----


def choose_add_edge_v1(edges: Sequence[Edge]) -> Edge:
    """Lexicographically first absent edge whose addition raises M by one."""
    adjacency = A.build_adjacency_v1(edges, LEFT_V1, RIGHT_V1)
    size = A.matching_size_v1(adjacency, LEFT_V1)
    for candidate in _absent_edges(edges):
        if A.matching_size_with_edge_added_v1(
                adjacency, LEFT_V1, candidate) == size + 1:
            return candidate
    raise RuntimeError("no absent edge raises the maximum matching")


def choose_delete_edge_v1(edges: Sequence[Edge]) -> Edge:
    """Lexicographically first present edge that is used but not necessary."""
    adjacency = A.build_adjacency_v1(edges, LEFT_V1, RIGHT_V1)
    size = A.matching_size_v1(adjacency, LEFT_V1)
    for candidate in edges:
        if (A.edge_is_in_some_maximum_matching_v1(adjacency, LEFT_V1, candidate)
                and A.matching_size_with_edge_deleted_v1(
                    adjacency, LEFT_V1, candidate) == size):
            return candidate
    raise RuntimeError("every edge of a maximum matching is necessary")


# =========================================================== frozen instance ==
# Everything below is the selected candidate, written out as literals so the
# question has a fixed identity that does not depend on running a search. The
# search is still run in verify_key_v1, and a literal that stops matching it is
# a failure rather than a silent update.

CANDIDATE_INDEX_V1 = 28
SEED_SHA256_V1 = "4c4d9a061bbaf2e59665b9cfd716ce34cfd8478cfbaa2ad641f3be97e700b36b"
GRAPH_SHA256_V1 = "9c6ac03b689c231e5ed1505db05010efb698d3b25581679e537e96c54e0809f0"

EDGES_V1: Tuple[Edge, ...] = (
    ("L1", "R10"), ("L1", "R12"),
    ("L2", "R6"), ("L2", "R10"),
    ("L3", "R1"), ("L3", "R9"),
    ("L4", "R2"), ("L4", "R3"),
    ("L5", "R2"), ("L5", "R3"), ("L5", "R6"), ("L5", "R11"),
    ("L6", "R5"), ("L6", "R10"),
    ("L7", "R2"), ("L7", "R4"), ("L7", "R6"), ("L7", "R9"),
    ("L8", "R2"), ("L8", "R3"), ("L8", "R7"), ("L8", "R8"), ("L8", "R11"),
    ("L9", "R1"), ("L9", "R10"),
    ("L10", "R4"), ("L10", "R7"), ("L10", "R8"),
    ("L11", "R5"), ("L11", "R9"), ("L11", "R10"), ("L11", "R12"),
    ("L12", "R6"), ("L12", "R10"),
)

ADD_EDGE_V1: Edge = ("L1", "R2")
DELETE_EDGE_V1: Edge = ("L1", "R10")


# ------------------------------------------------------------- the key -------
# EVALUATOR-ONLY. Never sent to any model, and never used to repair an answer.

ANSWER_KEY_V1: Dict[str, object] = {
    "maximum_matching_size": 11,
    "minimum_vertex_cover_size": 11,
    "hall_deficiency": 1,
    "smallest_hall_witness_size": 7,
    "smallest_hall_witness": ["L1", "L2", "L3", "L6", "L9", "L11", "L12"],
    "smallest_hall_witness_neighbourhood": ["R1", "R5", "R6", "R9", "R10", "R12"],
    "add_edge_new_maximum_matching_size": 12,
    "delete_edge_new_maximum_matching_size": 11,
    "delete_edge_is_in_some_maximum_matching": True,
    "delete_edge_is_necessary_for_every_maximum_matching": False,
}

WHY_THE_DELETE_EDGE_IS_THE_TRAP_V1 = (
    "L1-R10 lies in some maximum matching, and the question says so, which is "
    "exactly the premise a careless reader converts into necessity. It is not "
    "necessary: L1 also reaches R12, and there is a maximum matching of the "
    "same size that uses L1-R12 instead. Deleting L1-R10 therefore costs "
    "nothing. An edge is necessary only when deleting it drops M, and no amount "
    "of exhibiting one maximum matching that uses an edge can establish that."
)

WHY_M_IS_ELEVEN_V1 = (
    "The seven left vertices L1, L2, L3, L6, L9, L11, L12 have between them "
    "only the six right neighbours R1, R5, R6, R9, R10, R12, so at least one of "
    "the seven goes unmatched and M is at most 11. A matching of size 11 is "
    "exhibited, so M is exactly 11. The same fact appears as a vertex cover of "
    "size 11, which by Konig's theorem certifies the matching without any "
    "appeal to how hard one looked for a bigger one."
)


# ------------------------------------------------------------ the question ---

QUESTION_V1 = """Q7 - Blind Bipartite Certificate Problem

You are given a bipartite graph G=(L,R,E).

LEFT:
L1 L2 L3 L4 L5 L6 L7 L8 L9 L10 L11 L12

RIGHT:
R1 R2 R3 R4 R5 R6 R7 R8 R9 R10 R11 R12

EDGES (given as the neighbour list of each left vertex):
L1: R10, R12
L2: R6, R10
L3: R1, R9
L4: R2, R3
L5: R2, R3, R6, R11
L6: R5, R10
L7: R2, R4, R6, R9
L8: R2, R3, R7, R8, R11
L9: R1, R10
L10: R4, R7, R8
L11: R5, R9, R10, R12
L12: R6, R10

Let M denote the cardinality of a maximum matching.

Answer ALL of the following.

1. What is the exact value of M?

2. Give one explicit maximum matching.

3. Give one explicit minimum vertex cover.

4. Give a Hall-deficiency witness:
   a subset S of LEFT vertices for which |N(S)| < |S|.
   State S, N(S), and the deficiency |S|-|N(S)|.

5. Consider adding this currently absent edge:

   L1-R2

   Does the maximum matching cardinality change?
   Give the new cardinality and a concrete certificate/witness.

6. Consider the ORIGINAL graph again and delete this existing edge:

   L1-R10

   This edge belongs to at least one maximum matching.
   Does deleting it reduce the maximum matching cardinality?
   Give the resulting cardinality and a concrete certificate.

7. Explain concisely why your maximum-matching and minimum-cover claims certify
   optimality. Distinguish:

   "an edge appears in a maximum matching"

   from

   "that edge is necessary for every maximum matching."

Do not give hidden chain-of-thought.
Give explicit checkable certificates and a concise explanation.

Finish with:

ANSWER_CERTIFICATE

M = ...
MATCHING = ...
MIN_VERTEX_COVER = ...
HALL_SET = ...
HALL_NEIGHBORHOOD = ...
HALL_DEFICIENCY = ...
ADD_EDGE_NEW_M = ...
ADD_EDGE_CERTIFICATE = ...
DELETE_EDGE_NEW_M = ...
DELETE_EDGE_CERTIFICATE = ..."""

QUESTION_SHA256_V1 = hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest()


# ------------------------------------------------------------- the rubric ----

CRITERIA_V1: Tuple[Tuple[str, str, int], ...] = (
    ("exact_m", "gives M = 11 exactly", 4),
    ("valid_maximum_matching",
     "supplies an explicit matching of size 11 that is a matching of this graph", 6),
    ("valid_minimum_vertex_cover",
     "supplies an explicit vertex cover of size 11 that covers every edge", 6),
    ("correct_hall_witness",
     "supplies a left subset S with |N(S)| < |S|, states N(S) exactly, and gives "
     "the deficiency", 6),
    ("add_edge_counterfactual",
     "states that adding L1-R2 raises the maximum matching to 12 and gives a "
     "checkable witness", 5),
    ("delete_edge_counterfactual",
     "states that deleting L1-R10 leaves the maximum matching at 11 and gives a "
     "checkable witness", 5),
    ("optimality_explanation",
     "connects the matching to the cover or to the Hall obstruction without "
     "circular reasoning", 5),
    ("used_versus_necessary",
     "distinguishes an edge appearing in some maximum matching from an edge "
     "necessary for every maximum matching", 2),
    ("calibration",
     "claims no certificate it did not actually supply", 1),
)

MAXIMUM_SCORE_V1 = sum(points for _n, _d, points in CRITERIA_V1)

#: Criteria 1-6 are machine-verified and authoritative. 7-9 are scored by hand,
#: blind to provider and to whether the answer came from a baseline or the
#: council. No model scores any answer.
MACHINE_VERIFIED_CRITERIA_V1 = tuple(name for name, _d, _p in CRITERIA_V1[:6])
MANUAL_CRITERIA_V1 = tuple(name for name, _d, _p in CRITERIA_V1[6:])

ERROR_FLAGS_V1 = (
    "CLAIMS_A_PERFECT_MATCHING_OF_SIZE_TWELVE",
    "GIVES_A_MATCHING_THAT_REUSES_A_VERTEX",
    "GIVES_A_MATCHING_USING_AN_EDGE_NOT_IN_THE_GRAPH",
    "GIVES_A_VERTEX_COVER_THAT_LEAVES_AN_EDGE_UNCOVERED",
    "GIVES_A_COVER_LARGER_THAN_THE_MATCHING_AND_CALLS_IT_MINIMUM",
    "OFFERS_A_HALL_SET_THAT_IS_NOT_DEFICIENT",
    "MISSTATES_THE_NEIGHBOURHOOD_OF_ITS_OWN_HALL_SET",
    "SAYS_THE_ADDED_EDGE_CHANGES_NOTHING",
    "SAYS_THE_DELETED_EDGE_REDUCES_THE_MATCHING",
    "INFERS_NECESSITY_FROM_APPEARING_IN_A_MAXIMUM_MATCHING",
    "ASSERTS_OPTIMALITY_FROM_SEARCH_EFFORT_RATHER_THAN_A_CERTIFICATE",
)


# --------------------------------------------------------- key self-check ----


def verify_key_v1() -> Dict[str, object]:
    """Re-derive everything, from the seed up, through both verifiers.

    Checks four separate things, because each has failed somewhere in this
    project before: that the frozen literals still match what the declared rule
    generates, that the two verifiers agree, that the key matches both of them,
    and that the published question text matches its digest.
    """
    regenerated = generate_candidate_v1(CANDIDATE_INDEX_V1)
    reproduces = tuple(regenerated) == EDGES_V1
    graph_matches = graph_sha256_v1(list(EDGES_V1)) == GRAPH_SHA256_V1

    edges = list(EDGES_V1)
    a = A.solve_v1(edges, LEFT_V1, RIGHT_V1)
    b = B.solve_v1(edges, LEFT_V1, RIGHT_V1)
    adjacency = A.build_adjacency_v1(edges, LEFT_V1, RIGHT_V1)
    masks = B.adjacency_masks_v1(edges, LEFT_V1, RIGHT_V1)

    compared = ("maximum_matching_size", "minimum_vertex_cover_size",
                "hall_deficiency", "smallest_hall_witness_size")
    verifiers_agree = all(a[field] == b[field] for field in compared)

    add_a = A.matching_size_with_edge_added_v1(adjacency, LEFT_V1, ADD_EDGE_V1)
    add_b = B.matching_size_with_edge_added_v1(masks, LEFT_V1, RIGHT_V1, ADD_EDGE_V1)
    del_a = A.matching_size_with_edge_deleted_v1(adjacency, LEFT_V1, DELETE_EDGE_V1)
    del_b = B.matching_size_with_edge_deleted_v1(masks, LEFT_V1, RIGHT_V1,
                                                 DELETE_EDGE_V1)
    used_a = A.edge_is_in_some_maximum_matching_v1(adjacency, LEFT_V1, DELETE_EDGE_V1)
    used_b = B.edge_is_in_some_maximum_matching_v1(masks, LEFT_V1, RIGHT_V1,
                                                   DELETE_EDGE_V1)
    counterfactuals_agree = (add_a == add_b and del_a == del_b and used_a == used_b)

    key_matches = (
        ANSWER_KEY_V1["maximum_matching_size"] == a["maximum_matching_size"]
        and ANSWER_KEY_V1["minimum_vertex_cover_size"] == a["minimum_vertex_cover_size"]
        and ANSWER_KEY_V1["hall_deficiency"] == a["hall_deficiency"]
        and ANSWER_KEY_V1["smallest_hall_witness_size"] == a["smallest_hall_witness_size"]
        and list(ANSWER_KEY_V1["smallest_hall_witness"]) == a["smallest_hall_witness"]
        and list(ANSWER_KEY_V1["smallest_hall_witness_neighbourhood"])
        == a["smallest_hall_witness_neighbourhood"]
        and ANSWER_KEY_V1["add_edge_new_maximum_matching_size"] == add_a
        and ANSWER_KEY_V1["delete_edge_new_maximum_matching_size"] == del_a
        and ANSWER_KEY_V1["delete_edge_is_in_some_maximum_matching"] is used_a
        and ANSWER_KEY_V1["delete_edge_is_necessary_for_every_maximum_matching"]
        is (del_a < a["maximum_matching_size"])
    )

    question_matches = (
        hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest() == QUESTION_SHA256_V1)
    constraints = evaluate_constraints_v1(edges)

    return {
        "candidate_reproduces_from_the_seed": reproduces,
        "graph_sha256_matches": graph_matches,
        "verifiers_agree": verifiers_agree,
        "counterfactuals_agree": counterfactuals_agree,
        "key_matches_both_verifiers": key_matches,
        "question_matches_its_digest": question_matches,
        "all_eight_constraints_hold": satisfies_all_v1(constraints),
        "verifier_a": a,
        "verifier_b": b,
        "key_is_sound": bool(
            reproduces and graph_matches and verifiers_agree
            and counterfactuals_agree and key_matches and question_matches
            and satisfies_all_v1(constraints)
        ),
    }


if __name__ == "__main__":
    instance = select_instance_v1()
    add_edge = choose_add_edge_v1(instance["edges"])
    delete_edge = choose_delete_edge_v1(instance["edges"])
    print(f"candidate_index : {instance['candidate_index']}")
    print(f"seed_sha256     : {instance['seed_sha256']}")
    print(f"graph_sha256    : {instance['graph_sha256']}")
    print(f"edges           : {len(instance['edges'])}")
    print(f"ADD_EDGE        : {add_edge[0]}-{add_edge[1]}")
    print(f"DELETE_EDGE     : {delete_edge[0]}-{delete_edge[1]}")
    print(json.dumps(instance["constraints"], indent=2, default=str))
