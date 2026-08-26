"""Write the sealed OpenRouter wire specification manifest v2 once."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v2 import (
    FROZEN_MANIFEST_V2,
    FROZEN_VALIDATION_V2,
    FROZEN_REVALIDATION_V2,
    MANIFEST_RELATIVE_PATH_V2,
    VALIDATION_RELATIVE_PATH_V2,
    REVALIDATION_RELATIVE_PATH_V2,
    render_contract_v2,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError


def _write_once(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ContractValidationError(f"write-once evidence already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def publish(repository_root: Path) -> tuple[Path, Path, Path]:
    manifest_path = repository_root / MANIFEST_RELATIVE_PATH_V2
    validation_path = repository_root / VALIDATION_RELATIVE_PATH_V2
    revalidation_path = repository_root / REVALIDATION_RELATIVE_PATH_V2
    _write_once(manifest_path, render_contract_v2(FROZEN_MANIFEST_V2))
    _write_once(validation_path, render_contract_v2(FROZEN_VALIDATION_V2))
    _write_once(revalidation_path, render_contract_v2(FROZEN_REVALIDATION_V2))
    return manifest_path, validation_path, revalidation_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest_path, validation_path, revalidation_path = publish(args.repository_root.resolve())
    print(manifest_path)
    print(validation_path)
    print(revalidation_path)


if __name__ == "__main__":
    main()
