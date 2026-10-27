"""End-to-end demo: python demo.py"""
from datetime import datetime, timedelta

from smart_parking import (CompactCar, DisplayBoard, ElectricVehicle, LargeSUV, Motorcycle,
                           ParkingLotBuilder, SlotType as S)


class DemoClock:
    def __init__(self):
        self.t = datetime(2026, 1, 5, 8, 30)

    def now(self):
        return self.t


clock = DemoClock()
lot = (ParkingLotBuilder("Bengaluru Central")
       .with_clock(clock)
       .add_floor({S.MOTORCYCLE: 2, S.COMPACT: 3, S.LARGE: 1, S.EV_CHARGING: 1})
       .add_floor({S.COMPACT: 4, S.LARGE: 2, S.EV_CHARGING: 2})
       .build())
board = DisplayBoard()
lot.add_observer(board)

tickets = [lot.park(v) for v in (Motorcycle("KA01MC0001"), CompactCar("KA01CC0002"),
                                 LargeSUV("KA01SU0003"), ElectricVehicle("KA01EV0004"))]
for t in tickets:
    print(f"{t.ticket_id}: {t.vehicle!r} -> {t.slot.slot_id}")
print("\nDisplay board:\n" + board.render())

clock.t += timedelta(hours=2, minutes=10)
print()
for t in tickets:
    r = lot.unpark(t.ticket_id)
    f = r.fee
    print(f"{t.ticket_id} {t.vehicle.license_plate}: {f.billable_hours}h  base={f.base_fee} "
          f"peak={f.peak_surcharge} charging={f.charging_fee} total={f.total}")
