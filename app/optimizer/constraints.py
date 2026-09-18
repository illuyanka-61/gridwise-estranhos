"""Hard mathematical constraints for the campus energy linear program."""

from ortools.linear_solver import pywraplp
from app.schemas.request import BatterySpecs, HourData
from app.optimizer.model import OptimizerVariables


def add_constraints(
    solver: pywraplp.Solver,
    variables: OptimizerVariables,
    hours: list[HourData],
    battery: BatterySpecs,
    peak_penalty_weight: float = 0.0,
) -> None:
    """Adds energy balance, battery state transitions, and neutrality constraints."""
    # 1. End-of-day battery neutrality
    solver.Add(variables.E[23] == battery.initial_energy_kwh)

    # 2. Hourly transitions and energy balance
    prev_E = battery.initial_energy_kwh
    for h in range(24):
        # Battery state equation: E_after = E_before + C - D
        solver.Add(variables.E[h] == prev_E + variables.C[h] - variables.D[h])
        prev_E = variables.E[h]

        # Energy balance: Grid + Solar + Battery_Discharge = Demand + Battery_Charge
        solver.Add(
            variables.G[h] + variables.S[h] + variables.D[h]
            == hours[h].demand_kwh + variables.C[h]
        )

        # Peak grid tracking: peak_G >= G[h] only if peak penalty is enabled
        if peak_penalty_weight > 0:
            solver.Add(variables.peak_G >= variables.G[h])
