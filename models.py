from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class Notification:
    recipient: str
    subject: str
    message: str
    notification_id: str = ""

    def __post_init__(self):
        if not isinstance(self.recipient, str) or not self.recipient.strip():
            raise ValueError("Recipient cannot be empty.")
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("Subject cannot be empty.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Message cannot be empty.")
        if not self.notification_id:
            object.__setattr__(self, "notification_id", str(uuid4()))


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    recipient: str
    notification_id: str
    success: bool
    detail: str
    timestamp_utc: str

    @classmethod
    def create(cls, channel, recipient, notification_id, success, detail):
        return cls(
            channel=channel,
            recipient=recipient,
            notification_id=notification_id,
            success=success,
            detail=detail,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
        )
