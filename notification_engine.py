"""
Extensible Notification Dispatch Engine  (SOLID showcase)

S - Single Responsibility : Notification/Recipient (data), channels (delivery),
                            formatters (presentation), service (orchestration),
                            loggers (audit), transports (I/O) are separate.
O - Open/Closed           : add a channel by writing a new class and passing it
                            in. NotificationService is never edited.
L - Liskov Substitution   : every Channel honours one contract - returns a
                            DeliveryResult or raises DeliveryError only - so
                            the service treats all channels identically.
I - Interface Segregation : small, focused interfaces (Channel, Transport,
                            MessageFormatter, DeliveryLogger).
D - Dependency Inversion  : the service depends on Channel/DeliveryLogger
                            abstractions, injected via constructor; channels
                            depend on Transport abstractions, also injected.

Run:  python notification_engine.py
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Protocol


# ==========================================================================
# Domain models (S: pure data, no behaviour about delivery)
# ==========================================================================
class Priority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


@dataclass(frozen=True)
class Notification:
    subject: str
    body: str
    priority: Priority = Priority.NORMAL

    def __post_init__(self):
        if not self.body.strip():
            raise ValueError("notification body must not be empty")


@dataclass(frozen=True)
class Recipient:
    name: str
    # channel-name -> address, e.g. {"email": "a@b.com", "sms": "+919800000000"}
    addresses: Dict[str, str] = field(default_factory=dict)

    def address_for(self, channel: str) -> Optional[str]:
        return self.addresses.get(channel)


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    recipient: str
    success: bool
    detail: str = ""


class DeliveryError(Exception):
    """The ONLY exception a Channel is allowed to raise (LSP contract)."""


# ==========================================================================
# Abstractions (I: each is small and single-purpose)
# ==========================================================================
class Channel(ABC):
    """A delivery mechanism. Implement this to plug in a new channel."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique key, also used to look up the recipient's address."""

    @abstractmethod
    def send(self, notification: Notification, address: str) -> DeliveryResult:
        """Deliver or raise DeliveryError. Must not raise anything else."""


class Transport(Protocol):
    """Low-level I/O (SMTP server, SMS gateway, HTTP API...). Injected into
    channels so they never import a vendor SDK directly (D)."""

    def deliver(self, destination: str, payload: str) -> None: ...


class MessageFormatter(Protocol):
    def format(self, notification: Notification) -> str: ...


class DeliveryLogger(Protocol):
    def record(self, result: DeliveryResult) -> None: ...


# ==========================================================================
# Formatters (S: presentation separated from delivery)
# ==========================================================================
class PlainFormatter:
    def format(self, n: Notification) -> str:
        return f"{n.subject}\n\n{n.body}" if n.subject else n.body


class ShortFormatter:
    """For length-limited channels such as SMS."""
    def __init__(self, limit: int = 160):
        self._limit = limit

    def format(self, n: Notification) -> str:
        text = f"{n.subject}: {n.body}" if n.subject else n.body
        return text if len(text) <= self._limit else text[: self._limit - 1] + "…"


class MarkdownFormatter:
    def format(self, n: Notification) -> str:
        flag = "🚨 " if n.priority is Priority.HIGH else ""
        return f"{flag}*{n.subject}*\n{n.body}" if n.subject else n.body


# ==========================================================================
# Concrete channels (O: each is an extension, none touch the service)
# ==========================================================================
class _BaseChannel(Channel):
    """Shared template: validate -> format -> transport. Subclasses only
    declare name, formatter and address validation."""

    def __init__(self, transport: Transport, formatter: MessageFormatter):
        self._transport = transport
        self._formatter = formatter

    @abstractmethod
    def _valid(self, address: str) -> bool: ...

    def send(self, notification: Notification, address: str) -> DeliveryResult:
        if not self._valid(address):
            raise DeliveryError(f"invalid {self.name} address: {address!r}")
        try:
            self._transport.deliver(address, self._formatter.format(notification))
        except DeliveryError:
            raise
        except Exception as exc:                       # keep LSP contract
            raise DeliveryError(f"{self.name} transport failed: {exc}") from exc
        return DeliveryResult(self.name, address, True, "sent")


