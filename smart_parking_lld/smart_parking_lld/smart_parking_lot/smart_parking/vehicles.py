"""Vehicle hierarchy.

Each vehicle declares which slot types it may use, ordered from best fit to
worst fit.  Allocation strategies walk that list, so adding a new vehicle type
never requires touching allocation code (Open/Closed principle).
"""
from __future__ import annotations

from abc import ABC
from typing import ClassVar, Tuple

from .enums import SlotType, VehicleType


class Vehicle(ABC):
    vehicle_type: ClassVar[VehicleType]
    # Ordered by preference: smallest suitable slot first (minimises waste).
    compatible_slot_types: ClassVar[Tuple[SlotType, ...]]

    def __init__(self, license_plate: str):
        plate = (license_plate or "").strip().upper()
        if not plate:
            raise ValueError("license_plate must be a non-empty string")
        self.license_plate = plate

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.license_plate})"


class Motorcycle(Vehicle):
    vehicle_type = VehicleType.MOTORCYCLE
    compatible_slot_types = (SlotType.MOTORCYCLE, SlotType.COMPACT, SlotType.LARGE)


class CompactCar(Vehicle):
    vehicle_type = VehicleType.COMPACT_CAR
    compatible_slot_types = (SlotType.COMPACT, SlotType.LARGE)


class LargeSUV(Vehicle):
    vehicle_type = VehicleType.LARGE_SUV
    compatible_slot_types = (SlotType.LARGE,)


class ElectricVehicle(Vehicle):
    vehicle_type = VehicleType.ELECTRIC
    # Prefers a charging bay; falls back to a regular slot (no charging fee).
    compatible_slot_types = (SlotType.EV_CHARGING, SlotType.COMPACT, SlotType.LARGE)
