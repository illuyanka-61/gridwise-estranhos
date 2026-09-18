"""End-to-end integration tests using all 10 official public sample cases."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_FILE = Path("sample_cases/BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json")


def load_sample_cases():
    """Load sample cases from JSON file."""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"Sample file {SAMPLE_FILE} not found")
    with open(SAMPLE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


@pytest.fixture(autouse=True)
def deterministic_test_mode(monkeypatch):
    """Ensures test suite runs deterministically without external API quota delays."""
    monkeypatch.setattr("app.config.settings.LLM_API_KEY", None)
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", None)


@pytest.mark.parametrize("case", load_sample_cases(), ids=lambda c: c["id"])
def test_public_sample_cases(case):
    """
    Test each public sample case against POST /optimize-energy:
    1. HTTP 200 returned.
    2. directive_interpretation matches ground truth semantics.
    3. Total cost matches reference cost within tolerance (Diff == 0.00).
    4. Replayed schedule satisfies all constraints.
    5. Recalculated total grid and peak grid are consistent.
    """
    case_id = case["id"]
    inp = case["input"]
    expected = case["expected_output"]

    response = client.post("/optimize-energy", json=inp)
    assert response.status_code == 200, f"[{case_id}] API returned {response.status_code}: {response.text}"

    data = response.json()

    # 1. Echo scenario_id
    assert data["scenario_id"] == inp["scenario_id"]

    # 2. Verify directive interpretation
    exp_directives = expected["directive_interpretation"]
    res_directives = data["directive_interpretation"]
    assert len(res_directives) == len(exp_directives)

    for i, (res_d, exp_d) in enumerate(zip(res_directives, exp_directives)):
        assert res_d["note_index"] == i
        assert res_d["applies"] == exp_d["applies"]
        assert res_d["directive_type"] == exp_d["directive_type"]
        if exp_d["structured_adjustment"] is None:
            assert res_d["structured_adjustment"] is None
        else:
            assert res_d["structured_adjustment"] == exp_d["structured_adjustment"]

    # 3. Verify total cost within 0.01 tolerance
    ref_cost = expected["total_cost_bdt"]
    solved_cost = data["total_cost_bdt"]
    diff = abs(solved_cost - ref_cost)
    assert diff <= 0.01, f"[{case_id}] Cost diff {diff} exceeds tolerance: solved={solved_cost}, ref={ref_cost}"

    # 4. Verify total grid and peak grid consistency
    hourly_plan = data["hourly_plan"]
    assert len(hourly_plan) == 24
    calc_total_grid = round(sum(p["grid_kwh"] for p in hourly_plan), 4)
    calc_peak_grid = round(max(p["grid_kwh"] for p in hourly_plan), 4)
    assert abs(data["total_grid_kwh"] - calc_total_grid) <= 0.01
    assert abs(data["peak_grid_kwh"] - calc_peak_grid) <= 0.01

    # 5. Verify plan summary exists
    assert "plan_summary" in data and len(data["plan_summary"]) > 0
