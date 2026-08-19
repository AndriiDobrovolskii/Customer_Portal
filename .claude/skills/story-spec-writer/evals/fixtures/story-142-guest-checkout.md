# STORY-142: Guest Checkout

**As a** shopper who doesn't want to create an account,
**I want** to complete a purchase without registering,
**So that** I can buy quickly without friction.

## Acceptance Criteria

- **AC1:** Given a shopper on the cart page, when they click "Checkout," then they are offered a "Continue as Guest" option alongside "Log In."
- **AC2:** Given a shopper chooses "Continue as Guest," when they reach the checkout form, then they are only required to enter email, shipping address, and payment details (no password field is shown).
- **AC3:** Given a guest completes a purchase, when the order is placed, then a confirmation email is sent to the email address they entered, containing the order number and itemized total.
- **AC4:** Given a guest has completed checkout, when they view the confirmation page, then they are offered the option to create an account using the email and shipping info they already entered (no re-typing required).
