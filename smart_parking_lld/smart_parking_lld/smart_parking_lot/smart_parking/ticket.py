"""Ticket and Receipt value objects."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .enums import TicketStatus
from .slots import ParkingSlot
from .vehicles import Vehicle


@dataclass
class Ticket:
    ticket_id: str
    vehicle: Vehicle
    slot: ParkingSlot
    entry_time: datetime
    entry_occupancy: float  # lot occupancy (0..1) when the vehicle entered; drives surge pricing
    status: TicketStatus = TicketStatus.ACTIVE
    exit_time: Optional[datetime] = None


@dataclass(frozen=True)
class Receipt:
    ticket: Ticket
    duration: timedelta
    fee: "FeeBreakdown"  # noqa: F821 - defined in pricing.py
