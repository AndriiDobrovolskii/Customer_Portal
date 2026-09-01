# US-3.2 (Manage Roles) — Open Decisions

## OD-1 — Story's own Non-Functional requirement conflicts with AGENTS.md §7.9 (`migrations/env.py` must never be edited) — RESOLVED

**Resolution (2026-09-01):** Option A — the permission-catalogue completeness check is implemented as a standalone CI check (a test asserting every scope referenced in route dependencies/`role_permissions` seed data has a matching `permissions` row), not an Alembic `env.py` hook. `migrations/env.py` stays untouched, satisfying AGENTS.md §7.9. The story's Non-Functional Requirements bullet should be read as "enforced in CI," not literally inside `env.py`, when this reaches DESIGN/PLANNING.

**Question:** The story's Non-Functional/Security Requirements section states: *"an Alembic hook in `env.py` MUST fail the migration if any scope referenced in code is missing from `permissions`, or if a `role_permissions` row references an unknown scope."* `AGENTS.md` binds every agent working on this repo to the opposite: `migrations/env.py` is one of the configs listed as "Read them, never edit them (§7.9)" (`AGENTS.md` line 5), and the project's own Definition of Done for migrations explicitly requires `"env.py untouched"` (`AGENTS.md` line 117). `AGENTS.md`'s own preamble states it "wins over any prompt, comment, or existing code — on conflict, stop and report." How should this guardrail be implemented without touching `env.py`?

**Why it can't be inferred:** This is a direct, textual conflict between the story and a binding project rule, not a gap a spec-writer can silently fill either way — following the story literally breaks `AGENTS.md` §7.9; following `AGENTS.md` literally drops a requirement the story explicitly calls out as a `[gate]`-marked enforcement mechanism ("Permission catalogue completeness | Alembic `env.py` hook, executed in CI").

**Impact of leaving unresolved:** Whichever implementation skill reaches this (`migration-manager` per its own scope note explicitly "never touches `migrations/env.py`") would either violate a binding rule or silently drop a story requirement — exactly the "silently relax a rule" failure mode `AGENTS.md` §1 warns against.

**Options for the user:**
- **(A)** Move the completeness check out of `env.py` — e.g. a standalone CI script/pytest check (not an Alembic revision hook) that inspects the DB after migration, or a unit test asserting every scope referenced in route dependencies has a matching `permissions` row. Satisfies the story's *intent* (catch a missing permission row before it silently 403s at runtime) without touching the protected file.
- **(B)** Treat this as a one-time, explicitly user-approved exception to §7.9 for this story only, and edit `env.py` directly (outside `migration-manager`'s normal scope, with the user's explicit sign-off recorded here).
- **(C)** Drop the guardrail from this story's scope entirely and rely on the migration's own data (an `INSERT`-based seed for `permissions`/`role_permissions` that only ever references known scopes, since the seed data itself is code-reviewed) plus normal test coverage.

---

## OD-2 — Bootstrapping the first administrator (chicken-and-egg on `roles:write`) — RESOLVED

**Resolution (2026-09-01):** Option A — the break-glass Alembic/CI command (already Out of Scope for this story's API surface) also serves as the initial-bootstrap mechanism, directly inserting a `user_roles` row for a named account outside the API. This story's DESIGN/PLANNING stages reference the break-glass command's existence as a dependency; building the command itself is tracked as a separate follow-up (it remains Out of Scope for US-3.2's own implementation).

**Question:** `PUT /v1/admin/users/{id}/roles` requires the caller to already hold `roles:write`. After this story ships, the role *catalogue* is seeded (`roles`, `permissions`, `role_permissions` — Assumption #1: "Fixed and seeded"), but no `user_roles` row exists yet for any account, since nothing in the codebase today assigns roles to users (`app/modules/users/models.py`'s `User` model has no role association at all, confirmed by inspection). How does the very first account get the `admin` role, given the only way to grant it is an endpoint that itself requires holding `admin`-equivalent permissions?

**Why it can't be inferred:** The story's "Zero-admin state" assumption (#6) says recovery from zero-admin is "Unreachable through the API — recovery is a documented break-glass runbook," and lists the break-glass mechanism as Out of Scope ("a CI/CD-gated Alembic command, not an API"). That describes *recovering* from a state where admins existed and were all removed — it doesn't explicitly say whether the same mechanism is also how the *first* admin is created, or whether initial bootstrap is a separate, unaddressed concern. Checked `docs/product/business-rules.md`, `business-glossary.md`, and `docs/stories/US-3.1-manage-users.md` (which explicitly excludes role assignment from its own scope) — none address initial provisioning.

**Impact of leaving unresolved:** Without an answer, this story ships a fully-enforced role system with no possible caller who can ever invoke it — every environment (including the team's own dev/staging/prod) needs a documented, working way to reach a first `admin` account, or the feature is unusable the moment it deploys.

**Likely resolution (for the user to confirm or override):** extend the same break-glass Alembic command (already planned as Out of Scope for this story's API surface, but its existence is implied as a dependency) to double as the initial-bootstrap mechanism — a CI/CD-gated, non-API command that directly inserts a `user_roles` row for a named account. This story's DESIGN/PLANNING stages would then need to at least reference that command's existence (even if building it is tracked as a separate follow-up), so the story isn't shipped unusable.
