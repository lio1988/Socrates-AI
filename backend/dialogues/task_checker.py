"""A deterministic checker for ordering tasks stated entirely in the task text.

The only honest route to `SUPPORTED`. Everything else the council can produce is
a model's reading — provably anchored, but still a reading — and a reading is
what `MODEL_ASSERTION` exists to refuse. This module has no model in the loop at
any point: it parses the task itself, under a grammar small enough to write
down, and enumerates exhaustively.

The design rule throughout is **refuse rather than guess**. A task that does not
fit the grammar produces nothing, and nothing is exactly the right answer: the
claim stays unresolved, which is what it was before this file existed. The
failure mode to avoid is a checker that half-understands a task, silently drops
a constraint it could not parse, and reports a "unique" order that is unique
only under the subset it happened to read.

So the completeness guard matters more than the grammar does. Any sentence that
mentions one or two of the entities and does not parse aborts the whole check.
A dropped constraint is the one bug here that would manufacture false support,
and it is cheaper to refuse a task we could have handled than to answer one we
could not.

Scope: single-slot ordering. N named entities, each occupying one position, with
constraints over relative and absolute position. Not a general solver, and not
intended to become one — `EXTERNAL_EVIDENCE` and open-ended reasoning are out of
reach by construction, not by omission.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from .hybrid_epistemic import (
    AnchorSpan,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    VerificationClass,
    VerificationMethod,
    VerificationRecord,
    VerificationResult,
    source_digest,
    stable_id,
)

#: Identity written into every record this module produces. Deliberately not a
#: model id: admissible evidence is never attributable to one.
CHECKER_IDENTITY = "socrates.task_checker/v1"

#: Above this the enumeration stops being free. Eight entities is 40320 orders.
MAX_ENTITIES = 8

_NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8}

Order = Tuple[str, ...]
Constraint = Callable[[Order], bool]


# ── the grammar ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Rule:
    """One parsed constraint: how to test it, and the words it came from."""

    describe: str
    span: str
    test: Constraint


def _before(a: str, b: str) -> Constraint:
    return lambda order: order.index(a) < order.index(b)


def _immediately_before(a: str, b: str) -> Constraint:
    return lambda order: order.index(b) - order.index(a) == 1


def _at(a: str, index: int) -> Constraint:
    return lambda order: order.index(a) == index % len(order)


def _not_at(a: str, index: int) -> Constraint:
    return lambda order: order.index(a) != index % len(order)


def _sentences(text: str) -> List[str]:
    """Split into candidate statements, keeping each one's exact source text.

    Bullets, numbering and newlines are all statement separators here; a task
    that lists its constraints as `* Anna presents before Ben.` must split the
    same way as one that writes them as prose.
    """
    parts = re.split(r"(?<=[.;:])\s+|\n+", text)
    out = []
    for part in parts:
        cleaned = re.sub(r"^\s*(?:[-*•]|\(?\d+[.)])\s*", "", part).strip()
        if cleaned:
            out.append(cleaned)
    return out


def _normalise(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence).strip().rstrip(".;:").strip()


def _parse_sentence(sentence: str, names: Sequence[str]) -> Optional[_Rule]:
    """One sentence to one constraint, or None if it is not one we know."""
    text = _normalise(sentence)
    n = "|".join(re.escape(x) for x in names)
    verb = r"(?:presents?|speaks?|goes|appears?|is scheduled)"

    patterns: Tuple[Tuple[str, Callable[[re.Match], _Rule]], ...] = (
        (rf"^({n})\s+{verb}\s+immediately\s+before\s+({n})$",
         lambda m: _Rule(f"{m[1]} immediately before {m[2]}", text,
                         _immediately_before(m[1], m[2]))),
        (rf"^({n})\s+{verb}\s+immediately\s+after\s+({n})$",
         lambda m: _Rule(f"{m[2]} immediately before {m[1]}", text,
                         _immediately_before(m[2], m[1]))),
        (rf"^({n})\s+{verb}\s+before\s+({n})$",
         lambda m: _Rule(f"{m[1]} before {m[2]}", text, _before(m[1], m[2]))),
        (rf"^({n})\s+{verb}\s+after\s+({n})$",
         lambda m: _Rule(f"{m[2]} before {m[1]}", text, _before(m[2], m[1]))),
        (rf"^({n})\s+(?:is|{verb})\s+last$",
         lambda m: _Rule(f"{m[1]} last", text, _at(m[1], -1))),
        (rf"^({n})\s+(?:is\s+not|does\s+not\s+{verb})\s+last$",
         lambda m: _Rule(f"{m[1]} not last", text, _not_at(m[1], -1))),
        (rf"^({n})\s+(?:is|{verb})\s+first$",
         lambda m: _Rule(f"{m[1]} first", text, _at(m[1], 0))),
        (rf"^({n})\s+(?:is\s+not|does\s+not\s+{verb})\s+first$",
         lambda m: _Rule(f"{m[1]} not first", text, _not_at(m[1], 0))),
    )
    for pattern, build in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return build(match)
    return None


# ── reading the task ─────────────────────────────────────────────────────────

def _roster(text: str) -> Optional[Tuple[str, ...]]:
    """The entity list, from an explicit `A, B, C, and D` enumeration.

    Requiring the list to be written out is the point. Inferring a roster from
    capitalised words would let a stray proper noun quietly join the puzzle.
    """
    match = re.search(
        r"\b([A-Z][a-z]+)((?:,\s*[A-Z][a-z]+)+)\s*,?\s+and\s+([A-Z][a-z]+)\b", text)
    if match is None:
        return None
    middle = re.findall(r"[A-Z][a-z]+", match.group(2))
    names = (match.group(1), *middle, match.group(3))
    if len(set(names)) != len(names):
        return None
    if not 2 <= len(names) <= MAX_ENTITIES:
        return None

    # A stated count that disagrees with the list means we have misread one of
    # them, and guessing which would be exactly the wrong move.
    stated = re.search(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b",
                       text[:match.start()], re.IGNORECASE)
    if stated and _NUMBER_WORDS[stated.group(1).lower()] != len(names):
        return None
    return names


@dataclass(frozen=True)
class TaskCheck:
    """What deterministic enumeration established about the task."""

    roster: Tuple[str, ...]
    rules: Tuple[str, ...]
    spans: Tuple[Tuple[str, int], ...]
    valid_orders: Tuple[Order, ...]

    @property
    def determines_a_unique_order(self) -> bool:
        return len(self.valid_orders) == 1

    @property
    def unique_order(self) -> Optional[Order]:
        return self.valid_orders[0] if self.determines_a_unique_order else None


def check_ordering_task(task_text: str) -> Optional[TaskCheck]:
    """Enumerate a task's valid orders, or refuse.

    Returns None whenever anything is unclear: no explicit roster, a sentence
    mentioning entities that the grammar does not cover, a stated count that
    disagrees with the list. None means "this checker has nothing to say", which
    leaves every claim exactly where it was.
    """
    names = _roster(task_text)
    if names is None:
        return None

    rules: List[_Rule] = []
    for sentence in _sentences(task_text):
        mentioned = [x for x in names if re.search(rf"\b{re.escape(x)}\b", sentence)]
        if not mentioned:
            continue                      # framing, instructions, a question
        if len(mentioned) == len(names):
            continue                      # the roster sentence itself
        rule = _parse_sentence(sentence, names)
        if rule is None:
            # A sentence about the entities that we cannot read. It may be a
            # constraint, and enumerating without it would report a uniqueness
            # that does not hold.
            return None
        rules.append(rule)

    if not rules:
        return None                       # nothing to enumerate against

    spans: List[Tuple[str, int]] = []
    for rule in rules:
        offset = task_text.find(rule.span)
        if offset < 0:
            return None                   # normalisation lost the exact wording
        spans.append((rule.span, offset))

    valid = tuple(order for order in itertools.permutations(names)
                  if all(rule.test(order) for rule in rules))
    return TaskCheck(roster=names, rules=tuple(r.describe for r in rules),
                     spans=tuple(spans), valid_orders=valid)


# ── reading a claim ──────────────────────────────────────────────────────────

def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def order_asserted_by(claim_text: str, roster: Sequence[str],
                      task_text: str = "") -> Optional[Order]:
    """The complete ordering a claim states, or None if it states none clearly.

    Every window of `len(roster)` consecutive name mentions that forms a
    permutation must agree. A claim that lays out one order and then discusses
    a rejected alternative asserts two, and this refuses rather than picking.

    Windows whose wording is lifted verbatim from the task are not assertions.
    A section that opens by quoting "Anna, Ben, Clara, and David — must present"
    has repeated the roster, and reading that as a proposed order would hand out
    support for echoing the question — which, when the roster happens to be
    listed in the answer's order, is exactly the false positive that costs most.
    """
    size = len(roster)
    matches = list(re.finditer(
        r"\b(" + "|".join(re.escape(x) for x in roster) + r")\b", claim_text))
    haystack = _squash(task_text)
    found = set()
    for i in range(len(matches) - size + 1):
        window = matches[i:i + size]
        names = tuple(m.group(0) for m in window)
        if len(set(names)) != size:
            continue
        phrase = _squash(claim_text[window[0].start():window[-1].end()])
        if haystack and phrase in haystack:
            continue                      # the task's own words, quoted back
        found.add(names)
    return found.pop() if len(found) == 1 else None


# ── emitting records ─────────────────────────────────────────────────────────

def deterministic_support(check: TaskCheck, claim_id: str, claim_text: str,
                          task_text: str = "") -> Optional[EvidenceRecord]:
    """Admissible support: the task determines one order and the claim states it.

    `DETERMINISTIC_COMPUTATION`, attributed to this module rather than to any
    seat, so it passes `ADMISSIBLE_EVIDENCE_SOURCES` for the reason that rule
    exists — the computation is reproducible by anyone, from the task alone.
    """
    order = check.unique_order
    if order is None:
        return None
    if order_asserted_by(claim_text, check.roster, task_text) != order:
        return None
    return EvidenceRecord(
        evidence_id=stable_id("ev", claim_id, "checker", "-".join(order)),
        claim_id=claim_id,
        stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity=CHECKER_IDENTITY,
        content=(f"Exhaustive enumeration of {len(check.roster)}! orders under "
                 f"{len(check.rules)} constraints leaves exactly one: "
                 f"{', '.join(order)}."),
        citation="; ".join(text for text, _ in check.spans),
        provenance="deterministic_computation",
    )


def deterministic_refutation(check: TaskCheck, claim_id: str, claim_text: str,
                             task_text: str) -> Optional[VerificationRecord]:
    """The task determines one order and the claim states a different one.

    Carries no `verifier_provider_id`: nothing read this, it was computed.
    """
    order = check.unique_order
    if order is None:
        return None
    asserted = order_asserted_by(claim_text, check.roster, task_text)
    if asserted is None or asserted == order:
        return None
    digest = source_digest(task_text)
    return VerificationRecord(
        verification_id=stable_id("ver", claim_id, "checker", "-".join(asserted)),
        claim_id=claim_id,
        objection_id=None,
        verification_class=VerificationClass.TASK_INTERNAL,
        method=VerificationMethod.TASK_INTERNAL_CHECK,
        authoritative_inputs=tuple(
            AnchorSpan(text=text, offset=offset, source_id="task",
                       source_digest=digest)
            for text, offset in check.spans),
        condition_tested=f"is {', '.join(asserted)} consistent with the constraints?",
        result=VerificationResult.FALSIFIED,
        rationale=(f"The claimed order {', '.join(asserted)} violates the cited "
                   f"constraints; enumeration leaves only {', '.join(order)}."),
        scope="the cited task material only",
        limitations=("Exhaustive over the parsed constraints. It proves the "
                     "claimed order is not among the valid ones; it does not "
                     "judge anything the grammar could not read."),
        provenance="deterministic_computation",
    )
