"""
Multi-Currency Banking & Ledger Engine
Demonstrates the 4 pillars of OOP:
  * Encapsulation  - private attributes, validation, read-only properties
  * Abstraction    - abstract Account and Transaction base classes
  * Inheritance    - Savings / Checking / HighYield extend Account
  * Polymorphism   - accounts and transactions are used via their base types
Run:  python banking_engine.py
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from itertools import count
from typing import Dict, List, Optional


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------
class BankingError(Exception):
    """Base class for all domain errors."""


class ValidationError(BankingError):
    pass


class InsufficientFundsError(BankingError):
    pass


class AccountFrozenError(BankingError):
    pass


class UnknownAccountError(BankingError):
    pass


# --------------------------------------------------------------------------
# Currency & Money (immutable value objects -> safe encapsulation)
# --------------------------------------------------------------------------
class Currency(Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    JPY = "JPY"


_CENT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Banker's rounding to 2 decimal places."""
    return value.quantize(_CENT, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency

    def __post_init__(self):
        if not isinstance(self.currency, Currency):
            raise ValidationError("currency must be a Currency")
        try:
            amt = _q(Decimal(str(self.amount)))
        except Exception:
            raise ValidationError(f"invalid amount: {self.amount!r}")
        if not amt.is_finite():
            raise ValidationError("amount must be finite")
        object.__setattr__(self, "amount", amt)

    def _check(self, other: Money):
        if self.currency != other.currency:
            raise ValidationError(f"currency mismatch {self.currency.name} vs {other.currency.name}")

    def __add__(self, o: Money) -> Money:
        self._check(o)
        return Money(self.amount + o.amount, self.currency)

    def __sub__(self, o: Money) -> Money:
        self._check(o)
        return Money(self.amount - o.amount, self.currency)

    def __lt__(self, o: Money) -> bool:
        self._check(o)
        return self.amount < o.amount

    def __str__(self) -> str:
        return f"{self.amount:,.2f} {self.currency.name}"


class ExchangeRates:
    """Rates are stored relative to USD (1 USD = rate units)."""

    def __init__(self, usd_rates: Dict[Currency, Decimal]):
        self.__rates = {c: Decimal(str(r)) for c, r in usd_rates.items()}
        self.__rates[Currency.USD] = Decimal("1")
        if any(r <= 0 for r in self.__rates.values()):
            raise ValidationError("rates must be positive")

    def convert(self, money: Money, target: Currency) -> Money:
        if money.currency == target:
            return money
        try:
            usd = money.amount / self.__rates[money.currency]
            return Money(usd * self.__rates[target], target)
        except KeyError as e:
            raise ValidationError(f"no rate for {e.args[0]}")


# --------------------------------------------------------------------------
# Ledger entries (append-only audit trail)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LedgerEntry:
    entry_id: int
    timestamp: datetime
    account_id: str
    kind: str
    amount: Money
    balance_after: Money
    memo: str = ""


# --------------------------------------------------------------------------
# Abstract Account
# --------------------------------------------------------------------------
class Account(ABC):
    _ids = count(1000)

    def __init__(self, owner: str, currency: Currency, opening: Decimal = Decimal("0")):
        if not isinstance(owner, str) or not owner.strip():
            raise ValidationError("owner name required")
        self.__id = f"{self.__class__.__name__[:3].upper()}-{next(Account._ids)}"
        self.__owner = owner.strip()
        self.__currency = currency
        self.__balance = Money(opening, currency)
        self.__frozen = False
        self.__history: List[LedgerEntry] = []
        if self.__balance.amount < 0:
            raise ValidationError("opening balance cannot be negative")
        if opening:
            self._record("OPEN", self.__balance, "opening balance")

    # ---- read-only public view -------------------------------------------
    @property
    def account_id(self) -> str: return self.__id
    @property
    def owner(self) -> str: return self.__owner
    @property
    def currency(self) -> Currency: return self.__currency
    @property
    def balance(self) -> Money: return self.__balance
    @property
    def frozen(self) -> bool: return self.__frozen
    @property
    def history(self) -> tuple: return tuple(self.__history)   # immutable copy

    def freeze(self): self.__frozen = True
    def unfreeze(self): self.__frozen = False

    # ---- protected mutation (only subclasses & the engine path) ----------
    def _record(self, kind: str, amount: Money, memo: str = ""):
        self.__history.append(LedgerEntry(
            len(self.__history) + 1, datetime.now(timezone.utc),
            self.__id, kind, amount, self.__balance, memo))

    def _credit(self, amount: Money, kind: str = "CREDIT", memo: str = ""):
        self._guard(amount)
        self.__balance = self.__balance + amount
        self._record(kind, amount, memo)

    def _debit(self, amount: Money, kind: str = "DEBIT", memo: str = ""):
        self._guard(amount)
        if self.__balance.amount - amount.amount < self.min_balance_floor():
            raise InsufficientFundsError(
                f"{self.__id}: {amount} exceeds available {self.available()}")
        self.__balance = self.__balance - amount
        self._record(kind, amount, memo)

    def _guard(self, amount: Money):
        if self.__frozen:
            raise AccountFrozenError(f"{self.__id} is frozen")
        if amount.currency != self.__currency:
            raise ValidationError("amount currency must match account currency")
        if amount.amount <= 0:
            raise ValidationError("amount must be positive")

    # ---- public operations ------------------------------------------------
    def deposit(self, amount: Money, memo: str = ""):
        self._credit(amount, "DEPOSIT", memo)

    def withdraw(self, amount: Money, memo: str = ""):
        self._debit(amount, "WITHDRAW", memo)

    def available(self) -> Money:
        return Money(self.__balance.amount - self.min_balance_floor(), self.__currency)

    def min_balance_floor(self) -> Decimal:
        """Lowest balance allowed; overridden by subclasses (e.g. overdraft)."""
        return Decimal("0")

    # ---- abstract behaviour ----------------------------------------------
    @abstractmethod
    def accrue_interest(self) -> Money:
        """Apply one period (month) of interest. Returns amount credited."""

    @abstractmethod
    def deduct_fees(self) -> Money:
        """Apply one period (month) of fees. Returns amount charged."""

    def month_end(self) -> None:
        """Template method: same workflow, subclass-specific steps."""
        self.accrue_interest()
        self.deduct_fees()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.__id} {self.__owner} {self.__balance}>"


