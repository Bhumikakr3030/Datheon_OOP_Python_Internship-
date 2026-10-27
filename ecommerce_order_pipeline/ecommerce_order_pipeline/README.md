# E-Commerce Order Pipeline: Design Patterns

A Python educational project demonstrating Singleton, Factory, and Observer patterns in an order workflow.

## Features

- Thread-safe, process-local `ConfigManager` Singleton.
- Registry-based `PaymentFactory` for Credit Card, UPI, PayPal, and Crypto handlers.
- `PaymentHandler` abstraction with polymorphic `pay(order)` methods.
- Observer pattern broadcasts order status events to logistics, invoicing, and email listeners.
- Order state transition validation and immutable event records.
- Decimal-based monetary amounts, basic input validation, UTC timestamps, and unit tests.
- Observer failures do not prevent other listeners from receiving the event.

## Requirements

Python 3.10 or newer. No third-party packages are required.

## Run demo

```bash
python main.py
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Patterns demonstrated

### Singleton
`ConfigManager()` returns the same instance within one Python process. It is protected against concurrent initialization. This does not make it a cross-process or distributed singleton.

### Factory
`PaymentFactory` maps payment method names to builders. Add a payment handler by implementing `PaymentHandler` and registering its builder; the order service does not need changes.

### Observer
`OrderService` publishes immutable `OrderEvent` objects to subscribed observers. The logistics, invoicing, and email listeners receive events independently. Listeners can subscribe or unsubscribe at runtime.

## Production readiness caveat

Payment adapters currently simulate success. No actual card, UPI, PayPal, or cryptocurrency payment is executed. Real payment integrations must use provider SDKs, verified webhooks, secure secret storage, idempotency keys, timeout/retry policies, reconciliation, and appropriate compliance controls.

This demo keeps orders in memory. Production deployments need durable storage, database transactions, outbox/event delivery, authorization, audit trails, inventory reservation, and idempotent order/payment state transitions. The Singleton is process-local only and must not be treated as a distributed lock or shared configuration service.