class EmailChannel(_BaseChannel):
    name = "email"
    def __init__(self, transport, formatter: MessageFormatter = None):
        super().__init__(transport, formatter or PlainFormatter())
    def _valid(self, a): return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", a) is not None


class SmsChannel(_BaseChannel):
    name = "sms"
    def __init__(self, transport, formatter: MessageFormatter = None):
        super().__init__(transport, formatter or ShortFormatter(160))
    def _valid(self, a): return re.fullmatch(r"\+\d{8,15}", a) is not None


class SlackChannel(_BaseChannel):
    name = "slack"
    def __init__(self, transport, formatter: MessageFormatter = None):
        super().__init__(transport, formatter or MarkdownFormatter())
    def _valid(self, a): return re.fullmatch(r"[#@][\w.-]+", a) is not None


class WhatsAppChannel(_BaseChannel):
    name = "whatsapp"
    def __init__(self, transport, formatter: MessageFormatter = None):
        super().__init__(transport, formatter or MarkdownFormatter())
    def _valid(self, a): return re.fullmatch(r"\+\d{8,15}", a) is not None


# ==========================================================================
# Loggers (S + D: auditing is its own concern, swappable)
# ==========================================================================
class InMemoryLogger:
    def __init__(self):
        self._results: List[DeliveryResult] = []

    def record(self, result: DeliveryResult) -> None:
        self._results.append(result)

    @property
    def results(self) -> tuple:
        return tuple(self._results)


class NullLogger:
    def record(self, result: DeliveryResult) -> None:
        pass


# ==========================================================================
# The service (D: depends only on abstractions; O: closed for modification)
# ==========================================================================
class NotificationService:
    def __init__(self, channels: Iterable[Channel], logger: DeliveryLogger = None,
                 max_attempts: int = 2):
        self._channels: Dict[str, Channel] = {}
        for ch in channels:
            self.register(ch)
        self._logger: DeliveryLogger = logger or NullLogger()
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._max_attempts = max_attempts

    def register(self, channel: Channel) -> None:
        if channel.name in self._channels:
            raise ValueError(f"channel {channel.name!r} already registered")
        self._channels[channel.name] = channel

    @property
    def channel_names(self) -> tuple:
        return tuple(self._channels)

    def notify(self, notification: Notification, recipient: Recipient,
               via: Optional[Iterable[str]] = None) -> List[DeliveryResult]:
        """Send over the requested channels (default: every registered channel
        the recipient has an address for). One failing channel never blocks
        the others."""
        wanted = list(via) if via is not None else [
            n for n in self._channels if recipient.address_for(n)]
        results = [self._dispatch(n, notification, recipient) for n in wanted]
        for r in results:
            self._logger.record(r)
        return results

    def broadcast(self, notification: Notification,
                  recipients: Iterable[Recipient]) -> List[DeliveryResult]:
        out: List[DeliveryResult] = []
        for r in recipients:
            out.extend(self.notify(notification, r))
        return out

    def _dispatch(self, channel_name: str, n: Notification, r: Recipient) -> DeliveryResult:
        channel = self._channels.get(channel_name)
        if channel is None:
            return DeliveryResult(channel_name, r.name, False, "channel not registered")
        address = r.address_for(channel_name)
        if not address:
            return DeliveryResult(channel_name, r.name, False, "no address on file")
        last_error = ""
        for _ in range(self._max_attempts):
            try:
                return channel.send(n, address)
            except DeliveryError as exc:
                last_error = str(exc)
        return DeliveryResult(channel_name, address, False, last_error)


# ==========================================================================
# Demo transports (stand-ins for SMTP / Twilio / Slack API / WhatsApp API)
# ==========================================================================
class ConsoleTransport:
    def __init__(self, label: str):
        self._label = label

    def deliver(self, destination: str, payload: str) -> None:
        print(f"  [{self._label:<8}] -> {destination}: {payload.replace(chr(10), ' | ')}")


class FlakyTransport:
    """Fails the first N calls, then succeeds (tests retry)."""
    def __init__(self, fail_times: int):
        self._left = fail_times
        self.calls = 0

    def deliver(self, destination: str, payload: str) -> None:
        self.calls += 1
        if self._left > 0:
            self._left -= 1
            raise ConnectionError("gateway timeout")


