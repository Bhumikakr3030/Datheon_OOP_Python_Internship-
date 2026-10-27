"""Order orchestration and Observer event publication."""
from threading import RLock
from uuid import uuid4
from datetime import datetime, timezone

from .config import ConfigManager
from .models import Order, OrderEvent, OrderStatus
from .payments import PaymentFactory
from .observers import OrderObserver


_ALLOWED_TRANSITIONS = {
    OrderStatus.CREATED: {OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED},
    OrderStatus.PAYMENT_PENDING: {OrderStatus.PAID, OrderStatus.PAYMENT_FAILED, OrderStatus.CANCELLED},
    OrderStatus.PAYMENT_FAILED: {OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


class OrderService:
    def __init__(self, payment_factory: PaymentFactory, config: ConfigManager = None):
        if not isinstance(payment_factory, PaymentFactory):
            raise TypeError("payment_factory must be a PaymentFactory.")
        self.__payment_factory = payment_factory
        self.__config = config or ConfigManager()
        self.__observers = []
        self.__orders = {}
        self.__lock = RLock()

    def subscribe(self, observer: OrderObserver):
        if not isinstance(observer, OrderObserver):
            raise TypeError("Observer must implement OrderObserver.")
        with self.__lock:
            if observer in self.__observers:
                return
            self.__observers.append(observer)

    def unsubscribe(self, observer: OrderObserver):
        with self.__lock:
            if observer in self.__observers:
                self.__observers.remove(observer)

    def _publish(self, event: OrderEvent):
        # Copy the list so subscribe/unsubscribe during callbacks won't mutate iteration.
        with self.__lock:
            observers = tuple(self.__observers)
        errors = []
        for observer in observers:
            try:
                observer.on_order_event(event)
            except Exception as exc:
                # One listener failure should not block other listeners.
                errors.append(f"{type(observer).__name__}: {exc}")
        if errors:
            # In production, send these to a durable retry/dead-letter mechanism.
            self.__config.set("last_observer_errors", tuple(errors))

    def _transition(self, order: Order, new_status: OrderStatus, detail: str):
        with self.__lock:
            allowed = _ALLOWED_TRANSITIONS[order.status]
            if new_status not in allowed:
                raise ValueError(f"Invalid order transition: {order.status} -> {new_status}")
            previous = order.status
            order.status = new_status
            event = OrderEvent(
                event_id=str(uuid4()),
                order_id=order.order_id,
                previous_status=previous,
                new_status=new_status,
                occurred_at_utc=datetime.now(timezone.utc).isoformat(),
                detail=detail,
            )
            self.__orders[order.order_id] = order
        self._publish(event)
        return event

    def create_order(self, customer_id, amount, currency="INR") -> Order:
        order = Order(customer_id=customer_id, amount=amount, currency=currency)
        with self.__lock:
            self.__orders[order.order_id] = order
        self._publish(OrderEvent(
            event_id=str(uuid4()),
            order_id=order.order_id,
            previous_status=None,
            new_status=OrderStatus.CREATED,
            occurred_at_utc=datetime.now(timezone.utc).isoformat(),
            detail="Order created",
        ))
        return order

    def place_order(self, order_id: str, payment_method: str):
        with self.__lock:
            if order_id not in self.__orders:
                raise ValueError("Order not found.")
            order = self.__orders[order_id]

        self._transition(order, OrderStatus.PAYMENT_PENDING, "Payment initiated")
        handler = self.__payment_factory.create(payment_method)
        result = handler.pay(order)

        if result.success:
            self._transition(order, OrderStatus.PAID, result.message)
        else:
            self._transition(order, OrderStatus.PAYMENT_FAILED, result.message)
        return result

    def update_status(self, order_id: str, new_status: OrderStatus, detail="Status updated"):
        if not isinstance(new_status, OrderStatus):
            raise TypeError("new_status must be an OrderStatus value.")
        with self.__lock:
            if order_id not in self.__orders:
                raise ValueError("Order not found.")
            order = self.__orders[order_id]
        return self._transition(order, new_status, detail)

    def get_order(self, order_id: str) -> Order:
        with self.__lock:
            if order_id not in self.__orders:
                raise ValueError("Order not found.")
            return self.__orders[order_id]
