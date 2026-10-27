from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from .models import ParkingReceipt, ParkingSlot, ParkingTicket, SlotType, Vehicle, VehicleType

_COMPATIBLE_SLOTS = {
    VehicleType.MOTORCYCLE: {SlotType.MOTORCYCLE, SlotType.COMPACT, SlotType.LARGE},
    VehicleType.COMPACT_CAR: {SlotType.COMPACT, SlotType.LARGE},
    VehicleType.LARGE_SUV: {SlotType.LARGE},
    VehicleType.ELECTRIC_VEHICLE: {SlotType.EV_CHARGING, SlotType.LARGE},
}


class ParkingLot:
    """In-memory multi-floor lot with thread-safe slot allocation."""
    def __init__(self, name, floors, pricing):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Parking lot name cannot be empty.")
        if not isinstance(floors, dict) or not floors:
            raise ValueError("Provide floors as {floor_number: slot_definitions}.")
        self.__name = name.strip()
        self.__pricing = pricing
        self.__slots = {}
        self.__active_tickets = {}
        self.__ticket_by_plate = {}
        self.__lock = RLock()
        for floor_number, definitions in floors.items():
            if not isinstance(floor_number, int) or floor_number < 0:
                raise ValueError("Floor numbers must be non-negative integers.")
            for definition in definitions:
                slot_id, slot_type = definition["slot_id"], definition["slot_type"]
                charging = definition.get("supports_charging", False)
                if not isinstance(slot_id, str) or not slot_id.strip():
                    raise ValueError("Slot ID cannot be empty.")
                if slot_id in self.__slots:
                    raise ValueError(f"Duplicate slot ID: {slot_id}")
                if not isinstance(slot_type, SlotType):
                    raise TypeError("slot_type must be a SlotType.")
                if charging and slot_type != SlotType.EV_CHARGING:
                    raise ValueError("Charging support requires EV_CHARGING slot type.")
                self.__slots[slot_id] = ParkingSlot(slot_id.strip(), floor_number, slot_type, charging)

    def _choose_slot(self, vehicle):
        compatible = _COMPATIBLE_SLOTS[vehicle.vehicle_type]
        candidates = [s for s in self.__slots.values()
                      if s.occupied_by is None and s.slot_type in compatible]
        if vehicle.vehicle_type == VehicleType.ELECTRIC_VEHICLE:
            candidates.sort(key=lambda s: (not s.supports_charging, s.floor_number, s.slot_id))
        elif vehicle.vehicle_type == VehicleType.MOTORCYCLE:
            candidates.sort(key=lambda s: (s.slot_type != SlotType.MOTORCYCLE, s.floor_number, s.slot_id))
        elif vehicle.vehicle_type == VehicleType.COMPACT_CAR:
            candidates.sort(key=lambda s: (s.slot_type != SlotType.COMPACT, s.floor_number, s.slot_id))
        else:
            candidates.sort(key=lambda s: (s.floor_number, s.slot_id))
        return candidates[0] if candidates else None

    def park(self, vehicle: Vehicle, entry_time=None) -> ParkingTicket:
        if not isinstance(vehicle, Vehicle):
            raise TypeError("vehicle must be a Vehicle instance.")
        entry_time = entry_time or datetime.now(timezone.utc)
        if entry_time.tzinfo is None:
            raise ValueError("entry_time must be timezone-aware.")
        with self.__lock:
            plate = vehicle.license_plate
            if plate in self.__ticket_by_plate:
                raise ValueError("Vehicle already has an active parking ticket.")
            slot = self._choose_slot(vehicle)
            if slot is None:
                raise ValueError("No compatible parking slots available.")
            ticket = ParkingTicket(str(uuid4()), plate, slot.floor_number, slot.slot_id,
                                   entry_time, vehicle.vehicle_type)
            slot.occupied_by = plate
            self.__active_tickets[ticket.ticket_id] = ticket
            self.__ticket_by_plate[plate] = ticket.ticket_id
            return ticket

    def unpark(self, ticket_id: str, exit_time=None) -> ParkingReceipt:
        exit_time = exit_time or datetime.now(timezone.utc)
        if exit_time.tzinfo is None:
            raise ValueError("exit_time must be timezone-aware.")
        with self.__lock:
            try:
                ticket = self.__active_tickets[ticket_id]
            except KeyError:
                raise ValueError("Active parking ticket not found.") from None
            hours, amount = self.__pricing.calculate(ticket.vehicle_type, ticket.entry_time, exit_time)
            slot = self.__slots[ticket.slot_id]
            slot.occupied_by = None
            del self.__active_tickets[ticket_id]
            self.__ticket_by_plate.pop(ticket.license_plate, None)
            return ParkingReceipt(ticket.ticket_id, ticket.license_plate, ticket.slot_id,
                                  ticket.entry_time, exit_time, hours, amount, self.__pricing.currency)

    def availability(self):
        with self.__lock:
            result = {}
            for floor in sorted({s.floor_number for s in self.__slots.values()}):
                slots = [s for s in self.__slots.values() if s.floor_number == floor]
                result[floor] = {"total": len(slots),
                                 "available": sum(s.occupied_by is None for s in slots)}
            return result

    def active_ticket(self, ticket_id):
        with self.__lock:
            try:
                return self.__active_tickets[ticket_id]
            except KeyError:
                raise ValueError("Active parking ticket not found.") from None
