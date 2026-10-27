from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from uuid import uuid4


class VehicleType(str, Enum):
    MOTORCYCLE = "motorcycle"
    COMPACT_CAR = "compact_car"
    LARGE_SUV = "large_suv"
    ELECTRIC_VEHICLE = "electric_vehicle"


class SlotType(str, Enum):
    MOTORCYCLE = "motorcycle"
    COMPACT = "compact"
    LARGE = "large"
    EV_CHARGING = "ev_charging"


def as_money(value) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Use string, integer, or Decimal for money.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid monetary amount.") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amount must be finite and non-negative.")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Vehicle:
    license_plate: str
    vehicle_type: VehicleType

    def __post_init__(self):
        if not isinstance(self.license_plate, str) or not self.license_plate.strip():
            raise ValueError("License plate cannot be empty.")
        if not isinstance(self.vehicle_type, VehicleType):
            raise TypeError("vehicle_type must be a VehicleType.")
        object.__setattr__(self, "license_plate", self.license_plate.strip().upper())


@dataclass
class ParkingSlot:
    slot_id: str
    floor_number: int
    slot_type: SlotType
    supports_charging: bool = False
    occupied_by: str | None = None


@dataclass(frozen=True)
class ParkingTicket:
    ticket_id: str
    license_plate: str
    floor_number: int
    slot_id: str
    entry_time: datetime
    vehicle_type: VehicleType


@dataclass(frozen=True)
class ParkingReceipt:
    ticket_id: str
    license_plate: str
    slot_id: str
    entry_time: datetime
    exit_time: datetime
    parked_hours: int
    amount: Decimal
    currency: str
