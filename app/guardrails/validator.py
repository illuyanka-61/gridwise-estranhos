"""Deterministic guardrail validation for parsed LLM directives."""

from typing import Any
from app.schemas.directives import (
    DirectiveInterpretationItem,
    DirectiveType,
    SolarReductionAdjustment,
    MinimumBatteryReserveAdjustment,
    WindowHoursAdjustment,
    MaxGridWindowAdjustment,
)
from app.schemas.request import BatterySpecs


class GuardrailValidationError(Exception):
    """Raised when an interpreted directive violates deterministic guardrails."""

    pass


def validate_directive_interpretations(
    interpretations: list[DirectiveInterpretationItem],
    note_count: int,
    battery_specs: BatterySpecs,
) -> list[DirectiveInterpretationItem]:
    """
    Validates a list of interpreted directives against the scenario and competition rules:
    - Coverage: exactly one entry per note in index order 0..N-1
    - applies semantics: false only for no_op, true for all others
    - Valid structured_adjustment shape
    - Hours: unique integers 0..23 in ascending order
    - Numeric bounds: factor in [0, 1], reserve in [0, capacity], max_grid >= 0
    """
    if len(interpretations) != note_count:
        raise GuardrailValidationError(
            f"Expected {note_count} directive interpretations, got {len(interpretations)}"
        )

    for i, item in enumerate(interpretations):
        if item.note_index != i:
            raise GuardrailValidationError(
                f"Interpretation at position {i} has note_index {item.note_index}, expected {i}"
            )

        if item.directive_type == DirectiveType.NO_OP:
            if item.applies:
                raise GuardrailValidationError(
                    f"Note {i}: no_op directive must have applies=False"
                )
            if item.structured_adjustment is not None:
                raise GuardrailValidationError(
                    f"Note {i}: no_op directive must have structured_adjustment=None"
                )
        else:
            if not item.applies:
                raise GuardrailValidationError(
                    f"Note {i}: {item.directive_type.value} must have applies=True"
                )
            if item.structured_adjustment is None:
                raise GuardrailValidationError(
                    f"Note {i}: {item.directive_type.value} requires structured_adjustment"
                )

            adj = item.structured_adjustment
            hours = adj.hours
            if not hours:
                raise GuardrailValidationError(f"Note {i}: hours array cannot be empty")
            if len(hours) != len(set(hours)):
                raise GuardrailValidationError(f"Note {i}: hours array must have unique entries")
            if hours != sorted(hours):
                raise GuardrailValidationError(f"Note {i}: hours must be sorted in ascending order")
            for h in hours:
                if not (0 <= h <= 23):
                    raise GuardrailValidationError(f"Note {i}: hour {h} out of bounds [0, 23]")

            if item.directive_type == DirectiveType.SOLAR_REDUCTION:
                if not isinstance(adj, SolarReductionAdjustment):
                    raise GuardrailValidationError(f"Note {i}: invalid adjustment for solar_reduction")
                if not (0.0 <= adj.factor <= 1.0):
                    raise GuardrailValidationError(f"Note {i}: solar factor {adj.factor} not in [0, 1]")

            elif item.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
                if not isinstance(adj, MinimumBatteryReserveAdjustment):
                    raise GuardrailValidationError(f"Note {i}: invalid adjustment for minimum_battery_reserve")
                if adj.minimum_energy_kwh < 0.0:
                    raise GuardrailValidationError(f"Note {i}: reserve cannot be negative")
                if adj.minimum_energy_kwh > battery_specs.capacity_kwh:
                    raise GuardrailValidationError(
                        f"Note {i}: reserve {adj.minimum_energy_kwh} exceeds battery capacity {battery_specs.capacity_kwh}"
                    )

            elif item.directive_type in (DirectiveType.NO_CHARGE_WINDOW, DirectiveType.NO_DISCHARGE_WINDOW):
                if not isinstance(adj, WindowHoursAdjustment):
                    raise GuardrailValidationError(f"Note {i}: invalid adjustment for {item.directive_type.value}")

            elif item.directive_type == DirectiveType.MAX_GRID_WINDOW:
                if not isinstance(adj, MaxGridWindowAdjustment):
                    raise GuardrailValidationError(f"Note {i}: invalid adjustment for max_grid_window")
                if adj.max_grid_kwh < 0.0:
                    raise GuardrailValidationError(f"Note {i}: max_grid_kwh cannot be negative")

    return interpretations
