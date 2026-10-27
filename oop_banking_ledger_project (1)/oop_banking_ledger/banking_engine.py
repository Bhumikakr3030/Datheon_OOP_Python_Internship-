"""Educational multi-currency OOP banking ledger.

This is a portfolio/demo project, not production banking software.
Balances are maintained in each account's native currency. No FX conversion
is performed implicitly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from threading import RLock
from typing import Dict, Optional
from uuid import uuid4

CENT = Decimal("0.01")
SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP", "JPY"}


def to_money(value) -> Decimal:
    """Convert a string, integer, or Decimal into a finite two-decimal amount."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Use a string, integer, or Decimal for money (not float).")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid monetary amount.") from None
    if not amount.is_finite():
        raise ValueError("Monetary amount must be finite.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def to_rate(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid rate.") from None
    if not result.is_finite() or result < 0:
        raise ValueError("Rate must be finite and non-negative.")
    return result


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    account_id: str
    transaction_type: str
    amount: Decimal
    currency: str
    balance_after: Decimal
    timestamp_utc: str
    description: str


class Account(ABC):
    """Abstract account. Subclasses supply interest and fee policies."""

    def __init__(self, account_id: str, owner: str, currency: str,
                 opening_balance="0"):
        if not isinstance(account_id, str) or not account_id.strip():
            raise ValueError("Account ID cannot be empty.")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner cannot be empty.")
        if not isinstance(currency, str) or currency.upper() not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of {sorted(SUPPORTED_CURRENCIES)}.")
        balance = to_money(opening_balance)
        if balance < 0:
            raise ValueError("Opening balance cannot be negative.")

        self.__account_id = account_id.strip()
        self.__owner = owner.strip()
        self.__currency = currency.upper()
        self.__balance = balance
        self.__transactions = []
        self.__lock = RLock()

    @property
    def account_id(self) -> str:
        return self.__account_id

    @property
    def owner(self) -> str:
        return self.__owner

    @property
    def currency(self) -> str:
        return self.__currency

    @property
    def balance(self) -> Decimal:
        with self.__lock:
            return self.__balance

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        with self.__lock:
            return tuple(self.__transactions)

    @property
    def overdraft_limit(self) -> Decimal:
        return Decimal("0.00")

    def _record_locked(self, kind: str, amount: Decimal, description: str):
        self.__transactions.append(Transaction(
            transaction_id=str(uuid4()),
            account_id=self.__account_id,
            transaction_type=kind,
            amount=amount,
            currency=self.__currency,
            balance_after=self.__balance,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            description=description,
        ))

    def deposit(self, amount, description="Deposit") -> Decimal:
        amount = to_money(amount)
        if amount <= 0:
            raise ValueError("Deposit must be greater than zero.")
        with self.__lock:
            self.__balance += amount
            self._record_locked("DEPOSIT", amount, description)
            return self.__balance

    def withdraw(self, amount, description="Withdrawal") -> Decimal:
        amount = to_money(amount)
        if amount <= 0:
            raise ValueError("Withdrawal must be greater than zero.")
        with self.__lock:
            if self.__balance - amount < -self.overdraft_limit:
                raise ValueError("Insufficient funds.")
            self.__balance -= amount
            self._record_locked("WITHDRAWAL", amount, description)
            return self.__balance

    def _credit(self, amount, kind: str, description: str) -> Decimal:
        amount = to_money(amount)
        if amount <= 0:
            raise ValueError("Credit must be greater than zero.")
        with self.__lock:
            self.__balance += amount
            self._record_locked(kind, amount, description)
            return amount

    def _debit_fee(self, amount, description: str) -> Decimal:
        amount = to_money(amount)
        if amount < 0:
            raise ValueError("Fee cannot be negative.")
        if amount == 0:
            return Decimal("0.00")
        with self.__lock:
            if self.__balance - amount < -self.overdraft_limit:
                raise ValueError("Insufficient funds to pay fee.")
            self.__balance -= amount
            self._record_locked("FEE", amount, description)
            return amount

    def _monthly_interest(self, annual_rate: Decimal, description: str) -> Decimal:
        with self.__lock:
            if self.__balance <= 0:
                return Decimal("0.00")
            interest = to_money(self.__balance * annual_rate / Decimal("12"))
            if interest <= 0:
                return Decimal("0.00")
            self.__balance += interest
            self._record_locked("INTEREST", interest, description)
            return interest

    @abstractmethod
    def accrue_interest(self) -> Decimal:
        """Apply the account's interest policy."""
        raise NotImplementedError

    @abstractmethod
    def deduct_fees(self) -> Decimal:
        """Apply the account's fee policy."""
        raise NotImplementedError

    def statement(self) -> dict:
        with self.__lock:
            return {
                "account_id": self.__account_id,
                "owner": self.__owner,
                "currency": self.__currency,
                "balance": self.__balance,
                "transactions": tuple(self.__transactions),
            }


