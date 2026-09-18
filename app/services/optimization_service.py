"""Optimization service orchestrating the full end-to-end pipeline."""

import logging
import time

from app.config import settings
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse
from app.schemas.directives import DirectiveType
from app.directives.interpreter import directive_interpreter
from app.directives.application import apply_directives_to_scenario
from app.optimizer.solver import solve_scenario
from app.validation.schedule_validator import validate_and_replay_schedule

logger = logging.getLogger("gridwise.service")


def generate_plan_summary(
    directives: list,
    total_cost: float,
    total_grid: float,
    peak_grid: float,
) -> str:
    """Generates a concise human-readable summary of the operating strategy."""
    active_types = [
        d.directive_type.value for d in directives if d.applies and d.directive_type != DirectiveType.NO_OP
    ]
    if active_types:
        unique_types = sorted(list(set(active_types)))
        constraints_str = f"Applied directives: {', '.join(unique_types)}. "
    else:
        constraints_str = "No active operational constraints applied. "

    return (
        f"{constraints_str}"
        f"Optimized 24-hour schedule with total cost of {total_cost:.2f} BDT, "
        f"grid import of {total_grid:.2f} kWh, peak grid demand of {peak_grid:.2f} kWh, "
        f"and satisfied end-of-day battery neutrality."
    )


class OptimizationService:
    """End-to-end service coordinating interpretation, solving, and replay validation."""

    def __init__(self) -> None:
        pass

    async def optimize(self, request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
        """Executes the full pipeline for an incoming energy optimization request."""
        start_time = time.perf_counter()
        logger.info(f"[{request.scenario_id}] Starting optimization request with {len(request.operator_notes)} notes")

        # Step 1: Interpret operator notes and validate guardrails
        t0 = time.perf_counter()
        directives = await directive_interpreter.interpret_and_validate(
            request.operator_notes, request.battery
        )
        t_interp = time.perf_counter() - t0
        logger.info(f"[{request.scenario_id}] Directives interpreted in {t_interp:.3f}s: {[d.directive_type.value for d in directives]}")

        # Step 2: Deterministically apply directives to scenario parameters
        applied_constraints = apply_directives_to_scenario(
            request.hours, request.battery, directives
        )

        # Step 3: Solve the mathematical energy model
        t1 = time.perf_counter()
        hourly_plan, total_grid, total_cost, peak_grid = solve_scenario(
            hours=request.hours,
            battery=request.battery,
            constraints=applied_constraints,
            peak_penalty_weight=settings.PEAK_PENALTY_WEIGHT,
        )
        t_solve = time.perf_counter() - t1
        logger.info(f"[{request.scenario_id}] Solved in {t_solve:.3f}s: Cost={total_cost} BDT, Grid={total_grid} kWh")

        # Step 4: Independent replay validation
        validation_result = validate_and_replay_schedule(
            hourly_plan=hourly_plan,
            hours=request.hours,
            battery=request.battery,
            constraints=applied_constraints,
            reported_total_grid_kwh=total_grid,
            reported_total_cost_bdt=total_cost,
            reported_peak_grid_kwh=peak_grid,
        )

        if not validation_result.is_valid:
            error_msgs = "; ".join(f"[Hour {e.hour}]: {e.rule} - {e.message}" for e in validation_result.errors)
            logger.error(f"[{request.scenario_id}] Independent validation FAILED: {error_msgs}")
            raise RuntimeError(f"Schedule replay validation failed: {error_msgs}")

        # Step 5: Build plan summary
        summary = generate_plan_summary(directives, total_cost, total_grid, peak_grid)

        total_time = time.perf_counter() - start_time
        logger.info(f"[{request.scenario_id}] Completed successfully in {total_time:.3f}s")

        return OptimizeEnergyResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=total_grid,
            total_cost_bdt=total_cost,
            peak_grid_kwh=peak_grid,
            plan_summary=summary,
        )


optimization_service = OptimizationService()
