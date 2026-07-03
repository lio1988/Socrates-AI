"""
Phase 22 — The Teacher Loop (self-distillation flywheel), offline validation.

Verifies: SFT demonstrations come ONLY from ratified sessions; preference pairs
carry REAL peer-score margins with chosen==the winner draft's actual text (no
fabrication); dedupe + JSONL export; CED harvest hook is failure-isolated; and
the GPU/LoRA scaffold is inert-by-default (describes & generates, never trains,
never needs torch/keys/network).
"""

import asyncio
import json

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, AssembledAnswer, AssembledSection, DialogPhase,
    DraftScorecard, FinalResponse, ScoreBreakdown, SectionDraft, SectionName,
    SectionScore, SessionState,
)
from backend.dialogues.live_providers import build_council
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, BlockingObjectionProvider)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.training import (
    TrainingCorpus, harvest_session, build_training_plan, gpu_report,
    check_training_deps, write_training_script, reentry_instructions,
    TrainingUnavailable, LoRAConfig,
)
from backend.training.corpus import DEFAULT_MIN_MARGIN

Q = "Is knowledge merely justified true belief?"


# ── constructed state: deterministic preference-harvest math ──────────────────

def _bd(v):
    return ScoreBreakdown(epistemic_value=v, logical_rigor=v, factual_grounding=v,
                          constructive_impact=v, intellectual_honesty=v,
                          clarity_precision=v, grounded_creativity=v)


def _draft(did, author, core):
    return SectionDraft(draft_id=did, session_id="s", author_agent_id=author,
                        move_id=f"mv_{did}", provider_id=f"seat_{author}",
                        core_answer=core, crucial_stress_test="x", blind_spots="x",
                        nuance="x", final_verdict="x")


def _state_with_scored_drafts():
    st = SessionState(session_id="s", question=Q)
    st.section_drafts = [_draft("dA", "a0", "WINNER core answer"),
                         _draft("dB", "a1", "loser core answer")]
    # peer scores live in draft_scorecards: dA ~9, dB ~5 (voters are peers)
    for val, did, author in [(9.0, "dA", "a0"), (5.0, "dB", "a1")]:
        st.draft_scorecards.append(DraftScorecard(
            session_id="s", draft_id=did, author_agent_id=author, voter_agent_id="v",
            section_scores=[SectionScore(
                session_id="s", section_name=SectionName.CORE_ANSWER, draft_id=did,
                author_agent_id=author, voter_agent_id="v", score_breakdown=_bd(val),
                overall_score=val)]))
    st.assembled_answer = AssembledAnswer(session_id="s", sections=[
        AssembledSection(section_name=n,
                         selected_draft_id=("dA" if n == SectionName.CORE_ANSWER else ""),
                         selected_author_agent_id="a0",
                         content=("WINNER core answer" if n == SectionName.CORE_ANSWER else ""),
                         average_score=9.0, unresolved=(n != SectionName.CORE_ANSWER))
        for n in SectionName])
    return st


def _ratified_final(sid="s"):
    return FinalResponse(
        session_id=sid, question=Q, ratified=True, ratification_status="ratified",
        answer="A", synthesis=AssembledAnswer(session_id=sid, sections=[
            AssembledSection(section_name=n, selected_draft_id="dA",
                             selected_author_agent_id="a0", content=f"content {n.value}",
                             average_score=9.0) for n in SectionName]))


def test_preference_pair_is_winner_vs_loser_with_real_text():
    st = _state_with_scored_drafts()
    final = FinalResponse(session_id="s", question=Q, ratified=False,
                          ratification_status="repair_required")
    sft, prefs = harvest_session(st, final)
    assert len(prefs) == 1
    p = prefs[0]
    assert p.section == "core_answer"
    assert p.chosen == "WINNER core answer" and p.rejected == "loser core answer"
    assert p.margin == pytest.approx(4.0)          # 9 − 5, real peer-score gap


def test_preference_margin_gate():
    st = _state_with_scored_drafts()
    final = FinalResponse(session_id="s", question=Q, ratified=False,
                          ratification_status="repair_required")
    _, prefs = harvest_session(st, final, min_margin=5.0)   # gap is only 4.0
    assert prefs == []


def test_sft_only_from_ratified():
    st = _state_with_scored_drafts()
    # not ratified → no SFT synthesis demonstration, but preferences still harvested
    sft_no, prefs_no = harvest_session(
        st, FinalResponse(session_id="s", question=Q, ratified=False,
                          ratification_status="repair_required"))
    assert not any(e.provenance == "ratified_synthesis" for e in sft_no)
    assert prefs_no                                  # scores still yield a preference
    # ratified → the endorsed synthesis becomes an SFT demonstration
    sft_yes, _ = harvest_session(st, _ratified_final())
    assert any(e.provenance == "ratified_synthesis" and e.role == "synthesizer"
               for e in sft_yes)
    # and the SFT output is valid JSON of the endorsed answer
    ex = next(e for e in sft_yes if e.provenance == "ratified_synthesis")
    assert isinstance(json.loads(ex.output), dict)


# ── corpus accumulation, dedupe, export ───────────────────────────────────────

def test_corpus_dedupes_and_stats():
    corpus = TrainingCorpus()
    st, final = _state_with_scored_drafts(), _ratified_final()
    a = corpus.ingest_session(st, final)
    b = corpus.ingest_session(st, final)              # identical → deduped
    assert a["preferences_added"] == 1 and b["preferences_added"] == 0
    stats = corpus.stats()
    assert stats["preference_pairs"] == 1
    assert stats["sft_by_role"].get("synthesizer") == 1
    assert stats["schema_version"] == "teacher_corpus_v0"


def test_export_jsonl_round_trip(tmp_path):
    corpus = TrainingCorpus()
    corpus.ingest_session(_state_with_scored_drafts(), _ratified_final())
    paths = corpus.save(str(tmp_path))
    sft_lines = [json.loads(l) for l in open(paths["sft"], encoding="utf-8")]
    pref_lines = [json.loads(l) for l in open(paths["preferences"], encoding="utf-8")]
    assert sft_lines and all("instruction" in r and "output" in r for r in sft_lines)
    assert pref_lines and all({"prompt", "chosen", "rejected", "margin"} <= set(r)
                              for r in pref_lines)
    manifest = json.loads(open(paths["manifest"], encoding="utf-8").read())
    assert manifest["sft_examples"] == len(sft_lines)


# ── CED integration + failure isolation ───────────────────────────────────────

def test_ced_harvests_from_real_sessions():
    corpus = TrainingCorpus()
    ced, mode = build_council(env={}, council_size=2, training_corpus=corpus)
    assert mode == "mock"
    asyncio.run(ced.run_registry_session(Q, session_id="h1"))
    assert corpus.stats()["sft_examples"] >= 1        # ratified mock session teaches


def test_harvest_hook_is_failure_isolated():
    class Exploding:
        def ingest_session(self, state, final):
            raise RuntimeError("disk full")
    ced, _ = build_council(env={}, council_size=2, training_corpus=Exploding())
    final = asyncio.run(ced.run_registry_session(Q, session_id="boom"))
    assert final.ratified is True                     # session survives a broken corpus
    assert final.audit_summary.get("self_improvement_error") is True


# ── GPU / LoRA scaffold is inert and safe ─────────────────────────────────────

def test_gpu_report_never_crashes_without_torch():
    r = gpu_report()
    assert set(("torch_installed", "cuda_available", "devices", "note")) <= set(r)
    assert isinstance(r["cuda_available"], bool)


def test_check_training_deps_shape():
    deps = check_training_deps()
    assert set(deps) == {"torch", "transformers", "peft", "trl", "datasets"}
    assert all(isinstance(v, bool) for v in deps.values())


def test_training_plan_is_pure_description():
    stats = {"sft_examples": 120, "preference_pairs": 60}
    plan = build_training_plan(stats, LoRAConfig(), gpu={"cuda_available": False})
    d = plan.as_dict()
    assert d["stages"] == ["SFT", "DPO"] and d["sft_examples"] == 120
    assert d["device"] == "cpu"
    assert any("NVIDIA" in w for w in d["warnings"])   # honest about no-GPU


def test_generated_script_is_valid_python_and_complete(tmp_path):
    import ast
    path = str(tmp_path / "train_student.py")
    write_training_script(path, LoRAConfig(base_model="test/model"),
                          "sft.jsonl", "prefs.jsonl")
    src = open(path, encoding="utf-8").read()
    ast.parse(src)                                     # valid Python
    for token in ("SFTTrainer", "DPOTrainer", "LoraConfig", "test/model",
                  "torch.cuda.is_available()"):
        assert token in src


def test_training_is_never_auto_run():
    # importing/using the module trains nothing and needs no torch (all deps False)
    assert check_training_deps()["torch"] is False
    assert issubclass(TrainingUnavailable, RuntimeError)
    assert "provider adapter" in reentry_instructions()
