"""API routes for energy optimization."""

from fastapi import APIRouter, HTTPException, status
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse
from app.services.optimization_service import optimization_service
from app.optimizer.solver import OptimizationInfeasibleError

router = APIRouter(tags=["Optimization"])


@router.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize 24-hour campus energy schedule with operator directives",
)
async def optimize_energy(request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
    """
    Accepts 24-hour campus scenario + operator notes, converts notes into structured
    directives, optimizes grid cost via deterministic linear programming, and replays
    schedule independently before responding.
    """
    try:
        response = await optimization_service.optimize(request)
        return response
    except OptimizationInfeasibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Infeasible scenario: {exc}",
        ) from exc
    except Exception as exc:
        # Controlled 500 without leaking stack traces or sensitive environment variables
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during energy schedule optimization.",
        ) from exc
