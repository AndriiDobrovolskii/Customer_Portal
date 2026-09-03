# Open Decisions: US-2.4 Password Reset

**Story:** `docs/stories/US-2.4-password-reset.md`
**Pre-existing spec:** `docs/specifications/US-2.4-spec.md` (drafted 2026-08-22, Pass with Issues, predates the actual login/logout/refresh codebase now in place).
**Logged:** 2026-09-01

## Resolutions (2026-09-01)

All three Open Decisions below were resolved by the user on 2026-09-01, recommended option accepted in every case:

- **OD-1:** Local static breached-password list/bloom filter. No live network call; no new dependency.
- **OD-2:** Check order is 60 s per-account cooldown → 5/account/hour → 10/IP/hour; the first limit tripped returns its own `Retry-After`.
- **OD-3:** `POST /v1/auth/password-reset/request` writes an `auth_audit_log` entry (`event=password_reset_requested`) on every attempt, including unknown/deactivated-account attempts.

---

## OD-1 (High) — Breached-password check mechanism

**Question:** The story mandates the breached-password check "MUST use k-anonymity (a 5-character SHA-1 prefix) or a local bloom filter — never transmit the password or its full hash," but does not choose between the two. Which does this story build: a live call to a k-anonymity API (e.g. HIBP's `range` endpoint), or a locally bundled breached-password list/bloom filter?

**Why it can't be inferred:** Neither mechanism exists anywhere in the codebase today — no HTTP client wrapper for an external breach-check service, no bundled wordlist/bloom-filter asset, and no config settings for either. `httpx` is already a dependency (used for the test client), so a live k-anonymity call is technically possible without adding a package, but it would be the first outbound network call to a third party anywhere in this codebase — every other external-looking check (rate limits, revocation, audit) is self-contained against Postgres/Valkey. `docs/product/business-rules.md` and `docs/product/business-glossary.md` are silent on this.

**Impact if left unresolved:** DESIGN can't size the dependency (new module + settings vs. a shipped data file) and TESTS/IMPLEMENTATION can't decide how the integration suite exercises this path — the project's existing integration tests run entirely against real Postgres/Valkey via testcontainers with no external network dependency, and a live call would either need to be mocked (introducing this codebase's first HTTP-level test double) or would make the suite flaky/network-dependent.

**Recommendation:** Local static breached-password check (a bundled Top-N common-password list, or a small bloom filter built from one), consistent with this project's fully self-contained, network-free test suite. A live k-anonymity call is the more common real-world choice but is a bigger architectural change than this story's scope suggests.

## OD-2 (Medium) — Precedence between the three request-throttling limits

**Question:** `POST /v1/auth/password-reset/request` has three simultaneous limits (60 s per-account cooldown, 5/account/hour, 10/IP/hour). When more than one is tripped at once, which check runs first, and whose `Retry-After` value is returned?

**Why it can't be inferred:** No existing rate-limit gateway in this codebase combines a short cooldown with an hourly counter on the same route. `LoginThrottleCache` tracks only failure counts (account + IP) over one window; `RefreshRateLimitCache` (US-2.3, resolved OD-1) tracks a single per-`family_id` counter. Neither precedent has more than one active limit per check.

**Impact if left unresolved:** `implementation-planner`/`data-layer-builder` can't design the cache gateway's key structure or the service's check order without guessing which limit "wins" when two are tripped together (e.g. does the 5th request in an hour also always land inside the 60 s window, making the cooldown redundant, or can they diverge in a burst pattern that needs a defined precedence?).

**Recommendation:** Check cheapest-first: 60 s cooldown, then per-account hourly, then per-IP hourly; return the first tripped limit's own `Retry-After`. Mirrors the cooldown-then-broader-limit precedent already used by `email_verification`'s `resend_cooldown_seconds`.

## OD-3 (Low) — Audit logging on the request endpoint, not just confirm

**Question:** Should `POST /v1/auth/password-reset/request` itself write an `auth_audit_log` entry (e.g. `event=password_reset_requested`), or does auditing start only at `confirm` (PR-AC2's `password_reset_completed`), as literally stated?

**Why it can't be inferred:** Every other authentication flow already implemented (login, logout, refresh) audits both the attempt and the outcome, per this codebase's established pattern and `BR-014`'s audit-everything posture. The story's Acceptance Criteria only specify an audit entry on successful completion (PR-AC2); PR-AC1/PR-AC3 (the request endpoint, including the anti-enumeration path) say nothing about auditing.

**Impact if left unresolved:** A security investigation into an account-takeover attempt via password reset would have no server-side record of reset *requests* against an account — only of a reset that actually completed. Silently deciding this either way changes `auth_audit_log`'s write pattern for this story.

**Recommendation:** Log `password_reset_requested` uniformly (including for unknown/deactivated-account attempts, since the audit log is never customer-visible and writing it doesn't affect PR-AC3's anti-enumeration response) for consistency with every other auth flow's audit coverage.

## Resolved by precedent (not logged as Open Decisions)

- **PR-AC4's three-way token-state mapping** (`token-expired` vs `token-invalid` for expired / consumed / unknown-hash), left as an unresolved Open Question in the pre-existing `US-2.4` spec, is resolved by direct precedent: `app/modules/email_verification/service.py` — which handles the exact token shape this story cites as its model (`email_verification_tokens`) — already maps unknown-hash → `TokenInvalidError`, already-consumed → `TokenInvalidError`, expired → `TokenExpiredError`. Recommend applying the identical mapping here.
- **Missing/empty/malformed email on the request endpoint**, the pre-existing spec's second unresolved Open Question, is resolved by precedent: `LoginRequest.email` is typed as plain `str` with no format validation (`app/modules/users/schemas.py`); no endpoint in this codebase validates email format at the schema layer. Recommend the same: no dedicated format validation, `email: str`.
