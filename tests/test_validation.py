"""Tests for independent schedule replay and validation."""

import pytest
from app.schemas.request import BatterySpecs, HourData
from app.schemas.response import HourlyPlanEntry
from app.directives.rules import AppliedDirectiveConstraints
from app.validation.schedule_validator import validate_and_replay_schedule

BATTERY = BatterySpecs(
    capacity_kwh=100.0,
    initial_energy_kwh=50.0,
    minimum_energy_kwh=20.0,
    max_charge_kwh_per_hour=30.0,
    max_discharge_kwh_per_hour=30.0,
)

HOURS = [
    HourData(hour=h, demand_kwh=80.0, solar_kwh=0.0, tariff_bdt_per_kwh=10.0)
    for h in range(24)
]

CONSTRAINTS = AppliedDirectiveConstraints(
    effective_solar=[0.0] * 24,
    min_battery_reserve=[20.0] * 24,
    charge_allowed=[True] * 24,
    discharge_allowed=[True] * 24,
    max_grid_limit=[float("inf")] * 24,
)


def test_validator_catches_neutrality_violation():
    """Verify that ending the day with different battery energy is flagged as invalid."""
    # Create valid plan except hour 23 ends at 40 instead of 50
    plan = [
        HourlyPlanEntry(
            hour=h,
            grid_kwh=80.0,
            solar_used_kwh=0.0,
            battery_action="idle",
            battery_kwh=0.0,
            battery_energy_after_kwh=50.0 if h < 23 else 40.0,  # Neutrality violation
        )
        for h in range(24)
    ]
    res = validate_and_replay_schedule(plan, HOURS, BATTERY, CONSTRAINTS)
    assert not res.is_valid
    assert any(e.rule == "battery_neutrality" for e in res.errors)


def test_validator_catches_energy_balance_violation():
    """Verify that an energy mismatch in any hour is detected."""
    # Hour 5: demand is 80, but grid is 70 and solar/battery are 0
    plan = [
        HourlyPlanEntry(
            hour=h,
            grid_kwh=70.0 if h == 5 else 80.0,
            solar_used_kwh=0.0,
            battery_action="idle",
            battery_kwh=0.0,
            battery_energy_after_kwh=50.0,
        )
        for h in range(24)
    ]
    res = validate_and_replay_schedule(plan, HOURS, BATTERY, CONSTRAINTS)
    assert not res.is_valid
    assert any(e.rule == "energy_balance" and e.hour == 5 for e in res.errors)


def test_validator_catches_no_charge_violation():
    """Verify charging during a no_charge_window is flagged."""
    constraints = AppliedDirectiveConstraints(
        effective_solar=[0.0] * 24,
        min_battery_reserve=[20.0] * 24,
        charge_allowed=[False if h == 10 else True for h in range(24)],
        discharge_allowed=[True] * 24,
        max_grid_limit=[float("inf")] * 24,
    )
    # Hour 10 charges 10 kWh
    plan = []
    energy = 50.0
    for h in range(24):
        if h == 10:
            charge = 10.0
            energy += charge
            plan.append(
                HourlyPlanEntry(
                    hour=h,
                    grid_kwh=90.0,
                    solar_used_kwh=0.0,
                    battery_action="charge",
                    battery_kwh=charge,
                    battery_energy_after_kwh=energy,
                )
            )
        elif h == 11:
            discharge = 10.0
            energy -= discharge
            plan.append(
                HourlyPlanEntry(
                    hour=h,
                    grid_kwh=70.0,
                    solar_used_kwh=0.0,
                    battery_action="discharge",
                    battery_kwh=discharge,
                    battery_energy_after_kwh=energy,
                )
            )
        else:
            plan.append(
                HourlyPlanEntry(
                    hour=h,
                    grid_kwh=80.0,
                    solar_used_kwh=0.0,
                    battery_action="idle",
                    battery_kwh=0.0,
                    battery_energy_after_kwh=energy,
                )
            )

    res = validate_and_replay_schedule(plan, HOURS, BATTERY, constraints)
    assert not res.is_valid
    assert any(e.rule == "no_charge_window" and e.hour == 10 for e in res.errors)
