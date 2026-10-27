from notification_engine import (
    EmailChannel, SMSChannel, SlackChannel, WhatsAppChannel,
    InMemoryNotificationLogger, Notification, NotificationService,
    PlainTextFormatter,
)


def main():
    formatter = PlainTextFormatter()
    logger = InMemoryNotificationLogger()

    # Dependency Injection: channel implementations, formatter, and logger
    # are passed into the service from outside.
    service = NotificationService(
        channels=[
            EmailChannel(formatter),
            SMSChannel(formatter),
            SlackChannel(formatter),
            WhatsAppChannel(formatter),
        ],
        formatter=formatter,
        logger=logger,
    )

    notification = Notification(
        recipient="demo@example.com",
        subject="Internship project update",
        message="Your project build is ready for review.",
    )

    for result in service.send_to_many(
        ["email", "sms", "slack", "whatsapp"], notification
    ):
        print(
            f"{result.channel}: success={result.success}; "
            f"recipient={result.recipient}; detail={result.detail}"
        )

    print(f"Audit records: {len(logger.results)}")


if __name__ == "__main__":
    main()
