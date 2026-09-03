# Open Decisions: US-2.1 — Login

**Story:** docs/stories/US-2.1-login.md
**Existing spec:** docs/specifications/US-2.1-spec.md (Draft, refined 2026-08-22)
**Existing spec review:** docs/reviews/specifications/US-2.1-spec-review.md (Overall Verdict: **Pass with Issues**)
**Clarification run:** 2026-08-31 (retroactive — a spec and spec review already exist for this story, produced outside this pipeline; the CLARIFICATION stage that should have preceded them never formally ran, per the same "pre-existing, not run in this pipeline" pattern already recorded for US-1.4)
**Resolution:** All 6 substantive items (OD-1–OD-6) resolved by the user on 2026-08-31, all via the recommended option in each case. OD-7 (spec-quality, not a business decision) is forwarded to `story-spec-writer` directly.

## How to read this log

This is not a fresh clarification of an unspecified story. The spec-writer's own "Open Questions" section already surfaced six real gaps, and the spec reviewer independently confirmed the AC coverage was faithful but flagged two further precision issues. This log consolidates all of that, cross-checks each item against `docs/product/business-rules.md` / `business-glossary.md` and sibling specs for anything since resolved, and adds one item (#1 below) not previously raised. Every item is now resolved (see each item's **Status** line) — the questions themselves are kept verbatim below for traceability.

---

### OD-1 — RS256/JWKS is unimplemented; the codebase already uses a shared-secret HS256 scheme

**Status: Resolved 2026-08-31 — use the existing HS256 scheme.** The story's Assumption #3 ("RS256 with JWKS key rotation") is superseded for this story; login issues tokens via the already-shipped HS256 path (`app/core/config.py`'s `jwt_algorithm`, `app/core/security.py`). JWKS/asymmetric signing/rotation is out of scope here and would be its own future story if ever needed. `story-spec-writer` should drop the RS256/JWKS FR implication and not gate any AC on it.

**Question (as originally raised):** Story Assumption #3 states access-token signing is "RS256 with JWKS key rotation." Does US-2.1 need to build RS256 signing + a JWKS publishing endpoint from scratch, or should login use the JWT infrastructure that already exists?

**Why it can't be inferred:** `app/core/config.py:19,722` (`jwt_algorithm: str = "HS256"`) and `app/core/security.py` (`jwt.encode(..., settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)`) show the already-shipped auth code (the minimal login endpoint from commit `90a612b`, gated on `email_verified` only) uses a single shared secret, not an asymmetric keypair — there is no JWKS endpoint, no key-rotation mechanism, and no RS256 path anywhere in the repo. `docs/ARCHITECTURE.md:71` documents this as deliberately configurable ("HS256 or RS256 per settings — never hardcoded"), not as a commitment to RS256. LI-AC1 itself only requires "an access token (JWT, 15-minute TTL)" — it does not name an algorithm. The spec's own Open Questions section flagged the ambiguity ("Is RS256/JWKS a hard requirement... or informative context with no AC coverage?") but didn't check it against the codebase's current state.

**Impact if left unresolved:** Building JWKS key rotation is materially larger scope than anything an AC asks for (a new key-management subsystem, a public verification endpoint, rotation policy) and would ripple into every other story that verifies a token. A spec-writer or planner would otherwise have to guess whether to scope that in or quietly keep HS256 and treat the story's Assumption as stale.

---

### OD-2 — Mobile JSON-body refresh-token transport: in scope or not?

**Status: Resolved 2026-08-31 — out of scope for US-2.1.** Login always sets the refresh token as the `Set-Cookie` per the API Contract table; the `X-Client-Type: mobile` JSON-body branch is deferred entirely to US-2.3 (Refresh Token), which already documents it for its own endpoint. No new AC is added here.

