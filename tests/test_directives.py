"""Unit tests for directive extraction and semantics."""

import pytest
from app.schemas.directives import DirectiveType
from app.schemas.request import BatterySpecs
from app.llm.fallback import fallback_interpret_note
from app.guardrails.normalizer import (
    extract_solar_factor,
    extract_time_window,
    extract_battery_reserve,
    extract_max_grid,
)

SAMPLE_BATTERY = BatterySpecs(
    capacity_kwh=200.0,
    initial_energy_kwh=100.0,
    minimum_energy_kwh=40.0,
    max_charge_kwh_per_hour=50.0,
    max_discharge_kwh_per_hour=50.0,
)


def test_solar_reduction_percentage_semantics():
    """Verify distinction between 'reduce by X%' and 'treated as X%'."""
    # 80% reduction means factor = 0.20
    assert extract_solar_factor("Expect an 80% reduction in rooftop solar") == 0.20
    assert extract_solar_factor("reduce solar by 20%") == 0.80

    # usable solar treated as X% means factor = X/100
    assert extract_solar_factor("usable solar should be treated as roughly 25% of the forecast") == 0.25
    assert extract_solar_factor("Solar output will drop to about 20%") == 0.20
    assert extract_solar_factor("one-fifth of normal solar output") == 0.20
    assert extract_solar_factor("leave about half of the forecast") == 0.50


def test_time_window_normalization():
    """Verify start-inclusive end-exclusive whole-hour intervals."""
    # 1 PM to 3 PM -> [13, 14]
    assert extract_time_window("from 1 PM to 3 PM") == [13, 14]
    assert extract_time_window("1-3 PM") == [13, 14]
    assert extract_time_window("from noon until 2 PM") == [12, 13]
    assert extract_time_window("from 2 AM until 5 AM") == [2, 3, 4]
    assert extract_time_window("between 11 AM and 2 PM") == [11, 12, 13]
    assert extract_time_window("from 6 PM until 10 PM") == [18, 19, 20, 21]


def test_battery_reserve_relative_and_absolute():
    """Verify percentage of capacity vs absolute kWh extraction."""
    # 50% of 200 kWh capacity = 100 kWh
    res_pct = extract_battery_reserve("Keep at least 50% of the battery capacity stored", battery_capacity_kwh=200.0)
    assert res_pct == 100.0

    res_abs = extract_battery_reserve("Keep at least 90 kWh in the battery from 6 PM until 10 PM")
    assert res_abs == 90.0


def test_max_grid_window_extraction():
    """Verify max grid import cap extraction."""
    assert extract_max_grid("grid import must not exceed 155 kWh in any hour") == 155.0
    assert extract_max_grid("transformer limit is 180 kWh of grid import") == 180.0
    assert extract_max_grid("Grid intake must stay at or below 190 kWh") == 190.0


def test_paraphrased_no_charge():
    """Test paraphrased variants of no_charge_window."""
    phrases = [
        "The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance.",
        "The charging circuit will be unavailable from 2 PM until 4 PM.",
        "Battery charging is disabled from 11 AM until 1 PM while technicians inspect the charger.",
        "Do not charge the battery between 2 PM and 4 PM.",
        "Prevent battery charging from 2 PM to 4 PM.",
    ]
    for phrase in phrases:
        item = fallback_interpret_note(phrase, 0, SAMPLE_BATTERY)
        assert item.directive_type == DirectiveType.NO_CHARGE_WINDOW
        assert item.applies is True
        assert len(item.structured_adjustment.hours) > 0


def test_paraphrased_no_discharge():
    """Test paraphrased variants of no_discharge_window."""
    phrases = [
        "For protection testing, the battery must not discharge from 6 PM until 8 PM.",
        "Do not discharge the battery from 5 PM until 7 PM during relay testing.",
        "Discharging is unavailable from 5 PM to 7 PM.",
    ]
    for phrase in phrases:
        item = fallback_interpret_note(phrase, 0, SAMPLE_BATTERY)
        assert item.directive_type == DirectiveType.NO_DISCHARGE_WINDOW
        assert item.applies is True


def test_no_op_distractor():
    """Test irrelevant notes resolve to no_op."""
    distractors = [
        "The sports office moved next month's registration deadline.",
        "The cafeteria menu changes tomorrow.",
        "The library is extending book-return hours next week.",
        "The student affairs office will publish club notices tomorrow.",
        "A seminar room booking was moved to next week.",
    ]
    for note in distractors:
        item = fallback_interpret_note(note, 0, SAMPLE_BATTERY)
        assert item.directive_type == DirectiveType.NO_OP
        assert item.applies is False
        assert item.structured_adjustment is None
