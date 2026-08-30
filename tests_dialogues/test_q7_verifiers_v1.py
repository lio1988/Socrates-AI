"""Both Q7 verifiers must be able to say no, or their agreement means nothing.

Two programs that always answer yes agree perfectly and certify nothing. So most
of what is checked here is refusal: a matching that reuses a vertex, a matching
one short of maximum presented as maximum, a cover with an edge hanging out of
it, a cover bigger than necessary called minimum, a left set that is not
deficient offered as a Hall witness, and both counterfactuals asserted the wrong
way round.

Every negative control is checked against BOTH verifiers, which were written
over different representations - names and sets in A, bitmasks in B - so a claim
that slips past one has to survive the other as well.
"""

from __future__ import annotations

import pytest

import scripts.q7_bipartite_question_v1 as Q
import scripts.q7_verifier_a_v1 as A
import scripts.q7_verifier_b_v1 as B


@pytest.fixture(scope="module")
def instance():
    inst = Q.select_instance_v1()
    inst["add_edge"] = Q.choose_add_edge_v1(inst["edges"])
    inst["delete_edge"] = Q.choose_delete_edge_v1(inst["edges"])
    inst["adjacency"] = A.build_adjacency_v1(inst["edges"], Q.LEFT_V1, Q.RIGHT_V1)
    inst["masks"] = B.adjacency_masks_v1(inst["edges"], Q.LEFT_V1, Q.RIGHT_V1)
    inst["a"] = A.solve_v1(inst["edges"], Q.LEFT_V1, Q.RIGHT_V1)
    inst["b"] = B.solve_v1(inst["edges"], Q.LEFT_V1, Q.RIGHT_V1)
    return inst


# ------------------------------------------------- the instance is frozen ---


def test_the_selected_candidate_is_reproducible(instance):
    """Same seed, same rule, same graph - or the benchmark has no identity."""
    assert instance["candidate_index"] == 28
    assert instance["graph_sha256"] == (
        "9c6ac03b689c231e5ed1505db05010efb698d3b25581679e537e96c54e0809f0")
    assert len(instance["edges"]) == 34
    assert Q.generate_candidate_v1(28) == instance["edges"]


def test_no_earlier_candidate_would_have_done(instance):
    """The first satisfying candidate, not a chosen one."""
    for index in range(instance["candidate_index"]):
        report = Q.evaluate_constraints_v1(Q.generate_candidate_v1(index))
        assert not Q.satisfies_all_v1(report), (
            f"candidate {index} also qualifies, so 28 was not the first"
        )


def test_all_eight_declared_constraints_hold(instance):
    report = instance["constraints"]
    declared = [k for k in report if k.startswith("c") and k[1].isdigit()]
    assert len(declared) == 8
    assert all(report[k] for k in declared)
    assert report["maximum_matching_size"] == 11
    assert report["smallest_hall_witness_size"] >= 4


def test_the_counterfactual_edges_follow_their_stated_rules(instance):
    add_edge, delete_edge = instance["add_edge"], instance["delete_edge"]
    present = set(instance["edges"])
    assert add_edge not in present
    assert delete_edge in present
    # Lexicographically first, on the stated orderings.
    absent = [(l, r) for l in Q.LEFT_V1 for r in Q.RIGHT_V1 if (l, r) not in present]
    raising = [e for e in absent
               if A.matching_size_with_edge_added_v1(instance["adjacency"],
                                                     Q.LEFT_V1, e) == 12]
    assert raising[0] == add_edge
    usable = [e for e in instance["edges"]
              if A.edge_is_in_some_maximum_matching_v1(instance["adjacency"],
                                                       Q.LEFT_V1, e)
              and A.matching_size_with_edge_deleted_v1(instance["adjacency"],
                                                       Q.LEFT_V1, e) == 11]
    assert usable[0] == delete_edge


# ----------------------------------------------------- the two agree --------


def test_the_verifiers_agree_on_every_figure(instance):
    a, b = instance["a"], instance["b"]
    for field in ("maximum_matching_size", "minimum_vertex_cover_size",
                  "hall_deficiency", "smallest_hall_witness_size"):
        assert a[field] == b[field], field
    assert a["maximum_matching_size"] == 11
    assert a["minimum_vertex_cover_size"] == 11


def test_each_verifier_certificate_survives_the_other(instance):
    adjacency, masks, edges = (instance["adjacency"], instance["masks"],
                               instance["edges"])
    for source in ("a", "b"):
        solved = instance[source]
        assert B.check_matching_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                   solved["maximum_matching"])["is_matching"]
        assert A.check_matching_v1(adjacency,
                                   solved["maximum_matching"])["is_matching"]
        assert len(solved["maximum_matching"]) == 11
        assert A.check_vertex_cover_v1(adjacency, edges,
                                       solved["minimum_vertex_cover"])["is_cover"]
        assert B.check_vertex_cover_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                       solved["minimum_vertex_cover"])["is_cover"]
        assert A.check_hall_witness_v1(
            adjacency, solved["smallest_hall_witness"])["is_deficient"]
        assert B.check_hall_witness_v1(
            masks, Q.LEFT_V1, Q.RIGHT_V1,
            solved["smallest_hall_witness"])["is_deficient"]


def test_the_counterfactuals_agree(instance):
    adjacency, masks = instance["adjacency"], instance["masks"]
    add_edge, delete_edge = instance["add_edge"], instance["delete_edge"]
    assert (A.matching_size_with_edge_added_v1(adjacency, Q.LEFT_V1, add_edge)
            == B.matching_size_with_edge_added_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                                  add_edge) == 12)
    assert (A.matching_size_with_edge_deleted_v1(adjacency, Q.LEFT_V1, delete_edge)
            == B.matching_size_with_edge_deleted_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                                    delete_edge) == 11)
    assert A.edge_is_in_some_maximum_matching_v1(adjacency, Q.LEFT_V1, delete_edge)
    assert B.edge_is_in_some_maximum_matching_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                                 delete_edge)


