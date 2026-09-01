# US-3.2 (Manage Roles) — Clarification Report

## Scope, Actors, Business Value

**Actor:** An administrator managing another user's access. **Trigger:** a user's job function changes and their permissions need to match. **Business value:** "each person has exactly the access their job requires and no more" — the least-privilege backbone every other privileged-role story (US-2.5 MFA, US-3.1 Manage Users, US-3.3 Audit) is built to check against. Confirmed foundational: `docs/stories/README.md`'s suggested build order places US-3.2 first, "everything else checks its scopes," and this run of `us-clarifier` was itself triggered by US-2.5's clarification finding it has no role/scope system to depend on yet.

In scope: the role catalogue read endpoint, replacing a user's role set, and immediate propagation of permission changes to live sessions via `perm_epoch`. Out of scope: custom/tenant roles, row-level permissions, and the break-glass admin-recovery command (an Alembic/CI mechanism, not an API).

## What's Clear

- The fixed four-role catalogue (`customer`, `support_agent`, `admin`, `auditor`) and the six permission scopes are given directly and match `business-rules.md` BR-010 verbatim.
- `perm_epoch` vs. `revoke_before` as two deliberately separate Valkey keys is explained clearly, and matches `business-glossary.md`'s existing `Permission Epoch` entry.
- The token-staleness mechanism (MR-AC2) has a direct precedent already in the codebase: `app/modules/users/service.py` compares `UserSession.issued_at <= revoke_before` (looked up via the token's `jti`, not a JWT claim) for the existing `revoke_before` check. `perm_epoch` can follow the identical pattern — this is not an open decision, it's inferable from shipped code.
- Self-modification-forbidden, privilege-escalation-forbidden, and the last-admin guard (MR-AC5–7) are all precise and testable, and mirror the guard patterns already established for `admin_audit_log`-writing endpoints in US-3.1's story text (even though US-3.1 hasn't been implemented yet, its story document establishes consistent vocabulary).
- `PUT` full-replacement semantics (Assumption #2) and the `If-Match` requirement are unambiguous.

## What's Ambiguous / Not Yet Resolved

See `docs/decisions/US-3.2-open-decisions.md` for full detail. Summary:

- **OD-1:** The story's own Non-Functional Requirements section mandates an Alembic hook inside `migrations/env.py` for permission-catalogue completeness checking — but `AGENTS.md` §7.9 is a binding project rule that `env.py` must never be edited by any agent (explicitly listed in the Definition of Done as `"env.py untouched"`), and `AGENTS.md`'s own preamble says it wins over any conflicting instruction. This is a genuine rule conflict, not a spec-writer-fillable gap.
- **OD-2:** No story, business rule, or existing code addresses how the very first administrator account gets the `admin` role, given the only in-scope mechanism to grant roles itself requires already holding `roles:write`. Confirmed by inspection that `app/modules/users/models.py`'s `User` model has no role association today — this system currently has zero admins and zero way to create one through this story's API alone.

## Readiness Verdict

**Ready for Specification.**

Both Open Decisions resolved by the user 2026-09-01, recommended option accepted for each: OD-1 — the permission-catalogue completeness check moves to a standalone CI test, `migrations/env.py` stays untouched (AGENTS.md §7.9 preserved). OD-2 — the out-of-scope break-glass command doubles as initial-admin bootstrap; this story's DESIGN references it as a dependency without building it. See `docs/decisions/US-3.2-open-decisions.md` for full resolution text.
