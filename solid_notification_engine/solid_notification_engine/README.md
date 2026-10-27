# SOLID Notification Dispatch Engine

A Python portfolio project implementing an extensible notification library for Email, SMS, Slack, and WhatsApp.

## Features

- `NotificationChannel` abstraction for pluggable channels.
- Four sample channel adapters: `EmailChannel`, `SMSChannel`, `SlackChannel`, and `WhatsAppChannel`.
- Dependency Injection: channels, formatter, and logger are provided to `NotificationService`.
- Open/Closed Principle: add a channel by implementing `NotificationChannel` and injecting it; the service does not need edits.
- Separate `Notification` and `DeliveryResult` models.
- Input validation, immutable data models, and audit-result logging.
- Standard-library unit tests.
- **Demo only:** channel implementations simulate success; they do not send real email, SMS, Slack, or WhatsApp messages.

## Requirements

Python 3.10 or newer. No third-party dependencies.

## Run the demo

```bash
python main.py
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

## The five SOLID principles

### S — Single Responsibility Principle
- `Notification` represents message data.
- Each channel adapter handles one delivery channel.
- `NotificationService` coordinates dispatch.
- `PlainTextFormatter` formats content.
- `InMemoryNotificationLogger` stores delivery results.

### O — Open/Closed Principle
`NotificationService` works with the `NotificationChannel` abstraction. A new provider can be added by implementing that interface and injecting the new object, without changing the service.

### L — Liskov Substitution Principle
Every channel implements the same `name` and `send(notification)` contract and can be substituted wherever a `NotificationChannel` is expected.

### I — Interface Segregation Principle
The channel interface contains only channel identity and sending behavior. Formatting and logging are separate protocols, so channel implementations are not forced to implement unrelated methods.

### D — Dependency Inversion Principle
The service depends on abstractions (`NotificationChannel`, `NotificationFormatter`, and `NotificationLogger`) and receives implementations through its constructor. It does not instantiate concrete provider adapters internally.

## Adding a channel

1. Create a class that implements `NotificationChannel`.
2. Implement `name` and `send(notification)`.
3. Inject an instance into `NotificationService`.

No changes to the core service are needed.

## Connecting real providers

Replace the simulated methods in `channels.py` with provider SDK/API calls. Keep credentials in environment variables or a secret manager, handle provider errors and retries, and never commit credentials to GitHub. Configure sender identities and opt-in/consent requirements before sending real messages.

## Production considerations

For production use, add retry/backoff policies, timeouts, rate limiting, provider-specific recipient validation, idempotency, durable audit storage, delivery status callbacks, secrets management, privacy controls, and monitoring. Avoid logging message bodies or sensitive recipient details unnecessarily.
