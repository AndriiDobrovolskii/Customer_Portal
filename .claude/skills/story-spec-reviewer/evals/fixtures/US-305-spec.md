# Specification: Order Cancellation Before Shipment

**Source:** docs/backlog/US-305.md
**Story ID:** US-305
**Generated:** 2026-07-03
**Status:** Draft

## Summary

This spec covers cancelling an unshipped order, including the resulting status change, notification, refund, and partial cancellation of individual line items.

## Functional Requirements

### FR-1: Show cancel control on unshipped orders

Display a "Cancel Order" button on the order details view when the order has not yet shipped.

**Derived from:** AC1

### FR-2: Confirm and process cancellation

When the customer confirms cancellation, set the order status to "Cancelled" and send a cancellation confirmation email to the customer.

**Derived from:** AC2

### FR-3: Hide cancel control on shipped orders

Do not display the "Cancel Order" button on the order details view once the order has shipped.

**Derived from:** AC3

### FR-4: Automatic refund on cancellation

When a cancelled order had payment already captured, automatically issue a refund to the original payment method.

**Derived from:** AC4

### FR-5: Partial cancellation of line items

Allow the customer to cancel individual line items within an order rather than the whole order, with a partial refund issued only for the cancelled items. The order remains active for any remaining, non-cancelled items.

**Derived from:** AC2

## Non-Functional Requirements

Refunds must be processed within 2 business days of cancellation.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AC1   | "Given an order that has not yet shipped, when the customer views their order details, then a "Cancel Order" button is visible." | FR-1 |
| AC2   | "Given the customer clicks "Cancel Order", when they confirm the cancellation, then the order status changes to "Cancelled" and the customer receives a cancellation confirmation email." | FR-2 |
| AC3   | "Given an order has already shipped, when the customer views their order details, then no "Cancel Order" button is shown." | FR-3 |
| AC4   | "Given an order is cancelled, when payment was already captured, then a refund is automatically issued to the original payment method." | FR-4 |
