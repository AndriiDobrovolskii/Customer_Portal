# Specification: Bulk Invoice Download

**Source:** docs/backlog/US-410.md
**Story ID:** US-410
**Generated:** 2026-07-05
**Status:** Draft

## Summary

This spec covers bundling invoices for a selected billing period into a single downloadable file, handling the empty-results case, and restricting the control to admins.

## Functional Requirements

### FR-1: Bundle invoices for a date range

When an admin selects a date range on the Billing page and clicks "Download Invoices", the system shall bundle all invoices within that range and make the download available promptly.

**Derived from:** AC1

### FR-2: Empty range messaging

When the selected date range contains no invoices, display a message indicating no invoices were found for that range.

**Derived from:** AC2

### FR-3: Restrict control to admins

The "Download Invoices" control is only visible to admin users; non-admin users viewing the Billing page do not see it.

**Derived from:** AC3

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AC1   | "Given an admin on the Billing page, when they select a date range and click "Download Invoices", then all invoices within that range are bundled into a single downloadable file." | FR-1 |
| AC2   | "Given the admin has no invoices in the selected date range, when they click "Download Invoices", then they see a message stating no invoices were found for that range." | FR-2 |
| AC3   | "Given a non-admin user, when they view the Billing page, then the "Download Invoices" control is not visible to them." | FR-3 |
