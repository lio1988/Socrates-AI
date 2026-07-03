"""
Training-corpus harvester — turns real council dialogues into labelled data.

Two kinds of example, both grounded in what the council ACTUALLY did (no
fabrication — the labels are the council's own peer scores and mechanical
assembly, exactly the artifacts CED already owns):

  SFT (supervised demonstrations) — from RATIFIED sessions only:
    * the endorsed 5-section answer (the gold synthesis), and
    * the Socratic opening question,
    keyed by role so they can instruction-tune the corresponding seat.

  Preference pairs (for DPO/RLAIF) — from any session with peer scores:
    * per section, chosen = the peer-score WINNER draft's text,
      rejected = a clearly lower-scored draft's text (margin-gated),
    a genuine "the council judged A better than B" signal.

Pure, offline, deterministic. No torch, no network, no keys.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.dialogues.models import DialogPhase, FinalResponse, SessionState

SCHEMA_VERSION = "teacher_corpus_v0"
DEFAULT_MIN_MARGIN = 1.0   # peer-score gap (0–10 scale) for a usable preference

# Short, domain-neutral role instructions (the model learns the FORM, not a topic).
SYNTH_INSTRUCTION = (
    "As the council Synthesizer, produce the final answer as a JSON object with "
    "the five fields core_answer, crucial_stress_test, blind_spots, nuance, "
    "final_verdict.")
SOCRATES_INSTRUCTION = (
    "As Socrates, ask the single most load-bearing question about the following — "
    "the hidden assumption whose resolution would most change the conclusion.")
PREF_PROMPT = "Write the '{section}' of a council answer to: {question}"


@dataclass(frozen=True)
class SFTExample:
    instruction: str
    input: str
    output: str            # the endorsed content, JSON-serialised
    role: str
    provenance: str        # "ratified_synthesis" | "socratic_opening"
    source_session: str


@dataclass(frozen=True)
class PreferencePair:
    prompt: str
    chosen: str            # peer-score winner's section text
    rejected: str          # clearly lower-scored draft's section text
    margin: float          # winner_avg − rejected_avg (0–10 scale)
    section: str
    source_session: str


def _section_averages(state: SessionState, section) -> Dict[str, float]:
    by_draft: Dict[str, List[float]] = {}
    for sc in state.section_scores_for(section):
        if sc.overall_score is not None:
            by_draft.setdefault(sc.draft_id, []).append(float(sc.overall_score))
    return {d: sum(v) / len(v) for d, v in by_draft.items() if v}


def harvest_session(
    state: SessionState, final: FinalResponse, *, min_margin: float = DEFAULT_MIN_MARGIN,
) -> Tuple[List[SFTExample], List[PreferencePair]]:
    """Extract (sft_examples, preference_pairs) from one finished session."""
    sft: List[SFTExample] = []
    prefs: List[PreferencePair] = []

    # -- SFT: only endorsed (ratified) outputs become demonstrations --
    if final.ratified and final.synthesis:
        answer = {s.section_name.value: s.content for s in final.synthesis.sections
                  if not s.unresolved and s.content.strip()}
        if answer:
            sft.append(SFTExample(
                instruction=SYNTH_INSTRUCTION, input=state.question,
                output=json.dumps(answer, ensure_ascii=False, sort_keys=True),
                role="synthesizer", provenance="ratified_synthesis",
                source_session=state.session_id))
        opening = state.moves_for_phase(DialogPhase.OPENING)
        if opening:
            sft.append(SFTExample(
                instruction=SOCRATES_INSTRUCTION, input=state.question,
                output=json.dumps(opening[0].content, ensure_ascii=False, sort_keys=True),
                role="socrates", provenance="socratic_opening",
                source_session=state.session_id))

    # -- Preferences: peer-score margins per section (no ratification required;
    #    a clear scoring signal is the only requirement) --
    assembled = state.assembled_answer
    if assembled is not None and state.section_drafts:
        drafts = {d.draft_id: d for d in state.section_drafts}
        for sec in assembled.sections:
            section = sec.section_name
            avgs = _section_averages(state, section)
            if len(avgs) < 2:
                continue
            winner_id = (sec.selected_draft_id if sec.selected_draft_id in avgs
                         else max(avgs, key=avgs.get))
            winner = drafts.get(winner_id)
            if winner is None:
                continue
            chosen_text = winner.section_text(section)
            if not chosen_text.strip():
                continue
            for other_id, other_avg in sorted(avgs.items()):
                if other_id == winner_id:
                    continue
                margin = avgs[winner_id] - other_avg
                other = drafts.get(other_id)
                if margin < min_margin or other is None:
                    continue
                rejected_text = other.section_text(section)
                if not rejected_text.strip() or rejected_text == chosen_text:
                    continue
                prefs.append(PreferencePair(
                    prompt=PREF_PROMPT.format(section=section.value, question=state.question),
                    chosen=chosen_text, rejected=rejected_text,
                    margin=round(margin, 4), section=section.value,
                    source_session=state.session_id))
    return sft, prefs


class TrainingCorpus:
    """Accumulates deduped SFT + preference examples across sessions; exports the
    JSONL a local LoRA trainer consumes. CED-owned data; harvested mechanically."""

    def __init__(self, min_margin: float = DEFAULT_MIN_MARGIN) -> None:
        self.min_margin = min_margin
        self._sft: List[SFTExample] = []
        self._prefs: List[PreferencePair] = []
        self._sft_keys: set = set()
        self._pref_keys: set = set()

    # -- accumulation (failure-isolated caller: CED ingest hook) --
    def ingest_session(self, state: SessionState, final: FinalResponse) -> Dict[str, int]:
        sft, prefs = harvest_session(state, final, min_margin=self.min_margin)
        added_sft = added_pref = 0
        for ex in sft:
            key = (ex.provenance, ex.output)
            if key not in self._sft_keys:
                self._sft_keys.add(key)
                self._sft.append(ex)
                added_sft += 1
        for pp in prefs:
            key = (pp.section, pp.chosen, pp.rejected)
            if key not in self._pref_keys:
                self._pref_keys.add(key)
                self._prefs.append(pp)
                added_pref += 1
        return {"sft_added": added_sft, "preferences_added": added_pref}

    # -- access --
    def sft_examples(self) -> List[SFTExample]:
        return list(self._sft)

    def preference_pairs(self) -> List[PreferencePair]:
        return list(self._prefs)

    def stats(self) -> Dict[str, Any]:
        roles: Dict[str, int] = {}
        for ex in self._sft:
            roles[ex.role] = roles.get(ex.role, 0) + 1
        sections: Dict[str, int] = {}
        for pp in self._prefs:
            sections[pp.section] = sections.get(pp.section, 0) + 1
        return {
            "schema_version": SCHEMA_VERSION,
            "sft_examples": len(self._sft),
            "preference_pairs": len(self._prefs),
            "sft_by_role": roles,
            "preferences_by_section": sections,
            "min_margin": self.min_margin,
        }

    # -- persistence (local JSONL + manifest; PUBLIC dialogue content only) --
    def save(self, directory: str) -> Dict[str, str]:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        sft_path, pref_path, manifest = d / "sft.jsonl", d / "preferences.jsonl", d / "manifest.json"
        with sft_path.open("w", encoding="utf-8") as f:
            for ex in self._sft:
                f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
        with pref_path.open("w", encoding="utf-8") as f:
            for pp in self._prefs:
                f.write(json.dumps(asdict(pp), ensure_ascii=False) + "\n")
        manifest.write_text(json.dumps(self.stats(), ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        return {"sft": str(sft_path), "preferences": str(pref_path), "manifest": str(manifest)}
