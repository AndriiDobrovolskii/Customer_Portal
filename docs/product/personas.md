# Personas

## Customer

### Description

An external user who registers to access the Customer Portal and, optionally, raise support tickets.

### Goals

- Register and verify an account quickly (`US-001`, `US-002`).
- Log in securely and stay logged in across a normal working day without re-entering a password (`US-005`, `US-007`).
- See and manage their own profile, including a safely confirmed email change (`US-003`).
- Deactivate their own account, and reactivate it within a grace period if they change their mind (`US-004`).
- See every device signed in to their account and sign any of them out individually (`US-010`).
- Recover access via password reset without contacting support (`US-008`).
- Raise a support ticket and follow the reply thread to resolution (`US-014`, `US-015`, `US-016`).

### Frustrations

- A registration or login flow that leaks whether an email is already registered.
- Losing access to every device because one was signed out, or the reverse — a stolen device staying signed in after the account owner logs out elsewhere.
- Support tickets that read as a black hole, with no visible status or reply.

---

## Administrator

### Description

Internal staff responsible for provisioning and correcting the user directory and role assignments. MFA-mandatory.

### Goals

- Search and page through the user directory to handle a support escalation quickly (`US-011`, slice 1).
- Provision a new colleague's account by email invitation, without ever handling their password (`US-011`, slice 2).
- Correct a user's profile details when a record was entered wrong (`US-011`, slice 3).
- Deactivate an account immediately when someone leaves or an account is compromised (`US-011`, slice 4).
- Reissue an invitation whose 24-hour link expired, without losing the user's existing id, roles, or audit history (`US-011`, slice 5).
- Assign exactly the role a person's job requires, and see immediately why a request was denied if it would escalate their own privilege (`US-012`).

### Frustrations

- A role change that forces every affected user to fully log out and back in.
- Being unable to tell whether the system is one action away from having zero administrators.
- An audit trail that can be edited after the fact, making an investigation unreliable.

---

## Support Agent

### Description

Internal staff who work the ticket queue: replying to customers, adding internal notes for other agents, and resolving tickets. MFA-mandatory.

### Goals

- See the queue of tickets their permissions allow, not other customers' private tickets (`US-014` FR-2).
- Reply publicly to a customer, or leave an internal note visible only to other staff (`US-015`).
- Mark a ticket resolved with a note the customer will actually receive, and have it close itself automatically if the customer doesn't come back within the grace period (`US-016`).

### Frustrations

- An internal note leaking to the customer, or into a notification email.
- Two agents resolving the same ticket at once and one's resolution note silently overwriting the other's.

---

## Auditor

### Description

Internal staff (or a role held alongside another) whose job is to investigate incidents and answer compliance requests using the audit log. MFA-mandatory.

### Goals

- Query a filtered, tamper-evident record of who did what and when, without needing to reconstruct it from memory or scattered logs (`US-013`).
- Trust that no one — not even an administrator — could have altered or deleted an entry after the fact (`US-013` FR-4, FR-7).
- Follow an audit trail across an account that was later deleted or anonymized (`US-013` FR-8).

### Frustrations

- A query window so wide it silently truncates results instead of asking for a narrower range.
- Sensitive values (passwords, tokens, payment identifiers) appearing unredacted in an audit entry.
