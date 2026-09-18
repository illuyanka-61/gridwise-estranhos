"""Tests for request and response schema validation."""

import pytest
from pydantic import ValidationError
from app.schemas.request import BatterySpecs, HourData, OptimizeEnergyRequest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_battery_initial_energy_exceeds_capacity():
    """Validates that initial_energy_kwh cannot exceed capacity_kwh."""
    with pytest.raises(ValidationError):
        BatterySpecs(
            capacity_kwh=100.0,
            initial_energy_kwh=150.0,  # Invalid
            minimum_energy_kwh=20.0,
            max_charge_kwh_per_hour=30.0,
            max_discharge_kwh_per_hour=30.0,
        )


def test_invalid_hours_count_rejected():
    """Verify that requests with fewer than 24 hours are rejected."""
    hours = [
        HourData(hour=h, demand_kwh=100, solar_kwh=0, tariff_bdt_per_kwh=10)
        for h in range(12)  # Only 12 hours
    ]
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="TEST-FAIL",
            operator_notes=["Clean panels"],
            hours=hours,
            battery=BatterySpecs(
                capacity_kwh=100,
                initial_energy_kwh=50,
                minimum_energy_kwh=10,
                max_charge_kwh_per_hour=25,
                max_discharge_kwh_per_hour=25,
            ),
        )


def test_api_malformed_request_returns_400():
    """Verify POST /optimize-energy returns HTTP 400 on malformed body."""
    response = client.post("/optimize-energy", json={"invalid_key": "data"})
    assert response.status_code == 400
    assert "detail" in response.json()
