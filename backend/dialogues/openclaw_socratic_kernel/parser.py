"""Strict parsing of an auditor's raw text into a mode-specific check payload.

A valid JSON object is NOT enough: the payload must match the exact per-mode
field set, types, bounds, enums, decision coherence, carry no secret-shaped
data, and make no authority/tool/consultation/self-certification claim. Text
that is not a single JSON object, or an object that fails any of those checks,
fails closed - the service never fabricates or completes fields.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .schemas import MicroSocraticError, validate_check_payload


def parse_check_payload(mode: str, raw_text: str) -> Dict[str, Any]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise MicroSocraticError("auditor returned empty text")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise MicroSocraticError(
            "auditor did not return a single JSON object") from exc
    if not isinstance(parsed, dict):
        raise MicroSocraticError("auditor response must be a JSON object")
    return validate_check_payload(mode, parsed)


__all__ = ["parse_check_payload"]
