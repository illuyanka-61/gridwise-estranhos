"""Request schemas for POST /optimize-energy matching the BUP CSE Fest 2026 contract."""

from pydantic import BaseModel, Field, field_validator


class HourData(BaseModel):
    """Hourly campus demand, base solar availability, and grid tariff."""

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    demand_kwh: float = Field(..., ge=0.0, description="Campus electricity demand (kWh)")
    solar_kwh: float = Field(..., ge=0.0, description="Forecast solar generation (kWh)")
    tariff_bdt_per_kwh: float = Field(
        ..., ge=0.0, description="Grid tariff rate (BDT/kWh)"
    )


class BatterySpecs(BaseModel):
    """Battery capacity, initial state, reserve level, and rate limits."""

    capacity_kwh: float = Field(
        ..., gt=0.0, description="Maximum energy battery can store (kWh)"
    )
    initial_energy_kwh: float = Field(
        ..., ge=0.0, description="Energy in battery at start of hour 0 (kWh)"
    )
    minimum_energy_kwh: float = Field(
        ..., ge=0.0, description="Baseline minimum reserve level (kWh)"
    )
    max_charge_kwh_per_hour: float = Field(
        ..., ge=0.0, description="Maximum charge rate per hour (kWh)"
    )
    max_discharge_kwh_per_hour: float = Field(
        ..., ge=0.0, description="Maximum discharge rate per hour (kWh)"
    )

    @field_validator("initial_energy_kwh")
    @classmethod
    def validate_initial_within_capacity(
        cls, v: float, info
    ) -> float:
        data = info.data
        if "capacity_kwh" in data and v > data["capacity_kwh"]:
            raise ValueError("initial_energy_kwh cannot exceed capacity_kwh")
        return v


class OptimizeEnergyRequest(BaseModel):
    """Top-level request body for POST /optimize-energy."""

    scenario_id: str = Field(..., min_length=1, description="Scenario identifier")
    operator_notes: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="1-3 natural-language operator notes",
    )
    hours: list[HourData] = Field(
        ..., min_length=24, max_length=24, description="Exactly 24 hourly entries"
    )
    battery: BatterySpecs = Field(..., description="Battery specifications")

    @field_validator("operator_notes")
    @classmethod
    def validate_operator_notes(cls, v: list[str]) -> list[str]:
        for i, note in enumerate(v):
            if not note or not note.strip():
                raise ValueError(f"operator_notes[{i}] must be a non-empty string")
        return v

    @field_validator("hours")
    @classmethod
    def validate_hours_sequence(cls, v: list[HourData]) -> list[HourData]:
        if len(v) != 24:
            raise ValueError("hours array must contain exactly 24 entries")
        seen_hours = [h.hour for h in v]
        if seen_hours != list(range(24)):
            raise ValueError("hours must contain exactly hours 0 through 23 in sequential order")
        return v
