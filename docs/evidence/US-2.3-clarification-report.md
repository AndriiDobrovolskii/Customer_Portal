# Clarification Report: US-2.3 (Refresh Token)

**Story:** `docs/stories/US-2.3-refresh-token.md`
**Existing spec (outside this pipeline):** `docs/specifications/US-2.3-spec.md` (drafted 2026-08-22, reviewed at `docs/reviews/specifications/US-2.3-spec-review.md`, verdict Pass with Issues)
**Reviewed:** 2026-09-01

## Scope, Actor, Business Value

**Actor:** Any authenticated Customer Portal user (customer or staff) holding a valid refresh token — not role-specific.

**Trigger:** The client's access token has expired (or is about to), and the client calls `POST /v1/auth/refresh` with its refresh token to obtain a new access token without forcing the user to log in again.

**Business value:** Lets a user stay signed in for a normal working day (per the Customer persona's goal, `docs/product/personas.md`, "Log in securely and stay logged in across a normal working day without re-entering a password") while bounding the damage of a stolen refresh token — single-use rotation plus reuse detection means a copied token is only useful once before the theft is both detected and contained (whole family revoked, owner alerted).

**In scope:** `POST /v1/auth/refresh` — single-use rotation, reuse detection with family-wide revocation and alerting, idle/absolute lifetime enforcement, denial for deactivated/revoked accounts, atomic handling of concurrent same-token requests.

**Out of scope (per story):** Initial token issuance (US-2.1, already shipped), session listing (US-2.6, not yet built — reads the metadata this story writes).

## What's Clear

- All 6 ACs (RT-AC1–RT-AC6) are concrete, testable Given/When/Then statements with explicit thresholds (14-day idle, 30-day absolute, 10-second grace window) — confirmed already covered 1:1 (2:1 for RT-AC4) by the existing spec's FR-1–FR-7, per the prior spec review.
- `BR-008` (business-rules.md) already codifies this story's core reuse-detection behavior project-wide, so the story is consistent with established rules, not introducing a new pattern.
- The "same absolute expiry as the original" clause in RT-AC1 resolves how the 30-day absolute cap is tracked without a dedicated family-creation timestamp: `expires_at` is set once at family creation (already how `UserService`'s login flow does it, `refresh_token_ttl_seconds = 2,592,000` = 30 days) and copied forward unchanged on every rotation — no new column needed for this.
- US-2.2 (already merged, PR #5) added a minimal `revoked_at` column plus `get_refresh_token_by_hash`/`revoke_refresh_token_family` repository methods to `refresh_tokens` ahead of this story (its own OD-3) — this story adds the remaining columns its Data Model Notes list (`consumed_at`, `ip`, `user_agent`, `last_used_at`) and the rotation/reuse logic itself.
- `hash_refresh_token`/`generate_refresh_token` (`app/core/security.py`) already exist and are reused, not reinvented.

## What's Ambiguous — Open Decisions Logged

Six new items (`docs/decisions/US-2.3-open-decisions.md`, OD-1–OD-6), none inferable from `business-rules.md`, `business-glossary.md`, or the current codebase:

1. **OD-1** — Rate-limit (60/family/hour) response shape: undefined by story or spec.
2. **OD-2** — Mobile client (`X-Client-Type: mobile`) token delivery: named in the API Contract, zero ACs, zero existing code.
3. **OD-3** — RT-AC3's "indistinguishable" response: scope (status/body only vs. timing) left undefined by both story and spec, flagged but unresolved in the spec review.
4. **OD-4** — RT-AC2 requires `severity=high` on the audit entry; `auth_audit_log` has no `severity` column today.
5. **OD-5** — No stated check-ordering between reuse detection (RT-AC2) and account-eligibility (RT-AC5) when both apply to one request.
6. **OD-6** — RT-AC2's family-wide revocation has no mechanical link to the paired access-token session (`user_sessions` has no `family_id`); whether that's an accepted gap was never stated.

Plus two items carried forward from the 2026-08-22 spec review that were never resolved (RFC 7807 envelope shape and cookie `Path=/v1/auth` scoping both present in the story but not restated as spec requirements) — see the open-decisions doc's closing section.

## Readiness Verdict

**Not Ready — see Open Decisions.**

Six new Open Decisions (OD-1–OD-6) plus two carried-forward spec-review findings need the user's resolution before `story-spec-writer` revises `US-2.3-refresh-token-spec.md`. This mirrors the pattern from US-2.1 (7 ODs) and US-2.2 (6 ODs): the story and its pre-existing spec were written before the surrounding codebase (login's actual refresh-token shape, US-2.2's partial schema work, the login-throttle precedent) existed to check them against.
