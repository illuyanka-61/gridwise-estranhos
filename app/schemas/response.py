"""Response schemas matching the official BUP CSE Fest 2026 specification."""

from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.directives import DirectiveInterpretationItem


class HourlyPlanEntry(BaseModel):
    """Hourly schedule entry for each hour from 0 to 23."""

    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0..23)")
    grid_kwh: float = Field(..., ge=0.0, description="Grid energy purchased in kWh")
    solar_used_kwh: float = Field(
        ..., ge=0.0, description="Solar energy utilized in kWh"
    )
    battery_action: Literal["charge", "discharge", "idle"] = Field(
        ..., description="Action taken by battery storage"
    )
    battery_kwh: float = Field(
        ..., ge=0.0, description="Magnitude of charge or discharge in kWh (0 if idle)"
    )
    battery_energy_after_kwh: float = Field(
        ..., ge=0.0, description="Battery energy state after this hour in kWh"
    )


class OptimizeEnergyResponse(BaseModel):
    """Top-level response object for POST /optimize-energy."""

    scenario_id: str = Field(..., description="Echoes request scenario_id")
    directive_interpretation: list[DirectiveInterpretationItem] = Field(
        ..., description="Machine-checkable interpretations for each operator note"
    )
    hourly_plan: list[HourlyPlanEntry] = Field(
        ..., min_length=24, max_length=24, description="24-hour optimized schedule"
    )
    total_grid_kwh: float = Field(
        ..., ge=0.0, description="Total grid energy purchased across 24 hours"
    )
    total_cost_bdt: float = Field(
        ..., ge=0.0, description="Total electricity cost in BDT"
    )
    peak_grid_kwh: float = Field(
        ..., ge=0.0, description="Maximum single-hour grid import in kWh"
    )
    plan_summary: str = Field(
        ..., min_length=1, description="Human-readable summary of the strategy"
    )


class HealthResponse(BaseModel):
    """Readiness response for GET /health."""

    status: str = Field(default="ok", description="Service readiness indicator")
