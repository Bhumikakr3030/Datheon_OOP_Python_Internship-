from datetime import datetime, timezone, timedelta
from parking_lot import ParkingLot, HourlyRatePricing, Vehicle, VehicleType, SlotType


def main():
    lot = ParkingLot("Datheon Smart Parking", {
        0: [
            {"slot_id": "M-01", "slot_type": SlotType.MOTORCYCLE},
            {"slot_id": "C-01", "slot_type": SlotType.COMPACT},
            {"slot_id": "EV-01", "slot_type": SlotType.EV_CHARGING, "supports_charging": True},
        ],
        1: [
            {"slot_id": "L-01", "slot_type": SlotType.LARGE},
            {"slot_id": "EV-02", "slot_type": SlotType.EV_CHARGING, "supports_charging": True},
        ],
    }, HourlyRatePricing(currency="INR", peak_multiplier="1.25"))

    entry = datetime.now(timezone.utc)
    ticket = lot.park(Vehicle("KA01AB1234", VehicleType.ELECTRIC_VEHICLE), entry)
    receipt = lot.unpark(ticket.ticket_id, entry + timedelta(hours=2, minutes=10))
    print("Ticket:", ticket)
    print("Receipt:", receipt)
    print("Availability:", lot.availability())


if __name__ == "__main__":
    main()
