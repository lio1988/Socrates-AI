# Socrates AI — Computational Epistemic Dynamics (CED)

Reference implementation of a **claim-centric Knowledge Operating System**.
Independent AI reasoners turn uncertainty into structured, evidence-backed,
revisable knowledge through Socratic challenge, reflection, belief revision and
knowledge emergence.

This is **not** a chatbot and **not** a simple multi-agent debate app. Claims —
not agents — are the central living objects.

> Unknown → Question → Hypothesis → Claim → Challenge → Revision → Evidence →
> Knowledge Emergence → **Current Best Explanation**

## What's implemented (MVP Core — Phases 1 & 2, plus key Phase 3 gates)

| Module | Role |
|---|---|
| `epistemic/epistemic_state.py` | State machine with **validated transitions**. Makes `HYPOTHESIS → KNOWLEDGE` shortcuts impossible. |
| `epistemic/claim.py` | `Claim` as a first-class object: evidence, contradictions, dependencies, full revision history. |
| `epistemic/epistemic_graph.py` | Typed nodes/edges storing the **evolution of reasoning**, not just final facts. |
| `epistemic/knowledge_emergence.py` | Evidence-gated promotion. Weak-evidence majority ≠ knowledge; strong-evidence minority stays visible. |
| `agents/model_adapter.py` | Provider-agnostic adapter + deterministic `MockModel` (runs offline, zero cost). |
| `agents/base_agent.py` | Agent wrapping a model + a **rotating** role. |
| `orchestrator/socratic_rotation.py` | Enforces **no permanent authority** — Socratic role rotates. |
| `reasoning/elenchus_engine.py` | Structured Socratic refutation; applies lifecycle consequences. |
| `reasoning/reflection_engine.py` | Forces `INITIAL/SELF_CRITICISM/REVISION/FINAL`; only FINAL feeds claim extraction. |
| `reasoning/synthesis_engine.py` | Builds the Current Best Explanation; **cannot add new facts**. |
| `orchestrator/reasoning_loop.py` | The full §7 pipeline, end-to-end on mocks. |
| `constitution.py` | The five non-negotiable principles as **machine-checkable invariants**. |

## Run it

```bash
pip install -r requirements.txt
python run_demo.py "Should a small team adopt microservices?"
python -m pytest tests/ -v
```

The demo prints a Current Best Explanation plus a constitution audit (rotation
balance, no-permanent-authority check). No API key needed — it runs on mock
models. To use real models, set `ANTHROPIC_API_KEY` and switch a `ModelSpec`
provider to `"anthropic"` in `backend/config.py`.

## Design invariants (proven by tests)

- A claim cannot reach `KNOWLEDGE` without surviving challenge.
- The Socratic role rotates; a single dominator is flagged by the audit.
- A weakly-evidenced majority claim is **not** promoted.
- A strongly-evidenced claim **is** promoted; minority claims stay visible.
- Every state transition is logged to `revision_history`.
- Knowledge is reversible (`KNOWLEDGE → DISPUTED → …`).

## Not yet built (next phases)

Belief-revision actions (merge/split), evidence verifier with real sources,
Knowledge Evolution Memory persistence, Meta-Socrates process evaluator,
convergence metrics, and the FastAPI routes in `api/` (endpoint contracts are
specified in the directive §16). Build order follows directive §19.
