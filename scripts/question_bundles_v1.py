"""Question bundles: make a new experimental question a data file, not a patch.

Why this exists.

The Q2d authorization payload grew around a single experiment, so that
experiment's constants ended up hard-coded inside the payload builder: the
question digest, the rubric digest and the evaluator-key digest were literals.
Adding a second question therefore meant editing code, which changed the
implementation digest, which invalidated the manifest, which broke the pinned
test constant, which required a fresh operator approval — five steps for what is
conceptually one act.

Nothing about that ceremony was protecting anything the pinning does not already
protect. Two things genuinely must hold, and both survive here:

* the operator approves exactly one manifest digest before any spend, and
* the evidence records exactly which question, rubric and key produced a result,
  so two experiments can never be silently compared.

A bundle is the pin. It is written once from the question module, then checked
against that module on every load, so drift is caught the same way it was
before. What changes is that adding a question adds a file instead of editing a
builder.
"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from typing import Any, Dict, Mapping

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)

BUNDLE_SCHEMA_VERSION_V1 = "socrates-question-bundle/v1"

BUNDLE_DIRECTORY_V1 = (
    Path(__file__).resolve().parents[1]
    / "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs/question_bundles"
)

#: The only questions this harness may run. A name here must resolve to a module
#: exposing QUESTION_V1, QUESTION_SHA256_V1, CRITERIA_V1, MAXIMUM_SCORE_V1,
#: ERROR_FLAGS_V1 and verify_key_v1().
QUESTION_MODULES_V1: Mapping[str, str] = {
    "q2": "scripts.q2_ethics_question_v1",
    "q3": "scripts.q3_ethics_question_v1",
    "q4": "scripts.q4_ethics_question_v1",
}

#: Fields of a question module that form the evaluator key. Kept explicit so a
#: new key field cannot silently escape the digest.
_KEY_FIELDS_V1 = (
    "VALID_V1",
    "SOUND_V1",
    "FIRST_INVALID_STEP_V1",
    "DIAGNOSIS_V1",
    "COUNTERMODEL_V1",
    "FALLACY_FALLACY_V1",
    "VALIDITY_DERIVATION_V1",
    "WEAKEST_PREMISE_V1",
    "EQUIVOCATION_V1",
    "SUPPRESSED_PREMISE_V1",
    "SUPPRESSED_PREMISE_DEFECT_V1",
    "NECESSARY_NOT_SUFFICIENT_V1",
    # Q4 only. Every name here is read with hasattr, so adding names that q2 and
    # q3 do not define leaves their key payloads - and therefore their pinned
    # digests - byte-identical.
    "IMPOSSIBILITY_IS_GENUINE_V1",
    "PROOF_OF_IMPOSSIBILITY_V1",
    "MINIMAL_REPAIR_V1",
    "RESPONSIVENESS_IS_A_PASSENGER_V1",
)


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_question_module_v1(name: str):
    """Import one registered question module, refusing anything unregistered."""
    target = QUESTION_MODULES_V1.get(name)
    if target is None:
        raise ContractValidationError(
            f"unknown question {name!r}; register it in QUESTION_MODULES_V1"
        )
    return importlib.import_module(target)


def compute_bundle_v1(name: str) -> Dict[str, Any]:
    """Derive the three question-specific digests from the module itself."""
    module = load_question_module_v1(name)
    check = module.verify_key_v1()
    if not check.get("key_is_sound"):
        raise ContractValidationError(f"{name}: evaluator key failed its own check")
    if _sha_text(module.QUESTION_V1) != module.QUESTION_SHA256_V1:
        raise ContractValidationError(f"{name}: question text drifted from its digest")

    rubric = canonical_json(
        {
            "criteria": [
                {"name": n, "requirement": d, "points": p}
                for n, d, p in module.CRITERIA_V1
            ],
            "maximum": module.MAXIMUM_SCORE_V1,
            "error_flags": list(module.ERROR_FLAGS_V1),
        }
    )
    key_payload = canonical_json(
        {
            field: getattr(module, field)
            for field in _KEY_FIELDS_V1
            if hasattr(module, field)
        }
    )
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION_V1,
        "question_name": name,
        "question_module": QUESTION_MODULES_V1[name],
        "question_sha256": module.QUESTION_SHA256_V1,
        "rubric_sha256": _sha_text(rubric),
        "evaluator_key_sha256": _sha_text(key_payload),
        "maximum_score": module.MAXIMUM_SCORE_V1,
        "criteria_count": len(module.CRITERIA_V1),
        "error_flag_count": len(module.ERROR_FLAGS_V1),
    }


def bundle_path_v1(name: str) -> Path:
    return BUNDLE_DIRECTORY_V1 / f"{name}_question_bundle_v1.json"


def write_bundle_v1(name: str) -> Path:
    """Pin a question's digests. Write-once: an existing bundle is never edited."""
    path = bundle_path_v1(name)
    if path.exists():
        raise ContractValidationError(
            f"{name}: bundle already exists and is write-once: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(compute_bundle_v1(name)), encoding="utf-8")
    return path


def load_bundle_v1(name: str) -> Dict[str, Any]:
    """Read a pinned bundle and verify the module still matches it.

    This is where drift is caught. A question, rubric or key edited after the
    bundle was written fails here, before anything is dispatched — the same
    guarantee the hard-coded constants gave, without the code edit.
    """
    import json

    path = bundle_path_v1(name)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractValidationError(
            f"{name}: no pinned question bundle at {path}; write one first"
        ) from exc
    current = compute_bundle_v1(name)
    drifted = [k for k, v in current.items() if stored.get(k) != v]
    if drifted:
        raise ContractValidationError(
            f"{name}: pinned bundle disagrees with the question module: {drifted}"
        )
    return stored


__all__ = [
    "BUNDLE_DIRECTORY_V1",
    "BUNDLE_SCHEMA_VERSION_V1",
    "QUESTION_MODULES_V1",
    "bundle_path_v1",
    "compute_bundle_v1",
    "load_bundle_v1",
    "load_question_module_v1",
    "write_bundle_v1",
]
