# Open Decisions: US-2.3 (Refresh Token)

**Story:** `docs/stories/US-2.3-refresh-token.md`
**Existing spec (outside this pipeline):** `docs/specifications/US-007-refresh-token-spec.md`, reviewed at `docs/reviews/specifications/US-007-spec-review.md` (verdict: Pass with Issues, 2026-08-22 — 3 Open Questions never resolved, plus 2 Missing-Edge-Case findings)
**Generated:** 2026-09-01
**Resolved:** 2026-09-01 — user accepted the recommended option on all 6 items (OD-1–OD-6), same pattern as US-2.1/US-2.2. Both carried-forward spec-review findings are also to be addressed explicitly in the revised spec.

The story and its existing spec were written before US-2.1 (Login) and US-2.2 (Logout) were actually implemented. Reading the current codebase (`app/modules/users/{models,repository,service}.py`, `app/core/{config,email,security}.py`) surfaces several places where the real architecture is missing pieces this story needs, or leaves a genuine choice the story/spec never made. These are recorded here rather than silently guessed at.

---

## OD-1 — Refresh rate limit (60 req/family/hour): what response does an over-limit client get?

**Question:** The story's Assumptions & Defaults table sets a refresh rate limit of 60 requests/family/hour, but no Acceptance Criterion defines the response when it's exceeded (already flagged as an unresolved Open Question in `US-007-refresh-token-spec.md`). Does exceeding it return `429` with a `Retry-After` header — the same shape login throttling already uses (`TooManyAttemptsError`, `app/modules/users/exceptions.py:47`) — or the story's own `401 token-invalid` envelope, or something else?

**Why it can't be inferred:** Neither the story nor `business-rules.md`/`business-glossary.md` states this; the spec review flagged it and it was never answered.

**Impact of leaving unresolved:** A spec-writer would have to invent either a new error shape or silently reuse `401`, which would make a rate-limited client indistinguishable from an invalid-token client — undesirable for both client-side retry logic and server-side alerting (rate-limiting is a distinct signal from theft/reuse).

**Recommendation:** Reuse the existing `429` + `Retry-After` pattern (`TooManyAttemptsError`), keyed by `family_id` instead of IP/account. This keeps one throttling vocabulary in the codebase and keeps rate-limit responses distinguishable from `token-invalid`.

**Resolution (2026-09-01):** Confirmed — recommended option applied. `429` + `Retry-After`, keyed by `family_id`, reusing `TooManyAttemptsError`.

---

## OD-2 — Mobile client refresh-token delivery (`X-Client-Type: mobile`): build it now, or descope?

**Question:** The story's API Contract line reads "Refresh cookie (or body for `X-Client-Type: mobile`)," but no Acceptance Criterion covers the mobile path, and a grep of `app/` for `X-Client-Type`/`client_type`/`mobile` returns zero matches anywhere in the codebase — this mechanism doesn't exist yet in any form. Does US-2.3 build the mobile branch (return the rotated raw refresh token in the response body instead of/in addition to the cookie when this header is present), or is it explicitly out of scope for now?

**Why it can't be inferred:** The API Contract table names it, but every AC (RT-AC1–RT-AC6) only describes cookie-based rotation; nothing in `business-rules.md`/`business-glossary.md` or any other story mentions a mobile client type.

**Impact of leaving unresolved:** A spec-writer would either silently drop a contract line the story explicitly states, or invent the header name/body shape/precedence rules (does the cookie still get set too?) with no source to check against.

**Recommendation:** Descope for this story — same pattern as US-2.2's OD-4 (CSRF). No mobile client exists yet to consume this, and shipping a second token-delivery channel (raw refresh token in a JSON body) is a meaningfully different security posture (no `HttpOnly` protection) that deserves its own explicit sign-off rather than riding in as a contract-table footnote. Track as a follow-up once a mobile client is actually being built.

