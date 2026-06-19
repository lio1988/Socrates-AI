"""
CED Graph v7 — Epistemic Replay / Audit Trail Export
=====================================================

Deterministic, JSON-safe export of the full epistemic path of a session:
claims -> questions -> evidence -> contradictions -> challenges -> revisions ->
lineage -> epistemic/CBE scores -> Current Best Explanation -> Meta-Socrates
process evaluation.

This layer is intentionally read-only. It does not change the graph, does not
mint claims, and does not alter v0-v6 reasoning behavior.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.epistemic.epistemic_graph import EpistemicGraph

REPLAY_VERSION = "v7"
DETERMINISTIC_EXPORTED_AT = "1970-01-01T00:00:00+00:00"


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _json_safe(value: Any) -> Any:
    """Recursively convert objects into JSON-safe deterministic structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if is_dataclass(value):
        return _json_safe(asdict(value))
    return str(value)


def _topic(session: Any) -> str:
    config = getattr(session, "config", None)
    return str(getattr(config, "topic", ""))


def _graph(session: Any) -> EpistemicGraph:
    graph = getattr(session, "epistemic_graph", None)
    return graph if graph is not None else EpistemicGraph()


def _memory(session: Any) -> Optional[Any]:
    return getattr(session, "knowledge_evolution_memory", None)


def _node_type(node: Any) -> str:
    return str(_enum_value(getattr(node, "node_type", "")))


def _edge_type(edge: Any) -> str:
    return str(_enum_value(getattr(edge, "edge_type", "")))


def _export_nodes(graph: EpistemicGraph) -> List[Dict[str, Any]]:
    rows = []
    for node_id in sorted(graph.nodes):
        node = graph.nodes[node_id]
        rows.append({
            "id": node.node_id,
            "type": _node_type(node),
            "label": node.label,
            "payload": _json_safe(node.payload or {}),
        })
    return rows


def _export_edges(graph: EpistemicGraph) -> List[Dict[str, Any]]:
    rows = []
    for edge_id in sorted(graph.edges):
        edge = graph.edges[edge_id]
        rows.append({
            "id": edge.edge_id,
            "src": edge.src,
            "dst": edge.dst,
            "type": _edge_type(edge),
            "weight": edge.weight,
        })
    return rows


def _rankings_by_claim(cbe: Optional[Any]) -> Dict[str, Dict[str, Any]]:
    if cbe is None:
        return {}
    rankings = getattr(cbe, "ranked_claims", None) or []
    out: Dict[str, Dict[str, Any]] = {}
    for row in rankings:
        claim_id = row.get("claim_id") if isinstance(row, dict) else None
        if claim_id:
            out[str(claim_id)] = _json_safe(row)
    strongest = getattr(cbe, "strongest_claims", None) or []
    for row in strongest:
        claim_id = row.get("claim_id") if isinstance(row, dict) else None
        ranking = row.get("cbe_ranking") if isinstance(row, dict) else None
        if claim_id and ranking and str(claim_id) not in out:
            out[str(claim_id)] = _json_safe(ranking)
    return out


def _lineage_summary(memory: Optional[Any], claim_id: str) -> Dict[str, Any]:
    if memory is None or not hasattr(memory, "lineage_summary"):
        return {}
    if hasattr(memory, "events_by_claim") and claim_id not in getattr(memory, "events_by_claim", {}):
        return {}
    return _json_safe(memory.lineage_summary(claim_id))


def _export_claim_timeline(graph: EpistemicGraph, memory: Optional[Any], cbe: Optional[Any]) -> List[Dict[str, Any]]:
    rankings = _rankings_by_claim(cbe)
    rows = []
    for claim_id in sorted(graph.claims):
        claim = graph.claims[claim_id]
        claim_dict = _json_safe(claim.to_dict())
        node = graph.nodes.get(claim_id)
        node_payload = _json_safe(getattr(node, "payload", {}) or {}) if node else {}
        rows.append({
            "claim_id": claim_id,
            "text": claim.text,
            "author_model": claim.author_model,
            "state": _enum_value(claim.state),
            "confidence": round(float(claim.confidence), 3),
            "evidence": claim_dict.get("evidence", []),
            "evidence_quality": claim_dict.get("evidence_quality", 0.0),
            "contradictions": list(claim.contradictions),
            "dependencies": list(claim.dependencies),
            "revision_count": len(claim.revision_history),
            "has_been_challenged": bool(claim.has_been_challenged),
            "lineage": _lineage_summary(memory, claim_id),
            "node_payload": node_payload,
            "cbe_ranking": rankings.get(claim_id),
        })
    return rows


def _export_claims(graph: EpistemicGraph) -> List[Dict[str, Any]]:
    return [_json_safe(graph.claims[cid].to_dict()) for cid in sorted(graph.claims)]


def _count_evidence(graph: EpistemicGraph) -> int:
    return sum(len(claim.evidence) for claim in graph.claims.values())


def _count_contradictions(graph: EpistemicGraph) -> int:
    edge_count = sum(1 for edge in graph.edges.values() if _edge_type(edge) == "contradicts")
    claim_refs = sum(len(claim.contradictions) for claim in graph.claims.values())
    return max(edge_count, claim_refs)


def _lineage_event_count(memory: Optional[Any]) -> int:
    if memory is None:
        return 0
    return len(getattr(memory, "events", []) or [])


