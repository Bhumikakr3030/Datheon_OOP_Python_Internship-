"""Domain enumerations."""
from enum import Enum


class VehicleType(Enum):
    MOTORCYCLE = "motorcycle"
    COMPACT_CAR = "compact_car"
    LARGE_SUV = "large_suv"
    ELECTRIC = "electric"


class SlotType(Enum):
    MOTORCYCLE = "M"
    COMPACT = "C"
    LARGE = "L"
    EV_CHARGING = "E"


class TicketStatus(Enum):
    ACTIVE = "active"
    CLOSED = "closed"
