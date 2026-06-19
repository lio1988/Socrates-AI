"""CED Graph v10.2: deterministic Elenchus explanation helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

ELENCHUS_EXPLANATION_VERSION = "v10.2"

OUTCOME_REFUTED = "refuted"
OUTCOME_NOT_REFUTED_YET = "not_refuted_yet"
OUTCOME_PARTIALLY_WEAKENED = "partially_weakened"
OUTCOME_NEEDS_EVIDENCE = "needs_evidence"
OUTCOME_NOT_FALSIFIABLE = "not_falsifiable"
OUTCOME_WRONG_TARGET = "wrong_target"

META_STARTERS = (
    "deliver", "explain", "write", "summarize", "summarise", "give me",
    "give", "produce", "create", "make", "draft", "generate", "rewrite",
    "improve", "translate", "ask", "show me", "tell me", "please",
    "here is", "here's", "following the", "your task", "output",
)
META_PHRASES = (
    "socratic follow-up", "socratic question", "deliver a", "write a",
    "explain this", "summarize the debate", "give me a question",
    "produce a revision", "output json", "return json", "as requested",
)
EPISTEMIC_MARKERS = (
    " is ", " are ", " was ", " were ", " has ", " have ", " means ",
    " because ", " therefore ", " implies ", " shows ", " demonstrates ",
    " evidence ", " truth ", " false ", " valid ", " invalid ", " likely ",
    " unlikely ", " cannot ", " can not ", " must ", " should ",
    " counts as ", " we treat ", " we know ", " the claim ", " the price ",
    " cannot be ", " may be ", " can be ",
)
FINANCIAL_MARKERS = (
    "ipo", "price", "valuation", "retail", "investor", "underwriter",
    "revenue", "multiple", "dcf", "fair value", "liquidity", "allocation",
)

def normalize_text(text: str | None) -> str:
    return " ".join((text or "").strip().split()).lower()

def is_meta_instruction(text: str | None) -> bool:
    norm = normalize_text(text)
    if not norm:
        return False
    first = norm.split(".", 1)[0].strip()
    starts_like_instruction = any(first.startswith(marker) for marker in META_STARTERS)
    has_instruction_phrase = any(marker in norm for marker in META_PHRASES)
    epistemic_hits = sum(1 for marker in EPISTEMIC_MARKERS if marker in f" {norm} ")
    return bool((starts_like_instruction or has_instruction_phrase) and epistemic_hits <= 1)

def is_epistemic_claim(text: str | None) -> bool:
    norm = normalize_text(text)
    if not norm or len(norm) < 12:
        return False
    if is_meta_instruction(norm):
        return False
    if "?" in norm and not any(marker in norm for marker in ("because", "therefore", "implies")):
        return False
    return any(marker in f" {norm} " for marker in EPISTEMIC_MARKERS)

def classify_claim_target(text: str | None) -> str:
    if is_meta_instruction(text):
        return "meta_instruction"
    if is_epistemic_claim(text):
        return "epistemic_claim"
    return "not_falsifiable"

def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []

def collect_issues(payload: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for key in ("challenged_assumptions", "logic_gaps", "evidence_issues", "conclusion_issues"):
        issues.extend(_as_list(payload.get(key)))
    return issues

def infer_elenchus_outcome(target_claim_text: str, payload: Dict[str, Any]) -> str:
    kind = classify_claim_target(target_claim_text)
    if kind == "meta_instruction":
        return OUTCOME_WRONG_TARGET
    if kind == "not_falsifiable":
        return OUTCOME_NOT_FALSIFIABLE
    if bool(payload.get("falsification_successful", False)):
        return OUTCOME_REFUTED
    issues = collect_issues(payload)
    joined = " ".join(issues).lower()
    if any(key in joined for key in ("evidence", "data", "source", "verify", "valuation", "financial")):
        return OUTCOME_NEEDS_EVIDENCE
    if issues:
        return OUTCOME_PARTIALLY_WEAKENED
    return OUTCOME_NOT_REFUTED_YET

def build_reason(target_claim_text: str, payload: Dict[str, Any], outcome: str) -> str:
    if outcome == OUTCOME_WRONG_TARGET:
        return "The target is an instruction or task request, not a knowledge claim that can be tested."
    if outcome == OUTCOME_NOT_FALSIFIABLE:
        return "The target is too thin or question-like to be tested as a falsifiable claim."
    if outcome == OUTCOME_REFUTED:
        issues = collect_issues(payload)
        return issues[0] if issues else "The challenger found enough issues to refute the claim for now."
    if outcome == OUTCOME_NEEDS_EVIDENCE:
        return "The claim was not refuted yet, but it depends on evidence that has not been separated from competing explanations."
    if outcome == OUTCOME_PARTIALLY_WEAKENED:
        return "The claim survived full refutation, but weaknesses remain and should reduce confidence until repaired."
    return "The claim was not refuted yet. No decisive contradiction was established by this Elenchus pass."

def build_remaining_uncertainty(target_claim_text: str, outcome: str) -> str:
    if outcome == OUTCOME_WRONG_TARGET:
        return "A real epistemic claim must be selected before Elenchus can test it."
    if outcome == OUTCOME_NOT_FALSIFIABLE:
        return "The target needs a clearer proposition, boundary, and evidence condition before it can be challenged."
    if any(marker in normalize_text(target_claim_text) for marker in FINANCIAL_MARKERS):
        return "We still need evidence that separates competing financial explanations and incentives."
    if outcome == OUTCOME_REFUTED:
        return "The remaining question is whether a revised version can survive the identified challenge."
    return "The claim remains provisional until stronger evidence, a clearer objection, or a revision changes its status."

def build_next_socratic_question(target_claim_text: str, outcome: str) -> str:
    if outcome == OUTCOME_WRONG_TARGET:
        return "Which concrete knowledge claim should be tested instead of this instruction?"
    if outcome == OUTCOME_NOT_FALSIFIABLE:
        return "What exact proposition would make this claim testable rather than merely suggestive?"
    if any(marker in normalize_text(target_claim_text) for marker in FINANCIAL_MARKERS):
        return "What evidence would distinguish one financial explanation from its strongest alternative?"
    if outcome == OUTCOME_REFUTED:
        return "What revision would survive the strongest objection without weakening the claim into vagueness?"
    if outcome == OUTCOME_NEEDS_EVIDENCE:
        return "What evidence would decide between the claim and its strongest alternative explanation?"
    return "What would have to be true for this claim to fail?"

def evidence_needed_for(target_claim_text: str, outcome: str) -> List[str]:
    if outcome == OUTCOME_WRONG_TARGET:
        return ["A concrete epistemic claim text, not an instruction."]
    if outcome == OUTCOME_NOT_FALSIFIABLE:
        return ["A falsifiable proposition with a clear truth condition."]
    if any(marker in normalize_text(target_claim_text) for marker in FINANCIAL_MARKERS):
        return [
            "Source-backed valuation assumptions or comparable multiples.",
            "Evidence separating competing financial motives.",
            "Clear distinction between retail, issuer, and early-investor incentives.",
        ]
    return ["Evidence that could confirm or disconfirm the claim.", "The strongest alternative explanation."]

@dataclass
class ElenchusExplanation:
    elenchus_version: str
    outcome: str
    target_claim_id: Optional[str]
    target_claim_text: str
    target_is_epistemic_claim: bool
    reason: str
    remaining_uncertainty: str
    next_socratic_question: str
    evidence_needed: List[str] = field(default_factory=list)
    falsification_status: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

def explain_elenchus_result(target_claim_id: Optional[str], target_claim_text: str, payload: Dict[str, Any]) -> ElenchusExplanation:
    outcome = str(payload.get("outcome") or infer_elenchus_outcome(target_claim_text, payload))
    target_is_claim = classify_claim_target(target_claim_text) == "epistemic_claim"
    falsified = bool(payload.get("falsification_successful", False))
    evidence_needed = payload.get("evidence_needed") or evidence_needed_for(target_claim_text, outcome)
    if isinstance(evidence_needed, str):
        evidence_needed = [evidence_needed]
    return ElenchusExplanation(
        elenchus_version=ELENCHUS_EXPLANATION_VERSION,
        outcome=outcome,
        target_claim_id=target_claim_id,
        target_claim_text=target_claim_text,
        target_is_epistemic_claim=target_is_claim,
        reason=str(payload.get("reason") or build_reason(target_claim_text, payload, outcome)),
        remaining_uncertainty=str(payload.get("remaining_uncertainty") or build_remaining_uncertainty(target_claim_text, outcome)),
        next_socratic_question=str(payload.get("next_socratic_question") or build_next_socratic_question(target_claim_text, outcome)),
        evidence_needed=[str(item) for item in evidence_needed if str(item).strip()],
        falsification_status=str(payload.get("falsification_status") or ("successful" if falsified else "not_refuted_yet")),
    )

def format_elenchus_for_user(explanation: ElenchusExplanation) -> str:
    status_line = {
        OUTCOME_REFUTED: "Refuted for now.",
        OUTCOME_NOT_REFUTED_YET: "Not refuted yet.",
        OUTCOME_PARTIALLY_WEAKENED: "Partially weakened, not refuted.",
        OUTCOME_NEEDS_EVIDENCE: "Not refuted yet; needs evidence.",
        OUTCOME_NOT_FALSIFIABLE: "Not falsifiable yet.",
        OUTCOME_WRONG_TARGET: "Wrong target.",
    }.get(explanation.outcome, explanation.outcome)
    return (
        f"[ELENCHUS target={explanation.target_claim_id}] {status_line}\n"
        f"Target claim: {explanation.target_claim_text or 'No target claim text available.'}\n"
        f"Reason: {explanation.reason}\n"
        f"Remaining uncertainty: {explanation.remaining_uncertainty}\n"
        f"Next Socratic question: {explanation.next_socratic_question}"
    )
