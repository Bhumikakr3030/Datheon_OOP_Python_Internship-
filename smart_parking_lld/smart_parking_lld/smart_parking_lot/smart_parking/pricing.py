"""Dynamic hourly pricing (Strategy pattern).

Fee model
---------
* First `grace_minutes` are free.
* Billing is per started hour (ceil), at a per-vehicle-type hourly rate.
* Each billed hour that *starts* in a peak window costs `peak_multiplier` x.
* If the lot was >= `surge_threshold` full at entry, parking charges get a
  `surge_multiplier` surcharge.
* Parking charges are capped per 24h block (daily cap, per vehicle type).
* EVs parked in a charging bay pay an additional per-hour charging fee
  (not subject to the cap).
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Tuple

from .enums import SlotType, VehicleType
from .ticket import Ticket

_CENT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeeBreakdown:
    billable_hours: int
    base_fee: Decimal = Decimal("0.00")
    peak_surcharge: Decimal = Decimal("0.00")
    surge_surcharge: Decimal = Decimal("0.00")
    charging_fee: Decimal = Decimal("0.00")
    cap_adjustment: Decimal = Decimal("0.00")  # <= 0

    @property
    def total(self) -> Decimal:
        return (self.base_fee + self.peak_surcharge + self.surge_surcharge
                + self.charging_fee + self.cap_adjustment)


@dataclass
class PricingConfig:
    hourly_rates: Dict[VehicleType, Decimal] = field(default_factory=lambda: {
        VehicleType.MOTORCYCLE: Decimal("20"),
        VehicleType.COMPACT_CAR: Decimal("40"),
        VehicleType.LARGE_SUV: Decimal("60"),
        VehicleType.ELECTRIC: Decimal("50"),
    })
    daily_caps: Dict[VehicleType, Decimal] = field(default_factory=lambda: {
        VehicleType.MOTORCYCLE: Decimal("200"),
        VehicleType.COMPACT_CAR: Decimal("400"),
        VehicleType.LARGE_SUV: Decimal("600"),
        VehicleType.ELECTRIC: Decimal("500"),
    })
    grace_minutes: int = 15
    # [start_hour, end_hour) windows on the 24h clock
    peak_windows: Tuple[Tuple[int, int], ...] = ((8, 10), (17, 20))
    peak_multiplier: Decimal = Decimal("1.5")
    surge_threshold: float = 0.8
    surge_multiplier: Decimal = Decimal("1.25")
    ev_charging_rate: Decimal = Decimal("30")


class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, ticket: Ticket, exit_time: datetime) -> FeeBreakdown: ...


class DynamicHourlyPricing(PricingStrategy):
    def __init__(self, config: PricingConfig | None = None):
        self.config = config or PricingConfig()

    def _is_peak(self, moment: datetime) -> bool:
        return any(start <= moment.hour < end for start, end in self.config.peak_windows)

    def calculate(self, ticket: Ticket, exit_time: datetime) -> FeeBreakdown:
        if exit_time < ticket.entry_time:
            raise ValueError("exit_time cannot be earlier than entry_time")
        cfg = self.config

        minutes = math.ceil((exit_time - ticket.entry_time).total_seconds() / 60)
        if minutes <= cfg.grace_minutes:
            return FeeBreakdown(billable_hours=0)

        hours = math.ceil(minutes / 60)
        vtype = ticket.vehicle.vehicle_type
        rate = cfg.hourly_rates[vtype]

        base = rate * hours
        peak_blocks = sum(
            1 for i in range(hours) if self._is_peak(ticket.entry_time + timedelta(hours=i))
        )
        peak = rate * (cfg.peak_multiplier - 1) * peak_blocks
        surge = Decimal("0.00")
        if ticket.entry_occupancy >= cfg.surge_threshold:
            surge = (base + peak) * (cfg.surge_multiplier - 1)

        base, peak, surge = _q(base), _q(peak), _q(surge)
        parking_total = base + peak + surge
        cap = cfg.daily_caps[vtype] * math.ceil(hours / 24)
        cap_adjustment = min(Decimal("0"), cap - parking_total)

        charging = Decimal("0.00")
        if ticket.slot.slot_type is SlotType.EV_CHARGING:
            charging = _q(cfg.ev_charging_rate * hours)

        return FeeBreakdown(hours, base, peak, surge, charging, _q(cap_adjustment))
