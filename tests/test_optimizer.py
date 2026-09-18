"""Tests for the mathematical energy optimizer."""

import pytest
from app.schemas.request import BatterySpecs, HourData
from app.directives.rules import AppliedDirectiveConstraints
from app.optimizer.solver import solve_scenario, OptimizationInfeasibleError


def test_optimizer_shifts_to_low_tariff_hours():
    """Verify that the optimizer charges battery during cheap hours and discharges during peak hours."""
    # 24 hours: hour 2 is cheap (5 BDT), hour 20 is expensive (25 BDT), rest 10 BDT
    hours = [
        HourData(
            hour=h,
            demand_kwh=50.0,
            solar_kwh=0.0,
            tariff_bdt_per_kwh=5.0 if h == 2 else (25.0 if h == 20 else 10.0),
        )
        for h in range(24)
    ]
    battery = BatterySpecs(
        capacity_kwh=100.0,
        initial_energy_kwh=50.0,
        minimum_energy_kwh=10.0,
        max_charge_kwh_per_hour=40.0,
        max_discharge_kwh_per_hour=40.0,
    )
    constraints = AppliedDirectiveConstraints(
        effective_solar=[0.0] * 24,
        min_battery_reserve=[10.0] * 24,
        charge_allowed=[True] * 24,
        discharge_allowed=[True] * 24,
        max_grid_limit=[float("inf")] * 24,
    )

    plan, total_grid, total_cost, peak_grid = solve_scenario(hours, battery, constraints)

    # Battery should charge in hour 2
    assert plan[2].battery_action == "charge"
    assert plan[2].battery_kwh > 0

    # Battery should discharge in hour 20
    assert plan[20].battery_action == "discharge"
    assert plan[20].battery_kwh > 0

    # Battery should satisfy neutrality at hour 23
    assert abs(plan[23].battery_energy_after_kwh - 50.0) < 0.01


def test_optimizer_infeasible_when_demand_exceeds_limits():
    """Verify that an impossible max_grid cap raises OptimizationInfeasibleError."""
    hours = [
        HourData(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=10.0)
        for h in range(24)
    ]
    battery = BatterySpecs(
        capacity_kwh=50.0,
        initial_energy_kwh=10.0,
        minimum_energy_kwh=10.0,
        max_charge_kwh_per_hour=10.0,
        max_discharge_kwh_per_hour=10.0,
    )
    # Demand is 100, but grid is capped at 10 and max discharge is 10 -> impossible to supply 100 kWh
    constraints = AppliedDirectiveConstraints(
        effective_solar=[0.0] * 24,
        min_battery_reserve=[10.0] * 24,
        charge_allowed=[True] * 24,
        discharge_allowed=[True] * 24,
        max_grid_limit=[10.0] * 24,
    )

    with pytest.raises(OptimizationInfeasibleError):
        solve_scenario(hours, battery, constraints)
