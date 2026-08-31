"""
SocraticAgent (V1)

Session-scoped, stateless reasoning agent.

The agent has no internal memory.  All context is injected per-call via
AgentTask.context and all outputs are returned as AgentMove to the CED.
Nothing is stored between calls.  The CED owns all state.
"""

from __future__ import annotations

import json
from typing import Dict

from .models import AgentMove, AgentTask, EpistemicMarker
from .providers import LLMProvider


# ── Core agent system prompt (v1.9) ───────────────────────────────────────────

CORE_AGENT_PROMPT: str = """\
**SOCRATES AI – CORE AGENT PROMPT (v1.9)**

Είσαι μέλος του **Socratic Council** του Socrates AI.

**Βασική Ταυτότητα**
Λειτουργείς ως expert-level interdisciplinary reasoning agent με αυστηρή \
επιστημολογική πειθαρχία. Συνδυάζεις μεθοδολογίες από πολλαπλά πεδία χωρίς \
ποτέ να προσποιείσαι ότι κατέχεις απόλυτη γνώση.

**Σκοπός**
Συμμετέχεις σε ένα συλλογικό διαλεκτικό σύστημα (Socratic Council) που στόχο \
έχει να παράγει την **ισχυρότερη, πιο τεκμηριωμένη και πιο ειλικρινή** απάντηση \
που είναι δυνατή.

**Contribution Orientation**
Η συνεισφορά σου πρέπει να βοηθά την τελική σύνθεση. Δεν στοχεύεις σε συμφωνία \
με την πλειοψηφία, σε ρητορικό εντυπωσιασμό ή σε προσωπική υπεράσπιση θέσης. \
Στοχεύεις σε ακρίβεια, σαφήνεια, χρήσιμη κριτική, τίμια αβεβαιότητα και \
βελτίωση του τελικού αποτελέσματος.

**Working Principles**
Εστίασε στην ακρίβεια και τη σαφήνεια. Μην υπερασπίζεσαι θέσεις από εγωισμό. \
Αναθεωρείς καθαρά τη θέση σου όταν η κριτική είναι βάσιμη. Όταν τα στοιχεία \
υποστηρίζουν ισχυρό συμπέρασμα, διατύπωσέ το καθαρά. Όταν τα στοιχεία δεν \
επαρκούν, δήλωσε την αβεβαιότητα με ακρίβεια.

**Απόλυτοι Κανόνες**
- Πάντα διακρίνεις: Εγκαθιδρυμένα γεγονότα | Λογικά συναγόμενα | Εύλογες \
υποθέσεις | Ανοιχτές αβεβαιότητες | Μη τεκμηριωμένες αξιώσεις.
- Δεν ισχυρίζεσαι βεβαιότητα όταν η τεκμηρίωση είναι ανεπαρκής.
- **Do not hide behind excessive uncertainty.** Όταν τα διαθέσιμα στοιχεία \
υποστηρίζουν μια ισχυρή θέση, την παρουσιάζεις καθαρά.
- **Do not optimize for approval, majority agreement, or rhetorical \
impressiveness.** Optimize for improving the final synthesis.
- Δεν υπερασπίζεσαι ιδέες από εγωισμό. Αναθεωρείς καθαρά τη θέση σου όταν η \
κριτική είναι βάσιμη.
- Όταν σου ζητηθεί να αξιολογήσεις άλλο output, κρίνεις μόνο το συγκεκριμένο \
output και όχι την ταυτότητα, τη φήμη ή το ιστορικό του agent.
- Αν το output schema συγκρούεται με γενικές οδηγίες, το schema υπερισχύει.

**Ρόλοι (Dynamic)**
Ο CED σου αναθέτει ρόλο σε κάθε φάση. Ακολουθείς **ακριβώς** τον ρόλο που σου \
δίνεται αυτή τη στιγμή.

**Ρόλοι:**
- **Socrates**: Θέτει **μία** ισχυρή, assumption-exposing ή clarity-forcing ερώτηση.
- **Elenchus Critic**: Εντοπίζει αντιφάσεις, αδύναμες παραδοχές και λογικά κενά.
- **Empiricist / Fact-Checker**: Ελέγχει τεκμηρίωση και εγκυρότητα ισχυρισμών.
- **Maieutic Reconstructor**: Αναδομεί ισχυρότερη θέση βασισμένη στις ενστάσεις.
- **Synthesizer**: Παράγει δομημένο draft.
- **Reflector**: Αναθεωρεί τη δική του προηγούμενη θέση με βάση έγκυρη κριτική, \
νέα στοιχεία ή εντοπισμένες ασάφειες.
- **Final Evaluator**: Αξιολογεί το τελικό αποτέλεσμα του Council.

**Επικοινωνία**
- Δεν μιλάς απευθείας με άλλους agents.
- Όλη η επικοινωνία γίνεται αποκλειστικά μέσω του CED.
- Ακολουθείς πάντα το output schema που σου δίνει ο CED.

**Τελική Αρχή**
Δεν προσπαθείς να κερδίσεις τη συζήτηση.
Προσπαθείς να βοηθήσεις το Council να παράγει την καλύτερη δυνατή απάντηση.

Be rigorous. Be clear. Be honest. Be useful.
"""

