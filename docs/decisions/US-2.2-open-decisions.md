# Open Decisions: US-2.2 (Logout)

**Story:** `docs/stories/US-2.2-logout.md`
**Existing spec (outside this pipeline):** `docs/specifications/US-2.2-spec.md`, reviewed at `docs/reviews/specifications/US-2.2-spec-review.md` (verdict: Pass with Issues, 2026-08-22 — one High ambiguity never resolved)
**Generated:** 2026-08-31
**Resolved:** 2026-08-31 — user accepted the recommended option on all 6 items (OD-1–OD-4 explicitly confirmed via AskUserQuestion; OD-5–OD-6 carried the stated recommendation, same pattern as US-2.1's OD-1–OD-6).

The story and its existing spec were written generically, before US-2.1 (Login) was actually implemented. Reading the current codebase (`app/modules/users/{models,repository,service}.py`) surfaces several places where the real architecture has already diverged from, or is missing pieces the story assumes exist. These are recorded here rather than silently guessed at.

---

## OD-1 — Access-token revocation: reuse the existing `UserSession.revoked_at`, or build a separate Valkey `jti_denylist`?

**Question:** LO-AC1/FR-1 specify a Valkey key `jti_denylist:{jti}` with a TTL. But US-2.1 already built a Postgres `user_sessions` table (`jti` PK, `issued_at`, `expires_at`, `revoked_at`) that `UserService.get_authenticated_user` already checks on *every* authenticated request (`get_session_by_jti` → reject if `revoked_at is not None`). A `revoke_sessions_except(user_id, except_jti)` repository method that bulk-sets `revoked_at` already exists too. Should logout revoke by setting `UserSession.revoked_at = now()` for the presented jti (and call `revoke_sessions_except` for logout-all), reusing the mechanism that's already wired into the auth-check path — or should it additionally/instead build the Valkey denylist the story literally describes?

**Why it can't be inferred:** The story and its spec predate knowledge of how US-2.1 was actually implemented; neither `business-rules.md` nor `business-glossary.md` mention `UserSession` at all — they were written to match the story's original Valkey design. Nothing states which one wins now that a working DB-based mechanism already exists.

**Impact of leaving unresolved:** A spec-writer would either invent a second, redundant revocation channel (two sources of truth for "is this jti still valid," a maintenance and consistency risk) or silently repoint FR-1 at the DB table without recording that as a deliberate deviation from the story's stated design.

**Recommendation:** Reuse `UserSession.revoked_at` — it's already the enforcement point, needs no new Valkey key, and trivially satisfies the ≤2ms-latency NFR since the DB check is already unconditional on every request today.

**Resolution (2026-08-31):** Confirmed — reuse `UserSession.revoked_at`. No Valkey `jti_denylist` key is introduced. FR-1's Data-Model reference should describe this table, not a Valkey key.

---

## OD-2 — LO-AC4 vs. LO-AC5: how is idempotent repeat-logout reconciled with "any request with a denylisted jti gets 401"?

**Question:** Already flagged as a [High] unresolved ambiguity in the existing spec review, never answered. Given OD-1's DB mechanism: if the first `POST /v1/auth/logout` call sets that access token's `UserSession.revoked_at`, a second call presenting the *identical* access token will hit the same "session revoked" check that any other endpoint would — currently that returns `401` (`get_authenticated_user` returns `None`). But LO-AC4 requires `204` on that exact repeat call. Does `POST /v1/auth/logout` need a carve-out in the shared auth dependency — accept an access token whose jti is revoked *only when the endpoint being called is logout itself*, returning `204` — while every other endpoint still gets `401` for that same revoked jti (LO-AC5)? Or does LO-AC4 actually mean a second, different, not-yet-revoked access token (e.g. from another concurrent login) is used for the repeat call?

**Why it can't be inferred:** The source story itself contains the contradiction (already noted in `docs/specifications/US-2.2-spec.md`'s own Open Questions and the spec review's Ambiguities section); no product doc resolves it.

**Impact of leaving unresolved:** FR-4 is not implementable as literally worded without picking one reading — this blocks writing a passing spec.

**Recommendation:** Carve out logout-only leniency: an authenticated-but-revoked-jti request to `POST /v1/auth/logout` specifically (not `logout-all`) still resolves the caller and returns `204`, since logout is definitionally about a state that's already been reached. Every other endpoint keeps rejecting revoked jtis per LO-AC5.

**Resolution (2026-08-31):** Confirmed — logout-only leniency. `POST /v1/auth/logout`'s auth dependency (only that route, not `logout-all` or any other endpoint) accepts a jti whose `UserSession.revoked_at` is already set and still resolves the caller, returning `204`. Every other endpoint, including `logout-all`, keeps rejecting a revoked jti with `401` per LO-AC5.

---

## OD-3 — `refresh_tokens` has no revocation column or lookup method; does US-2.2 add a minimal one now?

**Question:** The `RefreshToken` model (`app/modules/users/models.py`) currently has `id`, `token_hash`, `family_id`, `user_id`, `issued_at`, `expires_at` — no `revoked_at`/`consumed_at` column, and `UserRepository` has no method to look up a token by hash or revoke a family. US-2.3 (Refresh Token, which per `docs/stories/README.md`'s suggested build order — "US-2.1 → US-2.3 → US-2.2" — was meant to land *before* logout) is the story that would normally add this. The user is sequencing US-2.2 next instead. Does US-2.2 add a minimal `revoked_at` column plus `get_by_token_hash`/`revoke_family` repository methods now, the same way US-2.1 added a "minimal" `refresh_tokens` table ahead of US-2.3 (precedent: US-2.1's OD-9)?

**Why it can't be inferred:** Neither the story nor `business-rules.md` says who builds the revocation column first; it's purely a function of build order, which the user is deliberately changing from the suggested sequence.

**Impact of leaving unresolved:** LO-AC1's "the presented refresh token is marked revoked, including its whole rotation family" is impossible to implement without some column to mark and some way to find the family — a spec-writer would have to silently invent the schema.

**Recommendation:** Yes, add a minimal `revoked_at` column now (same pattern as OD-9), scoped only to what logout needs; leave single-use consumption tracking (`consumed_at`, rotation) to US-2.3.

**Resolution (2026-08-31):** Confirmed — add a minimal `revoked_at` column to `refresh_tokens`, plus repository methods to look up a token by its hash (to resolve the presented cookie's token row) and to revoke every row sharing that row's `family_id`. `consumed_at` and single-use rotation tracking remain out of scope, deferred to US-2.3.

---

## OD-4 — No CSRF mechanism exists anywhere in the codebase; is US-2.2 the story that builds it?

**Question:** The story's NFR states "Logout is a state-changing, cookie-authenticated call → CSRF token required." A grep of `app/` for `csrf`/`CSRF` returns zero matches. US-2.1's own spec explicitly exempted login from this requirement ("the login endpoint is CSRF-exempt, but every cookie-authenticated state-changing endpoint requires a CSRF token") and, because login didn't need it, never built it. Logout is the first endpoint that actually requires CSRF protection. Does US-2.2 build the project's first CSRF middleware (cross-cutting, would touch `app/main.py` and every future cookie-authenticated route, not just this module), or is CSRF deliberately deferred/descoped for this story?

**Why it can't be inferred:** This was never resolved or logged as a deferred item anywhere (checked `docs/decisions/US-2.1-open-decisions.md` — no CSRF mention). It's a genuine gap in the codebase, not a documented decision.

**Impact of leaving unresolved:** A spec-writer would either silently drop the CSRF NFR from the spec (weakening the security posture the story asks for) or silently scope in a cross-cutting middleware component well beyond "logout" without the user having agreed to that scope.

**Recommendation:** Descope from US-2.2 — track as a follow-up story/tech-debt item, since building generic CSRF middleware is materially bigger than "add a logout endpoint" and affects every future cookie-authenticated route, not just this one. State this explicitly in the spec's Out of Scope rather than silently dropping the NFR.

**Resolution (2026-08-31):** Confirmed — descoped. The spec's Out of Scope section should state explicitly that CSRF protection is deferred to a dedicated follow-up story, and that this story's NFR (CSRF required) is not enforced by this implementation. Logout ships without CSRF protection for now, same as login shipped exempted.

---

## OD-5 — `auth_audit_log` has no `scope` column

**Question:** LO-AC1/LO-AC2 require an `auth_audit_log` entry with `scope` ∈ {`session`, `all_sessions`}. The existing `AuthAuditLog` model has `event` and `reason` (both used by login: `reason` currently holds failure reasons like `unknown_email`, `bad_password`, or `None` on success) but no `scope` column. Should `scope` be a new column, or should logout reuse the existing nullable `reason: String(32)` column to carry `session`/`all_sessions` values?

**Why it can't be inferred:** The story names `scope` as if it's an established field; it isn't in the current schema, and `business-rules.md` BR-009 doesn't specify the column either.

**Impact of leaving unresolved:** A spec-writer would have to guess between a schema migration (new column) and reusing `reason` for a differently-named concept.

**Recommendation:** Add a dedicated `scope` column — reusing `reason` (whose established meaning across every other row is "why did this fail") for an unrelated "which blast radius" concept on success-only logout rows would blur an already-established field's meaning.

**Resolution (2026-08-31):** Recommended option applied (not asked separately — Medium severity, same pattern as US-2.1's OD-1–OD-6 where the recommended option was accepted throughout). Add a dedicated nullable `scope: String(32)` column to `AuthAuditLog`, set on logout rows only (`session`/`all_sessions`); left `null` on every other event type.

---

## OD-6 — Access token valid but no refresh cookie present

**Question:** Already flagged [Low] in the existing spec review. LO-AC1's Given clause presumes both a valid access token *and* a refresh cookie. What happens when `POST /v1/auth/logout` is called with a valid access token but no refresh cookie (already cleared, or a non-browser client)?

**Why it can't be inferred:** Neither the story nor the spec addresses this combination.

**Impact of leaving unresolved:** Minor — affects one edge-case branch's exact behavior (still revoke the jti and return 204, just skip the cookie-clear/family-revoke steps that don't apply).

**Recommendation:** Treat it as the happy path minus the cookie-specific side effects: revoke the jti, audit-log `scope=session`, return `204`. No refresh-token revocation occurs because there is nothing to revoke.

**Resolution (2026-08-31):** Recommended option applied (Low severity, same rationale as OD-5). Missing refresh cookie is not treated as `LO-AC3`'s "no/invalid access token" case — the access token is still valid, so the jti is still revoked, the audit entry (`scope=session`) is still written, and `204` is still returned; only the cookie-clear and refresh-family-revoke steps are skipped since there's no cookie to act on.
