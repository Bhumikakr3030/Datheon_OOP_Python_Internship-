import threading
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from smart_parking import (
    CompactCar, DisplayBoard, DuplicateVehicleError, DynamicHourlyPricing, ElectricVehicle,
    InvalidTicketError, LargeSUV, LeastLoadedFloorStrategy, Motorcycle, ParkingFullError,
    ParkingLotBuilder, SlotType, TicketStatus,
)

M, C, L, E = SlotType.MOTORCYCLE, SlotType.COMPACT, SlotType.LARGE, SlotType.EV_CHARGING


class FakeClock:
    def __init__(self, start=datetime(2026, 1, 5, 11, 0)):  # Monday 11:00, off-peak
        self.t = start

    def now(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make_lot(*layouts, clock=None, allocation=None):
    b = ParkingLotBuilder("Test").with_clock(clock or FakeClock())
    for layout in layouts:
        b.add_floor(layout)
    if allocation:
        b.with_allocation(allocation)
    return b.build()


class AllocationTests(unittest.TestCase):
    def test_motorcycle_falls_back_to_larger_slots_then_fails(self):
        lot = make_lot({M: 1, C: 1, L: 1})
        types = [lot.park(Motorcycle(f"MC{i}")).slot.slot_type for i in range(3)]
        self.assertEqual(types, [M, C, L])
        with self.assertRaises(ParkingFullError):
            lot.park(Motorcycle("MC9"))

    def test_suv_only_uses_large_even_if_compact_free(self):
        lot = make_lot({C: 5, L: 1})
        lot.park(LargeSUV("SUV1"))
        with self.assertRaises(ParkingFullError):
            lot.park(LargeSUV("SUV2"))

    def test_ev_prefers_charging_then_falls_back_to_compact(self):
        lot = make_lot({E: 1, C: 1})
        self.assertEqual(lot.park(ElectricVehicle("EV1")).slot.slot_type, E)
        self.assertEqual(lot.park(ElectricVehicle("EV2")).slot.slot_type, C)

    def test_regular_cars_never_take_ev_bays(self):
        lot = make_lot({E: 2})
        with self.assertRaises(ParkingFullError):
            lot.park(CompactCar("CAR1"))

    def test_nearest_strategy_fills_lowest_floor_first(self):
        lot = make_lot({C: 2}, {C: 2})
        floors = [lot.park(CompactCar(f"C{i}")).slot.floor_number for i in range(3)]
        self.assertEqual(floors, [1, 1, 2])

    def test_least_loaded_strategy_balances_floors(self):
        lot = make_lot({C: 2}, {C: 2}, allocation=LeastLoadedFloorStrategy())
        floors = [lot.park(CompactCar(f"C{i}")).slot.floor_number for i in range(4)]
        self.assertEqual(floors, [1, 2, 1, 2])

    def test_freed_slot_is_reused_lowest_number_first(self):
        lot = make_lot({C: 3})
        t1, t2, _ = (lot.park(CompactCar(f"C{i}")) for i in range(3))
        lot.unpark(t2.ticket_id)
        lot.unpark(t1.ticket_id)
        self.assertEqual(lot.park(CompactCar("NEW")).slot.slot_id, t1.slot.slot_id)


class LifecycleTests(unittest.TestCase):
    def test_duplicate_vehicle_rejected_and_plate_normalised(self):
        lot = make_lot({C: 3})
        lot.park(CompactCar("ka01ab1234"))
        with self.assertRaises(DuplicateVehicleError):
            lot.park(CompactCar(" KA01AB1234 "))

    def test_invalid_and_double_unpark(self):
        lot = make_lot({C: 1})
        with self.assertRaises(InvalidTicketError):
            lot.unpark("TKT-999999")
        t = lot.park(CompactCar("A1"))
        lot.unpark(t.ticket_id)
        self.assertEqual(t.status, TicketStatus.CLOSED)
        with self.assertRaises(InvalidTicketError):
            lot.unpark(t.ticket_id)

    def test_vehicle_can_reenter_after_exit(self):
        lot = make_lot({C: 1})
        t = lot.park(CompactCar("A1"))
        lot.unpark(t.ticket_id)
        lot.park(CompactCar("A1"))

    def test_empty_plate_rejected(self):
        with self.assertRaises(ValueError):
            CompactCar("  ")

    def test_availability_and_display_board(self):
        lot = make_lot({C: 2, E: 1})
        board = DisplayBoard()
        lot.add_observer(board)
        t = lot.park(CompactCar("A1"))
        self.assertEqual(board.snapshot[1][C], 1)
        self.assertEqual(lot.availability()[1][E], 1)
        lot.unpark(t.ticket_id)
        self.assertEqual(board.snapshot[1][C], 2)
        self.assertIn("Floor 1", board.render())

    def test_receipt_contains_duration_and_fee(self):
        clock = FakeClock()
        lot = make_lot({C: 1}, clock=clock)
        t = lot.park(CompactCar("A1"))
        clock.advance(hours=2)
        receipt = lot.unpark(t.ticket_id)
        self.assertEqual(receipt.duration, timedelta(hours=2))
        self.assertEqual(receipt.fee.total, Decimal("80.00"))


class PricingTests(unittest.TestCase):
    def fee(self, vehicle, layout, minutes, start=None, setup=None):
        clock = FakeClock(start) if start else FakeClock()
        lot = make_lot(layout, clock=clock)
        if setup:
            setup(lot)
        t = lot.park(vehicle)
        clock.advance(minutes=minutes)
        return lot.unpark(t.ticket_id).fee

    def test_grace_period_is_free(self):
        self.assertEqual(self.fee(CompactCar("A"), {C: 1}, 15).total, Decimal("0"))

    def test_just_over_grace_bills_one_hour(self):
        self.assertEqual(self.fee(CompactCar("A"), {C: 1}, 16).total, Decimal("40.00"))

    def test_exactly_one_hour_vs_one_minute_over(self):
        self.assertEqual(self.fee(CompactCar("A"), {C: 1}, 60).total, Decimal("40.00"))
        self.assertEqual(self.fee(CompactCar("A"), {C: 1}, 61).total, Decimal("80.00"))

    def test_rates_by_vehicle_type(self):
        self.assertEqual(self.fee(Motorcycle("A"), {M: 1}, 60).total, Decimal("20.00"))
        self.assertEqual(self.fee(LargeSUV("A"), {L: 1}, 60).total, Decimal("60.00"))
        self.assertEqual(self.fee(ElectricVehicle("A"), {C: 1}, 60).total, Decimal("50.00"))

    def test_peak_surcharge_applies_per_hour_block(self):
        # 08:30 -> blocks start 08:30 (peak) and 09:30 (peak)
        f = self.fee(CompactCar("A"), {C: 1}, 120, start=datetime(2026, 1, 5, 8, 30))
        self.assertEqual((f.base_fee, f.peak_surcharge, f.total),
                         (Decimal("80.00"), Decimal("40.00"), Decimal("120.00")))
        # 09:30 -> only the first block is peak
        f = self.fee(CompactCar("A"), {C: 1}, 120, start=datetime(2026, 1, 5, 9, 30))
        self.assertEqual(f.total, Decimal("100.00"))

    def test_surge_when_lot_is_nearly_full_at_entry(self):
        def fill(lot):
            for i in range(4):
                lot.park(CompactCar(f"FILL{i}"))
        f = self.fee(CompactCar("LAST"), {C: 5}, 60, setup=fill)  # entry occupancy 0.8
        self.assertEqual((f.surge_surcharge, f.total), (Decimal("10.00"), Decimal("50.00")))

    def test_ev_charging_fee_only_in_charging_bay(self):
        in_bay = self.fee(ElectricVehicle("A"), {E: 1}, 120)
        self.assertEqual((in_bay.charging_fee, in_bay.total), (Decimal("60.00"), Decimal("160.00")))
        in_regular = self.fee(ElectricVehicle("B"), {C: 1}, 120)
        self.assertEqual(in_regular.total, Decimal("100.00"))

    def test_daily_cap(self):
        self.assertEqual(self.fee(CompactCar("A"), {C: 1}, 12 * 60).total, Decimal("400.00"))
        self.assertEqual(self.fee(CompactCar("A"), {C: 1}, 25 * 60).total, Decimal("800.00"))

    def test_custom_pricing_plugs_in(self):
        from smart_parking import PricingConfig
        pricing = DynamicHourlyPricing(PricingConfig(grace_minutes=0, peak_windows=()))
        clock = FakeClock()
        lot = ParkingLotBuilder("X").with_clock(clock).with_pricing(pricing).add_floor({C: 1}).build()
        t = lot.park(CompactCar("A"))
        clock.advance(minutes=5)
        self.assertEqual(lot.unpark(t.ticket_id).fee.total, Decimal("40.00"))

    def test_negative_duration_rejected(self):
        lot = make_lot({C: 1})
        t = lot.park(CompactCar("A"))
        with self.assertRaises(ValueError):
            DynamicHourlyPricing().calculate(t, t.entry_time - timedelta(minutes=1))


class ConcurrencyTests(unittest.TestCase):
    def test_no_double_allocation_under_contention(self):
        lot = make_lot({C: 20})
        tickets, full = [], []
        guard = threading.Lock()

        def worker(i):
            try:
                t = lot.park(CompactCar(f"CAR{i}"))
                with guard:
                    tickets.append(t)
            except ParkingFullError:
                with guard:
                    full.append(i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(60)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEqual(len(tickets), 20)
        self.assertEqual(len(full), 40)
        self.assertEqual(len({t.slot.slot_id for t in tickets}), 20)
        self.assertEqual(lot.occupancy_ratio(), 1.0)


if __name__ == "__main__":
    unittest.main()
