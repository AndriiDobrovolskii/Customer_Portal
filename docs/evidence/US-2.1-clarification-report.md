# Clarification Report: US-2.1 — Login

**Story:** docs/stories/US-2.1-login.md
**Reviewed against:** docs/product/product-vision.md, personas.md, business-rules.md, business-glossary.md; sibling stories US-1.2, US-1.4, US-2.3, US-2.5, US-2.6, US-013; existing spec + review (US-005); current codebase state.
**Date:** 2026-08-31

## Business Intent

Actor, trigger, and value are explicit and unambiguous: a registered Customer (`business-glossary.md` — Customer/Authentication) exchanges email+password for a session so they don't have to re-authenticate on every request. This matches the persona goal "Log in securely and stay logged in across a normal working day" (`personas.md`, Customer). No inference required.

## Acceptance Criteria — Completeness & Testability

All six ACs (LI-AC1–LI-AC6) are concrete, Gherkin-structured, and independently verifiable — no "handle appropriately"-style language. The existing spec (`US-005-login-spec.md`) and its review confirm faithful, complete coverage with no contradictions. This clarification pass did not find any AC-level gap the spec missed.

## Security & Validation Expectations

Well-covered by the story itself and reinforced by `business-rules.md`:
- Anti-enumeration (BR-005) — confirmed project-wide, applies here without modification.
- Deactivation ordering (BR-006) — confirmed: credential check always precedes state check, so a wrong password never leaks deactivation status.
- Password-in-logs scrubbing, Argon2id-in-threadpool, CSRF exemption for this endpoint specifically — all explicit in the story's Non-Functional section.

Two structural gaps remain, both logged as Open Decisions (see below): the token-signing scheme (OD-1) and the mobile transport branch (OD-2).

## Dependencies

- Depends on US-1.2 (email verification — VE-AC5, already shipped) and US-1.4 (deactivation — DA-AC6, already shipped and merged as of this session) for the two account-state error types LI-AC4 references. Both dependencies are satisfied in the codebase.
- `docs/stories/README.md` places US-2.1 first in the suggested build order after US-3.2, ahead of US-2.3/US-2.2 — consistent with US-2.5 (MFA) and US-2.6 (sessions) later depending on this story's success path.
- A partial, pre-existing login implementation already exists in `app/modules/users/` (router + service), built for VE-AC5/VE-AC6 only. It will need extension, not a fresh build, once this reaches IMPLEMENTATION — see the note at the end of the Open Decisions log.

## Open Decisions Summary

Seven items logged in `docs/decisions/US-2.1-open-decisions.md`:

| ID | Topic | Severity |
|---|---|---|
| OD-1 | RS256/JWKS assumption vs. shipped HS256 shared-secret scheme | High — scope-defining |
| OD-2 | Mobile JSON-body refresh-token transport in/out of scope | Medium — scope-defining |
| OD-3 | Audit logging for unknown-email path (LI-AC3) | Medium — security/audit completeness |
| OD-4 | Audit logging for blocked-login path (LI-AC4) | Medium — security/audit completeness |
| OD-5 | Per-IP throttle counter reset semantics (LI-AC5) | Low-Medium — security control precision |
| OD-6 | Audit logging for throttled/malformed paths (LI-AC5/6) | Low — audit completeness |
| OD-7 | Spec doesn't inline concrete JSON/audit-field shapes (reviewer finding) | Low — spec quality, not blocking |

None of these were invented by this pass — OD-2 through OD-7 restate what the spec-writer and spec-reviewer already found; OD-1 is the one new item, surfaced by checking the story's signing-algorithm assumption against the actual shipped code rather than against the spec text alone.

## Verdict

**Ready for Specification.**

All six substantive Open Decisions (OD-1–OD-6) were resolved by the user on 2026-08-31 — see `docs/decisions/US-2.1-open-decisions.md` for each item's Status line:

- OD-1: use the existing HS256 scheme; drop the RS256/JWKS assumption.
- OD-2: mobile JSON-body refresh transport is out of scope for this story.
- OD-3: unknown-email path logs `event=login_failed, reason=unknown_email`.
- OD-4: blocked-login path logs `event=login_failed, reason=email_not_verified` or `account_deactivated`.
- OD-5: per-IP throttle counter is deliberately left unreset on success.
- OD-6: neither `429` nor `422` responses are audit-logged.

OD-7 (spec doesn't inline concrete JSON/audit-field shapes) is a spec-quality note, not a business decision — forwarded directly to `story-spec-writer` for the next spec revision. The existing spec (`US-005-login-spec.md`) needs to be updated to incorporate OD-1–OD-7 before SPEC_REVIEW is re-run.
