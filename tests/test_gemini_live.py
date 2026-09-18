"""Test live Gemini API connection and directive interpretation when key is provided."""

import pytest
from app.config import settings
from app.schemas.request import BatterySpecs
from app.directives.interpreter import directive_interpreter
from app.schemas.directives import DirectiveType


@pytest.mark.asyncio
async def test_live_gemini_interpretation():
    """Verify live Gemini model parses operator directives correctly."""
    api_key = settings.effective_api_key
    if not api_key:
        pytest.skip("No GEMINI_API_KEY or LLM_API_KEY set in .env")

    battery = BatterySpecs(
        capacity_kwh=220,
        initial_energy_kwh=110,
        minimum_energy_kwh=40,
        max_charge_kwh_per_hour=50,
        max_discharge_kwh_per_hour=50,
    )

    notes = [
        "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
        "The sports office moved next month's registration deadline.",
    ]

    results = await directive_interpreter.interpret_and_validate(notes, battery)

    assert len(results) == 2
    # Note 0: solar reduction
    assert results[0].applies is True
    assert results[0].directive_type == DirectiveType.SOLAR_REDUCTION
    assert results[0].structured_adjustment.hours == [12, 13]
    assert results[0].structured_adjustment.factor == 0.25

    # Note 1: no_op
    assert results[1].applies is False
    assert results[1].directive_type == DirectiveType.NO_OP
    assert results[1].structured_adjustment is None
