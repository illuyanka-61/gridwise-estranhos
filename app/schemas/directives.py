"""Directive schemas and structured adjustment models."""

from enum import Enum
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class DirectiveType(str, Enum):
    """The six supported directive types defined in Section 04."""

    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"


class BaseHoursAdjustment(BaseModel):
    """Base model enforcing unique, ascending hours between 0 and 23."""

    hours: list[int] = Field(
        ...,
        min_length=1,
        max_length=24,
        description="Unique integers 0..23 in ascending order",
    )

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("hours array cannot be empty")
        for h in v:
            if not isinstance(h, int) or h < 0 or h > 23:
                raise ValueError(f"Hour {h} must be an integer between 0 and 23")
        if len(v) != len(set(v)):
            raise ValueError("hours must contain unique entries")
        if v != sorted(v):
            raise ValueError("hours must be sorted in ascending order")
        return v


class SolarReductionAdjustment(BaseHoursAdjustment):
    """Adjustment for solar_reduction: factor is the remaining usable fraction."""

    factor: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Usable solar fraction remaining (e.g. 80% reduction -> factor 0.2)",
    )


class MinimumBatteryReserveAdjustment(BaseHoursAdjustment):
    """Adjustment for minimum_battery_reserve."""

    minimum_energy_kwh: float = Field(
        ...,
        ge=0.0,
        description="Required minimum battery energy level in kWh",
    )


class WindowHoursAdjustment(BaseHoursAdjustment):
    """Adjustment for no_charge_window and no_discharge_window."""

    pass


class MaxGridWindowAdjustment(BaseHoursAdjustment):
    """Adjustment for max_grid_window."""

    max_grid_kwh: float = Field(
        ...,
        ge=0.0,
        description="Maximum permitted grid import in kWh during listed hours",
    )


StructuredAdjustmentType = Union[
    SolarReductionAdjustment,
    MinimumBatteryReserveAdjustment,
    WindowHoursAdjustment,
    MaxGridWindowAdjustment,
    None,
]


class DirectiveInterpretationItem(BaseModel):
    """Machine-checkable interpretation entry for one operator note."""

    note_index: int = Field(..., ge=0, description="Index of operator note (0..N-1)")
    applies: bool = Field(
        ..., description="true for active directives, false only for no_op"
    )
    directive_type: DirectiveType = Field(..., description="Supported directive type")
    structured_adjustment: StructuredAdjustmentType = Field(
        default=None, description="Adjustment payload or null for no_op"
    )
    explanation: str = Field(..., description="Short explanation of interpretation")

    @model_validator(mode="after")
    def validate_applies_and_adjustment(self) -> "DirectiveInterpretationItem":
        if self.directive_type == DirectiveType.NO_OP:
            if self.applies:
                raise ValueError("no_op directive must have applies=False")
            if self.structured_adjustment is not None:
                raise ValueError("no_op directive must have structured_adjustment=None")
        else:
            if not self.applies:
                raise ValueError(
                    f"{self.directive_type.value} must have applies=True"
                )
            if self.structured_adjustment is None:
                raise ValueError(
                    f"{self.directive_type.value} requires a non-null structured_adjustment"
                )
            # Check type consistency
            if (
                self.directive_type == DirectiveType.SOLAR_REDUCTION
                and not isinstance(self.structured_adjustment, SolarReductionAdjustment)
            ):
                raise ValueError(
                    "solar_reduction requires SolarReductionAdjustment with 'factor'"
                )
            if (
                self.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE
                and not isinstance(
                    self.structured_adjustment, MinimumBatteryReserveAdjustment
                )
            ):
                raise ValueError(
                    "minimum_battery_reserve requires MinimumBatteryReserveAdjustment with 'minimum_energy_kwh'"
                )
            if (
                self.directive_type in (DirectiveType.NO_CHARGE_WINDOW, DirectiveType.NO_DISCHARGE_WINDOW)
                and not isinstance(self.structured_adjustment, WindowHoursAdjustment)
            ):
                raise ValueError(
                    f"{self.directive_type.value} requires WindowHoursAdjustment"
                )
            if (
                self.directive_type == DirectiveType.MAX_GRID_WINDOW
                and not isinstance(self.structured_adjustment, MaxGridWindowAdjustment)
            ):
                raise ValueError(
                    "max_grid_window requires MaxGridWindowAdjustment with 'max_grid_kwh'"
                )
        return self