# --------------------------------------------------------------------------
# Concrete accounts
# --------------------------------------------------------------------------
class SavingsAccount(Account):
    ANNUAL_RATE = Decimal("0.03")
    MAX_FREE_WITHDRAWALS = 3
    EXTRA_WITHDRAWAL_FEE = Decimal("2.00")

    def __init__(self, owner, currency, opening=Decimal("0")):
        super().__init__(owner, currency, opening)
        self.__withdrawals_this_month = 0

    def withdraw(self, amount, memo=""):
        super().withdraw(amount, memo)
        self.__withdrawals_this_month += 1

    def accrue_interest(self) -> Money:
        interest = Money(self.balance.amount * self.ANNUAL_RATE / 12, self.currency)
        if interest.amount > 0:
            self._credit(interest, "INTEREST", f"{self.ANNUAL_RATE:.2%} APR")
        return interest

    def deduct_fees(self) -> Money:
        extra = max(0, self.__withdrawals_this_month - self.MAX_FREE_WITHDRAWALS)
        fee = Money(self.EXTRA_WITHDRAWAL_FEE * extra, self.currency)
        self.__withdrawals_this_month = 0
        if fee.amount > 0:
            self._debit(fee, "FEE", f"{extra} extra withdrawals")
        return fee


class CheckingAccount(Account):
    MONTHLY_FEE = Decimal("5.00")
    FEE_WAIVER_BALANCE = Decimal("1500")
    OVERDRAFT_LIMIT = Decimal("200")
    OVERDRAFT_FEE = Decimal("25.00")
    ANNUAL_RATE = Decimal("0.001")

    def min_balance_floor(self) -> Decimal:
        return -self.OVERDRAFT_LIMIT

    def accrue_interest(self) -> Money:
        if self.balance.amount <= 0:
            return Money(0, self.currency)
        interest = Money(self.balance.amount * self.ANNUAL_RATE / 12, self.currency)
        if interest.amount > 0:
            self._credit(interest, "INTEREST")
        return interest

    def deduct_fees(self) -> Money:
        fee = Decimal("0")
        if self.balance.amount < 0:
            fee += self.OVERDRAFT_FEE
        if self.balance.amount < self.FEE_WAIVER_BALANCE:
            fee += self.MONTHLY_FEE
        charge = Money(fee, self.currency)
        if charge.amount > 0:
            # fees may push into overdraft limit; bypass floor check deliberately
            self._force_fee(charge)
        return charge

    def _force_fee(self, charge: Money):
        floor = self.min_balance_floor()
        try:
            self._debit(charge, "FEE")
        except InsufficientFundsError:
            self._debit(Money(max(Decimal("0.01"), self.balance.amount - floor), self.currency)
                        if self.balance.amount > floor else Money(Decimal("0.01"), self.currency),
                        "FEE", "partial (limit reached)") if self.balance.amount > floor else None


