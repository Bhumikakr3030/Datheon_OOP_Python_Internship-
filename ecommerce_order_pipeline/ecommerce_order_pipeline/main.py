from order_pipeline import (
    ConfigManager, PaymentFactory, OrderService,
    LogisticsListener, InvoicingListener, EmailListener, OrderStatus,
)


def main():
    config = ConfigManager({"environment": "demo"})
    factory = PaymentFactory.default()
    service = OrderService(factory, config)

    logistics = LogisticsListener()
    invoicing = InvoicingListener()
    email = EmailListener()

    for listener in (logistics, invoicing, email):
        service.subscribe(listener)

    order = service.create_order("CUSTOMER-1001", "2499.00", "INR")
    payment = service.place_order(order.order_id, "upi")
    service.update_status(order.order_id, OrderStatus.PROCESSING, "Warehouse processing")
    service.update_status(order.order_id, OrderStatus.SHIPPED, "Handed to courier")

    print("Order:", order.order_id)
    print("Payment:", payment.provider, payment.success, payment.amount, payment.currency)
    print("Current status:", service.get_order(order.order_id).status.value)
    print("Events received - logistics:", len(logistics.events))
    print("Events received - invoicing:", len(invoicing.events))
    print("Events received - email:", len(email.events))
    print("Config:", config.snapshot())


if __name__ == "__main__":
    main()