**Question (as originally raised):** Story Assumption #2 says the refresh token is delivered as a JSON body field "when `X-Client-Type: mobile`," in addition to the cookie. No AC covers this branch, and the API Contract table (line 36) lists only `Set-Cookie: refresh_token` as the success shape. Is the mobile transport part of this story's success response, and if so what does it look like and which AC governs it?

**Why it can't be inferred:** `docs/stories/US-2.3-refresh-token.md:33` shows the *refresh* endpoint (a separate, explicitly out-of-scope story) does implement this same `X-Client-Type: mobile` switch for its own response — but that doesn't settle whether the *login* endpoint's initial token issuance also needs it. `business-rules.md` and `business-glossary.md` are silent on transport selection beyond citing this story's own Assumption #1.

**Impact if left unresolved:** A spec-writer would have to guess whether to add a second response branch (and a new AC) or drop the mobile-body assumption as unimplemented for this story, deferring it entirely to US-2.3.

---

### OD-3 — Does the unknown-email path (LI-AC3) write an audit entry, and with what `reason`?

**Status: Resolved 2026-08-31 — yes, `event=login_failed, reason=unknown_email`.** The audit log is staff-only (never exposed to the caller), so recording the real reason does not violate the response-level anti-enumeration rule (BR-005) — it only helps investigators. `story-spec-writer` should add this to FR-3.

**Question (as originally raised):** LI-AC2 (wrong password) specifies `reason=bad_password`. LI-AC3 (unknown email) requires "the same body, status and comparable timing" as LI-AC2 but is silent on whether an `auth_audit_log` entry is written at all, and if so what `reason` value distinguishes it from a genuine wrong-password attempt.

**Why it can't be inferred:** The Data Model Notes' event enum (`login_succeeded` / `login_failed`) doesn't define a reason vocabulary. Recording a distinct reason (e.g. `unknown_email`) would technically leak account-existence information into the audit log — which may be intentional (audit log is staff-only) or may be considered a violation of the anti-enumeration principle (BR-005) applied to storage, not just the response. Neither `business-rules.md` nor `US-3.3-view-audit-information-spec.md` resolves this.

**Impact if left unresolved:** A spec-writer would have to guess whether to log this path at all, and improvise a `reason` value with no stated vocabulary.

---

### OD-4 — Does a blocked login (LI-AC4: unverified / deactivated) write an audit entry, and with what `reason`?

**Status: Resolved 2026-08-31 — yes, `event=login_failed, reason=email_not_verified` or `reason=account_deactivated`.** These are security-relevant outcomes on a real, credential-verified account; staff should be able to see them in the audit trail. `story-spec-writer` should add this to FR-4.

**Question (as originally raised):** Same shape as OD-3, for the two `403` branches. The Data Model Notes' `event` enum has no obvious value for a state-gated block distinct from `login_failed`/`login_succeeded`.

**Why it can't be inferred:** BR-006 states deactivation revokes tokens and a deactivated account gets `403`, but says nothing about whether the login *attempt itself* is audited on that path. No sibling spec covers this.

**Impact if left unresolved:** Same as OD-3 — a spec-writer would improvise both whether to log and what value to use.

---

### OD-5 — Is the per-IP throttle counter reset on a successful login?

**Status: Resolved 2026-08-31 — no, left unreset.** One IP can serve many accounts (NAT, shared network); a success on one account shouldn't clear failure history that may reflect a different attacker on the same IP. This is deliberate asymmetry, not an oversight. `story-spec-writer` should state this explicitly in FR-5 rather than leaving it silent.