**Resolution (2026-09-01):** Confirmed — descoped. The spec's Out of Scope section states explicitly that `X-Client-Type: mobile` body-delivery is deferred to a dedicated follow-up story; this story implements cookie-based delivery only.

---

## OD-3 — "Indistinguishable" response (RT-AC3): status/body only, or timing too?

**Question:** RT-AC3 requires the response be "indistinguishable" across expired/unknown/revoked-by-logout, but never states which dimensions must match. This exact ambiguity was flagged as [Low] in the spec review and never resolved. `BR-005` establishes a project-wide precedent: login pays a dummy Argon2id cost specifically so response *timing* can't reveal account existence, and states "the same anti-enumeration discipline applies to email-verification resend and password-reset request" — but does not name refresh.

**Why it can't be inferred:** BR-005 lists specific flows it covers and refresh isn't one of them; nothing states whether that omission is deliberate (refresh doesn't compare against a password, so there's no expensive hash to fake) or simply not yet written down.

**Impact of leaving unresolved:** A spec-writer would have to guess whether a timing side-channel review applies here, and a security reviewer would have no documented bar to check the implementation against.

**Recommendation:** Scope "indistinguishable" to status code and response body only (all three cases return the identical `401 token-invalid` envelope verbatim). Unlike login, none of the three cases (expired/unknown/revoked) involves a variable-cost operation like password hashing — a DB lookup miss and a DB lookup hit-but-expired are already close to constant-time — so there's no BR-005-style expensive step to fake the cost of. State this explicitly in the spec rather than leaving it open again.

**Resolution (2026-09-01):** Confirmed — recommended option applied. "Indistinguishable" scoped to status code and response body only; the spec states this explicitly rather than leaving it open.

---

## OD-4 — `auth_audit_log` has no `severity` column

**Question:** RT-AC2 requires an audit entry with "`event=refresh_reuse_detected`, `severity=high`," but the current `AuthAuditLog` model (`app/modules/users/models.py`) has `event`, `reason`, `scope`, `actor_id`, `ip`, `user_agent`, `request_id`, `occurred_at` — no `severity` column. Should `severity` be a new nullable column (set `"high"` on this event, `null` elsewhere), or should severity be derived purely at query/read time from a static `event → severity` lookup maintained in application code (no schema change)?

**Why it can't be inferred:** Neither `business-rules.md` nor `business-glossary.md` mentions a severity concept on audit rows; this is the first story to need one.

**Impact of leaving unresolved:** A spec-writer would have to silently pick a schema shape for a field US-3.3 (View Audit Information) will also need to read/filter on.

**Recommendation:** Add a dedicated nullable `severity: String(16)` column — same reasoning as US-2.2's OD-5 (`scope` column): a derived-at-read-time lookup table works until US-3.3 needs to filter or sort the audit view by severity directly in SQL, at which point a column was needed anyway. Cheaper to add it now while the migration is already touching this table's neighborhood.

**Resolution (2026-09-01):** Confirmed — recommended option applied. Add a dedicated nullable `severity: String(16)` column to `AuthAuditLog`, set to `"high"` on `refresh_reuse_detected` rows only; `null` on every other event type.

---

## OD-5 — Check ordering: does reuse detection (RT-AC2) still fire if the account is already deactivated?

**Question:** The ACs don't state an evaluation order. If a presented refresh token is both *already consumed* (RT-AC2) and belongs to an account that's *now deactivated or past `revoke_before`* (RT-AC5), which check wins? Concretely: does the system still detect reuse, revoke the (already-dead) family, write the `high`-severity audit entry, and email the account owner — or does account-ineligibility short-circuit first and return a plain `401` with no reuse alerting?

**Why it can't be inferred:** The story lists RT-AC2 before RT-AC5, but that's document order, not a stated execution-order requirement; nothing in `business-rules.md` addresses precedence between these two checks.

**Impact of leaving unresolved:** This changes observable security behavior (whether a stolen-and-replayed token against a now-deactivated account still generates an alert) and a spec-writer has no source to cite either way.

