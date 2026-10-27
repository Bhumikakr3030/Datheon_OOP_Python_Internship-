import unittest

from notification_engine import (
    Notification, NotificationService, PlainTextFormatter,
    InMemoryNotificationLogger, EmailChannel, SMSChannel,
    SlackChannel, WhatsAppChannel, NotificationChannel, DeliveryResult,
)


class TestNotificationEngine(unittest.TestCase):
    def setUp(self):
        self.formatter = PlainTextFormatter()
        self.logger = InMemoryNotificationLogger()
        self.service = NotificationService(
            [
                EmailChannel(self.formatter),
                SMSChannel(self.formatter),
                SlackChannel(self.formatter),
                WhatsAppChannel(self.formatter),
            ],
            formatter=self.formatter,
            logger=self.logger,
        )
        self.notification = Notification(
            recipient="user@example.com",
            subject="Test",
            message="Hello from tests",
        )

    def test_all_four_channels_are_registered(self):
        self.assertEqual(
            self.service.available_channels,
            ("email", "slack", "sms", "whatsapp"),
        )

    def test_send_to_each_channel(self):
        results = self.service.send_to_many(
            ["email", "sms", "slack", "whatsapp"], self.notification
        )
        self.assertEqual(len(results), 4)
        self.assertTrue(all(result.success for result in results))
        self.assertEqual(len(self.logger.results), 4)

    def test_invalid_notification_rejected(self):
        with self.assertRaises(ValueError):
            Notification("", "Subject", "Message")
        with self.assertRaises(ValueError):
            Notification("person@example.com", " ", "Message")

    def test_unknown_channel_rejected(self):
        with self.assertRaises(ValueError):
            self.service.send("pager", self.notification)

    def test_duplicate_channel_rejected(self):
        with self.assertRaises(ValueError):
            NotificationService([EmailChannel(self.formatter), EmailChannel(self.formatter)])

    def test_result_has_notification_id(self):
        result = self.service.send("email", self.notification)
        self.assertEqual(result.notification_id, self.notification.notification_id)

    def test_open_closed_principle_new_channel_can_be_injected(self):
        class PushChannel(NotificationChannel):
            @property
            def name(self):
                return "push"

            def send(self, notification):
                return DeliveryResult.create(
                    self.name, notification.recipient, notification.notification_id,
                    True, "Push simulated"
                )

        service = NotificationService([PushChannel()])
        result = service.send("push", self.notification)
        self.assertTrue(result.success)
        self.assertEqual(service.available_channels, ("push",))

    def test_bad_service_input_rejected(self):
        with self.assertRaises(TypeError):
            self.service.send("email", "not a notification")


if __name__ == "__main__":
    unittest.main()
