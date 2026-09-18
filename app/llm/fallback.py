"""Deterministic rule-based fallback interpreter for offline mode and LLM failures."""

from app.schemas.directives import (
    DirectiveInterpretationItem,
    DirectiveType,
    SolarReductionAdjustment,
    MinimumBatteryReserveAdjustment,
    WindowHoursAdjustment,
    MaxGridWindowAdjustment,
)
from app.schemas.request import BatterySpecs
from app.guardrails.normalizer import (
    extract_time_window,
    extract_solar_factor,
    extract_battery_reserve,
    extract_max_grid,
)


def fallback_interpret_note(
    note: str,
    note_index: int,
    battery: BatterySpecs,
) -> DirectiveInterpretationItem:
    """
    Deterministically interprets an operator note without an external LLM.
    Acts as a high-reliability fallback and baseline parser.
    """
    clean = note.lower().strip()

    # 1. Distractor keywords -> no_op
    distractor_keywords = [
        "cafeteria", "menu", "sports office", "deadline", "registration",
        "library", "book", "club notices", "seminar room", "booking",
        "football", "holiday", "meeting", "parking", "exam", "grade",
    ]
    if any(k in clean for k in distractor_keywords) and not any(k in clean for k in ["solar", "battery", "grid", "feeder", "transformer", "substation"]):
        return DirectiveInterpretationItem(
            note_index=note_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="This note does not affect today's 24-hour energy schedule.",
        )

    # 2. Solar Reduction
    if any(k in clean for k in ["solar", "rooftop", "panel", "pv", "cleaning", "cloud"]):
        hours = extract_time_window(note)
        factor = extract_solar_factor(note)
        if hours and factor is not None:
            return DirectiveInterpretationItem(
                note_index=note_index,
                applies=True,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                structured_adjustment=SolarReductionAdjustment(hours=hours, factor=factor),
                explanation=f"Solar availability reduced to {factor * 100:.0f}% during window {hours}.",
            )

    # 3. No-Charge Window
    no_charge_terms = [
        "not charge", "cannot charge", "no charging", "charger will be isolated",
        "charging is disabled", "charging circuit will be unavailable", "charging unavailable",
        "charger offline", "disable charging", "prevent battery charging", "prevent charging",
        "keep the charger off", "stop charging",
    ]
    if any(k in clean for k in no_charge_terms):
        hours = extract_time_window(note)
        if hours:
            return DirectiveInterpretationItem(
                note_index=note_index,
                applies=True,
                directive_type=DirectiveType.NO_CHARGE_WINDOW,
                structured_adjustment=WindowHoursAdjustment(hours=hours),
                explanation=f"Battery charging is unavailable during hours {hours}.",
            )

    # 4. No-Discharge Window
    no_discharge_terms = [
        "not discharge", "cannot discharge", "no discharging", "discharging unavailable",
        "discharging is unavailable", "relay testing", "protection testing",
        "disable discharging", "prevent discharging", "prevent battery discharging",
    ]
    if any(k in clean for k in no_discharge_terms):
        hours = extract_time_window(note)
        if hours:
            return DirectiveInterpretationItem(
                note_index=note_index,
                applies=True,
                directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
                structured_adjustment=WindowHoursAdjustment(hours=hours),
                explanation=f"Battery discharging is unavailable during hours {hours}.",
            )

    # 5. Minimum Battery Reserve
    reserve_terms = [
        "reserve", "stored in the battery", "remain in the battery",
        "in the battery", "battery capacity", "storage", "data center",
    ]
    if any(k in clean for k in reserve_terms):
        hours = extract_time_window(note)
        reserve = extract_battery_reserve(note, battery.capacity_kwh)
        if hours and reserve is not None:
            return DirectiveInterpretationItem(
                note_index=note_index,
                applies=True,
                directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
                structured_adjustment=MinimumBatteryReserveAdjustment(
                    hours=hours, minimum_energy_kwh=reserve
                ),
                explanation=f"Minimum battery reserve of {reserve:.1f} kWh enforced for hours {hours}.",
            )

    # 6. Max Grid Window
    grid_terms = [
        "grid import", "feeder", "transformer", "grid intake", "substation",
        "import must not exceed", "intake must stay at or below", "grid limit",
    ]
    if any(k in clean for k in grid_terms):
        hours = extract_time_window(note)
        cap = extract_max_grid(note)
        if hours and cap is not None:
            return DirectiveInterpretationItem(
                note_index=note_index,
                applies=True,
                directive_type=DirectiveType.MAX_GRID_WINDOW,
                structured_adjustment=MaxGridWindowAdjustment(
                    hours=hours, max_grid_kwh=cap
                ),
                explanation=f"Campus grid import capped at {cap:.1f} kWh during hours {hours}.",
            )

    # Fallback to no_op if no directive applies
    return DirectiveInterpretationItem(
        note_index=note_index,
        applies=False,
        directive_type=DirectiveType.NO_OP,
        structured_adjustment=None,
        explanation="Note does not contain an applicable energy directive.",
    )


def fallback_interpret_all(
    operator_notes: list[str],
    battery: BatterySpecs,
) -> list[DirectiveInterpretationItem]:
    """Interprets all operator notes using deterministic rules."""
    return [
        fallback_interpret_note(note, i, battery)
        for i, note in enumerate(operator_notes)
    ]