**Recommendation:** Check token validity/reuse *before* account eligibility. Reuse of a consumed token is evidence of a compromise attempt regardless of the account's current status, and the alerting/audit trail (RT-AC2) is valuable independent of whether the account is presently usable — an attacker replaying a stolen token against a deactivated account is still worth a security email to the account owner. Order: (1) token exists and not expired → RT-AC3, (2) token already consumed → RT-AC2 (reuse, always alerts), (3) account eligibility → RT-AC5, (4) idle/absolute lifetime → RT-AC4, (5) atomic consume → RT-AC1/RT-AC6.

**Resolution (2026-09-01):** Confirmed — recommended option applied. Check order: (1) exists/not-expired → RT-AC3, (2) already consumed → RT-AC2 (always alerts, regardless of account status), (3) account eligibility → RT-AC5, (4) idle timeout → RT-AC4, (5) atomic consume → RT-AC1/RT-AC6. Clarification added during spec-writing: RT-AC4 bundles two separate thresholds (idle timeout and absolute cap) into one AC, but they're enforced by two different mechanisms at two different steps — the absolute cap is just `expires_at`, already checked at step 1 (it's fixed at family creation and copied forward unchanged on every rotation, per FR-1), so step 4 here is the idle-timeout (`last_used_at`) check only, not both.

---

## OD-6 — Does family revocation on reuse (RT-AC2) also kill the paired access-token session?

**Question:** `RefreshToken` and `UserSession` (the access-token/jti table) have no link to each other today — `family_id` lives only on `refresh_tokens`, and `UserSession` has no `family_id` or equivalent column. RT-AC2 says "every token in that family is revoked" — read narrowly, that's refresh tokens only, leaving any currently-valid access token (≤15 min TTL, `access_token_ttl_seconds = 900`) usable until it naturally expires. Should reuse detection also immediately revoke the associated access-token session (which would require adding a `family_id` link to `user_sessions`, a schema change beyond what the story's Data Model Notes list), or is a ≤15-minute residual window accepted as the cost of not building that link?

**Why it can't be inferred:** `business-glossary.md`'s "Revocation (`revoke_before`)" entry describes account-wide kill-everything revocation (logout-everywhere, deactivation, password reset) but reuse detection is explicitly family-scoped in the story text ("the whole session chain is destroyed" — referring to the refresh chain), not account-wide; nothing states whether "session chain" is meant to include the live access token.

**Impact of leaving unresolved:** A spec-writer would either silently add a schema link not listed in the story's Data Model Notes, or silently accept a residual-access window without stating it as a deliberate tradeoff.

**Recommendation:** Accept the ≤15-minute residual access-token window; do not add a `family_id` link to `user_sessions` for this story. The access token is short-lived by design specifically to bound this kind of exposure, adding the link is a cross-cutting schema change to a table this story doesn't otherwise touch, and the story's own Data Model Notes don't list it. State this explicitly as an accepted tradeoff in the spec rather than leaving it silently unaddressed.

**Resolution (2026-09-01):** Confirmed — recommended option applied. No `family_id` link added to `user_sessions`; the ≤15-minute residual access-token window is an accepted tradeoff, stated explicitly in the spec's Non-Functional Requirements.

---

## Carried forward, unresolved by the existing spec review (for the user to confirm alongside OD-1–OD-6)

- **[Medium, from spec review]** The RFC 7807 error envelope's exact field shape (from the story's Error Envelope section) should be restated in the spec's FR-2/FR-3/FR-6, not left implicit.
- **[Low-Medium, from spec review]** The refresh cookie's `Path=/v1/auth` scoping constraint should be stated as a requirement in FR-1 / NFRs, not left implicit.
- **[from story's own Open Questions]** The 10-second concurrent-refresh grace window (RT-AC6) is flagged by the story itself as needing validation against real frontend behavior once the SPA's refresh interceptor exists — noted, not blocking, since the story already frames it as a future check-in rather than an open question for this pipeline stage.
