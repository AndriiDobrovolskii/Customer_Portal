# STORY-88: Bulk Export of Invoices

As an account admin, I want to export multiple invoices at once so I don't
have to download them one by one for our bookkeeper.

Acceptance Criteria:

1. Admin can select multiple invoices from the invoices table using
   checkboxes.
2. An "Export Selected" button appears once at least one invoice is
   checked.
3. Clicking "Export Selected" downloads a single file containing all
   selected invoices.
4. Only admins can see the bulk export controls — regular users should not.
5. Exports of more than 500 invoices should be handled gracefully.
6. The export should be fast.

Note from PM: for really large exports we might want to email a link
instead of downloading directly, but let's not worry about that for v1.
