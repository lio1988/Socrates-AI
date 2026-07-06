# Phase 26G — Alignment Export Pack

Phase 26G is the first practical LLM-learning infrastructure layer after the
collector/miners. It does not train anything yet. It turns the learning data into
clean, deduplicated, split, manifest-backed JSONL artifacts that can later feed
DPO, SFT, reward-model, process-reward, or NeMo-style workflows.

## Why this phase matters

Good learning loops do not start with training. They start with export discipline:

```text
collect → mine → dedupe → split → hash → manifest → train later
```

Without stable dataset exports, later DPO/RLHF/RLAIF experiments become impossible
to reproduce.

## What was added

### `backend/dialogues/learning_alignment_exporter.py`

Main types:

- `AlignmentFormat`
- `DatasetSplit`
- `ExportedArtifact`
- `AlignmentDatasetManifest`
- `AlignmentExportPack`

Main helpers:

- `stable_hash(...)`
- `dedupe_records(...)`
- `deterministic_split(...)`
- `trace_sft_records(...)`
- `dpo_records(...)`
- `nemo_dpo_records(...)`
- `reward_pair_records(...)`
- `process_sft_records(...)`
- `build_alignment_export_pack(...)`
- `alignment_export_summary(...)`

### `tests_dialogues/test_learning_alignment_exporter.py`

Offline tests cover:

- stable hashes
- deduplication
- deterministic train/validation/test split
- trace SFT record generation
- DPO / NeMo-DPO / reward-pair records
- process SFT records
- manifest and artifact hash generation
- export summary

## Artifact formats

### Trace SFT

Supervised fine-tuning examples from eligible traces:

```json
{"prompt": "question", "response": "answer", "metadata": {...}}
```

### DPO

Standard chosen/rejected preference examples:

```json
{"prompt": "question", "chosen": "better answer", "rejected": "weaker answer"}
```

### NeMo DPO

Conversation-style preference records:

```json
{
  "prompt": [{"role": "user", "content": "question"}],
  "chosen": [{"role": "assistant", "content": "better answer"}],
  "rejected": [{"role": "assistant", "content": "weaker answer"}]
}
```

### Reward pairs

Pairwise reward-model records:

```json
{
  "input": "question",
  "candidate_a": "chosen answer",
  "candidate_b": "rejected answer",
  "preferred": "candidate_a",
  "label": 1
}
```

### Process SFT

Supervised examples from the process miner:

```json
{
  "prompt": "Earlier phase output... Produce the improved next process move...",
  "response": "better reflection/reconstruction/synthesis"
}
```

## Manifest

Every export pack includes `manifest.json` with:

- constitution version
- export policy version
- split seed
- validation/test ratio
- artifact count
- total record count
- per-format counts
- per-artifact SHA-256 hashes
- warnings for empty formats
- caller metadata

## Usage

```python
from backend.dialogues.learning_trace_collector import collect_learning_dataset
from backend.dialogues.learning_preference_miner import mine_preferences
from backend.dialogues.learning_process_miner import mine_process_examples
from backend.dialogues.learning_alignment_exporter import build_alignment_export_pack

state = ced.get_session(final.session_id)
dataset = collect_learning_dataset(state, registry=ced.registry)

mine_preferences(dataset, attach=True)
process_report = mine_process_examples(dataset, attach_preferences=True)

pack = build_alignment_export_pack(
    dataset,
    process_report=process_report,
    validation_ratio=0.10,
    test_ratio=0.0,
    seed="ced_alignment_v1",
    metadata={"experiment": "first_alignment_export"},
)

files = pack.as_files()
# files["dpo.train.jsonl"]
# files["nemo_dpo.train.jsonl"]
# files["reward_pairs.train.jsonl"]
# files["process_sft.train.jsonl"]
# files["manifest.json"]
```

## Parallel-learning invariant

This phase does not:

- train models
- fine-tune models
- call providers
- change `ced.py`
- change prompts
- change routing
- change scoring
- change ratification

It only prepares clean alignment artifacts.

## Recommended next phase

### Phase 26H — Dataset Quality Gates

Before training, add automatic checks:

- minimum record counts per format
- prompt/response length bounds
- duplicate ratio warnings
- chosen/rejected similarity checks
- toxic/private-data detectors later
- train/validation leakage checks
- manifest-level quality verdict
