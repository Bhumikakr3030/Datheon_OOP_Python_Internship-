# UML Class Diagram

```mermaid
classDiagram
    class VehicleType {
      <<enumeration>>
      MOTORCYCLE
      COMPACT_CAR
      LARGE_SUV
      ELECTRIC_VEHICLE
    }
    class SlotType {
      <<enumeration>>
      MOTORCYCLE
      COMPACT
      LARGE
      EV_CHARGING
    }
    class Vehicle {
      +license_plate: str
      +vehicle_type: VehicleType
    }
    class ParkingSlot {
      +slot_id: str
      +floor_number: int
      +slot_type: SlotType
      +supports_charging: bool
      +occupied_by: str
    }
    class ParkingTicket {
      +ticket_id: str
      +license_plate: str
      +floor_number: int
      +slot_id: str
      +entry_time: datetime
      +vehicle_type: VehicleType
    }
    class ParkingReceipt {
      +ticket_id: str
      +amount: Decimal
      +currency: str
      +parked_hours: int
    }
    class HourlyRatePricing {
      +calculate(vehicle_type, entry_time, exit_time)
    }
    class ParkingLot {
      -slots
      -active_tickets
      +park(vehicle, entry_time)
      +unpark(ticket_id, exit_time)
      +availability()
      +active_ticket(ticket_id)
    }

    Vehicle --> VehicleType
    ParkingSlot --> SlotType
    ParkingLot o-- ParkingSlot
    ParkingLot --> HourlyRatePricing
    ParkingLot --> ParkingTicket
    ParkingLot --> ParkingReceipt
```

## Allocation policy

- Motorcycle: motorcycle, compact, or large slots.
- Compact car: compact or large slots.
- Large SUV: large slots only.
- Electric vehicle: charging slots first, then large slots.
- Pick the lowest floor and slot ID among compatible slots.
- Charge at least one hour and round partial hours up.
- Apply the configured multiplier for weekend exits.
