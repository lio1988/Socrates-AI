"""Shared test locks for canonical dialogue tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.dialogues.socrates_zero.acquisition_tripwires import (
    AcquisitionBoundaryTripwireV0,
)


@pytest.fixture(autouse=True)
def _zero_external_acquisition_boundary(request: pytest.FixtureRequest):
    """Instrument every acquisition test, including future artifact tests."""

    test_name = Path(str(request.node.path)).name
    if not test_name.startswith(
        (
            "test_socrates_zero_acquisition",
            "test_socrates_zero_openrouter_acquisition",
        )
    ):
        yield
        return

    with AcquisitionBoundaryTripwireV0() as tripwire:
        yield tripwire
        tripwire.assert_clean()