class HighYieldAccount(Account):
    MIN_BALANCE = Decimal("5000")
    TIERS = [(Decimal("25000"), Decimal("0.045")), (Decimal("Infinity"), Decimal("0.055"))]
    BELOW_MIN_FEE = Decimal("15.00")

    def min_balance_floor(self) -> Decimal:
        return Decimal("0")

    def _rate(self) -> Decimal:
        bal = self.balance.amount
        for ceiling, rate in self.TIERS:
            if bal <= ceiling:
                return rate
        return self.TIERS[-1][1]

    def accrue_interest(self) -> Money:
        interest = Money(self.balance.amount * self._rate() / 12, self.currency)
        if interest.amount > 0:
            self._credit(interest, "INTEREST", f"{self._rate():.2%} tiered APR")
        return interest

    def deduct_fees(self) -> Money:
        fee = Money(self.BELOW_MIN_FEE if self.balance.amount < self.MIN_BALANCE else 0, self.currency)
        if fee.amount > 0:
            self._debit(fee, "FEE", "below minimum balance")
        return fee


# --------------------------------------------------------------------------
# Polymorphic transactions
# --------------------------------------------------------------------------
class Transaction(ABC):
    @abstractmethod
    def execute(self, bank: "Bank") -> str: ...


@dataclass
class Deposit(Transaction):
    account_id: str
    amount: Money

    def execute(self, bank):
        acct = bank.get(self.account_id)
        acct.deposit(bank.rates.convert(self.amount, acct.currency), "deposit")
        return f"Deposited {self.amount} -> {acct.account_id}"


@dataclass
class Withdrawal(Transaction):
    account_id: str
    amount: Money

    def execute(self, bank):
        acct = bank.get(self.account_id)
        acct.withdraw(bank.rates.convert(self.amount, acct.currency), "withdrawal")
        return f"Withdrew {self.amount} <- {acct.account_id}"


@dataclass
class Transfer(Transaction):
    source_id: str
    dest_id: str
    amount: Money   # expressed in the source account's currency

    def execute(self, bank):
        if self.source_id == self.dest_id:
            raise ValidationError("cannot transfer to the same account")
        src, dst = bank.get(self.source_id), bank.get(self.dest_id)
        out = bank.rates.convert(self.amount, src.currency)
        incoming = bank.rates.convert(out, dst.currency)
        # atomic: if credit fails, roll back debit
        src._debit(out, "TRANSFER_OUT", f"to {dst.account_id}")
        try:
            dst._credit(incoming, "TRANSFER_IN", f"from {src.account_id}")
        except BankingError:
            src._credit(out, "REVERSAL", "transfer failed")
            raise
        return f"Transferred {out} {src.account_id} -> {dst.account_id} ({incoming})"


class MonthEnd(Transaction):
    """Runs polymorphic interest + fees on every account."""
    def execute(self, bank):
        for acct in bank.accounts():
            acct.month_end()
        return f"Month-end processed for {len(bank.accounts())} accounts"


