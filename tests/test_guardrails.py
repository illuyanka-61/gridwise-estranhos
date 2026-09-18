"""Tests for deterministic directive guardrails."""

import pytest
from app.schemas.request import BatterySpecs
from app.schemas.directives import (
    DirectiveInterpretationItem,
    DirectiveType,
    SolarReductionAdjustment,
    MinimumBatteryReserveAdjustment,
    WindowHoursAdjustment,
)
from app.guardrails.validator import (
    validate_directive_interpretations,
    GuardrailValidationError,
)

BATTERY = BatterySpecs(
    capacity_kwh=200,
    initial_energy_kwh=100,
    minimum_energy_kwh=40,
    max_charge_kwh_per_hour=50,
    max_discharge_kwh_per_hour=50,
)


def test_guardrails_invalid_note_count():
    """Verify mismatch between note count and interpretation entries raises error."""
    items = [
        DirectiveInterpretationItem(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="None",
        )
    ]
    with pytest.raises(GuardrailValidationError):
        validate_directive_interpretations(items, note_count=2, battery_specs=BATTERY)


def test_guardrails_reserve_exceeds_capacity():
    """Verify battery reserve exceeding capacity is rejected."""
    items = [
        DirectiveInterpretationItem(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=MinimumBatteryReserveAdjustment(
                hours=[18, 19], minimum_energy_kwh=300.0  # Capacity is 200
            ),
            explanation="Invalid",
        )
    ]
    with pytest.raises(GuardrailValidationError):
        validate_directive_interpretations(items, note_count=1, battery_specs=BATTERY)


def test_guardrails_no_op_with_applies_true():
    """Verify no_op cannot have applies=True."""
    with pytest.raises(ValueError):
        DirectiveInterpretationItem(
            note_index=0,
            applies=True,  # Invalid for no_op
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Invalid",
        )
