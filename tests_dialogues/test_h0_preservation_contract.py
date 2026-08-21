"""Structural regression tests for the normative H0.5 preservation contract."""

from __future__ import annotations

import re
from pathlib import Path


CONTRACT = (
    Path(__file__).parents[1]
    / "docs"
    / "HYBRID_V1_H0_5_PRESERVATION_CONTRACT.md"
)
ALLOWED = {
    "UNCHANGED",
    "ADAPTED",
    "OPTIONAL",
    "DEFERRED",
    "RETIRED WITH EVIDENCE",
}
AUTHORITIES = {
    "CED",
    "HybridEpistemicLedger",
    "EventLedger",
    "AtomicReceiptStore",
    "OpenClaw",
    "scoring",
    "Ratification",
    "learning",
    "Deliberation Tree",
    "External Consultation",
    "Micro-Socratic Kernel",
}


def _matrix_rows(text: str) -> list[list[str]]:
    matrix = text.split("## 2. Canonical preservation matrix", 1)[1]
    matrix = matrix.split("## 3. Non-duplicate authority map", 1)[0]
    rows = []
    for line in matrix.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0] != "Feature":
            rows.append(cells)
    return rows


def test_every_preservation_matrix_row_has_exactly_one_allowed_decision():
    text = CONTRACT.read_text(encoding="utf-8")
    rows = _matrix_rows(text)

    assert len(rows) >= 100
    assert all(len(row) == 9 for row in rows)
    assert all(row[4] in ALLOWED for row in rows)
    assert len({row[0] for row in rows}) == len(rows)


def test_contract_freezes_t1_t19_and_all_authority_boundaries():
    text = CONTRACT.read_text(encoding="utf-8")

    amendment_section = text.split("## 9. Required amendments T1–T19", 1)[1]
    amendment_section = amendment_section.split("## 10.", 1)[0]
    numbers = [int(value) for value in re.findall(r"(?m)^(\d+)\. ", amendment_section)]
    assert numbers == list(range(1, 20))
    assert AUTHORITIES <= {item for item in AUTHORITIES if item in text}
    assert "No H1 implementation is authorized by this document." in text
