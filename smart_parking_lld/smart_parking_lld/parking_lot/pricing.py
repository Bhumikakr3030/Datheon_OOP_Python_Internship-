from datetime import datetime
from decimal import Decimal
from math import ceil
from .models import VehicleType, as_money


class HourlyRatePricing:
    """Configurable hourly rates plus an example weekend multiplier."""
    def __init__(self, rates=None, currency="INR", peak_multiplier="1.0"):
        defaults = {
            VehicleType.MOTORCYCLE: "20",
            VehicleType.COMPACT_CAR: "40",
            VehicleType.LARGE_SUV: "70",
            VehicleType.ELECTRIC_VEHICLE: "50",
        }
        if rates:
            defaults.update(rates)
        self.__rates = {key: as_money(value) for key, value in defaults.items()}
        if not isinstance(currency, str) or len(currency.strip()) != 3:
            raise ValueError("Currency must be a three-letter code.")
        self.__currency = currency.strip().upper()
        try:
            self.__peak_multiplier = Decimal(str(peak_multiplier))
        except Exception:
            raise ValueError("Invalid peak multiplier.") from None
        if not self.__peak_multiplier.is_finite() or self.__peak_multiplier < 1:
            raise ValueError("Peak multiplier must be finite and at least 1.")

    @property
    def currency(self):
        return self.__currency

    def calculate(self, vehicle_type: VehicleType, entry_time: datetime, exit_time: datetime):
        if exit_time < entry_time:
            raise ValueError("Exit time cannot precede entry time.")
        hours = max(1, ceil((exit_time - entry_time).total_seconds() / 3600))
        if vehicle_type not in self.__rates:
            raise ValueError("No rate configured for vehicle type.")
        multiplier = self.__peak_multiplier if exit_time.weekday() >= 5 else Decimal("1")
        amount = (self.__rates[vehicle_type] * hours * multiplier).quantize(Decimal("0.01"))
        return hours, amount
