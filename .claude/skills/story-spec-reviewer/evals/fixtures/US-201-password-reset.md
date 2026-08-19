# US-201: Password Reset via Email

**As a** user who forgot their password,
**I want** to reset it via an emailed link,
**So that** I can regain access to my account without contacting support.

## Acceptance Criteria

- **AC1:** Given a user on the login page, when they click "Forgot password?", then they are shown a form to enter their email address.
- **AC2:** Given a user submits their email, when the email exists in the system, then a reset link is sent to that email, valid for 30 minutes.
- **AC3:** Given a user clicks a valid, unexpired reset link, when they submit a new password, then their password is updated and they are redirected to the login page with a success message.
- **AC4:** Given a user clicks an expired or already-used reset link, when they attempt to submit a new password, then they see an error message stating the link is no longer valid, and are offered the option to request a new one.
