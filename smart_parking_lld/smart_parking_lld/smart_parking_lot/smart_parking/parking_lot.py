"""ParkingLot facade, availability observers and builder."""
from __future__ import annotations

import itertools
import threading
from typing import Dict, List, Mapping, Optional, Protocol, Sequence

from .allocation import NearestSlotStrategy, SlotAllocationStrategy
from .clock import Clock, SystemClock
from .enums import SlotType, TicketStatus
from .exceptions import DuplicateVehicleError, InvalidTicketError, ParkingFullError
from .pricing import DynamicHourlyPricing, PricingStrategy
from .slots import ParkingFloor
from .ticket import Receipt, Ticket
from .vehicles import Vehicle

Availability = Dict[int, Dict[SlotType, int]]  # floor -> slot type -> free count


class AvailabilityObserver(Protocol):
    def on_availability_changed(self, snapshot: Availability) -> None: ...


class DisplayBoard:
    """Entrance display board: always shows the latest free-slot counts."""

    def __init__(self) -> None:
        self.snapshot: Availability = {}

    def on_availability_changed(self, snapshot: Availability) -> None:
        self.snapshot = snapshot

    def render(self) -> str:
        lines = []
        for floor, counts in sorted(self.snapshot.items()):
            parts = ", ".join(f"{t.name}:{n}" for t, n in counts.items())
            lines.append(f"Floor {floor}: {parts}")
        return "\n".join(lines)


class ParkingLot:
    """Thread-safe facade. All state mutation happens under a single lock."""

    def __init__(
        self,
        name: str,
        floors: Sequence[ParkingFloor],
        allocation_strategy: Optional[SlotAllocationStrategy] = None,
        pricing_strategy: Optional[PricingStrategy] = None,
        clock: Optional[Clock] = None,
    ):
        if not floors:
            raise ValueError("A parking lot needs at least one floor")
        numbers = [f.floor_number for f in floors]
        if len(set(numbers)) != len(numbers):
            raise ValueError("Floor numbers must be unique")

        self.name = name
        self._floors = sorted(floors, key=lambda f: f.floor_number)
        self._floor_by_number = {f.floor_number: f for f in self._floors}
        self._allocation = allocation_strategy or NearestSlotStrategy()
        self._pricing = pricing_strategy or DynamicHourlyPricing()
        self._clock = clock or SystemClock()

        self._lock = threading.RLock()
        self._ids = itertools.count(1)
        self._tickets: Dict[str, Ticket] = {}          # active tickets by id
        self._plate_to_ticket: Dict[str, str] = {}     # active plates
        self._observers: List[AvailabilityObserver] = []

    # ---- public API ---------------------------------------------------
    def add_observer(self, observer: AvailabilityObserver) -> None:
        self._observers.append(observer)
        observer.on_availability_changed(self.availability())

    def park(self, vehicle: Vehicle) -> Ticket:
        with self._lock:
            if vehicle.license_plate in self._plate_to_ticket:
                raise DuplicateVehicleError(f"{vehicle.license_plate} is already parked")
            slot = self._allocation.allocate(self._floors, vehicle)
            if slot is None:
                raise ParkingFullError(f"No slot available for {vehicle!r}")

            entry_occupancy = self._occupancy_unlocked()
            self._floor_by_number[slot.floor_number].occupy(slot, vehicle)
            ticket = Ticket(
                ticket_id=f"TKT-{next(self._ids):06d}",
                vehicle=vehicle,
                slot=slot,
                entry_time=self._clock.now(),
                entry_occupancy=entry_occupancy,
            )
            self._tickets[ticket.ticket_id] = ticket
            self._plate_to_ticket[vehicle.license_plate] = ticket.ticket_id
            snapshot = self._availability_unlocked()
        self._notify(snapshot)
        return ticket

    def unpark(self, ticket_id: str) -> Receipt:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None or ticket.status is not TicketStatus.ACTIVE:
                raise InvalidTicketError(f"Unknown or closed ticket: {ticket_id}")

            exit_time = self._clock.now()
            fee = self._pricing.calculate(ticket, exit_time)  # may raise; nothing mutated yet

            ticket.exit_time = exit_time
            ticket.status = TicketStatus.CLOSED
            self._floor_by_number[ticket.slot.floor_number].vacate(ticket.slot)
            del self._tickets[ticket_id]
            del self._plate_to_ticket[ticket.vehicle.license_plate]
            snapshot = self._availability_unlocked()
        self._notify(snapshot)
        return Receipt(ticket=ticket, duration=exit_time - ticket.entry_time, fee=fee)

    def availability(self) -> Availability:
        with self._lock:
            return self._availability_unlocked()

    def occupancy_ratio(self) -> float:
        with self._lock:
            return self._occupancy_unlocked()

    # ---- internals ----------------------------------------------------
    def _availability_unlocked(self) -> Availability:
        return {
            f.floor_number: {t: f.free_count(t) for t in SlotType if f.capacity(t) > 0}
            for f in self._floors
        }

    def _occupancy_unlocked(self) -> float:
        capacity = sum(f.capacity() for f in self._floors)
        free = sum(f.total_free for f in self._floors)
        return 0.0 if capacity == 0 else (capacity - free) / capacity

    def _notify(self, snapshot: Availability) -> None:
        for observer in list(self._observers):
            observer.on_availability_changed(snapshot)


class ParkingLotBuilder:
    """Fluent builder for assembling a lot."""

    def __init__(self, name: str):
        self._name = name
        self._floors: List[ParkingFloor] = []
        self._allocation: Optional[SlotAllocationStrategy] = None
        self._pricing: Optional[PricingStrategy] = None
        self._clock: Optional[Clock] = None

    def add_floor(self, layout: Mapping[SlotType, int]) -> "ParkingLotBuilder":
        self._floors.append(ParkingFloor(len(self._floors) + 1, layout))
        return self

    def with_allocation(self, strategy: SlotAllocationStrategy) -> "ParkingLotBuilder":
        self._allocation = strategy
        return self

    def with_pricing(self, strategy: PricingStrategy) -> "ParkingLotBuilder":
        self._pricing = strategy
        return self

    def with_clock(self, clock: Clock) -> "ParkingLotBuilder":
        self._clock = clock
        return self

    def build(self) -> ParkingLot:
        return ParkingLot(self._name, self._floors, self._allocation, self._pricing, self._clock)