**Question (as originally raised):** LI-AC5 states "a successful login resets the account counter" but is silent on the per-IP counter (`login_fail:ip:{ip}`). Is that omission deliberate (e.g. because one IP may serve many accounts, so one account's success shouldn't clear another account's failures recorded under that IP) or an oversight?

**Why it can't be inferred:** `business-rules.md` has no per-IP throttling rule at all (BR-005 covers only anti-enumeration, not rate-limit reset semantics). The asymmetry is plausible as intentional (per-account vs. per-IP have different threat models) but nothing states it.

**Impact if left unresolved:** A spec-writer/implementer would have to guess the reset behavior for a security control, which is exactly the kind of silent decision this pipeline exists to prevent.

---

### OD-6 — Are `429` (throttled) or `422` (validation-failed) responses recorded in `auth_audit_log`?

**Status: Resolved 2026-08-31 — neither is logged.** `429` is already visible via the rate-limit counters themselves (Valkey); `422` never reaches credential verification at all. `auth_audit_log` stays scoped to real login attempts (succeeded / failed-with-a-real-or-attempted-credential-check). This is consistent with, and reconfirms, LI-AC6's own statement that a malformed request records nothing against the rate-limit counter either.

**Question (as originally raised):** Neither LI-AC5 nor LI-AC6 states this, and the event enum has no matching value for either case.

**Why it can't be inferred:** Same gap as OD-3/OD-4 — no source defines an event vocabulary broader than `login_succeeded`/`login_failed`.

**Impact if left unresolved:** Same as OD-3/OD-4.

---

### OD-7 (spec-review finding, restated) — Concrete response/error JSON shapes and full audit-field list aren't reproduced in the spec body

**Question:** Should the spec's FR-1–FR-6 be tightened to inline the exact success/error JSON shapes (`token_type`, `expires_in`, full RFC 7807 field set) and the full `auth_audit_log` field list, rather than requiring a reader to cross-reference the original story?

**Why it can't be inferred:** This is a spec-quality issue, not a business-rule gap — the source story already states the shapes (API Contract table, Error Envelope section, Data Model Notes); the spec just doesn't inline them. Recorded here so it isn't lost before the spec is next revised.

**Impact if left unresolved:** Lower severity than OD-1–OD-6 (reviewer rated it Medium/Low, not blocking) — a developer can still find the shapes in the source story, just not in the spec alone.

### OD-8 — Empty-string password: 422 or 401?

**Status: Resolved 2026-08-31 — treat as 422 validation-failed.** An empty-string `password` isn't a real credential attempt; it's rejected at request-schema validation, same as a missing `password` field, before it reaches credential verification or the rate-limit counter. Raised during SPEC_REVIEW (`docs/reviews/specifications/US-2.1-spec-review.md`, Missing Edge Cases) rather than during the original clarification pass; folded into FR-6 of `docs/specifications/US-2.1-spec.md`.

**Question (as originally raised):** Given a request body missing "password", or containing an unknown field — does LI-AC6's "missing password" also cover an empty-string password (`"password": ""`)?

**Why it can't be inferred:** Neither the story nor the original spec addresses this distinction.

**Impact if left unresolved:** An implementer would have to guess whether an empty string reaches Argon2id verification (and the throttle counter) or is rejected upfront.

---

### OD-9 — Refresh-token table: build a minimal version now, or issue an opaque unbacked cookie?

**Status: Resolved 2026-08-31 — build a minimal `refresh_tokens` table now.** Columns: `token_hash` (SHA-256, unique), `family_id`, `user_id`, `issued_at`, `expires_at`. `consumed_at` (rotation semantics), `ip`/`user_agent`/`last_used_at` (US-2.6's needs) are deferred to US-2.3/US-2.6, which read and extend this row later. Folded into `docs/designs/database/US-2.1-db-design.md` and `US-2.1-entity-model.md`.

**Question (as originally raised):** Raised during PLANNING's impact-analysis pass (`docs/impact-analysis/US-2.1-impact-analysis.md`), not during the original clarification pass. US-2.1's own story never mentions a `refresh_tokens` table in its Data Model Notes, but US-2.3-refresh-token.md's Out of Scope section states "Initial token issuance (US-2.1)" — assigning creation of the very first refresh token to this story. No such table or token-generation code exists anywhere in the codebase.

**Why it can't be inferred:** The two stories' scope statements only make sense together (US-2.1 issues, US-2.3 rotates), but neither story's own Data Model Notes section states the table shape this story needs — US-2.1 is silent, and US-2.3's shape includes columns (`consumed_at`, `ip`, `user_agent`, `last_used_at`) this story has no use for yet.

**Impact if left unresolved:** `db-designer`'s output would be incomplete relative to what FR-1 actually requires (a real cookie value), and `planner` would have to guess the table shape mid-implementation.

---

### OD-10 — LI-AC4's "deactivated → 403" is incomplete: US-1.4 assigns reactivation-on-login to this story

**Status: Resolved 2026-08-31 — build reactivation now.** FR-4 is amended: deactivated + correct credentials + within the 30-day grace period → reactivate (`status→active`, `deactivated_at` cleared, `account_lifecycle_audit_log` entry `event=reactivated, actor=self`, then proceed through the normal FR-1 success path) and `200`; deactivated + correct credentials + past the grace period → `403` as originally specified. Folded into `docs/specifications/US-2.1-spec.md`, `docs/designs/api/US-2.1-api-design.md`, `docs/impact-analysis/US-2.1-impact-analysis.md`, `docs/plans/US-2.1-implementation-plan.md`, `docs/plans/US-2.1-task-breakdown.md`.

**Question (as originally raised):** Raised via `advisor()` consultation during PLANNING→IMPLEMENTATION handoff, cross-referencing `docs/stories/US-1.4-deactivate-account.md` DA-AC8, `docs/specifications/US-1.4-spec.md` FR-8, and `docs/designs/api/US-1.4-api-design.md`'s own table ("FR-8 | Reactivation on login within 30-day grace period | **US-2.1 Login (extension)**"). US-1.4's shipped code (`app/modules/account/repository.py:deactivate_if_not_already`) never reactivates anyone — nothing in the codebase implements DA-AC8 anywhere. US-2.1's own LI-AC4 only carries the unconditional-403 half (citing DA-AC6), silently dropping the grace-period reactivation half US-1.4 explicitly deferred here.

**Why it can't be inferred:** `docs/stories/US-2.1-login.md`'s LI-AC4 text is genuinely silent on the grace period — a spec-writer working from the story alone, without cross-referencing US-1.4's design doc, would have no way to know reactivation belongs here at all.

**Impact if left unresolved:** DA-AC8 (a Pass-verdict spec's own FR-8) would have no implementation anywhere in the system — a deactivated user could never get their account back except by a mechanism nothing builds, silently breaking a committed product behavior (`personas.md`: "reactivate it within a grace period if they change their mind").

**Cross-module note:** reactivation writes to `account_lifecycle_audit_log`, owned by the `account` module, not `users`. Per `AGENTS.md` §3's service→service discipline, `users/service.py` calls a new `AccountService.reactivate_account()` method (Protocol-typed collaborator, injected) rather than reaching into `account`'s repository/models directly — mirroring the existing `revoke_other_sessions` cross-module pattern already used for the profile module's email-change flow.

---

## Notes carried forward, not open

- LI-AC4's ordering guarantee (credential check before state check, so a wrong password always yields generic `401`) is independently confirmed by BR-006 — no ambiguity.
- Anti-enumeration timing (LI-AC3) is confirmed project-wide by BR-005, which explicitly extends the same discipline to email-verification resend and password-reset request — no ambiguity.
- The existing minimal login endpoint (`app/modules/users/router.py`, `service.py:authenticate_user`, shipped in commit `90a612b` for VE-AC5/VE-AC6) covers only unverified-account gating and issues a bare access token with a bespoke `LoginResponse` shape — it does not check deactivation, does not throttle, does not audit-log, does not set a refresh cookie, does not return `token_type`/`expires_in`, and does not perform a dummy-hash verification on unknown emails (it raises immediately when `user is None`). This is existing-state context for PLANNING/IMPLEMENTATION, not an open decision — noted here so it isn't rediscovered from scratch later.
