"""Socrates Epistemic Hybrid v1 — H8 authority map.

Every subsystem is named here with exactly one authority class. The map exists so
that "advisory" is a checkable property rather than an intention: a component
classified ADVISORY must not be able to reach the governing epistemic core, and
``test_hybrid_authority_h8.py`` proves it by import graph rather than by promise.

The failure this prevents is quiet: a mature subsystem is reconnected for a good
reason, and its output starts deciding something it was never meant to decide.
The frozen fixtures record two such drifts — a numeric CBE rank selecting a false
claim, and a quality threshold labelling an objectively wrong answer
``well_supported``.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple


class AuthorityClass(str, Enum):
    """What a subsystem is permitted to decide."""

    #: May determine epistemic support, eligibility or release.
    AUTHORITATIVE = "authoritative"
    #: May inform reasoning. May never determine epistemic state.
    ADVISORY = "advisory"
    #: Measures how well something was argued. Never whether it is so.
    QUALITY = "quality"
    #: Reads and projects. Never writes authoritative state.
    OBSERVER = "observer"
    #: Explores or proposes candidates. Selection remains governed.
    SEARCH = "search"
    #: Changes future behaviour, never the truth of the present answer.
    LEARNING = "learning"
    #: Superseded. Retained for provenance and comparison only.
    LEGACY = "legacy"
    #: Declared and deliberately unimplemented. Reserved so nothing quietly
    #: fills the slot before its stage is reached.
    RESERVED = "reserved"


class SubsystemAuthority:
    """One subsystem's classification and the reason for it."""

    __slots__ = ("name", "module", "authority", "role", "note")

    def __init__(self, name: str, module: str, authority: AuthorityClass,
                 role: str, note: str = "") -> None:
        self.name = name
        self.module = module
        self.authority = authority
        self.role = role
        self.note = note


