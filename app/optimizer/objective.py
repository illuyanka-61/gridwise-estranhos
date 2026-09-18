"""Objective function setup for the linear program."""

from ortools.linear_solver import pywraplp
from app.schemas.request import HourData
from app.optimizer.model import OptimizerVariables


def set_objective(
    solver: pywraplp.Solver,
    variables: OptimizerVariables,
    hours: list[HourData],
    peak_penalty_weight: float = 1e-4,
) -> None:
    """Sets the objective to minimize total grid cost with secondary peak shaving and no simultaneous charge/discharge."""
    objective = solver.Objective()
    for h in range(24):
        objective.SetCoefficient(variables.G[h], hours[h].tariff_bdt_per_kwh)
        # Small penalty prevents simultaneous artificial charge/discharge in flat-tariff hours
        objective.SetCoefficient(variables.C[h], 1e-5)
        objective.SetCoefficient(variables.D[h], 1e-5)

    if peak_penalty_weight > 0:
        objective.SetCoefficient(variables.peak_G, peak_penalty_weight)

    objective.SetMinimization()
