import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from parking_lot import ParkingLot, HourlyRatePricing, Vehicle, VehicleType, SlotType


def make_lot():
    return ParkingLot("Test Lot", {
        0: [
            {"slot_id": "M1", "slot_type": SlotType.MOTORCYCLE},
            {"slot_id": "C1", "slot_type": SlotType.COMPACT},
            {"slot_id": "EV1", "slot_type": SlotType.EV_CHARGING, "supports_charging": True},
        ],
        1: [{"slot_id": "L1", "slot_type": SlotType.LARGE}],
    }, HourlyRatePricing(rates={
        VehicleType.MOTORCYCLE: "10", VehicleType.COMPACT_CAR: "20",
        VehicleType.LARGE_SUV: "30", VehicleType.ELECTRIC_VEHICLE: "25",
    }, currency="INR"))


class ParkingLotTests(unittest.TestCase):
    def setUp(self):
        self.lot = make_lot()
        self.start = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)

    def test_motorcycle_allocation(self):
        ticket = self.lot.park(Vehicle("ka01aa0001", VehicleType.MOTORCYCLE), self.start)
        self.assertEqual(ticket.slot_id, "M1")

    def test_ev_prefers_charging_slot(self):
        ticket = self.lot.park(Vehicle("KA01EV0001", VehicleType.ELECTRIC_VEHICLE), self.start)
        self.assertEqual(ticket.slot_id, "EV1")

    def test_hourly_fee_rounds_up(self):
        ticket = self.lot.park(Vehicle("KA01AB1234", VehicleType.COMPACT_CAR), self.start)
        receipt = self.lot.unpark(ticket.ticket_id, self.start + timedelta(hours=1, minutes=1))
        self.assertEqual(receipt.parked_hours, 2)
        self.assertEqual(receipt.amount, Decimal("40.00"))

    def test_slot_freed_after_unpark(self):
        ticket = self.lot.park(Vehicle("KA01AB0001", VehicleType.COMPACT_CAR), self.start)
        self.lot.unpark(ticket.ticket_id, self.start + timedelta(hours=1))
        next_ticket = self.lot.park(Vehicle("KA01AB0002", VehicleType.COMPACT_CAR), self.start)
        self.assertEqual(next_ticket.slot_id, "C1")

    def test_duplicate_active_vehicle_rejected(self):
        vehicle = Vehicle("KA01AB1234", VehicleType.COMPACT_CAR)
        self.lot.park(vehicle, self.start)
        with self.assertRaises(ValueError):
            self.lot.park(vehicle, self.start)

    def test_full_compatible_slots_rejected(self):
        self.lot.park(Vehicle("KA01AA0001", VehicleType.LARGE_SUV), self.start)
        with self.assertRaises(ValueError):
            self.lot.park(Vehicle("KA01AA0002", VehicleType.LARGE_SUV), self.start)

    def test_invalid_exit_does_not_free_slot(self):
        ticket = self.lot.park(Vehicle("KA01AB1234", VehicleType.COMPACT_CAR), self.start)
        with self.assertRaises(ValueError):
            self.lot.unpark(ticket.ticket_id, self.start - timedelta(minutes=1))
        self.assertEqual(self.lot.active_ticket(ticket.ticket_id), ticket)

    def test_empty_plate_rejected(self):
        with self.assertRaises(ValueError):
            Vehicle(" ", VehicleType.MOTORCYCLE)


if __name__ == "__main__":
    unittest.main()
