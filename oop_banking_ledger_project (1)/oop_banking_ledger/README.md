# Multi-Currency Banking & Ledger Engine

A Python OOP portfolio project for the Datheon OOP & System Design Internship task.

## Features

- Abstract `Account` base class with abstract `accrue_interest()` and `deduct_fees()`.
- `SavingsAccount`, `CheckingAccount`, and `HighYieldAccount`.
- Encapsulated account state using private attributes and read-only properties.
- Input validation and `Decimal` monetary arithmetic.
- Native currency attached to each account (`INR`, `USD`, `EUR`, `GBP`, `JPY`).
- Polymorphic transaction dispatch through `TransactionProcessor`.
- Immutable transaction records with IDs, UTC timestamps, amount, currency, and resulting balance.
- Basic locks around account state changes.
- Unit tests using the Python standard library.

## Requirements

Python 3.10 or newer. No third-party packages required.

## Run the demo

```bash
python banking_engine.py
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Example

```python
from banking_engine import SavingsAccount, TransactionProcessor

account = SavingsAccount(
    "S001", "Alice", currency="INR", opening_balance="10000"
)
processor = TransactionProcessor()
processor.register(account)

processor.process("S001", "deposit", "500")
processor.process("S001", "interest")
print(account.statement())
```

## Four pillars of OOP

1. **Abstraction:** `Account` is abstract and defines the common account contract.
2. **Encapsulation:** account state is stored in private attributes and exposed through properties/methods.
3. **Inheritance:** all three concrete account types inherit from `Account`.
4. **Polymorphism:** `TransactionProcessor` invokes common interface methods; each account implements its own interest and fee policy.

## Multi-currency behavior

Each account has exactly one native currency. Currency is stored on every transaction. The engine does not add balances across currencies and does not silently convert money. Foreign exchange conversion is intentionally out of scope; a future implementation should require an explicit, timestamped exchange-rate quote and record both sides of the conversion.

## Assumptions

- Interest is calculated as `balance × annual rate ÷ 12`, rounded to cents.
- Savings fees apply when the balance is below the configured minimum.
- Checking accounts do not accrue interest in this example.
- The configured checking overdraft limit permits the balance to become negative up to that limit.
- The fee action charges the account-specific fee once per invocation; scheduling monthly fees is outside this demo.

## Limitations

This is an educational project, not production banking software. A production ledger requires durable storage, authorization, idempotency, double-entry journal postings, reconciliation, audit controls, and transactional guarantees across transfers.
