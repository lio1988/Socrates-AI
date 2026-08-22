"""Deterministic checking for finite, explicitly-constrained tasks.

The only producer of admissible support. Everything else the council makes is a
model's reading — anchored, quotable, and still a reading — which is what
``MODEL_INTERPRETATION`` exists to refuse. Nothing here calls a model.

Three rules the rest of the file is built to keep:

**Parsing is not authority.** A deterministic evaluator is authoritative only
once the task is already an unambiguous machine representation. Getting there is
parsing, and parsing can be wrong. So every ambiguity is fatal to the check
rather than resolved by preference: two readings of a sentence, a sentence about
the entities that no pattern matches, a stated count that disagrees with the
roster. A model may propose a parse; that proposal has no authority here and is
not accepted as input.

**Entity extraction is not relation extraction.** The words
``Anna, Ben, Clara, David`` name four people. They do not say those four present
in that order, and reading them as an ordering would let any text that lists the
roster earn support for the arrangement that happens to match. A candidate order
is recognised only where the task or claim presents one as an ordering — an
explicit frame like "the order is" or "could the order be".

**Three outcomes, never two.** VALID, INVALID and NOT_APPLICABLE are distinct.
Collapsing NOT_APPLICABLE into INVALID would turn "we cannot represent this"
into "this is false", which is the more damaging of the two mistakes and the
easier one to make.

Scope is deliberately small and is not intended to grow into a general prover.
Anything wanting causal interpretation, analogy, intent, legal or scientific
judgement, ordinary semantic entailment, probability or world knowledge is out
of class by construction: it has no finite constraint form, so it never parses,
so it returns NOT_APPLICABLE.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

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

CHECKER_ID = "socrates.task_checker"
CHECKER_VERSION = "v1"
AUTHORITY_CLASS = EvidenceSourceType.DETERMINISTIC_COMPUTATION.value

#: Enumeration budget. Eight entities is 40320 orders; beyond it the answer is
#: RESOURCE_BOUND, never a heuristic shortcut.
MAX_ENTITIES = 8

_NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8}

Order = Tuple[str, ...]
Predicate = Callable[[Order], bool]


class ProblemClass(str, Enum):
    """What the checker recognises. Everything else is out of class."""

    #: N named entities in N ordered slots, under relative and absolute
    #: position constraints: before, after, immediately before/after, first,
    #: last, position N, and exclusions of those.
    FINITE_ORDERING = "finite_ordering"


class CheckerStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"


class NotApplicableReason(str, Enum):
    """Why the checker declined. Never a verdict about the claim."""

    OUT_OF_CLASS = "out_of_class"
    NO_ROSTER = "no_roster"
    COUNT_MISMATCH = "count_mismatch"
    DUPLICATE_ENTITY = "duplicate_entity"
    NO_CONSTRAINTS = "no_constraints"
    UNPARSEABLE_CONSTRAINT = "unparseable_constraint"
    AMBIGUOUS_PARSE = "ambiguous_parse"
    RESOURCE_BOUND = "resource_bound"
    NO_CANDIDATE = "no_candidate"
    AMBIGUOUS_CANDIDATE = "ambiguous_candidate"
    UNSATISFIABLE_TASK = "unsatisfiable_task"


# ── the receipt ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CheckerReceipt:
    """An auditable record of one deterministic evaluation.

    Deliberately not a bare VERIFIED flag. A reader who has the task text can
    replay every field: the entities that were extracted, the constraints they
    were reduced to, what was tested against them, and which of them the
    candidate satisfied or violated. A flag asks to be trusted; this does not.
    """

    result: CheckerStatus
    problem_class: Optional[str] = None
    normalized_entities: Tuple[str, ...] = ()
    normalized_constraints: Tuple[str, ...] = ()
    #: The task's own sentences the constraints were read from, verbatim. The
    #: normalised forms above are the checker's paraphrase; these are what a
    #: reader can look up, and what a refutation anchors to.
    cited_spans: Tuple[str, ...] = ()
    candidate_checked: Optional[str] = None
    violated_constraints: Tuple[str, ...] = ()
    satisfied_constraints: Tuple[str, ...] = ()
    input_digest: str = ""
    reason: Optional[str] = None
    solution_count: Optional[int] = None
    candidate_is_valid: Optional[bool] = None
    candidate_is_invalid: Optional[bool] = None
    candidate_is_unique: Optional[bool] = None
    statement_must_hold: Optional[bool] = None
    statement_could_hold: Optional[bool] = None
    checker_id: str = CHECKER_ID
    checker_version: str = CHECKER_VERSION
    deterministic: bool = True
    authority_class: str = AUTHORITY_CLASS

    @property
    def is_applicable(self) -> bool:
        return self.result is not CheckerStatus.NOT_APPLICABLE

    @property
    def establishes_the_candidate(self) -> bool:
        """May this receipt create support?

        Only when the task *determines* the answer: a candidate order that is
        the only one satisfying the constraints, or a statement true under every
        satisfying assignment. A candidate that merely could hold is consistent
        with the task, which is not the same as established by it.
        """
        if self.result is not CheckerStatus.VALID:
            return False
        return bool(self.candidate_is_unique) or bool(self.statement_must_hold)

    def to_dict(self) -> Dict[str, Any]:
        """Canonical, ordered, JSON-safe. Two runs must produce byte equality."""
        return {
            "checker_id": self.checker_id,
            "checker_version": self.checker_version,
            "problem_class": self.problem_class,
            "normalized_entities": list(self.normalized_entities),
            "normalized_constraints": list(self.normalized_constraints),
            "cited_spans": list(self.cited_spans),
            "candidate_checked": self.candidate_checked,
            "result": self.result.value,
            "violated_constraints": list(self.violated_constraints),
            "satisfied_constraints": list(self.satisfied_constraints),
            "input_digest": self.input_digest,
            "reason": self.reason,
            "solution_count": self.solution_count,
            "candidate_is_valid": self.candidate_is_valid,
            "candidate_is_invalid": self.candidate_is_invalid,
            "candidate_is_unique": self.candidate_is_unique,
            "statement_must_hold": self.statement_must_hold,
            "statement_could_hold": self.statement_could_hold,
            "deterministic": self.deterministic,
            "authority_class": self.authority_class,
        }

    def digest(self) -> str:
        import json
        return source_digest(json.dumps(self.to_dict(), sort_keys=False,
                                        ensure_ascii=False))


def _declined(reason: NotApplicableReason, *, digest: str = "",
              entities: Tuple[str, ...] = (),
              constraints: Tuple[str, ...] = (),
              candidate: Optional[str] = None) -> CheckerReceipt:
    """A receipt for a check that did not happen. Still auditable."""
    return CheckerReceipt(
        result=CheckerStatus.NOT_APPLICABLE, problem_class=None,
        normalized_entities=entities, normalized_constraints=constraints,
        candidate_checked=candidate, input_digest=digest, reason=reason.value)


# ── the grammar ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Rule:
    describe: str
    span: str
    test: Predicate = field(compare=False, repr=False,
                            default=lambda order: True)


def _before(a: str, b: str) -> Predicate:
    return lambda order: order.index(a) < order.index(b)


def _immediately_before(a: str, b: str) -> Predicate:
    return lambda order: order.index(b) - order.index(a) == 1


def _at(a: str, index: int) -> Predicate:
    return lambda order: order.index(a) == index % len(order)


def _not_at(a: str, index: int) -> Predicate:
    return lambda order: order.index(a) != index % len(order)


_ORDINALS = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4,
             "sixth": 5, "seventh": 6, "eighth": 7, "last": -1}

#: Words that make a sentence's constraint content genuinely uncertain. Their
#: presence alongside entities is ambiguity, not an unknown pattern: a
#: conditional or disjunctive constraint has more than one reading and the
#: checker has no way to pick between them.
_AMBIGUITY_MARKERS = (
    "unless", "otherwise", "either", " or ", "if ", "maybe", "perhaps",
    "possibly", "probably", "usually", "typically", "might", "may ", "could ",
    "should", "at least one of", "some of", "prefer", "tends", "likely",
)


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.;:?!])\s+|\n+", text)
    out = []
    for part in parts:
        cleaned = re.sub(r"^\s*(?:[-*•]|\(?\d+[.)])\s*", "", part).strip()
        if cleaned:
            out.append(cleaned)
    return out


def _normalise(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence).strip().rstrip(".;:?!").strip()


def _patterns(names: Sequence[str]) -> Tuple[Tuple[str, Callable[[Any], _Rule]], ...]:
    n = "|".join(re.escape(x) for x in names)
    # The copula belongs here. "Anna is before Ben" states exactly the relation
    # "Anna presents before Ben" states, with the same single reading, and
    # rejecting it was a missing synonym rather than a scope boundary. Every
    # pattern below is anchored end to end, so "is immediately before" cannot
    # also match the plain "before" form.
    verb = (r"(?:is|are|was|were|presents?|speaks?|goes|comes|appears?|"
            r"is scheduled|is placed|is positioned)")
    ordinal = "|".join(_ORDINALS)
    return (
        (rf"^({n})\s+{verb}\s+immediately\s+before\s+({n})$",
         lambda m: _Rule(f"{m[1]} immediately before {m[2]}", "",
                         _immediately_before(m[1], m[2]))),
        (rf"^({n})\s+{verb}\s+immediately\s+after\s+({n})$",
         lambda m: _Rule(f"{m[2]} immediately before {m[1]}", "",
                         _immediately_before(m[2], m[1]))),
        (rf"^({n})\s+{verb}\s+before\s+({n})$",
         lambda m: _Rule(f"{m[1]} before {m[2]}", "", _before(m[1], m[2]))),
        (rf"^({n})\s+{verb}\s+after\s+({n})$",
         lambda m: _Rule(f"{m[2]} before {m[1]}", "", _before(m[2], m[1]))),
        (rf"^({n})\s+(?:is\s+not|does\s+not\s+{verb})\s+({ordinal})$",
         lambda m: _Rule(f"{m[1]} not {m[2].lower()}", "",
                         _not_at(m[1], _ORDINALS[m[2].lower()]))),
        (rf"^({n})\s+(?:is|{verb})\s+({ordinal})$",
         lambda m: _Rule(f"{m[1]} {m[2].lower()}", "",
                         _at(m[1], _ORDINALS[m[2].lower()]))),
        (rf"^({n})\s+(?:is\s+not|does\s+not\s+{verb})\s+in\s+position\s+(\d+)$",
         lambda m: _Rule(f"{m[1]} not position {m[2]}", "",
                         _not_at(m[1], int(m[2]) - 1))),
        (rf"^({n})\s+(?:is|{verb})\s+in\s+position\s+(\d+)$",
         lambda m: _Rule(f"{m[1]} position {m[2]}", "",
                         _at(m[1], int(m[2]) - 1))),
    )


def _parse_constraint(sentence: str, names: Sequence[str]
                      ) -> Tuple[Optional[_Rule], Optional[NotApplicableReason]]:
    """One sentence to one rule, or a reason the checker must decline.

    Two readings is ambiguity and one reading is a parse; zero readings of a
    sentence that talks about the entities is a constraint we cannot see, which
    is just as fatal. Enumerating without it would report a uniqueness that the
    task does not actually have.
    """
    text = _normalise(sentence)
    lowered = f" {text.lower()} "
    if any(marker in lowered for marker in _AMBIGUITY_MARKERS):
        return None, NotApplicableReason.AMBIGUOUS_PARSE

    found: List[_Rule] = []
    for pattern, build in _patterns(names):
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            rule = build(match)
            found.append(_Rule(rule.describe, text, rule.test))
    if not found:
        return None, NotApplicableReason.UNPARSEABLE_CONSTRAINT
    if len({r.describe for r in found}) > 1:
        return None, NotApplicableReason.AMBIGUOUS_PARSE
    return found[0], None


# ── reading the task ─────────────────────────────────────────────────────────

def _roster(text: str) -> Tuple[Optional[Tuple[str, ...]], Optional[NotApplicableReason]]:
    """The entity list, from an explicit `A, B, C, and D` enumeration.

    Requiring it written out is the point. Harvesting capitalised words would
    let a stray proper noun join the puzzle, and the checker would enumerate a
    problem the task never posed.
    """
    match = re.search(
        r"\b([A-Z][a-z]+)((?:,\s*[A-Z][a-z]+)+)\s*,?\s+and\s+([A-Z][a-z]+)\b", text)
    if match is None:
        return None, NotApplicableReason.NO_ROSTER
    middle = re.findall(r"[A-Z][a-z]+", match.group(2))
    names = (match.group(1), *middle, match.group(3))
    if len(set(names)) != len(names):
        return None, NotApplicableReason.DUPLICATE_ENTITY
    if len(names) < 2:
        return None, NotApplicableReason.NO_ROSTER
    if len(names) > MAX_ENTITIES:
        return None, NotApplicableReason.RESOURCE_BOUND

    stated = re.search(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b",
                       text[:match.start()], re.IGNORECASE)
    if stated and _NUMBER_WORDS[stated.group(1).lower()] != len(names):
        return None, NotApplicableReason.COUNT_MISMATCH
    return names, None


@dataclass(frozen=True)
class TaskModel:
    """A task reduced to an unambiguous machine representation."""

    entities: Tuple[str, ...]
    rules: Tuple[_Rule, ...]
    solutions: Tuple[Order, ...]
    digest: str

    @property
    def constraint_names(self) -> Tuple[str, ...]:
        return tuple(r.describe for r in self.rules)

    @property
    def cited_spans(self) -> Tuple[str, ...]:
        return tuple(r.span for r in self.rules)

    @property
    def spans(self) -> Tuple[Tuple[str, int], ...]:
        return tuple((r.span, 0) for r in self.rules)


def model_task(task_text: str) -> Tuple[Optional[TaskModel], Optional[NotApplicableReason]]:
    """Reduce a task to entities, constraints and its full solution set.

    Returns (None, reason) at the first sign that the reduction is not safe.
    """
    names, reason = _roster(task_text)
    if names is None:
        return None, reason

    rules: List[_Rule] = []
    for sentence in _sentences(task_text):
        mentioned = [x for x in names if re.search(rf"\b{re.escape(x)}\b", sentence)]
        if not mentioned:
            continue                            # framing, instructions, question
        if len(mentioned) == len(names):
            continue                            # the roster sentence itself
        rule, why = _parse_constraint(sentence, names)
        if rule is None:
            return None, why
        rules.append(rule)

    if not rules:
        return None, NotApplicableReason.NO_CONSTRAINTS

    solutions = tuple(order for order in itertools.permutations(names)
                      if all(rule.test(order) for rule in rules))
    return TaskModel(entities=names, rules=tuple(rules), solutions=solutions,
                     digest=source_digest(task_text)), None


# ── reading a candidate ──────────────────────────────────────────────────────

_FRAME = re.compile(
    r"\b(?:order|ordering|sequence|arrangement|schedule|ranking|line[-\s]?up|"
    r"permutation)\b[^.;:!?]{0,24}?(?:\bis\b|\bare\b|\bwas\b|\bbe\b|:|=)\s*",
    re.IGNORECASE)

_SEPARATOR = re.compile(
    r"^(?:\s*(?:,|;|and|then|followed\s+by|before|<|-|–|—|→|->)\s*)+",
    re.IGNORECASE)


def _read_run(text: str, roster: Sequence[str]) -> Optional[Order]:
    """Read a run of roster names joined only by ordering separators."""
    names_re = re.compile(r"^(" + "|".join(re.escape(x) for x in roster) + r")\b")
    got: List[str] = []
    cursor = 0
    while len(got) < len(roster):
        match = names_re.match(text[cursor:])
        if match is None:
            break
        got.append(match.group(1))
        cursor += match.end()
        if len(got) == len(roster):
            break
        gap = _SEPARATOR.match(text[cursor:])
        if gap is None:
            break
        cursor += gap.end()
    if len(got) != len(roster) or len(set(got)) != len(roster):
        return None
    return tuple(got)


def candidate_order(text: str, roster: Sequence[str]
                    ) -> Tuple[Optional[Order], Optional[NotApplicableReason]]:
    """The ordering a text explicitly presents as one, or a reason there is none.

    An occurrence of the roster is not an ordering. "Anna, Ben, Clara, David"
    names four people; only a frame — "the order is", "could the sequence be" —
    presents them as an arrangement. Without that this would hand out support to
    any text that happens to list the entities in the answer's order, which is
    exactly what a task's own roster sentence does.
    """
    found = set()
    for frame in _FRAME.finditer(text):
        run = _read_run(text[frame.end():], roster)
        if run is not None:
            found.add(run)
    if not found:
        return None, NotApplicableReason.NO_CANDIDATE
    if len(found) > 1:
        return None, NotApplicableReason.AMBIGUOUS_CANDIDATE
    return found.pop(), None


# ── the three evaluations ────────────────────────────────────────────────────

def evaluate_candidate(task_text: str, candidate_text: str) -> CheckerReceipt:
    """Check one proposed ordering against the task's constraints.

    VALID means it satisfies every parsed constraint; ``candidate_is_unique``
    says whether it is the only one that does. INVALID names the constraints it
    breaks. NOT_APPLICABLE means the checker could not safely represent the
    problem and says nothing at all about the candidate.
    """
    model, reason = model_task(task_text)
    if model is None:
        return _declined(reason, digest=source_digest(task_text))

    order, why = candidate_order(candidate_text, model.entities)
    if order is None:
        return _declined(why, digest=model.digest, entities=model.entities,
                         constraints=model.constraint_names)

    satisfied = tuple(r.describe for r in model.rules if r.test(order))
    violated = tuple(r.describe for r in model.rules if not r.test(order))
    valid = not violated
    return CheckerReceipt(
        result=CheckerStatus.VALID if valid else CheckerStatus.INVALID,
        problem_class=ProblemClass.FINITE_ORDERING.value,
        normalized_entities=model.entities,
        normalized_constraints=model.constraint_names,
        cited_spans=model.cited_spans,
        candidate_checked=", ".join(order),
        violated_constraints=violated,
        satisfied_constraints=satisfied,
        input_digest=model.digest,
        solution_count=len(model.solutions),
        candidate_is_valid=valid,
        candidate_is_invalid=not valid,
        candidate_is_unique=(valid and len(model.solutions) == 1),
        statement_could_hold=valid,
        statement_must_hold=(valid and len(model.solutions) == 1),
    )


def evaluate_statement(task_text: str, statement_text: str) -> CheckerReceipt:
    """Check a positional statement against every satisfying assignment.

    ``statement_must_hold`` is true only when the statement holds under all of
    them — never inferred from one satisfying example. ``statement_could_hold``
    is true when at least one satisfies it. A statement no assignment satisfies
    is INVALID; a statement the grammar cannot read is NOT_APPLICABLE, and the
    two must not be confused.
    """
    model, reason = model_task(task_text)
    if model is None:
        return _declined(reason, digest=source_digest(task_text))
    if not model.solutions:
        return _declined(NotApplicableReason.UNSATISFIABLE_TASK,
                         digest=model.digest, entities=model.entities,
                         constraints=model.constraint_names)

    rule, why = _parse_constraint(statement_text, model.entities)
    if rule is None:
        return _declined(why, digest=model.digest, entities=model.entities,
                         constraints=model.constraint_names,
                         candidate=_normalise(statement_text))

    holding = [order for order in model.solutions if rule.test(order)]
    must = len(holding) == len(model.solutions)
    could = bool(holding)
    return CheckerReceipt(
        result=CheckerStatus.VALID if could else CheckerStatus.INVALID,
        problem_class=ProblemClass.FINITE_ORDERING.value,
        normalized_entities=model.entities,
        normalized_constraints=model.constraint_names,
        cited_spans=model.cited_spans,
        candidate_checked=rule.describe,
        violated_constraints=() if could else (rule.describe,),
        satisfied_constraints=(rule.describe,) if could else (),
        input_digest=model.digest,
        solution_count=len(model.solutions),
        statement_must_hold=must,
        statement_could_hold=could,
    )


# ── emitting records ─────────────────────────────────────────────────────────

def _receipt_text(receipt: CheckerReceipt) -> str:
    import json
    return json.dumps(receipt.to_dict(), sort_keys=False, ensure_ascii=False)


def receipt_support(receipt: CheckerReceipt, claim_id: str) -> Optional[EvidenceRecord]:
    """Admissible support, and only from a receipt that determines the answer.

    Attributed to the checker, never to a seat: the computation is reproducible
    by anyone holding the task, which is the property
    ``ADMISSIBLE_EVIDENCE_SOURCES`` is actually asking for.
    """
    if not receipt.establishes_the_candidate:
        return None
    return EvidenceRecord(
        evidence_id=stable_id("ev", claim_id, receipt.digest()),
        claim_id=claim_id,
        stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity=f"{CHECKER_ID}/{CHECKER_VERSION}",
        content=_receipt_text(receipt),
        citation="; ".join(receipt.cited_spans),
        receipt_ref=receipt.digest(),
        provenance="deterministic_computation",
    )


def receipt_refutation(receipt: CheckerReceipt, claim_id: str,
                       task_text: str) -> Optional[VerificationRecord]:
    """A refutation the checker computed. Carries no verifier: nothing read it."""
    if receipt.result is not CheckerStatus.INVALID:
        return None
    digest = source_digest(task_text)
    spans = []
    for text in receipt.cited_spans:
        offset = task_text.find(text)
        if offset >= 0:
            spans.append(AnchorSpan(text=text, offset=offset, source_id="task",
                                    source_digest=digest))
    if not spans:
        return None                   # nothing to anchor to; say nothing
    return VerificationRecord(
        verification_id=stable_id("ver", claim_id, receipt.digest()),
        claim_id=claim_id,
        objection_id=None,
        verification_class=VerificationClass.TASK_INTERNAL,
        method=VerificationMethod.TASK_INTERNAL_CHECK,
        authoritative_inputs=tuple(spans),
        condition_tested=f"does {receipt.candidate_checked} satisfy the constraints?",
        result=VerificationResult.FALSIFIED,
        rationale=(f"Violates: {'; '.join(receipt.violated_constraints)}. "
                   f"{_receipt_text(receipt)}"),
        scope="the parsed constraints only",
        limitations=("Exhaustive over the constraints the grammar read. It says "
                     "nothing about anything the grammar could not represent."),
        provenance="deterministic_computation",
    )
