"""Machine scoring for Q7, with every partial-credit split fixed in advance.

Criteria 1-6 are decided here and the decision is authoritative. Criteria 7-9
are not scored by any program and not by any model: they are read by hand, with
provider and council identity hidden, and they are the only places where
judgement enters.

The point-splits below were written before a single answer existed. That matters
more than it looks: a split invented after reading the answers is a split chosen
to produce a ranking, and there is no way to tell the two apart afterwards.

Strictness is deliberate. A field that does not parse deterministically earns
nothing for that field, even when a human can see what was meant. The rule is
the one the master task states - no machine credit unless the literal output
supplies enough to validate it - and it applies identically to a baseline sample
and to the council's synthesis.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Sequence, Tuple

import scripts.q7_bipartite_question_v1 as Q
import scripts.q7_verifier_a_v1 as A
import scripts.q7_verifier_b_v1 as B

Edge = Tuple[str, str]

#: Declared before any answer was collected.
POINT_SPLITS_V1: Dict[str, Dict[str, int]] = {
    "exact_m": {"correct_value": 4},
    "valid_maximum_matching": {"is_a_matching": 4, "has_size_eleven": 2},
    "valid_minimum_vertex_cover": {"covers_every_edge": 4, "has_size_eleven": 2},
    "correct_hall_witness": {"subset_is_deficient": 3,
                             "neighbourhood_stated_exactly": 2,
                             "deficiency_value_correct": 1},
    "add_edge_counterfactual": {"correct_new_cardinality": 3,
                                "certificate_validates": 2},
    "delete_edge_counterfactual": {"correct_new_cardinality": 3,
                                   "certificate_validates": 2},
}

_VERTEX = re.compile(r"\b([LR])\s*(\d{1,2})\b", re.IGNORECASE)
_PAIR = re.compile(r"\bL\s*(\d{1,2})\s*(?:-|–|—|,|:|→|->|\s)\s*R\s*(\d{1,2})\b",
                   re.IGNORECASE)


def extract_scored_text_v1(raw: str) -> str:
    """The text a certificate is read from.

    Answers arrive as a JSON envelope whose fields hold the prose, so the
    certificate lives inside a JSON string with escaped newlines. Reading the
    envelope as raw text finds nothing at all - every line anchor fails against
    a literal backslash-n - and scores a correct answer zero. That happened on
    the first pass over the Q7 baselines and is the reason this function exists.

    Every string value in the envelope is concatenated, in key order. Taking one
    named field instead would be a choice about where a certificate is allowed
    to appear, and models place it differently; concatenating everything is the
    rule that does not advantage one layout over another. Nothing here is hidden
    reasoning: it is all returned text.
    """
    text = raw or ""
    try:
        envelope = json.loads(text)
    except (ValueError, TypeError):
        return text
    parts: List[str] = []

    def _walk(node: object) -> None:
        # Recursive, because the council nests its answer one level down under
        # "content" while a baseline puts it at the top. A collector that reads
        # only the top level finds the baseline and misses the council, and
        # scored a correct synthesis zero on the first pass over this run.
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for _key, value in sorted(node.items()):
                _walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                _walk(value)

    _walk(envelope)
    return "\n".join(parts) if parts else text


#: The one relaxation available, and the only one. ANCHORED requires the field
#: to begin a line, which is what the question asked for; UNANCHORED accepts it
#: anywhere on a line, so "Bottom-line: M = 11" counts.
#:
#: Both are reported, never blended. The anchored score is the pre-declared one
#: and stays authoritative. The unanchored score exists because on this run the
#: anchored score turned out to measure formatting: three baselines and two
#: council moves stated a fully correct, machine-checkable certificate in prose
#: and scored zero. Reporting only the first would say those answers were wrong,
#: and they were not.
#:
#: The negative lookbehind matters: an unanchored search for "M =" would
#: otherwise match inside "ADD_EDGE_NEW_M = 12" and read the wrong number.
def _field(text: str, name: str, anchored: bool = True) -> Optional[str]:
    """The literal text after `NAME =`, if present.

    Reads the LAST occurrence, because a model that restates its certificate
    after a correction means the later one. Nothing else is inferred.
    """
    prefix = r"^\s*" if anchored else r"(?<![A-Za-z0-9_])"
    found = None
    pattern = prefix + re.escape(name) + r"\s*=\s*([^\n]*)"
    for match in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
        found = match.group(1).strip()
    return found


def _int_field(text: str, name: str, anchored: bool = True) -> Optional[int]:
    raw = _field(text, name, anchored)
    if raw is None:
        return None
    numbers = re.findall(r"-?\d+", raw)
    if len(numbers) != 1:
        return None            # ambiguous: no credit, by the declared rule
    return int(numbers[0])


def _pairs_field(text: str, name: str, anchored: bool = True) -> Optional[List[Edge]]:
    raw = _field(text, name, anchored)
    if raw is None:
        return None
    pairs = [(f"L{int(l)}", f"R{int(r)}") for l, r in _PAIR.findall(raw)]
    return pairs or None


def _vertices_field(text: str, name: str, side: str,
                    anchored: bool = True) -> Optional[List[str]]:
    raw = _field(text, name, anchored)
    if raw is None:
        return None
    out: List[str] = []
    for letter, number in _VERTEX.findall(raw):
        vertex = f"{letter.upper()}{int(number)}"
        if side == "any" or vertex[0] == side:
            if vertex not in out:
                out.append(vertex)
    return out or None


def parse_certificate_v1(raw: str, anchored: bool = True) -> Dict[str, object]:
    """Everything the answer literally committed to, and nothing more."""
    text = extract_scored_text_v1(raw)
    a = anchored
    return {
        "M": _int_field(text, "M", a),
        "MATCHING": _pairs_field(text, "MATCHING", a),
        "MIN_VERTEX_COVER": _vertices_field(text, "MIN_VERTEX_COVER", "any", a),
        "HALL_SET": _vertices_field(text, "HALL_SET", "L", a),
        "HALL_NEIGHBORHOOD": _vertices_field(text, "HALL_NEIGHBORHOOD", "R", a),
        "HALL_DEFICIENCY": _int_field(text, "HALL_DEFICIENCY", a),
        "ADD_EDGE_NEW_M": _int_field(text, "ADD_EDGE_NEW_M", a),
        "ADD_EDGE_CERTIFICATE": _pairs_field(text, "ADD_EDGE_CERTIFICATE", a),
        "DELETE_EDGE_NEW_M": _int_field(text, "DELETE_EDGE_NEW_M", a),
        "DELETE_EDGE_CERTIFICATE": _pairs_field(text, "DELETE_EDGE_CERTIFICATE", a),
        "has_certificate_block": "ANSWER_CERTIFICATE" in text.upper(),
    }


def _both_agree_matching(edges: Sequence[Edge], pairs: Sequence[Edge]) -> bool:
    adjacency = A.build_adjacency_v1(list(edges), Q.LEFT_V1, Q.RIGHT_V1)
    masks = B.adjacency_masks_v1(list(edges), Q.LEFT_V1, Q.RIGHT_V1)
    left = A.check_matching_v1(adjacency, list(pairs))["is_matching"]
    right = B.check_matching_v1(masks, Q.LEFT_V1, Q.RIGHT_V1,
                                list(pairs))["is_matching"]
    if left != right:
        raise AssertionError("the two verifiers disagree on a matching")
    return bool(left)


def score_v1(raw: str, anchored: bool = True) -> Dict[str, object]:
    """Criteria 1-6 only. 7-9 are added by hand, blind, afterwards."""
    parsed = parse_certificate_v1(raw, anchored)
    edges = list(Q.EDGES_V1)
    adjacency = A.build_adjacency_v1(edges, Q.LEFT_V1, Q.RIGHT_V1)
    masks = B.adjacency_masks_v1(edges, Q.LEFT_V1, Q.RIGHT_V1)
    key = Q.ANSWER_KEY_V1

    detail: Dict[str, Dict[str, object]] = {}
    points = 0

    # 1
    got = parsed["M"] == key["maximum_matching_size"]
    detail["exact_m"] = {"claimed": parsed["M"], "correct": got,
                         "points": POINT_SPLITS_V1["exact_m"]["correct_value"] * got}
    points += detail["exact_m"]["points"]

    # 2
    split = POINT_SPLITS_V1["valid_maximum_matching"]
    pairs = parsed["MATCHING"]
    is_matching = bool(pairs) and _both_agree_matching(edges, pairs)
    right_size = is_matching and len(pairs) == key["maximum_matching_size"]
    earned = split["is_a_matching"] * is_matching + split["has_size_eleven"] * right_size
    detail["valid_maximum_matching"] = {
        "size": len(pairs) if pairs else None, "is_a_matching": is_matching,
        "has_size_eleven": right_size, "points": earned}
    points += earned

    # 3
    split = POINT_SPLITS_V1["valid_minimum_vertex_cover"]
    cover = parsed["MIN_VERTEX_COVER"]
    covers = bool(cover) and A.check_vertex_cover_v1(adjacency, edges, cover)["is_cover"]
    if cover:
        assert covers == B.check_vertex_cover_v1(
            masks, Q.LEFT_V1, Q.RIGHT_V1, cover)["is_cover"]
    right_size = covers and len(set(cover)) == key["minimum_vertex_cover_size"]
    earned = split["covers_every_edge"] * covers + split["has_size_eleven"] * right_size
    detail["valid_minimum_vertex_cover"] = {
        "size": len(set(cover)) if cover else None, "covers_every_edge": covers,
        "has_size_eleven": right_size, "points": earned}
    points += earned

    # 4
    split = POINT_SPLITS_V1["correct_hall_witness"]
    subset = parsed["HALL_SET"]
    checked = (A.check_hall_witness_v1(adjacency, subset, parsed["HALL_NEIGHBORHOOD"])
               if subset else None)
    deficient = bool(checked and checked["is_deficient"])
    exact_neighbourhood = bool(
        deficient and checked.get("claimed_neighbourhood_is_exact") is True)
    deficiency_ok = bool(deficient
                         and parsed["HALL_DEFICIENCY"] == checked["deficiency"])
    earned = (split["subset_is_deficient"] * deficient
              + split["neighbourhood_stated_exactly"] * exact_neighbourhood
              + split["deficiency_value_correct"] * deficiency_ok)
    detail["correct_hall_witness"] = {
        "subset_size": checked["subset_size"] if checked else None,
        "subset_is_deficient": deficient,
        "neighbourhood_stated_exactly": exact_neighbourhood,
        "deficiency_value_correct": deficiency_ok, "points": earned}
    points += earned

    # 5 and 6
    for name, field, cert_field, expected, edge, present in (
        ("add_edge_counterfactual", "ADD_EDGE_NEW_M", "ADD_EDGE_CERTIFICATE",
         key["add_edge_new_maximum_matching_size"], Q.ADD_EDGE_V1, True),
        ("delete_edge_counterfactual", "DELETE_EDGE_NEW_M",
         "DELETE_EDGE_CERTIFICATE",
         key["delete_edge_new_maximum_matching_size"], Q.DELETE_EDGE_V1, False),
    ):
        split = POINT_SPLITS_V1[name]
        value_ok = parsed[field] == expected
        altered = list(edges)
        if present:
            altered = sorted(set(altered) | {edge},
                             key=lambda e: (int(e[0][1:]), int(e[1][1:])))
        else:
            altered = [e for e in altered if e != edge]
        cert = parsed[cert_field]
        cert_ok = bool(cert) and _both_agree_matching(altered, cert) and len(cert) == expected
        earned = (split["correct_new_cardinality"] * value_ok
                  + split["certificate_validates"] * cert_ok)
        detail[name] = {"claimed": parsed[field], "correct_new_cardinality": value_ok,
                        "certificate_validates": cert_ok, "points": earned}
        points += earned

    return {
        "parsed": parsed,
        "machine_detail": detail,
        "machine_points": points,
        "machine_maximum": sum(sum(s.values()) for s in POINT_SPLITS_V1.values()),
        "manual_criteria_pending": list(Q.MANUAL_CRITERIA_V1),
    }
