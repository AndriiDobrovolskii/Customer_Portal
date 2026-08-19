# US-410: Bulk Invoice Download

**As an** account admin,
**I want** to download all invoices for a billing period as a single file,
**So that** I can share them with our finance team without downloading each one individually.

## Acceptance Criteria

- **AC1:** Given an admin on the Billing page, when they select a date range and click "Download Invoices", then all invoices within that range are bundled into a single downloadable file.
- **AC2:** Given the admin has no invoices in the selected date range, when they click "Download Invoices", then they see a message stating no invoices were found for that range.
- **AC3:** Given a non-admin user, when they view the Billing page, then the "Download Invoices" control is not visible to them.
