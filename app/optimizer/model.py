"""Optimization model variables and container using OR-Tools GLOP."""

from dataclasses import dataclass
from ortools.linear_solver import pywraplp
from app.schemas.request import BatterySpecs, HourData
from app.directives.rules import AppliedDirectiveConstraints


@dataclass
class OptimizerVariables:
    """Decision variables for the 24-hour horizon."""

    G: list[pywraplp.Variable]  # Grid import (kWh) for h=0..23
    S: list[pywraplp.Variable]  # Solar used (kWh) for h=0..23
    C: list[pywraplp.Variable]  # Battery charge (kWh) for h=0..23
    D: list[pywraplp.Variable]  # Battery discharge (kWh) for h=0..23
    E: list[pywraplp.Variable]  # Battery energy after hour h (kWh) for h=0..23
    peak_G: pywraplp.Variable  # Auxiliary variable bounding max grid import


def create_optimizer_model(
    hours: list[HourData],
    battery: BatterySpecs,
    constraints: AppliedDirectiveConstraints,
) -> tuple[pywraplp.Solver, OptimizerVariables]:
    """Creates the linear programming solver and decision variables."""
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if not solver:
        raise RuntimeError("OR-Tools GLOP solver could not be created")

    G = []
    S = []
    C = []
    D = []
    E = []

    for h in range(24):
        # Grid import variable with optional max grid directive bound
        max_g = constraints.max_grid_limit[h]
        g_var = solver.NumVar(0.0, max_g, f"G_{h}")
        G.append(g_var)

        # Solar used bounded by effective solar
        eff_solar = constraints.effective_solar[h]
        s_var = solver.NumVar(0.0, eff_solar, f"S_{h}")
        S.append(s_var)

        # Charge rate bounded by max_charge or 0 if no_charge_window
        max_c = battery.max_charge_kwh_per_hour if constraints.charge_allowed[h] else 0.0
        c_var = solver.NumVar(0.0, max_c, f"C_{h}")
        C.append(c_var)

        # Discharge rate bounded by max_discharge or 0 if no_discharge_window
        max_d = battery.max_discharge_kwh_per_hour if constraints.discharge_allowed[h] else 0.0
        d_var = solver.NumVar(0.0, max_d, f"D_{h}")
        D.append(d_var)

        # Battery energy bounded between active minimum reserve and total capacity
        min_res = constraints.min_battery_reserve[h]
        e_var = solver.NumVar(min_res, battery.capacity_kwh, f"E_{h}")
        E.append(e_var)

    peak_G = solver.NumVar(0.0, float("inf"), "peak_G")

    return solver, OptimizerVariables(G=G, S=S, C=C, D=D, E=E, peak_G=peak_G)
