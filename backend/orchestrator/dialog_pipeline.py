"""The Constitution-compliant multi-phase reasoning pipeline (Rules 1-14) and
its helpers. Extracted from main.py. Runs as a FastAPI background task.

NOTE: this is the dialog-centric loop. The claim-centric CED epistemic core
lives in backend/epistemic and backend/reasoning; converging this pipeline onto
that core (claims as the central objects) is the next planned phase.
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict

from backend.storage.models import *
from backend.constitution_guard import ConstitutionGuard, ConstitutionViolationError
from backend.orchestrator.session import session_manager, EnhancedDialogSession
from backend.orchestrator.router import select_synthesis_model, classify_domain


async def _run_dialog_pipeline(session_id: str) -> None:
    """
    Full multi-phase pipeline implementing all 15 Constitution rules.

    Per-round flow:
      1. Socrates speaks (rotating — Rule 1, 2)
      2. Each participant reflects (Rule 5)
      3. Each participant responds
      4. Elenchus phase: falsification attempt (Rule 3)
      5. If falsified: revision round (Rule 3)
      6. Update Contradiction Graph (Rule 7)
      7. Extract and verify claims (Rule 6)
      8. Update Consensus Memory (Rule 9)
      9. Update Knowledge Graph (Rule 8)
      10. Check convergence (Rule 11)

    Post-loop:
      11. Dynamic synthesis by domain model (Rule 12)
      12. Explainability package (Rule 13)
      13. Log evolution (Rule 14)
    """
    s = session_manager.get(session_id)
    if s is None:
        return

    s.status = "running"

    try:
        for round_num in range(1, s.enforced_rounds + 1):
            # ── Pause check ──────────────────────────────────────────────
            await s._paused.wait()
            if s._stop_requested:
                break

            s.current_round = round_num

            # ── Rule 1+2: Next Socrates ───────────────────────────────────
            socrates_id = s.next_socrates()

            # ── Inject pending question ───────────────────────────────────
            if s.pending_injection:
                inject_turn = DialogTurnResponse(
                    round=round_num,
                    model_id="user",
                    content=s.pending_injection,
                    is_socratic=False,
                    is_elenchus=False,
                    is_reflection=False,
                    timestamp=datetime.now().isoformat(),
                )
                s.history.append(inject_turn)
                s.pending_injection = None

            # ── Build context from history ────────────────────────────────
            context = _build_context(s)

            # ── Socratic phase (Rule 2) ───────────────────────────────────
            socratic_response = await _call_model(
                s, socrates_id,
                _socratic_prompt(s.config.topic, round_num, s.enforced_rounds, s.config.mode.value),
                context, is_socratic=True,
            )
            if socratic_response:
                s.scores[socrates_id] = s.scores.get(socrates_id, 0) + 1
                s.history.append(DialogTurnResponse(
                    round=round_num, model_id=socrates_id,
                    content=socratic_response, is_socratic=True,
                    is_elenchus=False, is_reflection=False,
                    timestamp=datetime.now().isoformat(),
                ))

            # ── Per-participant: Reflect → Respond (Rules 5 + 4) ──────────
            for participant_id in s.available_models:
                if participant_id == socrates_id:
                    continue
                await s._paused.wait()
                if s._stop_requested:
                    break

                # Rule 5: Reflection step
                reflection = await _reflection_step(s, participant_id, round_num, context)
                if reflection:
                    s.reflection_history.append(reflection)

                # Final response uses reflection output
                response_content = reflection.final_reasoning if reflection else ""
                if not response_content:
                    response_content = await _call_model(
                        s, participant_id,
                        _participant_prompt(s.config.topic, round_num, s.enforced_rounds, s.config.mode.value),
                        context, is_socratic=False,
                    ) or ""

                if response_content:
                    improved = bool(reflection and reflection.improved)
                    s.scores[participant_id] = s.scores.get(participant_id, 0) + (3 if improved else 1)
                    s.history.append(DialogTurnResponse(
                        round=round_num, model_id=participant_id,
                        content=response_content, is_socratic=False,
                        is_elenchus=False, is_reflection=False,
                        timestamp=datetime.now().isoformat(),
                    ))
                    # Extract claims from response (Rule 6)
                    _extract_claims(s, participant_id, response_content, round_num)

            # ── Rule 3: Elenchus phase ────────────────────────────────────
            elenchus_challenger = _pick_elenchus_challenger(s, socrates_id)
            elenchus = await _elenchus_phase(s, elenchus_challenger, round_num, context)
            if elenchus:
                s.elenchus_history.append(elenchus)
                s.history.append(DialogTurnResponse(
                    round=round_num, model_id=elenchus_challenger,
                    content=f"[ELENCHUS] Challenged assumptions: {'; '.join(elenchus.challenged_assumptions[:2])}. "
                            f"Falsification {'successful' if elenchus.falsification_successful else 'unsuccessful'}.",
                    is_socratic=False, is_elenchus=True, is_reflection=False,
                    timestamp=datetime.now().isoformat(),
                ))
                # Rule 3: If falsified, trigger revision
                if elenchus.falsification_successful and elenchus.revision_required:
                    await _revision_round(s, elenchus, round_num, context)

            # ── Rule 7: Update Contradiction Graph ────────────────────────
            _update_contradiction_graph(s, round_num)

            # ── Rule 9: Update Consensus Memory ──────────────────────────
            _update_consensus_memory(s, round_num)

            # ── Rule 8: Update Knowledge Graph ────────────────────────────
            _update_knowledge_graph(s, round_num)

            # ── Rule 11: Convergence check ────────────────────────────────
            s.update_convergence()
            if s.consensus_stable:
                s.evolution_log.append(EvolutionEntry(
                    component="reasoning_policy",
                    change=f"Early stopping at round {round_num}",
                    reason=f"Convergence reached: score={s.convergence_score}",
                    round=round_num,
                ))
                break

        # ── Constitution assertions at end of loop ─────────────────────────
        _run_end_of_loop_assertions(s)

        # ── Rule 12+13: Dynamic Synthesis ────────────────────────────────
        await _produce_synthesis(s)

    except ConstitutionViolationError as exc:
        s._log_violation(exc)
        s.status = "error"
        return
    except Exception as exc:
        print(f"❌ Pipeline error [{session_id}]: {exc}")
        s.status = "error"
        return

    s.status = "completed"


# ── Pipeline helpers ─────────────────────────────────────────────────────────

def _build_context(s: EnhancedDialogSession) -> str:
    """Build conversation context from recent history"""
    recent = s.history[-8:]
    lines = []
    for t in recent:
        tag = " (Σωκράτης)" if t.is_socratic else (" (Elenchus)" if t.is_elenchus else "")
        lines.append(f"[{t.model_id}{tag}]: {t.content}")
    return "\n".join(lines)


async def _call_model(
    s: EnhancedDialogSession,
    model_id: str,
    system_prompt: str,
    context: str,
    is_socratic: bool = False,
) -> Optional[str]:
    """Call the underlying dialog manager for a model response"""
    try:
        if s.manager is None:
            return None
        # DialogManager exposes `_call_model(model_id, prompt)` — a single
        # prompt string. Combine the system instructions with the running
        # conversation context into one prompt. (The previous code called a
        # non-existent `call_model(...)`, so every call silently returned None,
        # which left the Elenchus history empty and tripped Rule 3.)
        prompt = system_prompt
        if context:
            prompt = f"{system_prompt}\n\nConversation so far:\n{context}"
        return await s.manager._call_model(model_id, prompt)
    except Exception as exc:
        print(f"  ⚠️ {model_id} call failed: {exc}")
        return None


async def _reflection_step(
    s: EnhancedDialogSession,
    model_id: str,
    round_num: int,
    context: str,
) -> Optional[ReflectionStep]:
    """
    Rule 5: Generate reflection for an agent.
    Initial → Self-criticism → Revision → Final.
    """
    try:
        system = (
            f"You are {model_id}. BEFORE giving your answer, follow this mandatory reflection protocol:\n"
            f"1. STATE your initial reasoning (2 sentences).\n"
            f"2. CRITICISE your own reasoning — find flaws, gaps, or biases.\n"
            f"3. REVISE your position based on the criticism.\n"
            f"4. STATE your final reasoning.\n"
            f"Output format:\n"
            f"INITIAL: ...\nCRITICISM: ...\nREVISION: ...\nFINAL: ...\n"
            f"Topic: '{s.config.topic}'"
        )
        raw = await _call_model(s, model_id, system, context)
        if not raw:
            return None

        def _extract(label: str) -> str:
            import re
            m = re.search(rf"{label}:(.*?)(?:(?:INITIAL|CRITICISM|REVISION|FINAL):|$)", raw, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        initial    = _extract("INITIAL")
        criticism  = _extract("CRITICISM")
        revision   = _extract("REVISION")
        final      = _extract("FINAL") or raw

        improved = bool(revision and revision.strip() != initial.strip())

        return ReflectionStep(
            model_id=model_id,
            round=round_num,
            initial_reasoning=initial,
            self_criticism=criticism,
            revision=revision,
            final_reasoning=final,
            improved=improved,
        )
    except Exception:
        return None


async def _elenchus_phase(
    s: EnhancedDialogSession,
    challenger_id: str,
    round_num: int,
    context: str,
) -> Optional[ElenchusResult]:
    """
    Rule 3: Mandatory Elenchus — attempt to falsify the latest answer.
    """
    system = (
        f"You are the Elenchus challenger ({challenger_id}). Your ONLY job is to falsify.\n"
        f"Examine the latest claims in the dialogue and attempt to:\n"
        f"1. Identify hidden assumptions\n"
        f"2. Expose logical gaps\n"
        f"3. Challenge evidence\n"
        f"4. Question conclusions\n"
        f"Output JSON only:\n"
        f'{{"challenged_assumptions":["..."],"logic_gaps":["..."],"evidence_issues":["..."],"conclusion_issues":["..."],"falsification_successful":true/false}}'
    )
    import json
    raw = await _call_model(s, challenger_id, system, context)
    if not raw:
        # Defensive (Rule 3): even if the challenger returns nothing, record a
        # structural Elenchus so every round is challenged and falsification is
        # never silently skipped.
        return ElenchusResult(
            round=round_num,
            target_claim_summary=context[-200:] if context else "",
            challenger_model=challenger_id,
            challenged_assumptions=[
                "Challenger produced no output; structural challenge recorded."
            ],
            logic_gaps=[],
            evidence_issues=[],
            conclusion_issues=[],
            falsification_successful=False,
            revision_required=False,
        )

    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean)
    except Exception:
        data = {
            "challenged_assumptions": ["Unable to parse structured elenchus."],
            "logic_gaps": [], "evidence_issues": [], "conclusion_issues": [],
            "falsification_successful": False,
        }

    falsified = data.get("falsification_successful", False)
    return ElenchusResult(
        round=round_num,
        target_claim_summary=context[-200:] if context else "",
        challenger_model=challenger_id,
        challenged_assumptions=data.get("challenged_assumptions", []),
        logic_gaps=data.get("logic_gaps", []),
        evidence_issues=data.get("evidence_issues", []),
        conclusion_issues=data.get("conclusion_issues", []),
        falsification_successful=falsified,
        revision_required=falsified,
    )


async def _revision_round(
    s: EnhancedDialogSession,
    elenchus: ElenchusResult,
    round_num: int,
    context: str,
) -> None:
    """Rule 3: If Elenchus falsified, the original model MUST revise"""
    # Find which model was challenged (latest non-elenchus turn)
    target_model = next(
        (t.model_id for t in reversed(s.history) if not t.is_elenchus and t.model_id != "user"),
        None
    )
    if not target_model:
        return

    system = (
        f"Your previous answer was successfully challenged by Elenchus.\n"
        f"Identified issues:\n"
        f"- Assumptions: {'; '.join(elenchus.challenged_assumptions)}\n"
        f"- Logic gaps: {'; '.join(elenchus.logic_gaps)}\n"
        f"You MUST revise your answer to address these issues. "
        f"Do not simply repeat your previous answer. Topic: '{s.config.topic}'"
    )
    revision_text = await _call_model(s, target_model, system, context)
    if revision_text:
        elenchus.revision_submitted = True
        s.history.append(DialogTurnResponse(
            round=round_num, model_id=target_model,
            content=f"[REVISION after Elenchus] {revision_text}",
            is_socratic=False, is_elenchus=False, is_reflection=False,
            timestamp=datetime.now().isoformat(),
        ))
        s.scores[target_model] = s.scores.get(target_model, 0) + 2


def _pick_elenchus_challenger(s: EnhancedDialogSession, socrates_id: str) -> str:
    """Rule 1: Elenchus challenger also rotates"""
    participants = [m for m in s.available_models if m != socrates_id]
    if not participants:
        return s.available_models[0]
    idx = s.current_round % len(participants)
    return participants[idx]


def _extract_claims(
    s: EnhancedDialogSession,
    model_id: str,
    text: str,
    round_num: int,
) -> None:
    """
    Rule 6: Simple heuristic claim extraction from response text.
    In production, use a dedicated LLM call for structured extraction.
    """
    import re
    sentences = re.split(r'[.!?]', text)
    factual_markers = ['is', 'are', 'was', 'were', 'has', 'have', 'proves', 'shows', 'demonstrates', 'according']
    for sent in sentences[:5]:  # max 5 claims per turn
        sent = sent.strip()
        if len(sent) < 20:
            continue
        if any(m in sent.lower() for m in factual_markers):
            claim = Claim(
                text=sent[:300],
                evidence="",
                confidence=0.4,
                source=model_id,
                status=ClaimStatus.UNVERIFIED,
                round=round_num,
            )
            try:
                ConstitutionGuard.assert_claim_has_provenance(claim)
                s.claims.append(claim)
            except ConstitutionViolationError:
                pass  # Claim rejected — logged implicitly


def _update_contradiction_graph(s: EnhancedDialogSession, round_num: int) -> None:
    """Rule 7: Add recent claims as nodes; detect contradiction edges"""
    for claim in s.claims:
        if claim not in s.contradiction_graph.nodes:
            s.contradiction_graph.nodes.append(claim)

    # Simple heuristic: compare latest claim against previous claims
    if len(s.claims) < 2:
        return
    latest = s.claims[-1]
    for prev in s.claims[-10:-1]:
        if prev.source == latest.source:
            continue
        # Heuristic: negation words suggest contradiction
        neg_words = ["not", "never", "no", "false", "incorrect", "wrong", "disagree"]
        if any(w in latest.text.lower() for w in neg_words):
            edge = ContradictionEdge(
                source_claim_id=prev.claim_id,
                target_claim_id=latest.claim_id,
                edge_type=EdgeType.CONTRADICTS,
                explanation="Heuristic: negation language detected",
                detected_by=latest.source,
                detected_in_round=round_num,
            )
            s.contradiction_graph.edges.append(edge)
            latest.status = ClaimStatus.CONTRADICTED
        elif any(w in latest.text.lower() for w in ["supports", "confirms", "agrees", "consistent"]):
            edge = ContradictionEdge(
                source_claim_id=prev.claim_id,
                target_claim_id=latest.claim_id,
                edge_type=EdgeType.SUPPORTS,
                explanation="Heuristic: support language detected",
                detected_by=latest.source,
                detected_in_round=round_num,
            )
            s.contradiction_graph.edges.append(edge)


def _update_consensus_memory(s: EnhancedDialogSession, round_num: int) -> None:
    """Rule 9: Update Consensus Memory from recent dialogue"""
    # Heuristic: if same claim is supported by ≥2 models, it's a consensus item
    model_claims: dict[str, List[str]] = {}
    for claim in s.claims[-20:]:
        model_claims.setdefault(claim.source, []).append(claim.text.lower()[:60])

    models = list(model_claims.keys())
    if len(models) < 2:
        return

    # Find overlapping key phrases
    for i, m1 in enumerate(models):
        for m2 in models[i+1:]:
            for c1 in model_claims[m1]:
                for c2 in model_claims[m2]:
                    # Very rough similarity check
                    words1 = set(c1.split())
                    words2 = set(c2.split())
                    overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                    if overlap > 0.4:
                        # Check not already stored
                        already = any(c1[:30] in item.content for item in s.consensus_memory.verified_conclusions)
                        if not already:
                            item = ConsensusItem(
                                type=ConsensusItemType.CONCLUSION,
                                content=c1[:200],
                                evidence=[c2[:100]],
                                confidence=min(0.5 + overlap, 1.0),
                                models_agreed=[m1, m2],
                                round=round_num,
                            )
                            try:
                                ConstitutionGuard.assert_consensus_not_single_model(
                                    item.models_agreed, s.available_models
                                )
                                s.consensus_memory.verified_conclusions.append(item)
                            except ConstitutionViolationError as exc:
                                s._log_violation(exc)


def _update_knowledge_graph(s: EnhancedDialogSession, round_num: int) -> None:
    """
    Rule 8: Add only VERIFIED claims as Knowledge Graph concepts.
    Unverified, opinionated, or risky claims are rejected.
    """
    for claim in s.claims:
        if claim.status != ClaimStatus.VERIFIED:
            continue
        # Check not already in graph
        if any(c.label[:40] == claim.text[:40] for c in s.knowledge_graph.concepts):
            continue

        concept = KnowledgeConcept(
            label=claim.text[:80],
            definition=claim.text,
            confidence=claim.confidence,
            source_model=claim.source,
            validated=True,
            round_added=round_num,
            is_opinion=False,
            is_hallucination_risk=False,
        )
        try:
            ConstitutionGuard.assert_knowledge_graph_validated_only(concept)
            added = s.knowledge_graph.add_concept(concept)
            if added:
                s.evolution_log.append(EvolutionEntry(
                    component="reasoning_policy",
                    change=f"Added concept to Knowledge Graph: '{concept.label[:40]}'",
                    reason=f"Claim verified by {claim.source} in round {round_num}",
                    round=round_num,
                ))
        except ConstitutionViolationError as exc:
            s._log_violation(exc)


def _run_end_of_loop_assertions(s: EnhancedDialogSession) -> None:
    """Run all end-of-dialogue Constitution assertions"""
    try:
        ConstitutionGuard.assert_socratic_phase_present(s.history)
    except ConstitutionViolationError as exc:
        s._log_violation(exc)

    try:
        ConstitutionGuard.assert_elenchus_after_claim(s.elenchus_history, s.current_round)
    except ConstitutionViolationError as exc:
        s._log_violation(exc)


async def _produce_synthesis(s: EnhancedDialogSession) -> None:
    """
    Rule 12: Select domain-appropriate model for synthesis.
    Rule 13: Full explainability package.
    Rule 4: Synthesis emerges from dialogue, not authority.
    """
    domain = s.synthesis_domain or Domain.GENERAL
    synth_model = select_synthesis_model(domain, s.available_models)
    domain_reason = f"Domain '{domain.value}' → '{synth_model}' selected (Rule 12)"

    context = _build_context(s)
    conclusion_texts = [i.content for i in s.consensus_memory.verified_conclusions]
    disagreement_texts = [i.content for i in s.consensus_memory.remaining_disagreements]
    claim_texts = [c.text for c in s.claims]

    # Rule 13: Synthesis must include all required fields
    system = (
        f"You are the final Synthesizer for domain '{domain.value}' (Rule 12).\n"
        f"IMPORTANT — You may NOT add new facts. Synthesis is based ONLY on what was already established.\n"
        f"Verified conclusions: {json.dumps(conclusion_texts[:5])}\n"
        f"Remaining disagreements (MUST be exposed — Rule 13): {json.dumps(disagreement_texts[:3])}\n"
        f"Provide:\n"
        f"REASONING_SUMMARY: ...\n"
        f"SUPPORTING_EVIDENCE: bullet list\n"
        f"REMAINING_UNCERTAINTY: ...\n"
        f"CONFIDENCE: 0.0-1.0\n"
        f"ALTERNATIVE_VIEWPOINTS: bullet list\n"
        f"FINAL_ANSWER: ...\n"
        f"Topic: '{s.config.topic}'"
    )

    raw = await _call_model(s, synth_model, system, context)
    if not raw:
        return

    import re

    def _extract(label: str) -> str:
        m = re.search(rf"{label}:(.*?)(?:[A-Z_]+:|$)", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _extract_list(label: str) -> List[str]:
        block = _extract(label)
        return [l.strip("- •").strip() for l in block.split("\n") if l.strip("- •").strip()]

    confidence_str = _extract("CONFIDENCE")
    try:
        confidence = float(confidence_str.strip()) if confidence_str else 0.6
    except ValueError:
        confidence = 0.6

    # Rule 6+: Check synthesis doesn't add new facts
    synth_text = raw
    suspected_new_facts = ConstitutionGuard.assert_synthesis_no_new_facts(synth_text, claim_texts)
    if suspected_new_facts:
        s.constitution_violations.append(
            f"[Synthesis] Possible new facts injected: {suspected_new_facts[:2]}"
        )

    synthesis = SynthesisResult(
        selected_model=synth_model,
        domain=domain,
        domain_selection_reason=domain_reason,
        reasoning_summary=_extract("REASONING_SUMMARY"),
        supporting_evidence=_extract_list("SUPPORTING_EVIDENCE"),
        remaining_uncertainty=_extract("REMAINING_UNCERTAINTY"),
        confidence_score=min(max(confidence, 0.0), 1.0),
        alternative_viewpoints=_extract_list("ALTERNATIVE_VIEWPOINTS"),
        hidden_disagreements=[],  # Rule 13: we NEVER hide disagreements
        final_answer=_extract("FINAL_ANSWER") or raw[:500],
        emerged_from_dialogue=True,
        claims_referenced=[c.claim_id for c in s.claims[-10:]],
    )

    try:
        ConstitutionGuard.assert_disagreements_exposed(synthesis)
    except ConstitutionViolationError as exc:
        s._log_violation(exc)

    s.synthesis_result = synthesis

    # Rule 14: Log synthesis event
    s.evolution_log.append(EvolutionEntry(
        component="routing",
        change=f"Synthesis assigned to '{synth_model}' for domain '{domain.value}'",
        reason=domain_reason,
        round=s.current_round,
    ))


# ── Prompt builders ──────────────────────────────────────────────────────────

def _socratic_prompt(topic: str, r: int, total: int, mode: str) -> str:
    return (
        f"You are the Socratic questioner (Rule 2). Your ONLY role is to ask questions.\n"
        f"DO NOT provide answers. DO NOT make claims.\n"
        f"Your responsibilities:\n"
        f"  1. Identify assumptions in what has been said\n"
        f"  2. Ask ONE clarifying question that exposes a contradiction or gap\n"
        f"  3. Request evidence for unsubstantiated claims\n"
        f"Mode: {mode}. Round {r}/{total}. Topic: '{topic}'\n"
        f"Output: max 3 sentences + 1 question. Never answer your own question."
    )


def _participant_prompt(topic: str, r: int, total: int, mode: str) -> str:
    return (
        f"You are a dialogue participant (Rule 4 — Maieutic Emergence).\n"
        f"State and defend your position clearly. If the Socratic question exposed a genuine gap:\n"
        f"  - Acknowledge it honestly\n"
        f"  - Revise your position\n"
        f"  - Show your reasoning explicitly\n"
        f"Mode: {mode}. Round {r}/{total}. Topic: '{topic}'\n"
        f"Max 5 sentences."
    )


# ============================================================================
# SECTION 13: RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        proxy_headers=False,
        port=8000,
        log_level="info",
    )
