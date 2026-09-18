"""Data structures holding processed hourly constraints resulting from applied directives."""

from dataclasses import dataclass, field


@dataclass
class AppliedDirectiveConstraints:
    """Hourly energy bounds and limits after deterministic directive application."""

    effective_solar: list[float]  # Length 24
    min_battery_reserve: list[float]  # Length 24
    charge_allowed: list[bool]  # Length 24
    discharge_allowed: list[bool]  # Length 24
    max_grid_limit: list[float]  # Length 24, float('inf') if no cap
