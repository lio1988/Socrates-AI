"""
Local LoRA fine-tuning scaffold (NVIDIA GPU) — describe & prepare, never auto-run.

This module is deliberately *inert* by default: it reports the GPU, checks which
training dependencies are present, builds a human-readable plan, and writes a
self-contained, reproducible training script the operator runs on their own
NVIDIA box. It lazy-imports torch and NEVER launches training from inside the
council process — training is an explicit, resource-gated action.

Nothing here makes a network call, reads `.env`, or needs a key.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# A small, permissively-licensed open base is the sensible default student — big
# enough to reason, small enough for a single consumer NVIDIA GPU with LoRA.
DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
_TRAINING_DEPS = ("torch", "transformers", "peft", "trl", "datasets")


class TrainingUnavailable(RuntimeError):
    """Raised when a training action is requested but the environment can't do it."""


# ── environment introspection (all lazy / guarded — safe with no torch) ───────

def gpu_report() -> Dict[str, Any]:
    """Describe the NVIDIA GPU situation without requiring torch to be installed."""
    try:
        import torch  # lazy — only touched when explicitly asked
    except Exception:
        return {"torch_installed": False, "cuda_available": False, "devices": [],
                "note": "Install a CUDA build of PyTorch to train on an NVIDIA GPU "
                        "(https://pytorch.org/get-started/locally/)."}
    try:
        cuda = bool(torch.cuda.is_available())
        devices: List[Dict[str, Any]] = []
        if cuda:
            for i in range(torch.cuda.device_count()):
                p = torch.cuda.get_device_properties(i)
                devices.append({"index": i, "name": p.name,
                                "total_memory_gb": round(p.total_memory / 1e9, 2)})
        return {"torch_installed": True, "torch_version": torch.__version__,
                "cuda_available": cuda, "devices": devices,
                "note": "NVIDIA GPU ready." if cuda else
                        "torch present but no CUDA GPU visible (CPU training is impractical)."}
    except Exception as exc:   # never let introspection crash a caller
        return {"torch_installed": True, "cuda_available": False, "devices": [],
                "note": f"GPU introspection failed: {type(exc).__name__}"}


def check_training_deps() -> Dict[str, bool]:
    """Which training libraries are importable right now."""
    import importlib.util
    return {dep: importlib.util.find_spec(dep) is not None for dep in _TRAINING_DEPS}


# ── configuration + plan (pure data) ──────────────────────────────────────────

@dataclass
class LoRAConfig:
    base_model: str = DEFAULT_BASE_MODEL
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj"])
    learning_rate: float = 2e-4
    epochs: int = 3
    per_device_batch_size: int = 1
    grad_accum_steps: int = 8
    max_seq_len: int = 2048
    do_sft: bool = True
    do_dpo: bool = True
    output_dir: str = "runs/socrates-student"


@dataclass
class TrainingPlan:
    base_model: str
    sft_examples: int
    preference_pairs: int
    stages: List[str]
    est_sft_steps: int
    device: str
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"base_model": self.base_model, "sft_examples": self.sft_examples,
                "preference_pairs": self.preference_pairs, "stages": self.stages,
                "est_sft_steps": self.est_sft_steps, "device": self.device,
                "warnings": self.warnings}


def build_training_plan(corpus_stats: Dict[str, Any], config: Optional[LoRAConfig] = None,
                        gpu: Optional[Dict[str, Any]] = None) -> TrainingPlan:
    """A pure description of the run implied by a corpus + config. Trains nothing."""
    config = config or LoRAConfig()
    gpu = gpu if gpu is not None else gpu_report()
    n_sft = int(corpus_stats.get("sft_examples", 0))
    n_pref = int(corpus_stats.get("preference_pairs", 0))
    effective_batch = max(1, config.per_device_batch_size * config.grad_accum_steps)
    est_steps = (n_sft * config.epochs + effective_batch - 1) // effective_batch if n_sft else 0

    stages: List[str] = []
    if config.do_sft and n_sft:
        stages.append("SFT")
    if config.do_dpo and n_pref:
        stages.append("DPO")

    warnings: List[str] = []
    if not gpu.get("cuda_available"):
        warnings.append("No CUDA GPU visible — LoRA training will be impractical; "
                        "run this on an NVIDIA GPU box.")
    if n_sft < 100:
        warnings.append(f"Only {n_sft} SFT examples — expect overfitting; harvest more "
                        "ratified dialogues before training.")
    if config.do_dpo and n_pref < 50:
        warnings.append(f"Only {n_pref} preference pairs — DPO signal will be weak.")
    if not stages:
        warnings.append("Corpus is empty for the enabled stages — nothing to train.")
    device = "cuda" if gpu.get("cuda_available") else "cpu"
    return TrainingPlan(config.base_model, n_sft, n_pref, stages, est_steps, device, warnings)


