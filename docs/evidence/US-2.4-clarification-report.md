# Clarification Report: US-2.4 Password Reset

**Reviewed:** 2026-09-01
**Story:** `docs/stories/US-2.4-password-reset.md`
**Persona:** Customer — "Recover access via password reset without contacting support" (`docs/product/personas.md`), listed dependency-free of any other in-flight story.

## Scope, Actor, Business Value

A Customer who forgot their password requests a reset link by email, then submits a new password using the token from that link — self-service account recovery with no support-agent involvement, consistent with the product's "User self-service" goal (`docs/product/product-vision.md`). Two endpoints: `POST /v1/auth/password-reset/request` (issue, anti-enumeration) and `POST /v1/auth/password-reset/confirm` (consume + set new password + revoke every session).

## What's Clear

- Token shape, TTL (30 min), single-use, hash-only storage, and invalidation of any prior unconsumed token: fully specified, explicitly modeled on `email_verification_tokens` (US-1.2).
- Anti-enumeration requirement (PR-AC3) is a direct extension of the already-established `BR-005` pattern (login, email-verification resend, and now password-reset request all share this discipline).
- Post-reset session/refresh revocation (PR-AC2) reuses the existing `revoke_before:{user_id}` mechanism verbatim — already documented as one of its triggers in `docs/product/business-glossary.md`'s **Revocation** entry, citing this story by its pre-existing spec ID (`US-2.4` FR-2).
- Password policy (12 chars, breached-list rejection, not-equal-to-current) and its 422 handling, including "don't consume the token on a policy failure," are unambiguous.
- Error envelope and `type_slugs` follow the same RFC 7807 pattern used throughout Epic 2.
- A pre-existing spec (`docs/specifications/US-2.4-spec.md`, 2026-08-22) already covers this story in detail, drafted before US-2.1/2.2/2.3 were actually implemented — same situation as those three stories' own clarification rounds. Re-reading it against the now-real codebase resolved both of its own unresolved Open Questions by precedent (see below) and surfaced 3 new items the original draft couldn't have anticipated, since the infrastructure it would reuse didn't exist yet in August.

## Resolved by Precedent (no Open Decision needed)

1. **PR-AC4's token-state → error-type mapping** — the pre-existing spec left open which of {expired, consumed, unknown-hash} maps to `token-expired` vs `token-invalid`. `app/modules/email_verification/service.py`, handling the identical token shape this story is explicitly modeled on, already answers it: unknown-hash and already-consumed both → `token-invalid`; expired → `token-expired`.
2. **Missing/malformed email on the request endpoint** — the pre-existing spec's other open question. `LoginRequest.email` (`app/modules/users/schemas.py`) is a plain `str` with no format validation anywhere in this codebase; same precedent applies here.

## Open Decisions (see `docs/decisions/US-2.4-open-decisions.md`)

| # | Severity | Question |
|---|---|---|
| OD-1 | High | Breached-password check: live k-anonymity API call vs. a local static list/bloom filter — neither exists in the codebase today, and this would be the project's first outbound third-party network call if the live option is chosen. |
| OD-2 | Medium | Precedence between the three request-throttling limits (60 s cooldown, 5/account/hour, 10/IP/hour) when more than one trips at once — no existing cache gateway combines more than one active limit per route. |
| OD-3 | Low | Should the request endpoint itself write an `auth_audit_log` entry, or does auditing start only at confirm as literally stated — every other auth flow audits both attempt and outcome. |

All three resolved by the user 2026-09-01, recommended option accepted throughout: OD-1 local static breached-password list/bloom filter (no live network call); OD-2 check order cooldown → per-account/hour → per-IP/hour, first tripped limit's `Retry-After` wins; OD-3 the request endpoint writes `auth_audit_log` (`event=password_reset_requested`) on every attempt, including unknown/deactivated accounts.

## Verdict

**Ready for Specification.** All Open Decisions resolved 2026-09-01 — see `docs/decisions/US-2.4-open-decisions.md`. Advancing to SPECIFICATION: `story-spec-writer` revising the existing `US-2.4-password-reset-spec.md` to incorporate OD-1–3 plus the two precedent-resolved items above.
