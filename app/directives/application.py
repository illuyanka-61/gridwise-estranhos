"""Deterministic application of validated directives to energy model parameters."""

from app.schemas.request import BatterySpecs, HourData
from app.schemas.directives import (
    DirectiveInterpretationItem,
    DirectiveType,
    SolarReductionAdjustment,
    MinimumBatteryReserveAdjustment,
    WindowHoursAdjustment,
    MaxGridWindowAdjustment,
)
from app.directives.rules import AppliedDirectiveConstraints


def apply_directives_to_scenario(
    hours: list[HourData],
    battery: BatterySpecs,
    directives: list[DirectiveInterpretationItem],
) -> AppliedDirectiveConstraints:
    """
    Deterministically transforms base scenario parameters into hourly operational bounds
    according to Section 5.3 of the official Problem Statement.
    """
    effective_solar = [h.solar_kwh for h in hours]
    min_battery_reserve = [battery.minimum_energy_kwh for _ in range(24)]
    charge_allowed = [True] * 24
    discharge_allowed = [True] * 24
    max_grid_limit = [float("inf")] * 24

    for item in directives:
        if not item.applies or item.directive_type == DirectiveType.NO_OP:
            continue

        adj = item.structured_adjustment
        if adj is None:
            continue

        if item.directive_type == DirectiveType.SOLAR_REDUCTION:
            assert isinstance(adj, SolarReductionAdjustment)
            for h in adj.hours:
                # If multiple reductions apply, multiply or take minimum
                effective_solar[h] = effective_solar[h] * adj.factor

        elif item.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
            assert isinstance(adj, MinimumBatteryReserveAdjustment)
            for h in adj.hours:
                min_battery_reserve[h] = max(
                    min_battery_reserve[h], adj.minimum_energy_kwh
                )

        elif item.directive_type == DirectiveType.NO_CHARGE_WINDOW:
            assert isinstance(adj, WindowHoursAdjustment)
            for h in adj.hours:
                charge_allowed[h] = False

        elif item.directive_type == DirectiveType.NO_DISCHARGE_WINDOW:
            assert isinstance(adj, WindowHoursAdjustment)
            for h in adj.hours:
                discharge_allowed[h] = False

        elif item.directive_type == DirectiveType.MAX_GRID_WINDOW:
            assert isinstance(adj, MaxGridWindowAdjustment)
            for h in adj.hours:
                max_grid_limit[h] = min(max_grid_limit[h], adj.max_grid_kwh)

    return AppliedDirectiveConstraints(
        effective_solar=effective_solar,
        min_battery_reserve=min_battery_reserve,
        charge_allowed=charge_allowed,
        discharge_allowed=discharge_allowed,
        max_grid_limit=max_grid_limit,
    )
