"""Slot allocation algorithms (Strategy pattern)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from .slots import ParkingFloor, ParkingSlot
from .vehicles import Vehicle


class SlotAllocationStrategy(ABC):
    @abstractmethod
    def allocate(self, floors: Sequence[ParkingFloor], vehicle: Vehicle) -> Optional[ParkingSlot]:
        """Return the slot to use (without occupying it) or None if the lot is full."""


class NearestSlotStrategy(SlotAllocationStrategy):
    """Best-fit slot type first, then lowest floor, then lowest slot number.

    Keeps vehicles close to the entrance and avoids wasting large slots on
    small vehicles while smaller slots are still free.
    Complexity: O(types * floors).
    """

    def allocate(self, floors, vehicle):
        for slot_type in vehicle.compatible_slot_types:
            for floor in floors:  # floors are sorted ascending by the lot
                slot = floor.peek_free(slot_type)
                if slot is not None:
                    return slot
        return None


class LeastLoadedFloorStrategy(SlotAllocationStrategy):
    """Best-fit slot type first, then the floor with the lowest occupancy.

    Spreads traffic across floors to reduce congestion on any single ramp.
    """

    def allocate(self, floors, vehicle):
        for slot_type in vehicle.compatible_slot_types:
            candidates = [f for f in floors if f.free_count(slot_type) > 0]
            if candidates:
                best = min(candidates, key=lambda f: (f.occupancy_ratio, f.floor_number))
                return best.peek_free(slot_type)
        return None
