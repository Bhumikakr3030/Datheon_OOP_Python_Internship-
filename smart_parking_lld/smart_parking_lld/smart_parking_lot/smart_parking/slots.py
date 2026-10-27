"""ParkingSlot and ParkingFloor.

A floor keeps one min-heap of free slots per slot type, so finding the
lowest-numbered free slot is O(1) and occupying/vacating is O(log n).
"""
from __future__ import annotations

import heapq
from typing import Dict, List, Mapping, Optional, Tuple

from .enums import SlotType
from .vehicles import Vehicle


class ParkingSlot:
    def __init__(self, floor_number: int, number: int, slot_type: SlotType):
        self.floor_number = floor_number
        self.number = number
        self.slot_type = slot_type
        self._vehicle: Optional[Vehicle] = None

    @property
    def slot_id(self) -> str:
        return f"F{self.floor_number}-{self.slot_type.value}{self.number:03d}"

    @property
    def vehicle(self) -> Optional[Vehicle]:
        return self._vehicle

    @property
    def is_free(self) -> bool:
        return self._vehicle is None

    def assign(self, vehicle: Vehicle) -> None:
        if self._vehicle is not None:
            raise ValueError(f"Slot {self.slot_id} is already occupied")
        self._vehicle = vehicle

    def release(self) -> None:
        self._vehicle = None

    def __repr__(self) -> str:
        return f"ParkingSlot({self.slot_id})"


class ParkingFloor:
    def __init__(self, floor_number: int, layout: Mapping[SlotType, int]):
        if any(count < 0 for count in layout.values()):
            raise ValueError("slot counts must be >= 0")
        self.floor_number = floor_number
        self._capacity: Dict[SlotType, int] = {t: layout.get(t, 0) for t in SlotType}
        self._free: Dict[SlotType, List[Tuple[int, ParkingSlot]]] = {t: [] for t in SlotType}
        self.slots: List[ParkingSlot] = []

        number = 0
        for slot_type in SlotType:
            for _ in range(self._capacity[slot_type]):
                number += 1  # unique per floor, so heap tuples never compare slots
                slot = ParkingSlot(floor_number, number, slot_type)
                self.slots.append(slot)
                self._free[slot_type].append((number, slot))
            heapq.heapify(self._free[slot_type])

    # ---- queries -------------------------------------------------------
    def peek_free(self, slot_type: SlotType) -> Optional[ParkingSlot]:
        heap = self._free[slot_type]
        return heap[0][1] if heap else None

    def free_count(self, slot_type: SlotType) -> int:
        return len(self._free[slot_type])

    def capacity(self, slot_type: Optional[SlotType] = None) -> int:
        if slot_type is None:
            return sum(self._capacity.values())
        return self._capacity[slot_type]

    @property
    def total_free(self) -> int:
        return sum(len(h) for h in self._free.values())

    @property
    def occupancy_ratio(self) -> float:
        cap = self.capacity()
        return 0.0 if cap == 0 else (cap - self.total_free) / cap

    # ---- mutations (called only by ParkingLot while holding its lock) ---
    def occupy(self, slot: ParkingSlot, vehicle: Vehicle) -> None:
        heap = self._free[slot.slot_type]
        if not heap or heap[0][1] is not slot:
            raise ValueError("Only the next free slot of a type can be occupied")
        heapq.heappop(heap)
        slot.assign(vehicle)

    def vacate(self, slot: ParkingSlot) -> None:
        slot.release()
        heapq.heappush(self._free[slot.slot_type], (slot.number, slot))
