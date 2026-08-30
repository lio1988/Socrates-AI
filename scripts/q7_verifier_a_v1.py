"""Q7 verifier A: augmenting paths, alternating trees, Konig's construction.

One of two verifiers that must agree before any Q7 figure is trusted or any
model is called. This one is the textbook route: a Hopcroft-Karp style search
for a maximum matching, then a single alternating-tree sweep from the exposed
left vertices, which yields the minimum vertex cover and the Hall-deficient set
as by-products of the same tree.

Verifier B answers the same questions by counting instead of by searching, and
imports nothing from here. The point of keeping them apart is that a benchmark
key computed once, by one program, by one author, has been wrong before in this
project: the first Q6 search compared which score vector won rather than which
proposal won, and returned a confident wrong number that only an independently
established case caught. Two derivations that share a subroutine share its bugs.

Everything here is exact integer combinatorics on a graph of 12 + 12 vertices.
There is no sampling, no tolerance and no heuristic.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

Edge = Tuple[str, str]
Adjacency = Dict[str, List[str]]


# ---------------------------------------------------------------- graph ------


def build_adjacency_v1(edges: Iterable[Edge], left: Sequence[str],
                       right: Sequence[str]) -> Adjacency:
    """Left-keyed adjacency, with every left vertex present even if isolated."""
    adjacency: Adjacency = {vertex: [] for vertex in left}
    right_set = set(right)
    for l_vertex, r_vertex in edges:
        if l_vertex not in adjacency:
            raise ValueError(f"unknown left vertex {l_vertex!r}")
        if r_vertex not in right_set:
            raise ValueError(f"unknown right vertex {r_vertex!r}")
        if r_vertex not in adjacency[l_vertex]:
            adjacency[l_vertex].append(r_vertex)
    for l_vertex in adjacency:
        adjacency[l_vertex].sort(key=_vertex_sort_key)
    return adjacency


def _vertex_sort_key(vertex: str) -> Tuple[str, int]:
    return (vertex[0], int(vertex[1:]))


def neighbourhood_v1(adjacency: Adjacency, subset: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for l_vertex in subset:
        out.update(adjacency[l_vertex])
    return out


# ------------------------------------------------- maximum matching ---------


def maximum_matching_v1(adjacency: Adjacency,
                        left: Sequence[str]) -> Dict[str, str]:
    """Hopcroft-Karp: repeated BFS layering, then a DFS phase along the layers.

    Returns the matching as a left -> right map. Deterministic: the adjacency
    lists are sorted, and the left vertices are processed in the given order, so
    the same graph always yields the same matching.
    """
    match_left: Dict[str, Optional[str]] = {v: None for v in left}
    match_right: Dict[str, Optional[str]] = {}
    for l_vertex in left:
        for r_vertex in adjacency[l_vertex]:
            match_right.setdefault(r_vertex, None)

    INF = float("inf")

    def _bfs() -> bool:
        dist: Dict[Optional[str], float] = {}
        queue: deque = deque()
        for l_vertex in left:
            if match_left[l_vertex] is None:
                dist[l_vertex] = 0
                queue.append(l_vertex)
            else:
                dist[l_vertex] = INF
        dist[None] = INF
        while queue:
            l_vertex = queue.popleft()
            if dist[l_vertex] >= dist[None]:
                continue
            for r_vertex in adjacency[l_vertex]:
                nxt = match_right[r_vertex]
                if dist.get(nxt, INF) == INF:
                    dist[nxt] = dist[l_vertex] + 1
                    if nxt is not None:
                        queue.append(nxt)
        _bfs.dist = dist                      # type: ignore[attr-defined]
        return dist[None] != INF

    def _dfs(l_vertex: str) -> bool:
        dist = _bfs.dist                      # type: ignore[attr-defined]
        for r_vertex in adjacency[l_vertex]:
            nxt = match_right[r_vertex]
            if (dist.get(nxt, INF) == dist[l_vertex] + 1
                    and (nxt is None or _dfs(nxt))):
                match_left[l_vertex] = r_vertex
                match_right[r_vertex] = l_vertex
                return True
        dist[l_vertex] = INF
        return False

    while _bfs():
        for l_vertex in left:
            if match_left[l_vertex] is None:
                _dfs(l_vertex)

    return {l: r for l, r in match_left.items() if r is not None}


def matching_size_v1(adjacency: Adjacency, left: Sequence[str]) -> int:
    return len(maximum_matching_v1(adjacency, left))


# ------------------------------------- alternating tree: cover and Hall ------


def _alternating_reachable_v1(adjacency: Adjacency, left: Sequence[str],
                              matching: Dict[str, str]) -> Tuple[Set[str], Set[str]]:
    """Left and right vertices reachable from exposed left vertices.

    Alternating from an exposed left vertex: unmatched edges go left to right,
    matched edges come back right to left. Nothing here can reach an exposed
    right vertex, because that would be an augmenting path and the matching is
    maximum.
    """
    matched_right_to_left = {r: l for l, r in matching.items()}
    reached_left: Set[str] = {v for v in left if v not in matching}
    reached_right: Set[str] = set()
    frontier = list(reached_left)
    while frontier:
        l_vertex = frontier.pop()
        for r_vertex in adjacency[l_vertex]:
            if r_vertex in reached_right:
                continue
            reached_right.add(r_vertex)
            partner = matched_right_to_left.get(r_vertex)
            if partner is not None and partner not in reached_left:
                reached_left.add(partner)
                frontier.append(partner)
    return reached_left, reached_right


def minimum_vertex_cover_v1(adjacency: Adjacency,
                            left: Sequence[str]) -> Set[str]:
    """Konig: (L not reached) union (R reached) covers every edge, and |cover|=M."""
    matching = maximum_matching_v1(adjacency, left)
    reached_left, reached_right = _alternating_reachable_v1(
        adjacency, left, matching)
    return {v for v in left if v not in reached_left} | reached_right


def hall_witness_v1(adjacency: Adjacency,
                    left: Sequence[str]) -> Optional[Tuple[Set[str], Set[str]]]:
    """A deficient left set from the alternating tree, or None if none exists.

    The left vertices reachable from the exposed ones are exactly a witness:
    their neighbourhood is the reached right set, and it is smaller by the
    number of exposed left vertices. This is a *maximum-deficiency* witness, not
    necessarily a smallest one; the smallest is found by enumeration in
    verifier B and, here, by shrinking.
    """
    matching = maximum_matching_v1(adjacency, left)
    if len(matching) == len(left):
        return None
    reached_left, reached_right = _alternating_reachable_v1(
        adjacency, left, matching)
    return reached_left, reached_right


def smallest_hall_witness_v1(adjacency: Adjacency, left: Sequence[str]
                             ) -> Optional[Tuple[FrozenSet[str], FrozenSet[str]]]:
    """Smallest deficient left set, found by shrinking a maximum-deficiency one.

    Deficiency cannot appear inside a set that is not itself deficient, so a
    smallest witness is searched inside the alternating-tree witness rather than
    over all 4096 subsets. Verifier B does the exhaustive version, and the two
    must return the same *size*.
    """
    witness = hall_witness_v1(adjacency, left)
    if witness is None:
        return None
    candidates, _neighbours = witness
    ordered = sorted(candidates, key=_vertex_sort_key)
    from itertools import combinations
    for size in range(1, len(ordered) + 1):
        for subset in combinations(ordered, size):
            neighbours = neighbourhood_v1(adjacency, subset)
            if len(neighbours) < size:
                return frozenset(subset), frozenset(neighbours)
    return None


# ------------------------------------------------- certificate checking -----


def check_matching_v1(adjacency: Adjacency, pairs: Sequence[Edge]) -> Dict[str, object]:
    """Is this a matching at all, and how big is it? No credit for near-misses."""
    problems: List[str] = []
    seen_left: Set[str] = set()
    seen_right: Set[str] = set()
    for l_vertex, r_vertex in pairs:
        if l_vertex not in adjacency:
            problems.append(f"{l_vertex} is not a left vertex")
            continue
        if r_vertex not in adjacency[l_vertex]:
            problems.append(f"{l_vertex}-{r_vertex} is not an edge of the graph")
        if l_vertex in seen_left:
            problems.append(f"{l_vertex} is matched more than once")
        if r_vertex in seen_right:
            problems.append(f"{r_vertex} is matched more than once")
        seen_left.add(l_vertex)
        seen_right.add(r_vertex)
    return {"is_matching": not problems, "size": len(pairs), "problems": problems}


def check_vertex_cover_v1(adjacency: Adjacency, edges: Sequence[Edge],
                          cover: Sequence[str]) -> Dict[str, object]:
    cover_set = set(cover)
    uncovered = [f"{l}-{r}" for l, r in edges
                 if l not in cover_set and r not in cover_set]
    return {
        "is_cover": not uncovered,
        "size": len(cover_set),
        "uncovered_edges": uncovered,
    }


def check_hall_witness_v1(adjacency: Adjacency, subset: Sequence[str],
                          claimed_neighbourhood: Optional[Sequence[str]] = None,
                          ) -> Dict[str, object]:
    subset_set = set(subset)
    unknown = sorted(v for v in subset_set if v not in adjacency)
    neighbours = neighbourhood_v1(adjacency, subset_set - set(unknown))
    result: Dict[str, object] = {
        "unknown_vertices": unknown,
        "subset_size": len(subset_set),
        "true_neighbourhood": sorted(neighbours, key=_vertex_sort_key),
        "true_neighbourhood_size": len(neighbours),
        "deficiency": len(subset_set) - len(neighbours),
        "is_deficient": not unknown and len(neighbours) < len(subset_set),
    }
    if claimed_neighbourhood is not None:
        result["claimed_neighbourhood_is_exact"] = (
            set(claimed_neighbourhood) == neighbours)
    return result


# ------------------------------------------------------- counterfactuals ----


def matching_size_with_edge_added_v1(adjacency: Adjacency, left: Sequence[str],
                                     edge: Edge) -> int:
    l_vertex, r_vertex = edge
    if r_vertex in adjacency[l_vertex]:
        raise ValueError(f"{l_vertex}-{r_vertex} is already an edge")
    widened = {k: list(v) for k, v in adjacency.items()}
    widened[l_vertex] = sorted(widened[l_vertex] + [r_vertex], key=_vertex_sort_key)
    return matching_size_v1(widened, left)


def matching_size_with_edge_deleted_v1(adjacency: Adjacency, left: Sequence[str],
                                       edge: Edge) -> int:
    l_vertex, r_vertex = edge
    if r_vertex not in adjacency[l_vertex]:
        raise ValueError(f"{l_vertex}-{r_vertex} is not an edge")
    narrowed = {k: list(v) for k, v in adjacency.items()}
    narrowed[l_vertex] = [v for v in narrowed[l_vertex] if v != r_vertex]
    return matching_size_v1(narrowed, left)


def edge_is_in_some_maximum_matching_v1(adjacency: Adjacency, left: Sequence[str],
                                        edge: Edge) -> bool:
    """Force the edge, match the rest, and see whether the total is still M.

    This is the property Q7 asks the models to distinguish from necessity. An
    edge lies in SOME maximum matching exactly when contracting it costs
    nothing; it is necessary for EVERY maximum matching when deleting it costs
    one.
    """
    l_vertex, r_vertex = edge
    if r_vertex not in adjacency[l_vertex]:
        raise ValueError(f"{l_vertex}-{r_vertex} is not an edge")
    remaining_left = [v for v in left if v != l_vertex]
    restricted = {
        v: [r for r in adjacency[v] if r != r_vertex] for v in remaining_left
    }
    return 1 + matching_size_v1(restricted, remaining_left) == matching_size_v1(
        adjacency, left)


def count_maximum_matchings_v1(adjacency: Adjacency, left: Sequence[str],
                               cap: int = 3) -> int:
    """How many maximum matchings there are, counted up to `cap`.

    Only used to confirm the instance is not one where the answer is forced, so
    a cap keeps it cheap.
    """
    target = matching_size_v1(adjacency, left)
    found = 0

    def _recurse(index: int, used_right: Set[str], size: int) -> None:
        nonlocal found
        if found >= cap:
            return
        remaining = len(left) - index
        if size + remaining < target:
            return
        if index == len(left):
            if size == target:
                found += 1
            return
        l_vertex = left[index]
        for r_vertex in adjacency[l_vertex]:
            if r_vertex not in used_right:
                used_right.add(r_vertex)
                _recurse(index + 1, used_right, size + 1)
                used_right.discard(r_vertex)
                if found >= cap:
                    return
        _recurse(index + 1, used_right, size)

    _recurse(0, set(), 0)
    return found


# ------------------------------------------------------------- summary ------


def solve_v1(edges: Sequence[Edge], left: Sequence[str],
             right: Sequence[str]) -> Dict[str, object]:
    adjacency = build_adjacency_v1(edges, left, right)
    matching = maximum_matching_v1(adjacency, left)
    cover = minimum_vertex_cover_v1(adjacency, left)
    smallest = smallest_hall_witness_v1(adjacency, left)
    return {
        "verifier": "A (augmenting paths + Konig alternating tree)",
        "maximum_matching_size": len(matching),
        "maximum_matching": sorted(
            ((l, r) for l, r in matching.items()), key=lambda e: _vertex_sort_key(e[0])),
        "minimum_vertex_cover": sorted(cover, key=_vertex_sort_key),
        "minimum_vertex_cover_size": len(cover),
        "hall_deficiency": len(left) - len(matching),
        "smallest_hall_witness": (
            sorted(smallest[0], key=_vertex_sort_key) if smallest else None),
        "smallest_hall_witness_neighbourhood": (
            sorted(smallest[1], key=_vertex_sort_key) if smallest else None),
        "smallest_hall_witness_size": len(smallest[0]) if smallest else None,
    }