class SavingsAccount(Account):
    def __init__(self, account_id, owner, currency="INR", opening_balance="0",
                 annual_rate="0.04", monthly_fee="25", minimum_balance="500"):
        super().__init__(account_id, owner, currency, opening_balance)
        self.__annual_rate = to_rate(annual_rate)
        self.__monthly_fee = to_money(monthly_fee)
        self.__minimum_balance = to_money(minimum_balance)
        if self.__monthly_fee < 0 or self.__minimum_balance < 0:
            raise ValueError("Fee and minimum balance cannot be negative.")

    def accrue_interest(self) -> Decimal:
        return self._monthly_interest(self.__annual_rate, "Savings monthly interest")

    def deduct_fees(self) -> Decimal:
        if self.balance < self.__minimum_balance:
            return self._debit_fee(self.__monthly_fee, "Savings maintenance fee")
        return Decimal("0.00")


class CheckingAccount(Account):
    def __init__(self, account_id, owner, currency="INR", opening_balance="0",
                 transaction_fee="10", overdraft_limit="0"):
        super().__init__(account_id, owner, currency, opening_balance)
        self.__transaction_fee = to_money(transaction_fee)
        self.__overdraft_limit = to_money(overdraft_limit)
        if self.__transaction_fee < 0 or self.__overdraft_limit < 0:
            raise ValueError("Fee and overdraft limit cannot be negative.")

    @property
    def overdraft_limit(self) -> Decimal:
        return self.__overdraft_limit

    def accrue_interest(self) -> Decimal:
        return Decimal("0.00")

    def deduct_fees(self) -> Decimal:
        return self._debit_fee(self.__transaction_fee, "Checking service fee")


class HighYieldAccount(Account):
    def __init__(self, account_id, owner, currency="INR", opening_balance="0",
                 annual_rate="0.06", monthly_fee="5"):
        super().__init__(account_id, owner, currency, opening_balance)
        self.__annual_rate = to_rate(annual_rate)
        self.__monthly_fee = to_money(monthly_fee)
        if self.__monthly_fee < 0:
            raise ValueError("Monthly fee cannot be negative.")

    def accrue_interest(self) -> Decimal:
        return self._monthly_interest(self.__annual_rate, "High-yield monthly interest")

    def deduct_fees(self) -> Decimal:
        return self._debit_fee(self.__monthly_fee, "High-yield account fee")


class TransactionProcessor:
    """Polymorphic dispatcher: calls the common Account interface."""

    def __init__(self):
        self.__accounts: Dict[str, Account] = {}
        self.__lock = RLock()

    def register(self, account: Account) -> None:
        if not isinstance(account, Account):
            raise TypeError("Only Account instances can be registered.")
        with self.__lock:
            if account.account_id in self.__accounts:
                raise ValueError("Duplicate account ID.")
            self.__accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Account:
        with self.__lock:
            if account_id not in self.__accounts:
                raise ValueError("Account not found.")
            return self.__accounts[account_id]

    def process(self, account_id: str, action: str, amount=None):
        account = self.get_account(account_id)
        if not isinstance(action, str):
            raise ValueError("Action must be a string.")
        action = action.strip().lower()

        if action == "deposit":
            if amount is None:
                raise ValueError("Deposit requires an amount.")
            return account.deposit(amount)
        if action == "withdraw":
            if amount is None:
                raise ValueError("Withdrawal requires an amount.")
            return account.withdraw(amount)
        if action == "interest":
            if amount is not None:
                raise ValueError("Interest is calculated by the account.")
            return account.accrue_interest()
        if action == "fees":
            if amount is not None:
                raise ValueError("Fees are determined by the account.")
            return account.deduct_fees()
        raise ValueError(f"Unsupported action: {action}")


if __name__ == "__main__":
    processor = TransactionProcessor()
    savings = SavingsAccount("S001", "Alice", "INR", "10000")
    checking = CheckingAccount("C001", "Bob", "USD", "2000")
    high_yield = HighYieldAccount("H001", "Charlie", "EUR", "50000")

    for account in (savings, checking, high_yield):
        processor.register(account)

    print("Savings deposit balance:", processor.process("S001", "deposit", "500"))
    print("Checking withdrawal balance:", processor.process("C001", "withdraw", "250"))
    print("Savings interest credited:", processor.process("S001", "interest"))
    print("Checking fee charged:", processor.process("C001", "fees"))
    print("High-yield interest credited:", processor.process("H001", "interest"))

    for account_id in ("S001", "C001", "H001"):
        statement = processor.get_account(account_id).statement()
        print(f"{statement['account_id']} | {statement['currency']} "
              f"{statement['balance']} | transactions={len(statement['transactions'])}")
