"""Exact-model epistemic source identity.

Seat ids, provider-instance ids, rounds and utterance counts are routing/process
identity, not epistemic independence. This module supplies the one neutral
policy used by both the dialogue observability layer and the governing Hybrid
core:

    one exact actual model identity == one epistemic source

Unknown identity contributes no independence (fail closed).
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Set


def normalize_model_identity(value: Any) -> Optional[str]:
    """Canonical exact model id, or None when it cannot be established."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def authoritative_model_identity(adapter: Any) -> Optional[str]:
    """Resolve an adapter's authoritative exact model id, fail closed.

    Adapters must opt in by exposing ``authoritative_model_id()``. We
    deliberately do not infer from ``provider_id`` or blindly trust a generic
    ``model`` attribute: a route/request label is not proof of the model that
    actually served the call.
    """
    resolver = getattr(adapter, "authoritative_model_id", None)
    if not callable(resolver):
        return None
    try:
        return normalize_model_identity(resolver())
    except Exception:
        return None


def independent_model_sources(records: Iterable[Any], *, attribute: str) -> Set[str]:
    """Distinct known exact-model identities carried by records."""
    out: Set[str] = set()
    for record in records:
        identity = normalize_model_identity(getattr(record, attribute, None))
        if identity is not None:
            out.add(identity)
    return out


def dedupe_by_model_identity(records: Iterable[Any], *, attribute: str) -> List[Any]:
    """First record per known exact model. Unknown identities contribute zero."""
    by_model = {}
    for record in records:
        identity = normalize_model_identity(getattr(record, attribute, None))
        if identity is not None:
            by_model.setdefault(identity, record)
    return list(by_model.values())
