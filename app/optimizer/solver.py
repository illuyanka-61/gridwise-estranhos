"""Optimization solver execution and schedule formatting."""

from typing import Literal
from ortools.linear_solver import pywraplp

from app.schemas.request import BatterySpecs, HourData
from app.schemas.response import HourlyPlanEntry
from app.directives.rules import AppliedDirectiveConstraints
from app.optimizer.model import create_optimizer_model
from app.optimizer.constraints import add_constraints
from app.optimizer.objective import set_objective


class OptimizationError(Exception):
    """Base exception for optimization failures."""

    pass


class OptimizationInfeasibleError(OptimizationError):
    """Raised when no feasible schedule exists for the scenario and constraints."""

    pass


def solve_scenario(
    hours: list[HourData],
    battery: BatterySpecs,
    constraints: AppliedDirectiveConstraints,
    peak_penalty_weight: float = 1e-4,
) -> tuple[list[HourlyPlanEntry], float, float, float]:
    """
    Solves the 24-hour campus energy schedule using OR-Tools GLOP.

    Returns:
        tuple: (hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh)
    """
    solver, variables = create_optimizer_model(hours, battery, constraints)
    add_constraints(solver, variables, hours, battery)
    set_objective(solver, variables, hours, peak_penalty_weight=peak_penalty_weight)

    status = solver.Solve()

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        raise OptimizationInfeasibleError(
            f"Solver failed to find an optimal solution. Status code: {status}"
        )

    hourly_plan: list[HourlyPlanEntry] = []

    for h in range(24):
        g_val = round(max(0.0, variables.G[h].solution_value()), 4)
        s_val = round(max(0.0, variables.S[h].solution_value()), 4)
        c_val = max(0.0, variables.C[h].solution_value())
        d_val = max(0.0, variables.D[h].solution_value())
        e_val = round(max(0.0, variables.E[h].solution_value()), 4)

        # Net out battery action to ensure strictly one of charge/discharge/idle
        net_battery = c_val - d_val
        if net_battery > 1e-3:
            action: Literal["charge", "discharge", "idle"] = "charge"
            kwh = round(net_battery, 4)
        elif net_battery < -1e-3:
            action = "discharge"
            kwh = round(-net_battery, 4)
        else:
            action = "idle"
            kwh = 0.0

        hourly_plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=g_val,
                solar_used_kwh=s_val,
                battery_action=action,
                battery_kwh=kwh,
                battery_energy_after_kwh=e_val,
            )
        )

    # Recompute totals exactly from hourly_plan
    total_grid_kwh = round(sum(entry.grid_kwh for entry in hourly_plan), 4)
    total_cost_bdt = round(
        sum(entry.grid_kwh * hours[h].tariff_bdt_per_kwh for h, entry in enumerate(hourly_plan)),
        4,
    )
    peak_grid_kwh = round(max(entry.grid_kwh for entry in hourly_plan), 4)

    return hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh
