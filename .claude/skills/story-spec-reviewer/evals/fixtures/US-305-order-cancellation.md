# US-305: Order Cancellation Before Shipment

**As a** customer,
**I want** to cancel an order before it ships,
**So that** I don't receive items I no longer want.

## Acceptance Criteria

- **AC1:** Given an order that has not yet shipped, when the customer views their order details, then a "Cancel Order" button is visible.
- **AC2:** Given the customer clicks "Cancel Order", when they confirm the cancellation, then the order status changes to "Cancelled" and the customer receives a cancellation confirmation email.
- **AC3:** Given an order has already shipped, when the customer views their order details, then no "Cancel Order" button is shown.
- **AC4:** Given an order is cancelled, when payment was already captured, then a refund is automatically issued to the original payment method.