# --------------------------------------------------- negative controls ------


def test_a_matching_that_reuses_a_vertex_is_rejected(instance):
    good = instance["a"]["maximum_matching"]
    left_vertex, right_vertex = good[0]
    other_right = next(r for l, r in good[1:] if r != right_vertex)
    bad = [(left_vertex, right_vertex), (left_vertex, other_right)] + good[2:]
    assert not A.check_matching_v1(instance["adjacency"], bad)["is_matching"]
    assert not B.check_matching_v1(instance["masks"], Q.LEFT_V1, Q.RIGHT_V1,
                                   bad)["is_matching"]


def test_a_matching_using_a_non_edge_is_rejected(instance):
    present = set(instance["edges"])
    absent = next((l, r) for l in Q.LEFT_V1 for r in Q.RIGHT_V1
                  if (l, r) not in present)
    assert not A.check_matching_v1(instance["adjacency"], [absent])["is_matching"]
    assert not B.check_matching_v1(instance["masks"], Q.LEFT_V1, Q.RIGHT_V1,
                                   [absent])["is_matching"]


def test_a_matching_one_short_of_maximum_is_valid_but_not_maximum(instance):
    """The commonest wrong answer: a real matching, presented as the largest."""
    short = instance["a"]["maximum_matching"][:-1]
    assert A.check_matching_v1(instance["adjacency"], short)["is_matching"]
    assert len(short) == 10
    assert len(short) < instance["a"]["maximum_matching_size"]
    assert len(short) < B.maximum_matching_size_v1(instance["masks"])


def test_an_incomplete_vertex_cover_is_rejected(instance):
    holed = instance["a"]["minimum_vertex_cover"][:-1]
    a_result = A.check_vertex_cover_v1(instance["adjacency"], instance["edges"],
                                       holed)
    b_result = B.check_vertex_cover_v1(instance["masks"], Q.LEFT_V1, Q.RIGHT_V1,
                                       holed)
    assert not a_result["is_cover"] and a_result["uncovered_edges"]
    assert not b_result["is_cover"] and b_result["uncovered_edges"]
    assert set(a_result["uncovered_edges"]) == set(b_result["uncovered_edges"])


def test_an_oversized_cover_is_a_cover_but_not_minimum(instance):
    padded = sorted(set(instance["a"]["minimum_vertex_cover"]) | set(Q.LEFT_V1))
    assert A.check_vertex_cover_v1(instance["adjacency"], instance["edges"],
                                   padded)["is_cover"]
    assert len(padded) > instance["a"]["minimum_vertex_cover_size"]
    assert len(padded) > B.minimum_vertex_cover_v1(instance["masks"], Q.LEFT_V1,
                                                   Q.RIGHT_V1)[0]


def test_a_false_hall_witness_is_rejected(instance):
    """A left set whose neighbourhood is big enough is simply not a witness."""
    witness = instance["a"]["smallest_hall_witness"]
    not_deficient = [v for v in Q.LEFT_V1 if v not in witness][:2]
    assert len(not_deficient) == 2
    a_result = A.check_hall_witness_v1(instance["adjacency"], not_deficient)
    b_result = B.check_hall_witness_v1(instance["masks"], Q.LEFT_V1, Q.RIGHT_V1,
                                       not_deficient)
    assert not a_result["is_deficient"]
    assert not b_result["is_deficient"]
    assert a_result["deficiency"] == b_result["deficiency"] <= 0


def test_a_witness_with_a_misstated_neighbourhood_is_caught(instance):
    witness = instance["a"]["smallest_hall_witness"]
    truth = instance["a"]["smallest_hall_witness_neighbourhood"]
    checked = A.check_hall_witness_v1(instance["adjacency"], witness, truth[:-1])
    assert checked["is_deficient"]
    assert checked["claimed_neighbourhood_is_exact"] is False


def test_the_wrong_add_edge_effect_is_rejected(instance):
    """Claiming the addition changes nothing, when it takes the matching to 12."""
    adjacency, masks = instance["adjacency"], instance["masks"]
    truth_a = A.matching_size_with_edge_added_v1(adjacency, Q.LEFT_V1,
                                                 instance["add_edge"])
    truth_b = B.matching_size_with_edge_added_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                                 instance["add_edge"])
    assert truth_a == truth_b == 12
    assert truth_a != 11, "the wrong answer 'no change' must not validate"


def test_the_wrong_delete_edge_effect_is_rejected(instance):
    """The trap: an edge in a maximum matching is assumed necessary to it."""
    adjacency, masks = instance["adjacency"], instance["masks"]
    truth_a = A.matching_size_with_edge_deleted_v1(adjacency, Q.LEFT_V1,
                                                   instance["delete_edge"])
    truth_b = B.matching_size_with_edge_deleted_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                                   instance["delete_edge"])
    assert truth_a == truth_b == 11
    assert truth_a != 10, "the wrong answer 'M drops to 10' must not validate"
    # And the edge really does occur in a maximum matching, so the trap is live.
    assert A.edge_is_in_some_maximum_matching_v1(adjacency, Q.LEFT_V1,
                                                 instance["delete_edge"])


def test_an_edge_can_be_used_without_being_necessary(instance):
    """The distinction the question is built on, demonstrated on this instance."""
    adjacency = instance["adjacency"]
    edge = instance["delete_edge"]
    assert A.edge_is_in_some_maximum_matching_v1(adjacency, Q.LEFT_V1, edge)
    assert A.matching_size_with_edge_deleted_v1(adjacency, Q.LEFT_V1, edge) == 11
