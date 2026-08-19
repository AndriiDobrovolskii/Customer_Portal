# Specification: Password Reset via Email

**Source:** docs/backlog/US-201.md
**Story ID:** US-201
**Generated:** 2026-07-01
**Status:** Draft

## Summary

This spec covers the password reset flow: requesting a reset link by email and setting a new password from that link.

## Functional Requirements

### FR-1: Forgot password entry point

When a user clicks "Forgot password?" on the login page, display a form requesting their email address.

**Derived from:** AC1

### FR-2: Send time-limited reset link

When a user submits an email that exists in the system, send a password reset link to that address. The link is valid for 30 minutes from the time it is sent.

**Derived from:** AC2

### FR-3: Reset password from valid link

When a user follows a valid, unexpired reset link and submits a new password, update the account's password and redirect the user to the login page with a success message.

**Derived from:** AC3

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AC1   | "Given a user on the login page, when they click "Forgot password?", then they are shown a form to enter their email address." | FR-1 |
| AC2   | "Given a user submits their email, when the email exists in the system, then a reset link is sent to that email, valid for 30 minutes." | FR-2 |
| AC3   | "Given a user clicks a valid, unexpired reset link, when they submit a new password, then their password is updated and they are redirected to the login page with a success message." | FR-3 |
| AC4   | "Given a user clicks an expired or already-used reset link, when they attempt to submit a new password, then they see an error message stating the link is no longer valid, and are offered the option to request a new one." | FR-3 |