#: The complete map. Adding a subsystem without classifying it is a test failure.
AUTHORITY_MAP: Tuple[SubsystemAuthority, ...] = (
    # ── authoritative: the single governing path ─────────────────────────────
    SubsystemAuthority(
        "hybrid epistemic core", "backend.dialogues.hybrid_epistemic",
        AuthorityClass.AUTHORITATIVE,
        "claims, objections, evidence, verification, revision, contradiction, "
        "eligibility, claim-level ratification, frozen release",
        "The only component that may decide epistemic support."),
    SubsystemAuthority(
        "hybrid ledger", "backend.dialogues.hybrid_shadow",
        AuthorityClass.AUTHORITATIVE,
        "the one append-only record store",
        "Single store on purpose: a parallel ledger would be a second authority."),
    SubsystemAuthority(
        "CED orchestrator", "backend.dialogues.ced", AuthorityClass.AUTHORITATIVE,
        "execution: roles, phases, task routing, provider governance",
        "Authoritative over process. Not over truth."),
    SubsystemAuthority(
        "provider registry", "backend.dialogues.provider_registry",
        AuthorityClass.AUTHORITATIVE,
        "provider readiness, quorum, fail-closed statuses",
        "Fail-closed behaviour is authoritative; a failure never becomes an answer."),

    # ── quality: how well it was argued ──────────────────────────────────────
    SubsystemAuthority(
        "peer and section scoring", "backend.dialogues.ced",
        AuthorityClass.QUALITY,
        "seven-dimension peer scores, section scores, blind assembly ranking",
        "Measured live: quality does not track premise truth."),
    SubsystemAuthority(
        "epistemic leaderboard", "backend.dialogues.ced", AuthorityClass.QUALITY,
        "contributor ranking",
        "Rank is quality machinery. Rank is never evidence."),
    SubsystemAuthority(
        "hybrid support separation", "backend.dialogues.hybrid_support",
        AuthorityClass.OBSERVER,
        "reports the quality plane and the support plane side by side",
        "Reports both, merges neither, decides nothing."),

    # ── advisory ─────────────────────────────────────────────────────────────
    SubsystemAuthority(
        "epistemic markers", "backend.dialogues.reasoning_prompts",
        AuthorityClass.ADVISORY,
        "model self-description; audit, calibration, verification prioritisation",
        "Self-description is never evidence for itself."),
    SubsystemAuthority(
        "reasoning kernels", "backend.dialogues.openclaw_socratic_kernel",
        AuthorityClass.ADVISORY,
        "bounded per-agent self-questioning",
        "Reasoning assistance, not truth authority."),
    SubsystemAuthority(
        "external consultation", "backend.dialogues.openclaw_consultation",
        AuthorityClass.ADVISORY,
        "one isolated provider call per request",
        "A provider answering a question is a model assertion. It becomes "
        "evidence only when independently attributable to a source or tool."),
    SubsystemAuthority(
        "council ratification", "backend.dialogues.ced", AuthorityClass.ADVISORY,
        "acceptance as a governance act, plus caveats and blocking objections",
        "Decides acceptance. Never converts unsupported material into support."),

    # ── observer ─────────────────────────────────────────────────────────────
    SubsystemAuthority(
        "council live view", "backend.orchestrator.ced_live_writer",
        AuthorityClass.OBSERVER,
        "projection of execution for viewing",
        "Projection only; it writes no authoritative state."),
    SubsystemAuthority(
        "learning trace collector", "backend.dialogues.learning_trace_collector",
        AuthorityClass.OBSERVER,
        "records traces for later learning",
        "Records what happened. Changes nothing about it."),

    # ── search ───────────────────────────────────────────────────────────────
    SubsystemAuthority(
        "deliberation tree", "backend.dialogues.ced", AuthorityClass.SEARCH,
        "optional UCB-selected revision expansions enriching the draft pool",
        "Proposes candidates. Eligibility stays governed."),

    # ── learning ─────────────────────────────────────────────────────────────
    SubsystemAuthority(
        "openclaw learning", "backend.dialogues.openclaw_memory",
        AuthorityClass.LEARNING,
        "lessons, consolidation, injected context",
        "Changes future behaviour, never the truth of the present answer."),
    SubsystemAuthority(
        "self improvement", "backend.dialogues.self_improvement",
        AuthorityClass.LEARNING,
        "process review feeding later sessions",
        "Advisory to the future only."),

    # ── legacy: superseded authority, retained for provenance ────────────────
    SubsystemAuthority(
        "legacy epistemic hint", "backend.dialogues.ced", AuthorityClass.LEGACY,
        "mean peer score >= 7.5 -> well_supported",
        "Superseded by the hybrid core. Retained as a reported label and as the "
        "comparison the migration is measured against. It gates nothing: its "
        "only consumers are display, tracing and observation."),
    SubsystemAuthority(
        "legacy evidence scoring", "backend.epistemic.evidence_scoring",
        AuthorityClass.LEGACY,
        "evidence quality/mass thresholds producing WELL_SUPPORTED",
        "Better epistemics than the quality threshold - it weighs evidence "
        "stance and filters self-assertion - but still a numeric path to a "
        "support verdict. Preserved for provenance; not governing."),
    SubsystemAuthority(
        "legacy epistemic graph and CBE", "backend.epistemic_graph",
        AuthorityClass.LEGACY,
        "claim graph, contradiction detection, current-best-explanation ranking",
        "Its provenance and lineage semantics are valuable and preserved. Its "
        "numeric ranking selected a false claim first in the frozen fixture and "
        "is not governing."),
    SubsystemAuthority(
        "argumentation / Dung adapter", "backend.epistemic.argumentation_framework",
        AuthorityClass.LEGACY,
        "abstract argumentation semantics",
        "Optional diagnostics. Never a hidden release authority."),

    # ── infrastructure with authority over its own guarantees ────────────────
    SubsystemAuthority(
        "atomic receipt store", "backend.dialogues.openclaw_receipts",
        AuthorityClass.AUTHORITATIVE,
        "durable, atomic receipt persistence",
        "Authoritative over what was recorded, never over whether it is true."),
    SubsystemAuthority(
        "conversation continuity", "backend.dialogues.conversation",
        AuthorityClass.AUTHORITATIVE,
        "multi-turn session identity and carry-over",
        "Authoritative over which session a turn belongs to. Not over truth."),
    SubsystemAuthority(
        "event ledger / live projection", "backend.orchestrator.live_epistemics",
        AuthorityClass.OBSERVER,
        "execution events projected for viewing",
        "Reads execution. Writes no authoritative state."),

    # ── reserved: declared, deliberately unimplemented ───────────────────────
    SubsystemAuthority(
        "candidate tournament synthesis", "backend.dialogues.models",
        AuthorityClass.RESERVED,
        "FinalSynthesisMode.CANDIDATE_TOURNAMENT",
        "Reserved for V2/V3 and raises NotImplementedError today. Kept declared "
        "so the slot cannot be filled quietly by something else."),
    SubsystemAuthority(
        "external evidence substrate", "backend.evidence",
        AuthorityClass.RESERVED,
        "governed retrieval, citations and tool receipts for H3B",
        "Empty by decision. H3B external verification stays blocked rather than "
        "being simulated by a second model."),
)

#: Classes that may decide epistemic support, eligibility or release.
GOVERNING_CLASSES: Tuple[AuthorityClass, ...] = (AuthorityClass.AUTHORITATIVE,)

#: The module that owns epistemic support. Nothing else may compute it.
GOVERNING_CORE_MODULE = "backend.dialogues.hybrid_epistemic"


def by_authority(authority: AuthorityClass) -> Tuple[SubsystemAuthority, ...]:
    return tuple(s for s in AUTHORITY_MAP if s.authority is authority)


def authority_of(name: str) -> AuthorityClass:
    for subsystem in AUTHORITY_MAP:
        if subsystem.name == name:
            return subsystem.authority
    raise KeyError(f"unclassified subsystem: {name}")


def as_table() -> Tuple[Dict[str, str], ...]:
    return tuple({"subsystem": s.name, "module": s.module,
                  "authority": s.authority.value, "role": s.role, "note": s.note}
                 for s in AUTHORITY_MAP)
