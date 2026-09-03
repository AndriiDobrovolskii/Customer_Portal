# Non-Functional Requirements

These are the cross-cutting bars every story is held to, beyond its own functional requirements. Engineering-process NFRs (coverage, layering, migrations) are stated here for product-doc visibility but are authoritative in `AGENTS.md` — if this file and `AGENTS.md` ever disagree, `AGENTS.md` wins.

## NFR-001 Password & Secret Handling

Passwords, hashes, tokens, and session identifiers must never appear in an API response, a log line, a trace, or an APM payload — a scrubbing rule is required for `password`/`current_password`-shaped keys. Raw verification tokens (email verification, password reset, invitation) are delivered in the request body or a URL fragment, never a URL query string, so they cannot leak via access logs or `Referer` headers.

**Derived from:** `US-1.1` FR-6; `US-1.2` NFR; `US-2.4` NFR; `US-2.1` NFR. See [[business-rules]] BR-004.

---

## NFR-002 Anti-Enumeration

Login, email-verification resend, and password-reset request must not let an attacker distinguish "no such account" from "account exists" via status code, response body, or response timing. Where a real cryptographic operation would normally run (e.g. password verification), a dummy operation of comparable cost runs instead so timing doesn't leak existence.

**Derived from:** `US-2.1` FR-3, NFR; `US-1.2` FR-8; `US-2.4` FR-3. See [[business-rules]] BR-005.

---

## NFR-003 Rate Limiting & Brute-Force Protection

Every unauthenticated or self-service write endpoint that could be abused (login, MFA verification, registration-adjacent resends, password-reset requests, ticket creation, ticket replies) enforces a per-account and, where applicable, a per-IP rate limit, returning `429` with `Retry-After`. Brute-force protection on login and MFA verification additionally invalidates the attempt state (throttles the account / invalidates the `mfa_token`) rather than only slowing the attacker down.

**Derived from:** `US-2.1` FR-5; `US-2.5` FR-5; `US-2.4` FR-6; `US-4.1` FR-8; `US-4.2` NFR.

---

## NFR-004 Session & Token Revocation Latency

A revocation (`revoke_before`) or permission change (`perm_epoch`) must be checked on *every* authenticated request via shared middleware, not opt-in per route, so no endpoint can accidentally skip it. The denylist/revocation check must add negligible latency to the shared auth path (the login story sets an explicit p95 budget for the check).

**Derived from:** `US-1.4` NFR; `US-2.2` NFR; `US-3.2` NFR. See [[business-rules]] BR-006, BR-011.

---

## NFR-005 Database-Enforced Invariants

Constraints that matter for correctness or security are enforced at the database layer, not only in application code, wherever a spec calls this out explicitly: case-insensitive email uniqueness (atomic under concurrency), single-use token consumption (atomic check-and-consume), audit-log immutability (`INSERT`/`SELECT`-only grants, no `UPDATE`/`DELETE`), and internal-ticket-reply isolation (PostgreSQL Row-Level Security keyed on session actor context).

**Derived from:** `US-1.1` FR-2; `US-1.2` FR-1; `US-2.3` FR-7 (NFR); `US-3.3` FR-4; `US-4.2` FR-3, FR-5.

---

## NFR-006 Audit Trail Completeness

Every mutation — including one that fails authorization — is audited; a denied attempt is often the more interesting event. Every audit-log *read* is itself audited. The audit trail must remain queryable and intact after the account it references is permanently deleted or anonymized, with direct identifiers redacted but the trail itself unbroken.

**Derived from:** `US-3.1` NFR; `US-3.3` FR-2, FR-8.

---

## NFR-007 Traceability

Every implementation must be traceable to a User Story (`docs/stories/`), a Specification (`docs/specifications/`), and its tests — this is the same discipline the spec-writer/spec-reviewer traceability matrices already enforce upstream of code.

**Derived from:** `AGENTS.md` §1, §6 (Definition of Done, item 3); the traceability matrix convention already present in every `docs/specifications/*.md`.

---

## NFR-008 Architecture & Layering

`router → dependencies → service → repository/cache gateway → models/schemas`, enforced mechanically by `import-linter` (`AGENTS.md` §3, §7.3). No ORM object crosses service → router; every nested relationship a schema needs is eager-loaded in the repository statement, never lazily resolved under `AsyncSession`.

**Derived from:** `AGENTS.md` §3.

---

## NFR-009 Testing & Coverage

New behavior ships with unit tests (hand-written fakes, never `MagicMock`, for repositories/cache gateways) and, for new/changed endpoints, integration tests against real PostgreSQL and Valkey with no `unittest.mock` in `tests/integration/`. Coverage floor is 85% overall, 90%+ for `service.py`/`router.py`, and is a floor, not a target — excluding files to reach it is a violation.

**Derived from:** `AGENTS.md` §5, §6 (Definition of Done, items 3–4), §7.7.

---

## NFR-010 Build & Migration Stability

A change is not complete if the gate (`pre-commit run --all-files`, mypy strict, `lint-imports`) fails, or if a migration's `upgrade → downgrade → upgrade` cycle doesn't actually run clean. Migration history is append-only.

**Derived from:** `AGENTS.md` §6 (Definition of Done, items 1, 2, 5).

---

## NFR-011 Performance Targets

Where a spec states one, the p95 latency budget for the endpoint is a build requirement, not a suggestion — e.g. login ≤ 400 ms (including its deliberate ~100 ms hashing cost), refresh ≤ 120 ms, session listing ≤ 200 ms, admin user search ≤ 300 ms at 100k users, audit query ≤ 500 ms for a 50-row page over 30 days, ticket creation ≤ 400 ms, reply thread fetch ≤ 300 ms for 100 replies.

**Derived from:** `US-2.1`, `US-2.3`, `US-2.6`, `US-3.1`, `US-3.3`, `US-4.1`, `US-4.2` — each spec's own Non-Functional Requirements section.

---

## NFR-012 PII & Data Minimization

List and detail responses carry no credential material (password hash, token, session cookie) and no more personal data than the endpoint's purpose requires. Location data derived from IP is coarsened (city/country, not street-level) and session metadata is purged on a stated retention window. Redaction applies both to values returned by the API and to values inspected directly in storage.

**Derived from:** `US-2.6` NFR; `US-3.1` NFR; `US-3.3` FR-6.
