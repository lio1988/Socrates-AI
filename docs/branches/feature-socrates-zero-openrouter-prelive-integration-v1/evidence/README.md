# Evidence — OpenRouter pre-live integration v1

S6 composes evidence that already exists rather than producing new wire evidence.

| layer | source |
| --- | --- |
| request intent | Route Controls v1 `OpenRouterRequestIntentReceiptV1` |
| wire semantics | Wire Specification Manifest v2r1, pinned commit `4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db` |
| mapping | S5 `openrouter_raw_wire_mapping_v2` |

Fixture response bodies reuse the S5 wire shapes, themselves derived from the six
retained official snapshots. No official source was retrieved in this phase.