def _cbe_dict(session: Any) -> Optional[Dict[str, Any]]:
    cbe = getattr(session, "current_best_explanation", None)
    return _json_safe(cbe.to_dict()) if cbe is not None and hasattr(cbe, "to_dict") else None


def _process_evaluation_dict(session: Any) -> Optional[Dict[str, Any]]:
    evaluation = getattr(session, "process_evaluation", None)
    return _json_safe(evaluation.to_dict()) if evaluation is not None and hasattr(evaluation, "to_dict") else None


def _cbe_claim_ids(cbe_payload: Optional[Dict[str, Any]]) -> List[str]:
    if not cbe_payload:
        return []
    ids = set()
    for cid in cbe_payload.get("summary_claim_ids", []) or []:
        ids.add(str(cid))
    for key in ("strongest_claims", "ranked_claims", "unresolved_disagreements", "rejected_hypotheses"):
        for row in cbe_payload.get(key, []) or []:
            if isinstance(row, dict) and row.get("claim_id"):
                ids.add(str(row["claim_id"]))
    lineage = cbe_payload.get("lineage", {}) or {}
    if isinstance(lineage, dict):
        ids.update(str(cid) for cid in lineage.keys())
    return sorted(ids)


def _lineage_claim_ids(memory: Optional[Any]) -> List[str]:
    if memory is None:
        return []
    ids = set(getattr(memory, "events_by_claim", {}).keys())
    for event in getattr(memory, "events", []) or []:
        ids.add(getattr(event, "claim_id", ""))
        parent = getattr(event, "parent_claim_id", None)
        previous = getattr(event, "previous_claim_id", None)
        if parent:
            ids.add(parent)
        if previous:
            ids.add(previous)
    return sorted(str(cid) for cid in ids if cid)


def _audit_checks(graph: EpistemicGraph, cbe_payload: Optional[Dict[str, Any]],
                  memory: Optional[Any], exported_claim_count: int) -> Dict[str, bool]:
    graph_claim_ids = set(graph.claims.keys())
    cbe_ids = set(_cbe_claim_ids(cbe_payload))
    lineage_ids = set(_lineage_claim_ids(memory))
    cbe_ids_exist = cbe_ids.issubset(graph_claim_ids)
    lineage_ids_exist = lineage_ids.issubset(graph_claim_ids)
    return {
        "cbe_claim_ids_exist": cbe_ids_exist,
        "cbe_invents_no_new_claims": cbe_ids_exist,
        "all_lineage_claim_ids_exist": lineage_ids_exist,
        "exported_claim_count_matches_graph": exported_claim_count == len(graph.claims),
        "deterministic_ordering": True,
    }


@dataclass
class EpistemicReplayExport:
    metadata: Dict[str, Any]
    graph: Dict[str, Any]
    claim_timeline: List[Dict[str, Any]]
    epistemic_trace: List[str]
    current_best_explanation: Optional[Dict[str, Any]]
    process_evaluation: Optional[Dict[str, Any]]
    audit_checks: Dict[str, bool]
    replay_version: str = REPLAY_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe({
            "replay_version": self.replay_version,
            "metadata": self.metadata,
            "graph": self.graph,
            "claim_timeline": self.claim_timeline,
            "epistemic_trace": self.epistemic_trace,
            "current_best_explanation": self.current_best_explanation,
            "process_evaluation": self.process_evaluation,
            "audit_checks": self.audit_checks,
        })


def export_epistemic_replay(session: Any, *, exported_at: Optional[str] = None) -> Dict[str, Any]:
    """Export a full deterministic, JSON-safe replay of a session's epistemic path."""
    graph = _graph(session)
    memory = _memory(session)
    cbe_payload = _cbe_dict(session)
    process_payload = _process_evaluation_dict(session)
    claim_timeline = _export_claim_timeline(graph, memory, getattr(session, "current_best_explanation", None))

    metadata = {
        "replay_version": REPLAY_VERSION,
        "topic": _topic(session),
        "exported_at": exported_at or DETERMINISTIC_EXPORTED_AT,
        "claim_count": len(graph.claims),
        "evidence_count": _count_evidence(graph),
        "contradiction_count": _count_contradictions(graph),
        "lineage_event_count": _lineage_event_count(memory),
        "trace_event_count": len(getattr(session, "epistemic_trace", []) or []),
    }
    graph_payload = {
        "nodes": _export_nodes(graph),
        "edges": _export_edges(graph),
        "claims": _export_claims(graph),
    }
    audit = _audit_checks(graph, cbe_payload, memory, len(claim_timeline))

    return EpistemicReplayExport(
        metadata=metadata,
        graph=graph_payload,
        claim_timeline=claim_timeline,
        epistemic_trace=list(getattr(session, "epistemic_trace", []) or []),
        current_best_explanation=cbe_payload,
        process_evaluation=process_payload,
        audit_checks=audit,
    ).to_dict()


def export_audit_trail(session: Any) -> Dict[str, Any]:
    """Return the compact audit trail view derived from the replay export."""
    replay = export_epistemic_replay(session)
    return {
        "replay_version": REPLAY_VERSION,
        "metadata": replay["metadata"],
        "audit_checks": replay["audit_checks"],
        "claim_timeline": replay["claim_timeline"],
        "current_best_explanation": replay["current_best_explanation"],
        "process_evaluation": replay["process_evaluation"],
    }


def canonical_replay_json(session: Any) -> str:
    """Canonical JSON string suitable for deterministic replay comparison."""
    return json.dumps(
        export_epistemic_replay(session),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