# --------------------------------------------------------------------------
# Bank (engine / dispatcher)
# --------------------------------------------------------------------------
class Bank:
    def __init__(self, rates: ExchangeRates):
        self.__accounts: Dict[str, Account] = {}
        self.__log: List[str] = []
        self.rates = rates

    def open(self, account: Account) -> Account:
        self.__accounts[account.account_id] = account
        return account

    def get(self, account_id: str) -> Account:
        try:
            return self.__accounts[account_id]
        except KeyError:
            raise UnknownAccountError(account_id)

    def accounts(self) -> List[Account]:
        return list(self.__accounts.values())

    def process(self, tx: Transaction) -> Optional[str]:
        """Polymorphic dispatch: engine never inspects the concrete type."""
        try:
            msg = tx.execute(self)
            self.__log.append(f"OK    {msg}")
        except BankingError as e:
            msg = None
            self.__log.append(f"FAIL  {type(tx).__name__}: {e}")
        return msg

    @property
    def log(self) -> tuple:
        return tuple(self.__log)

    def total_in(self, currency: Currency) -> Money:
        total = Money(0, currency)
        for a in self.__accounts.values():
            total = total + self.rates.convert(a.balance, currency)
        return total


# --------------------------------------------------------------------------
# Demo + self-tests
# --------------------------------------------------------------------------
def _demo():
    rates = ExchangeRates({Currency.EUR: "0.92", Currency.GBP: "0.79",
                           Currency.INR: "83.20", Currency.JPY: "150"})
    bank = Bank(rates)
    sav = bank.open(SavingsAccount("Asha", Currency.USD, Decimal("10000")))
    chk = bank.open(CheckingAccount("Asha", Currency.EUR, Decimal("800")))
    hy = bank.open(HighYieldAccount("Ravi", Currency.GBP, Decimal("30000")))

    txs = [
        Deposit(sav.account_id, Money(500, Currency.USD)),
        Withdrawal(chk.account_id, Money(900, Currency.EUR)),        # uses overdraft
        Withdrawal(chk.account_id, Money(500, Currency.EUR)),        # blocked
        Transfer(sav.account_id, hy.account_id, Money(1000, Currency.USD)),  # cross-currency
        Transfer(sav.account_id, sav.account_id, Money(1, Currency.USD)),    # invalid
        MonthEnd(),
    ]
    for t in txs:
        bank.process(t)

    print("=== Processing log ===")
    print("\n".join(bank.log))
    print("\n=== Balances ===")
    for a in bank.accounts():
        print(f"{a.account_id:<10} {a.owner:<5} {a.balance}")
    print(f"\nBank total (USD): {bank.total_in(Currency.USD)}")


def _tests():
    r = ExchangeRates({Currency.EUR: "0.9"})
    # abstraction
    try:
        Account("x", Currency.USD)  # type: ignore
        raise AssertionError("Account should be abstract")
    except TypeError:
        pass
    # encapsulation
    s = SavingsAccount("T", Currency.USD, Decimal("100"))
    try:
        s.balance = Money(1, Currency.USD)  # type: ignore
        raise AssertionError("balance must be read-only")
    except AttributeError:
        pass
    assert not hasattr(s, "balance_") and "_Account__balance" in vars(s)
    # validation
    for bad in (Money(-5, Currency.USD),):
        try:
            s.deposit(bad); raise AssertionError
        except ValidationError:
            pass
    try:
        s.deposit(Money(5, Currency.EUR)); raise AssertionError
    except ValidationError:
        pass
    # insufficient funds on savings, overdraft on checking
    try:
        s.withdraw(Money(101, Currency.USD)); raise AssertionError
    except InsufficientFundsError:
        pass
    c = CheckingAccount("T", Currency.USD, Decimal("10"))
    c.withdraw(Money(100, Currency.USD)); assert c.balance.amount == Decimal("-90.00")
    # polymorphism: interest differs per subclass
    h = HighYieldAccount("T", Currency.USD, Decimal("12000"))
    assert h.accrue_interest().amount == Decimal("45.00")      # 4.5%/12 on 12k
    # transfer atomicity
    bank = Bank(r)
    a = bank.open(SavingsAccount("A", Currency.USD, Decimal("100")))
    b = bank.open(SavingsAccount("B", Currency.EUR, Decimal("0")))
    b.freeze()
    bank.process(Transfer(a.account_id, b.account_id, Money(50, Currency.USD)))
    assert a.balance.amount == Decimal("100.00"), "rollback failed"
    b.unfreeze()
    bank.process(Transfer(a.account_id, b.account_id, Money(50, Currency.USD)))
    assert b.balance.amount == Decimal("45.00")
    print("All self-tests passed.\n")


if __name__ == "__main__":
    _tests()
    _demo()