# ── the NVIDIA entrypoint: a standalone, reproducible training script ─────────

def write_training_script(path: str, config: LoRAConfig, sft_path: str,
                          pref_path: str) -> str:
    """
    Write a self-contained trl/peft LoRA script the operator runs on their GPU:
        python train_student.py
    We GENERATE (not execute) it — the council process never trains. Returns the
    path written. The script is validated as syntactically-correct Python.
    """
    tm = ", ".join(repr(m) for m in config.target_modules)
    script = f'''"""
Auto-generated Socrates-AI student training script (LoRA, NVIDIA GPU).
Generated by backend.training.local_trainer — run it yourself on a CUDA box:
    pip install "torch" transformers peft trl datasets accelerate
    python {Path(path).name}
This script trains a LOCAL model. No API key, no network to Anthropic.
"""
import json
import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer, DPOConfig, DPOTrainer

BASE_MODEL = {config.base_model!r}
SFT_PATH = {sft_path!r}
PREF_PATH = {pref_path!r}
OUTPUT_DIR = {config.output_dir!r}

assert torch.cuda.is_available(), "This script requires an NVIDIA CUDA GPU."

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16,
                                             device_map="auto")

peft_config = LoraConfig(r={config.lora_rank}, lora_alpha={config.lora_alpha},
                         lora_dropout={config.lora_dropout},
                         target_modules=[{tm}], task_type="CAUSAL_LM")

def _read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

# ---- Stage 1: SFT on the council's endorsed (ratified) demonstrations ----
if {config.do_sft}:
    rows = _read_jsonl(SFT_PATH)
    def _to_text(r):
        return (r["instruction"] + "\\n\\n" + r["input"] + "\\n\\n" + r["output"])
    ds = Dataset.from_dict({{"text": [_to_text(r) for r in rows]}})
    sft_cfg = SFTConfig(output_dir=OUTPUT_DIR + "/sft",
                        per_device_train_batch_size={config.per_device_batch_size},
                        gradient_accumulation_steps={config.grad_accum_steps},
                        learning_rate={config.learning_rate}, num_train_epochs={config.epochs},
                        max_seq_length={config.max_seq_len}, bf16=True, logging_steps=10)
    SFTTrainer(model=model, args=sft_cfg, train_dataset=ds,
               peft_config=peft_config, tokenizer=tokenizer).train()

# ---- Stage 2: DPO on the council's peer-score preference pairs ----
if {config.do_dpo}:
    pairs = _read_jsonl(PREF_PATH)
    ds = Dataset.from_dict({{
        "prompt": [p["prompt"] for p in pairs],
        "chosen": [p["chosen"] for p in pairs],
        "rejected": [p["rejected"] for p in pairs]}})
    dpo_cfg = DPOConfig(output_dir=OUTPUT_DIR + "/dpo",
                        per_device_train_batch_size={config.per_device_batch_size},
                        gradient_accumulation_steps={config.grad_accum_steps},
                        learning_rate={config.learning_rate}, num_train_epochs=1, bf16=True)
    DPOTrainer(model=model, args=dpo_cfg, train_dataset=ds,
               peft_config=peft_config, tokenizer=tokenizer).train()

model.save_pretrained(OUTPUT_DIR + "/final")
tokenizer.save_pretrained(OUTPUT_DIR + "/final")
print("Student saved to", OUTPUT_DIR + "/final")
'''
    ast.parse(script)   # guarantee we only ever emit valid Python
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(script, encoding="utf-8")
    return str(p)


def reentry_instructions(model_dir: str = "runs/socrates-student/final") -> str:
    """How the trained student re-enters the council — closing the flywheel."""
    return (
        "Re-entry (close the loop):\n"
        f"  1. Serve the LoRA-merged student at {model_dir} behind an OpenAI-compatible\n"
        "     endpoint (vLLM/TGI) OR load it in-process.\n"
        "  2. Wrap it in a provider adapter over the SAME transport seam the live\n"
        "     Anthropic adapter uses (offline_provider_adapter.OfflineProviderAdapter:\n"
        "     implement _produce_raw_text to call the local model).\n"
        "  3. registry.register(student_seat) — it now deliberates AND is peer-scored\n"
        "     alongside the frontier seats; TopicSkill/Calibration/SeatHealth track it.\n"
        "  4. Re-run the R1 verifier + R3a dialectic-delta to measure whether the\n"
        "     student improved. If yes, the next harvest is partly its own — the\n"
        "     flywheel turns. Never claim capability without the external-truth check."
    )
