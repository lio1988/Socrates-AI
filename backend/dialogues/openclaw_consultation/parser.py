"""Strict parsing of a consulted model's raw text into a mode payload.

A valid JSON object is NOT enough: the payload must match the exact per-mode
field set, types, bounds, enums, carry no secret-shaped data, and make no
authority/tool-use claim. Text that is not a single JSON object, or a JSON
object that fails any of those checks, fails closed - the service never
fabricates or completes fields.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .schemas import ConsultationError, validate_payload


def parse_structured_payload(mode: str, raw_text: str) -> Dict[str, Any]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ConsultationError("consulted model returned empty text")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConsultationError(
            "consulted model did not return a single JSON object") from exc
    if not isinstance(parsed, dict):
        raise ConsultationError(
            "consulted model response must be a JSON object")
    # validate_payload re-checks field set, types, bounds, enums, secrets,
    # and authority-claim patterns for the exact mode.
    return validate_payload(mode, parsed)


__all__ = ["parse_structured_payload"]