# ==========================================================================
# Demo + tests
# ==========================================================================
def _tests():
    # --- OCP: a brand-new channel defined OUTSIDE the library core ---------
    class PushChannel(Channel):
        name = "push"
        def __init__(self, transport): self._t = transport
        def send(self, notification, address):
            try:
                self._t.deliver(address, notification.body)
            except Exception as e:
                raise DeliveryError(str(e)) from e
            return DeliveryResult(self.name, address, True, "sent")

    log = InMemoryLogger()
    svc = NotificationService(
        [EmailChannel(ConsoleTransport("smtp")), SmsChannel(ConsoleTransport("sms-gw"))],
        logger=log)
    svc.register(PushChannel(ConsoleTransport("push")))     # no core edits
    assert svc.channel_names == ("email", "sms", "push")

    bob = Recipient("Bob", {"email": "bob@example.com", "sms": "+919800000001",
                            "push": "device-42"})
    res = svc.notify(Notification("Hi", "Hello Bob"), bob)
    assert all(r.success for r in res) and len(res) == 3

    # --- validation + failure isolation -----------------------------------
    bad = Recipient("Eve", {"email": "not-an-email", "sms": "+919800000002"})
    res = svc.notify(Notification("Hi", "x"), bad)
    by = {r.channel: r for r in res}
    assert not by["email"].success and by["sms"].success

    # --- missing address / unknown channel --------------------------------
    r = svc.notify(Notification("Hi", "x"), bob, via=["slack", "whatsapp"])
    assert [x.detail for x in r] == ["channel not registered"] * 2
    r = svc.notify(Notification("Hi", "x"), Recipient("Zed", {}), via=["email"])
    assert r[0].detail == "no address on file"

    # --- retry via injected flaky transport (DIP) --------------------------
    flaky = FlakyTransport(fail_times=1)
    s2 = NotificationService([SlackChannel(flaky)], max_attempts=2)
    r = s2.notify(Notification("Deploy", "done"), Recipient("Ops", {"slack": "#ops"}))
    assert r[0].success and flaky.calls == 2
    flaky3 = FlakyTransport(fail_times=5)
    s3 = NotificationService([SlackChannel(flaky3)], max_attempts=3)
    r = s3.notify(Notification("Deploy", "done"), Recipient("Ops", {"slack": "#ops"}))
    assert not r[0].success and flaky3.calls == 3

    # --- duplicate registration / empty body -------------------------------
    try:
        svc.register(EmailChannel(ConsoleTransport("x"))); raise AssertionError
    except ValueError:
        pass
    try:
        Notification("s", "  "); raise AssertionError
    except ValueError:
        pass

    # --- SMS truncation ----------------------------------------------------
    assert len(ShortFormatter(20).format(Notification("S", "x" * 100))) == 20
    assert len(log.results) == 3 + 2 + 2 + 1
    print("All self-tests passed.\n")


def _demo():
    logger = InMemoryLogger()
    service = NotificationService(
        channels=[
            EmailChannel(ConsoleTransport("smtp")),
            SmsChannel(ConsoleTransport("sms-gw")),
            SlackChannel(ConsoleTransport("slack")),
            WhatsAppChannel(ConsoleTransport("wa-api")),
        ],
        logger=logger,
    )
    asha = Recipient("Asha", {"email": "asha@example.com", "sms": "+919812345678",
                              "slack": "@asha", "whatsapp": "+919812345678"})
    ravi = Recipient("Ravi", {"email": "ravi@example", "sms": "+919800000009"})  # bad email

    alert = Notification("Server down", "Prod API latency > 5s for 10 min.", Priority.HIGH)
    print("=== Broadcast ===")
    service.broadcast(alert, [asha, ravi])

    print("\n=== Delivery report ===")
    for r in logger.results:
        mark = "OK  " if r.success else "FAIL"
        print(f"{mark} {r.channel:<9} {r.recipient:<18} {r.detail}")


if __name__ == "__main__":
    _tests()
    _demo()