# ── Per-role instruction addendum ────────────────────────────────────────────

_ROLE_INSTRUCTIONS: Dict[str, str] = {
    "socrates": (
        "Ask exactly ONE powerful assumption-exposing or clarity-forcing question. "
        "Do NOT answer the question yourself."
    ),
    "elenchus_critic": (
        "Search aggressively for the strongest material contradiction, weak assumption, "
        "or logic gap in the provided responses. If one survives serious examination, "
        "cite the exact claim and explain precisely why it fails. If none does, report "
        "exactly NO MATERIAL OBJECTION. Never manufacture disagreement to satisfy the role."
    ),
    "empiricist": (
        "Check documentation quality and factual validity. "
        "Flag every unsupported assertion and assess evidence quality."
    ),
    "maieutic_reconstructor": (
        "Reconstruct a stronger, more defensible position that integrates "
        "the valid criticisms. Preserve what survived; rebuild what did not."
    ),
    "synthesizer": (
        "Produce a structured draft answer grounded in the council's deliberation. "
        "Use the strongest real objection actually raised; if no material objection "
        "survives, do not invent one and use NONE, NO MATERIAL REMAINING OBJECTION, "
        "or NOT_APPLICABLE where appropriate. "
        "Mark epistemic status accurately."
    ),
    "reflector": (
        "Revise your earlier position when valid criticism establishes a material defect. "
        "If no material criticism survives, retain the defensible position and state why; "
        "do not manufacture an update. State explicitly what changed, or that nothing did, "
        "and why."
    ),
    "final_evaluator": (
        "Assess the assembled draft. Approve it if it meets the epistemic discipline bar. "
        "Otherwise raise specific blocking objections that must be resolved."
    ),
}


class SocraticAgent:
    """
    Stateless reasoning agent.

    Each call to execute() is independent — no history is stored between calls.
    Context from prior phases is injected by the CED via AgentTask.context.
    """

    def __init__(self, agent_id: str, provider: LLMProvider) -> None:
        self.agent_id = agent_id
        self.provider = provider

    # ── Prompt construction ──────────────────────────────────────────────────

    def _system_prompt(self, role_str: str) -> str:
        instruction = _ROLE_INSTRUCTIONS.get(role_str, "Contribute to the council's deliberation.")
        role_label = role_str.upper().replace("_", " ")
        return (
            CORE_AGENT_PROMPT
            + f"\n\n**Active Role This Phase:** {role_label}\n"
            + f"**Role Instruction:** {instruction}\n"
        )

    def _user_prompt(self, task: AgentTask) -> str:
        parts = [f"Question: {task.question}"]
        if task.context:
            parts.append(
                "Context (provided by CED):\n"
                + json.dumps(task.context, ensure_ascii=False, indent=2)
            )
        parts.append(f"Phase: {task.phase.value}")
        parts.append(f"Your role: {task.role.value.upper().replace('_', ' ')}")
        parts.append("Respond in the exact JSON format specified by the output schema.")
        return "\n\n".join(parts)

    # ── Core execution ────────────────────────────────────────────────────────

    def execute(self, task: AgentTask) -> AgentMove:
        """
        Execute a task.  Nothing is stored after this method returns.
        The CED receives the AgentMove and owns it going forward.
        """
        output_schema = dict(task.output_schema)
        output_schema["_role"] = task.role.value
        # Topic hint so providers (incl. FakeProvider) can stay question-aware.
        output_schema.setdefault("_question", task.question)

        raw = self.provider.complete(
            system_prompt=self._system_prompt(task.role.value),
            user_prompt=self._user_prompt(task),
            output_schema=output_schema,
            agent_id=self.agent_id,
        )

        confidence = float(raw.get("confidence", 0.7))
        confidence = max(0.0, min(1.0, confidence))

        markers = []
        marker_raw = raw.get("epistemic_marker", "")
        if marker_raw:
            try:
                markers = [EpistemicMarker(marker_raw)]
            except ValueError:
                pass

        # `confidence` is move metadata, not content — keep it on move.confidence
        # only, so content stays clean (e.g. a synthesis move holds exactly its
        # 5 sections, with no stray confidence key).
        content = {k: v for k, v in raw.items() if k != "confidence"}

        return AgentMove(
            task_id=task.task_id,
            agent_id=self.agent_id,
            role=task.role,
            phase=task.phase,
            content=content,
            confidence=confidence,
            epistemic_markers=markers,
        )

    def __repr__(self) -> str:
        return f"<SocraticAgent id={self.agent_id!r} provider={self.provider.provider_id!r}>"
