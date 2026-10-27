# Smart Parking Lot — Low-Level Design

An object-oriented, multi-floor smart parking lot in Python, with UML, tickets, slot allocation, dynamic hourly pricing, and unit tests.

## Features
- Motorcycles, compact cars, large SUVs, and electric vehicles.
- Multiple floors and typed slots.
- EV charging-slot preference.
- Automated allocation using compatibility and deterministic tie-breaking.
- Unique parking tickets and exit receipts.
- Hourly billing with partial hours rounded up and configurable weekend multiplier.
- Thread-safe slot allocation and ticket updates.
- Input validation and tests.

## Requirements
Python 3.10 or newer. No external dependencies.

## Run
```bash
python main.py
```

## Test
```bash
python -m unittest discover -s tests -v
```

## UML
See `UML.md` for the Mermaid class diagram and allocation rules.

## Assumptions
- Each vehicle may have only one active ticket.
- Rates are per hour and minimum charge is one hour.
- EVs prefer dedicated charging slots; if none are free, they may use large slots.
- Weekend multiplier is based on the exit date.
- Data is stored in memory.

## Production caveats
This is an educational LLD implementation, not a complete deployed parking system. Production use requires persistent storage, payment integration, access control, sensor/gate integration, idempotent entry/exit processing, and monitoring. The weekend rule uses the exit timestamp's weekday and does not split a stay across rate periods.
