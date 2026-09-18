"""Independent schedule validator and replay engine.

Verifies the optimized schedule hour-by-hour against all physical,
operational, and directive constraints without trusting the optimizer.
"""

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.request import BatterySpecs, HourData
from app.schemas.response import HourlyPlanEntry
from app.directives.rules import AppliedDirectiveConstraints


class ValidationErrorDetail(BaseModel):
    """Details of a single validation failure."""

    hour: Optional[int] = None
    rule: str
    message: str


class ScheduleValidationResult(BaseModel):
    """Result of independent schedule replay validation."""

    is_valid: bool
    recomputed_total_grid_kwh: float
    recomputed_total_cost_bdt: float
    recomputed_peak_grid_kwh: float
    errors: list[ValidationErrorDetail] = Field(default_factory=list)


def validate_and_replay_schedule(
    hourly_plan: list[HourlyPlanEntry],
    hours: list[HourData],
    battery: BatterySpecs,
    constraints: AppliedDirectiveConstraints,
    reported_total_grid_kwh: Optional[float] = None,
    reported_total_cost_bdt: Optional[float] = None,
    reported_peak_grid_kwh: Optional[float] = None,
    tolerance: float = 0.01,
) -> ScheduleValidationResult:
    """
    Replays the hourly plan from hour 0 through 23 and verifies all constraints.

    Returns:
        ScheduleValidationResult containing validity status, recomputed metrics, and errors.
    """
    errors: list[ValidationErrorDetail] = []

    if len(hourly_plan) != 24:
        errors.append(
            ValidationErrorDetail(
                hour=None,
                rule="plan_length",
                message=f"Expected exactly 24 hourly entries, got {len(hourly_plan)}",
            )
        )
        return ScheduleValidationResult(
            is_valid=False,
            recomputed_total_grid_kwh=0.0,
            recomputed_total_cost_bdt=0.0,
            recomputed_peak_grid_kwh=0.0,
            errors=errors,
        )

    prev_energy = battery.initial_energy_kwh
    recomputed_grid_sum = 0.0
    recomputed_cost_sum = 0.0
    recomputed_peak_grid = 0.0

    for h in range(24):
        entry = hourly_plan[h]
        hour_data = hours[h]

        if entry.hour != h:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="hour_index",
                    message=f"Plan entry at index {h} has hour={entry.hour}",
                )
            )

        # 1. Non-negativity
        if entry.grid_kwh < -tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="non_negative_grid",
                    message=f"grid_kwh cannot be negative: {entry.grid_kwh}",
                )
            )
        if entry.solar_used_kwh < -tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="non_negative_solar",
                    message=f"solar_used_kwh cannot be negative: {entry.solar_used_kwh}",
                )
            )
        if entry.battery_kwh < -tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="non_negative_battery_kwh",
                    message=f"battery_kwh cannot be negative: {entry.battery_kwh}",
                )
            )

        # 2. Solar usage limit
        eff_solar = constraints.effective_solar[h]
        if entry.solar_used_kwh > eff_solar + tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="solar_availability",
                    message=f"solar_used_kwh ({entry.solar_used_kwh}) exceeds effective solar ({eff_solar})",
                )
            )

        # 3. Battery Action & Rate Limits
        charge_kwh = entry.battery_kwh if entry.battery_action == "charge" else 0.0
        discharge_kwh = entry.battery_kwh if entry.battery_action == "discharge" else 0.0

        if entry.battery_action == "idle" and entry.battery_kwh > tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="idle_action",
                    message=f"battery_kwh must be 0 when idle, got {entry.battery_kwh}",
                )
            )

        if entry.battery_action == "charge":
            if not constraints.charge_allowed[h] and charge_kwh > tolerance:
                errors.append(
                    ValidationErrorDetail(
                        hour=h,
                        rule="no_charge_window",
                        message=f"Charging not allowed during hour {h}, charged {charge_kwh}",
                    )
                )
            if charge_kwh > battery.max_charge_kwh_per_hour + tolerance:
                errors.append(
                    ValidationErrorDetail(
                        hour=h,
                        rule="max_charge_rate",
                        message=f"charge_kwh ({charge_kwh}) exceeds max_charge ({battery.max_charge_kwh_per_hour})",
                    )
                )

        if entry.battery_action == "discharge":
            if not constraints.discharge_allowed[h] and discharge_kwh > tolerance:
                errors.append(
                    ValidationErrorDetail(
                        hour=h,
                        rule="no_discharge_window",
                        message=f"Discharging not allowed during hour {h}, discharged {discharge_kwh}",
                    )
                )
            if discharge_kwh > battery.max_discharge_kwh_per_hour + tolerance:
                errors.append(
                    ValidationErrorDetail(
                        hour=h,
                        rule="max_discharge_rate",
                        message=f"discharge_kwh ({discharge_kwh}) exceeds max_discharge ({battery.max_discharge_kwh_per_hour})",
                    )
                )

        # 4. Battery State Transition
        expected_after_energy = prev_energy + charge_kwh - discharge_kwh
        if abs(entry.battery_energy_after_kwh - expected_after_energy) > tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="battery_transition",
                    message=(
                        f"battery_energy_after_kwh ({entry.battery_energy_after_kwh}) != "
                        f"prev_energy ({prev_energy}) + charge ({charge_kwh}) - discharge ({discharge_kwh}) "
                        f"[{expected_after_energy}]"
                    ),
                )
            )

        # 5. Capacity and Reserve Limits
        active_min = constraints.min_battery_reserve[h]
        if entry.battery_energy_after_kwh < active_min - tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="minimum_reserve",
                    message=f"battery_energy ({entry.battery_energy_after_kwh}) below active minimum ({active_min})",
                )
            )
        if entry.battery_energy_after_kwh > battery.capacity_kwh + tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="battery_capacity",
                    message=f"battery_energy ({entry.battery_energy_after_kwh}) exceeds capacity ({battery.capacity_kwh})",
                )
            )

        # 6. Grid Window Limit
        max_g = constraints.max_grid_limit[h]
        if entry.grid_kwh > max_g + tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="max_grid_window",
                    message=f"grid_kwh ({entry.grid_kwh}) exceeds max_grid_kwh limit ({max_g})",
                )
            )

        # 7. Hourly Energy Balance: Grid + Solar_used + Discharge == Demand + Charge
        generation_side = entry.grid_kwh + entry.solar_used_kwh + discharge_kwh
        consumption_side = hour_data.demand_kwh + charge_kwh
        if abs(generation_side - consumption_side) > tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=h,
                    rule="energy_balance",
                    message=(
                        f"Energy balance failed: Gen ({generation_side:.2f}) != Demand ({consumption_side:.2f}). "
                        f"[grid={entry.grid_kwh}, solar={entry.solar_used_kwh}, discharge={discharge_kwh}, "
                        f"demand={hour_data.demand_kwh}, charge={charge_kwh}]"
                    ),
                )
            )

        # Update running tallies
        recomputed_grid_sum += entry.grid_kwh
        recomputed_cost_sum += entry.grid_kwh * hour_data.tariff_bdt_per_kwh
        if entry.grid_kwh > recomputed_peak_grid:
            recomputed_peak_grid = entry.grid_kwh

        prev_energy = entry.battery_energy_after_kwh

    # 8. End-of-day battery neutrality
    final_energy = hourly_plan[-1].battery_energy_after_kwh
    if abs(final_energy - battery.initial_energy_kwh) > tolerance:
        errors.append(
            ValidationErrorDetail(
                hour=23,
                rule="battery_neutrality",
                message=(
                    f"Final battery energy ({final_energy:.2f}) does not match "
                    f"initial energy ({battery.initial_energy_kwh:.2f})"
                ),
            )
        )

    # 9. Consistency with reported totals
    if reported_total_grid_kwh is not None:
        if abs(reported_total_grid_kwh - recomputed_grid_sum) > tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=None,
                    rule="reported_total_grid_kwh",
                    message=f"Reported total grid ({reported_total_grid_kwh}) != recomputed ({recomputed_grid_sum:.2f})",
                )
            )

    if reported_total_cost_bdt is not None:
        if abs(reported_total_cost_bdt - recomputed_cost_sum) > tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=None,
                    rule="reported_total_cost_bdt",
                    message=f"Reported total cost ({reported_total_cost_bdt}) != recomputed ({recomputed_cost_sum:.2f})",
                )
            )

    if reported_peak_grid_kwh is not None:
        if abs(reported_peak_grid_kwh - recomputed_peak_grid) > tolerance:
            errors.append(
                ValidationErrorDetail(
                    hour=None,
                    rule="reported_peak_grid_kwh",
                    message=f"Reported peak grid ({reported_peak_grid_kwh}) != recomputed ({recomputed_peak_grid:.2f})",
                )
            )

    return ScheduleValidationResult(
        is_valid=(len(errors) == 0),
        recomputed_total_grid_kwh=round(recomputed_grid_sum, 4),
        recomputed_total_cost_bdt=round(recomputed_cost_sum, 4),
        recomputed_peak_grid_kwh=round(recomputed_peak_grid, 4),
        errors=errors,
    )
