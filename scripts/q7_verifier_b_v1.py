"""Q7 verifier B: bitmask counting, with no augmenting path anywhere in it.

The second of the two Q7 verifiers. It answers the same questions as verifier A
and shares no code and no method with it:

    maximum matching   A searches for augmenting paths;
                       B evaluates a dynamic program over subsets of the right
                       side, which never constructs a path at all.

    minimum cover      A reads it off Konig's alternating tree, so its cover is
                       a by-product of its matching;
                       B minimises |A| + |{r : some edge leaves L\\A}| over all
                       4096 left subsets A, which never mentions a matching.

    Hall witness       A shrinks the alternating-tree witness;
                       B enumerates all 4096 left subsets and takes the smallest
                       deficient one outright.

Because B's cover never touches B's matching, "minimum cover size equals maximum
matching size" is an observation the two halves of this file make separately.
That agreement is real evidence, and it is the reason B is worth writing rather
than trusting one implementation twice.

Nothing is imported from scripts.q7_verifier_a_v1, and nothing here is a copy of
anything there.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

Edge = Tuple[str, str]


def _index_maps(left: Sequence[str], right: Sequence[str]
                ) -> Tuple[Dict[str, int], Dict[str, int]]:
    return ({v: i for i, v in enumerate(left)},
            {v: i for i, v in enumerate(right)})


def adjacency_masks_v1(edges: Iterable[Edge], left: Sequence[str],
                       right: Sequence[str]) -> List[int]:
    """One bitmask of right-vertex indices per left vertex, in left order."""
    left_index, right_index = _index_maps(left, right)
    masks = [0] * len(left)
    for l_vertex, r_vertex in edges:
        if l_vertex not in left_index:
            raise ValueError(f"unknown left vertex {l_vertex!r}")
        if r_vertex not in right_index:
            raise ValueError(f"unknown right vertex {r_vertex!r}")
        masks[left_index[l_vertex]] |= 1 << right_index[r_vertex]
    return masks


# --------------------------------------- maximum matching by subset DP -------


def maximum_matching_size_v1(masks: Sequence[int]) -> int:
    """Largest matching, by dynamic programming over which right vertices are free.

    f(i, free) is the best obtainable from left vertices i onwards while `free`
    is the set of unused right vertices. Every left vertex is either skipped or
    paired with one free neighbour. No path, no augmentation, no ordering
    heuristic: it is an exhaustive evaluation with sharing.
    """
    count = len(masks)

    @lru_cache(maxsize=None)
    def _best(index: int, free: int) -> int:
        if index == count:
            return 0
        best = _best(index + 1, free)
        available = masks[index] & free
        while available:
            bit = available & -available
            available ^= bit
            candidate = 1 + _best(index + 1, free ^ bit)
            if candidate > best:
                best = candidate
        return best

    result = _best(0, (1 << count) - 1)
    _best.cache_clear()
    return result


def one_maximum_matching_v1(masks: Sequence[int], left: Sequence[str],
                            right: Sequence[str]) -> List[Edge]:
    """Rebuild one optimal assignment by following the same recurrence forward."""
    count = len(masks)

    @lru_cache(maxsize=None)
    def _best(index: int, free: int) -> int:
        if index == count:
            return 0
        best = _best(index + 1, free)
        available = masks[index] & free
        while available:
            bit = available & -available
            available ^= bit
            candidate = 1 + _best(index + 1, free ^ bit)
            if candidate > best:
                best = candidate
        return best

    pairs: List[Edge] = []
    free = (1 << count) - 1
    for index in range(count):
        target = _best(index, free)
        if target == _best(index + 1, free):
            continue                     # skipping this left vertex is optimal
        available = masks[index] & free
        while available:
            bit = available & -available
            available ^= bit
            if 1 + _best(index + 1, free ^ bit) == target:
                pairs.append((left[index], right[bit.bit_length() - 1]))
                free ^= bit
                break
    _best.cache_clear()
    return pairs


# ----------------------------- minimum vertex cover by subset minimisation ---


def minimum_vertex_cover_v1(masks: Sequence[int], left: Sequence[str],
                            right: Sequence[str]) -> Tuple[int, List[str]]:
    """Best cover over every choice of which left vertices to buy.

    Fix the left half A of the cover. Then every edge leaving a left vertex
    outside A must be covered on the right, so the right half is forced: it is
    exactly the union of the neighbourhoods of L\\A. Minimising |A| + |forced|
    over all 4096 subsets is therefore exact, and it never asks what a matching
    is.
    """
    count = len(masks)
    best_size: Optional[int] = None
    best_cover: List[str] = []
    for chosen in range(1 << count):
        forced = 0
        for index in range(count):
            if not (chosen >> index) & 1:
                forced |= masks[index]
        size = bin(chosen).count("1") + bin(forced).count("1")
        if best_size is None or size < best_size:
            best_size = size
            best_cover = (
                [left[i] for i in range(count) if (chosen >> i) & 1]
                + [right[j] for j in range(len(right)) if (forced >> j) & 1]
            )
    return int(best_size or 0), best_cover


# ------------------------------------------- Hall deficiency by enumeration --


def hall_report_v1(masks: Sequence[int], left: Sequence[str], right: Sequence[str]
                   ) -> Dict[str, object]:
    """Every left subset, its neighbourhood, and the extremes of the deficiency."""
    count = len(masks)
    max_deficiency = 0
    smallest_witness: Optional[Tuple[int, int]] = None   # (subset bits, size)
    for subset in range(1, 1 << count):
        neighbourhood = 0
        size = 0
        bits = subset
        while bits:
            bit = bits & -bits
            bits ^= bit
            index = bit.bit_length() - 1
            neighbourhood |= masks[index]
            size += 1
        deficiency = size - bin(neighbourhood).count("1")
        if deficiency > max_deficiency:
            max_deficiency = deficiency
        if deficiency > 0:
            if smallest_witness is None or size < smallest_witness[1]:
                smallest_witness = (subset, size)
    witness_vertices: Optional[List[str]] = None
    witness_neighbourhood: Optional[List[str]] = None
    if smallest_witness is not None:
        subset = smallest_witness[0]
        neighbourhood = 0
        witness_vertices = []
        for index in range(count):
            if (subset >> index) & 1:
                witness_vertices.append(left[index])
                neighbourhood |= masks[index]
        witness_neighbourhood = [right[j] for j in range(len(right))
                                 if (neighbourhood >> j) & 1]
    return {
        "maximum_deficiency": max_deficiency,
        "smallest_witness": witness_vertices,
        "smallest_witness_neighbourhood": witness_neighbourhood,
        "smallest_witness_size": (
            smallest_witness[1] if smallest_witness is not None else None),
    }


# ------------------------------------------------------- counterfactuals ----


def _with_edge(masks: Sequence[int], left: Sequence[str], right: Sequence[str],
               edge: Edge, present: bool) -> List[int]:
    left_index, right_index = _index_maps(left, right)
    l_vertex, r_vertex = edge
    bit = 1 << right_index[r_vertex]
    out = list(masks)
    index = left_index[l_vertex]
    if present:
        out[index] |= bit
    else:
        out[index] &= ~bit
    return out


def matching_size_with_edge_added_v1(masks: Sequence[int], left: Sequence[str],
                                     right: Sequence[str], edge: Edge) -> int:
    return maximum_matching_size_v1(_with_edge(masks, left, right, edge, True))


def matching_size_with_edge_deleted_v1(masks: Sequence[int], left: Sequence[str],
                                       right: Sequence[str], edge: Edge) -> int:
    return maximum_matching_size_v1(_with_edge(masks, left, right, edge, False))


def edge_is_in_some_maximum_matching_v1(masks: Sequence[int], left: Sequence[str],
                                        right: Sequence[str], edge: Edge) -> bool:
    """Buy the edge, forbid its two endpoints, and see whether M survives."""
    left_index, right_index = _index_maps(left, right)
    l_index = left_index[edge[0]]
    r_bit = 1 << right_index[edge[1]]
    if not masks[l_index] & r_bit:
        raise ValueError(f"{edge[0]}-{edge[1]} is not an edge")
    reduced = [
        (mask & ~r_bit) if i != l_index else 0
        for i, mask in enumerate(masks)
    ]
    return 1 + maximum_matching_size_v1(reduced) == maximum_matching_size_v1(masks)


# ------------------------------------------------------------- summary ------


def solve_v1(edges: Sequence[Edge], left: Sequence[str],
             right: Sequence[str]) -> Dict[str, object]:
    masks = adjacency_masks_v1(edges, left, right)
    size = maximum_matching_size_v1(masks)
    cover_size, cover = minimum_vertex_cover_v1(masks, left, right)
    hall = hall_report_v1(masks, left, right)
    return {
        "verifier": "B (subset dynamic programming + cover minimisation)",
        "maximum_matching_size": size,
        "maximum_matching": one_maximum_matching_v1(masks, left, right),
        "minimum_vertex_cover": cover,
        "minimum_vertex_cover_size": cover_size,
        "hall_deficiency": len(left) - size,
        "smallest_hall_witness": hall["smallest_witness"],
        "smallest_hall_witness_neighbourhood": hall["smallest_witness_neighbourhood"],
        "smallest_hall_witness_size": hall["smallest_witness_size"],
        "maximum_hall_deficiency": hall["maximum_deficiency"],
    }


# ------------------------------------------- certificate checking on bits ---
#
# A has its own checkers, written over sets of vertex names. These are written
# over the bitmasks, so a claim that slips past one representation still has to
# survive the other. Both are needed: "the two verifiers agree" is only evidence
# if each can independently refuse.


def check_matching_v1(masks: Sequence[int], left: Sequence[str],
                      right: Sequence[str], pairs: Sequence[Edge]
                      ) -> Dict[str, object]:
    left_index, right_index = _index_maps(left, right)
    problems: List[str] = []
    used_left = 0
    used_right = 0
    for l_vertex, r_vertex in pairs:
        if l_vertex not in left_index or r_vertex not in right_index:
            problems.append(f"{l_vertex}-{r_vertex} names a vertex not in the graph")
            continue
        l_bit = 1 << left_index[l_vertex]
        r_bit = 1 << right_index[r_vertex]
        if not masks[left_index[l_vertex]] & r_bit:
            problems.append(f"{l_vertex}-{r_vertex} is not an edge")
        if used_left & l_bit:
            problems.append(f"{l_vertex} is used twice")
        if used_right & r_bit:
            problems.append(f"{r_vertex} is used twice")
        used_left |= l_bit
        used_right |= r_bit
    return {"is_matching": not problems, "size": len(pairs), "problems": problems}


def check_vertex_cover_v1(masks: Sequence[int], left: Sequence[str],
                          right: Sequence[str], cover: Sequence[str]
                          ) -> Dict[str, object]:
    left_index, right_index = _index_maps(left, right)
    cover_left = 0
    cover_right = 0
    for vertex in cover:
        if vertex in left_index:
            cover_left |= 1 << left_index[vertex]
        elif vertex in right_index:
            cover_right |= 1 << right_index[vertex]
        else:
            return {"is_cover": False, "size": len(set(cover)),
                    "uncovered_edges": [f"unknown vertex {vertex}"]}
    uncovered: List[str] = []
    for index, mask in enumerate(masks):
        if (cover_left >> index) & 1:
            continue
        exposed = mask & ~cover_right
        while exposed:
            bit = exposed & -exposed
            exposed ^= bit
            uncovered.append(f"{left[index]}-{right[bit.bit_length() - 1]}")
    return {"is_cover": not uncovered, "size": len(set(cover)),
            "uncovered_edges": uncovered}


def check_hall_witness_v1(masks: Sequence[int], left: Sequence[str],
                          right: Sequence[str], subset: Sequence[str]
                          ) -> Dict[str, object]:
    left_index, _right_index = _index_maps(left, right)
    unknown = sorted(v for v in set(subset) if v not in left_index)
    neighbourhood = 0
    for vertex in set(subset) - set(unknown):
        neighbourhood |= masks[left_index[vertex]]
    size = len(set(subset) - set(unknown))
    neighbourhood_size = bin(neighbourhood).count("1")
    return {
        "unknown_vertices": unknown,
        "subset_size": size,
        "true_neighbourhood": [right[j] for j in range(len(right))
                               if (neighbourhood >> j) & 1],
        "true_neighbourhood_size": neighbourhood_size,
        "deficiency": size - neighbourhood_size,
        "is_deficient": not unknown and neighbourhood_size < size,
    }
