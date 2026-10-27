from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from uuid import uuid4


class OrderStatus(str, Enum):
    CREATED = "created"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    PAYMENT_FAILED = "payment_failed"


def parse_amount(value) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Use string, integer, or Decimal for monetary amounts.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid monetary amount.") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be finite and greater than zero.")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class OrderEvent:
    event_id: str
    order_id: str
    previous_status: OrderStatus | None
    new_status: OrderStatus
    occurred_at_utc: str
    detail: str


@dataclass
class Order:
    customer_id: str
    amount: Decimal
    currency: str = "INR"
    order_id: str = field(default_factory=lambda: str(uuid4()))
    status: OrderStatus = OrderStatus.CREATED
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not isinstance(self.customer_id, str) or not self.customer_id.strip():
            raise ValueError("Customer ID cannot be empty.")
        self.amount = parse_amount(self.amount)
        if not isinstance(self.currency, str) or len(self.currency.strip()) != 3:
            raise ValueError("Currency must be a three-letter code, e.g. INR.")
        self.currency = self.currency.strip().upper()
