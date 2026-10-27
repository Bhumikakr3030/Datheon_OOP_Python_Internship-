import unittest
from decimal import Decimal

from order_pipeline import (
    ConfigManager, PaymentFactory, OrderService, OrderStatus,
    LogisticsListener, InvoicingListener, EmailListener, PaymentHandler,
)


class OrderPipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager({"test_mode": True})
        self.factory = PaymentFactory.default()
        self.service = OrderService(self.factory, self.config)
        self.logistics = LogisticsListener()
        self.invoicing = InvoicingListener()
        self.email = EmailListener()
        for listener in (self.logistics, self.invoicing, self.email):
            self.service.subscribe(listener)

    def test_singleton_config(self):
        self.assertIs(ConfigManager(), ConfigManager())
        ConfigManager().set("unit_test_key", "value")
        self.assertEqual(self.config.get("unit_test_key"), "value")

    def test_factory_creates_all_payment_handlers(self):
        for method in ("credit_card", "upi", "paypal", "crypto"):
            handler = self.factory.create(method)
            self.assertIsInstance(handler, PaymentHandler)

    def test_order_payment_and_observers(self):
        order = self.service.create_order("C-1", "120.00", "INR")
        result = self.service.place_order(order.order_id, "upi")
        self.assertTrue(result.success)
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(len(self.logistics.events), 3)
        self.assertEqual(len(self.invoicing.events), 3)
        self.assertEqual(len(self.email.events), 3)

    def test_status_event_broadcast(self):
        order = self.service.create_order("C-2", "10", "USD")
        self.service.place_order(order.order_id, "paypal")
        self.service.update_status(order.order_id, OrderStatus.PROCESSING)
        self.assertEqual(self.logistics.events[-1].new_status, OrderStatus.PROCESSING)

    def test_unsubscribe(self):
        self.service.unsubscribe(self.email)
        order = self.service.create_order("C-3", "10", "INR")
        self.assertEqual(len(self.email.events), 0)
        self.assertEqual(len(self.logistics.events), 1)

    def test_unknown_payment_method(self):
        order = self.service.create_order("C-4", "10", "INR")
        with self.assertRaises(ValueError):
            self.service.place_order(order.order_id, "cash")

    def test_invalid_amount_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_order("C-5", "-2", "INR")

    def test_invalid_order_transition_rejected(self):
        order = self.service.create_order("C-6", "10", "INR")
        with self.assertRaises(ValueError):
            self.service.update_status(order.order_id, OrderStatus.DELIVERED)

    def test_factory_open_for_extension(self):
        from order_pipeline.payments import PaymentResult
        class GiftCardPayment(PaymentHandler):
            @property
            def provider_name(self):
                return "gift_card"
            def pay(self, order):
                return PaymentResult("p1", self.provider_name, True,
                                     order.amount, order.currency, "Demo gift card")
        self.factory.register("gift_card", GiftCardPayment)
        self.assertEqual(self.factory.create("gift_card").provider_name, "gift_card")


if __name__ == "__main__":
    unittest.main()
