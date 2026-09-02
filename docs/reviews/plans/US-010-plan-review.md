# Plan Review: Active Session Management (US-2.6 / spec US-010)

**Story ID:** US-2.6 (spec US-010)
**Plan Reviewed:** docs/plans/US-010-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-010-task-breakdown.md
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass with Issues

## Summary

The plan and task breakdown cover every file `US-010-impact-analysis.md` named, and task ordering respects `AGENTS.md` §3's downward-only direction and the migration-before-model-use rule with no violations. Risk and test-strategy sections are concrete and correctly split unit-fake vs. integration-on-real-infrastructure per `AGENTS.md` §5. Three issues keep this from a clean Pass: `app/core/config.py` and `.env.example` are touched by the plan and task breakdown but were never named in `US-010-impact-analysis.md`'s own affected-file survey; the plan's own Files To Modify bullet for `config.py` lists fewer settings than its own Risks section and the task breakdown both require; and the Risks section rates the new composite index's migration as uniformly "low" without addressing that `refresh_tokens` is a write-heavy table (every login/refresh inserts a row), which is exactly the class of hazard `AGENTS.md` §4/`migration-manager`'s own workflow calls out as needing an explicit `CREATE INDEX CONCURRENTLY` guard.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/users/models.py` (`AuthAuditLog.target_family`, new composite index) | Covered | Architectural Change #5, #1; Files To Modify; T2 | |
| `app/modules/users/schemas.py` (`SessionEntry`, `SessionListResponse`) | Covered | Files To Modify; T1 | |
| `app/modules/users/repository.py` (`list_live_families_for_user`, family-`created_at`/oldest-family query, `lock_families_for_user`, reused `get_refresh_token_by_hash`/`revoke_refresh_token_family`, `create_auth_audit_log_entry` signature change) | Covered | Architectural Change #1, #2; Files To Modify; T2 | |
| `app/modules/users/service.py` (`list_sessions`, `revoke_session`, login-path eviction) | Covered | Architectural Change #2, #3; Files To Modify; T5 | |
| `app/modules/users/router.py` (2 new routes) | Covered | Files To Modify; T6 | |
| `app/modules/users/dependencies.py` (no change) | Covered | Files To Modify (explicit "no change") | |
| `app/modules/users/exceptions.py` (`SessionNotFoundError`, `CurrentSessionError`) | Covered | Architectural Change #5; Files To Modify; T5 | |
| `app/core/geoip.py`, `app/core/device.py` (new) | Covered | Architectural Change #4; Files To Create; T4 | |
| Migration (`auth_audit_log.target_family`, new index) | Covered | Files To Modify; Risks; T3 | |
| New test files (unit: service + core primitives; integration: router + login-eviction + concurrency) | Covered | Files To Modify; Testing Strategy; T7, T8 | |
| Existing test files that change (`test_users_service.py` audit-signature ripple; existing login-flow tests) | Covered | Risks ("`create_auth_audit_log_entry` signature ripple"); T7 | |

## Risk Realism

- **[Medium] New `refresh_tokens` index rated "low" migration risk without addressing table write volume** — Plan says (Risks): "**Migration risk: low.** One additive nullable column (`auth_audit_log.target_family`) and one new index on an existing table — no `ALTER` narrows an existing column, no backfill needed." `refresh_tokens` is written on every login and every refresh-token rotation across the entire application (confirmed by `US-010-db-design.md`'s own description of the table's access pattern) — a plain `CREATE INDEX` on a table this active takes a lock that blocks concurrent writes for the index-build duration, exactly the hazard `migration-manager`'s own workflow flags as something "the Rewriter cannot reach" and requiring an explicit `autocommit_block()` + `if_not_exists=True` guard with `CREATE INDEX CONCURRENTLY`. The plan's "no backfill needed" framing addresses column-nullability risk correctly but doesn't address index-creation lock risk at all — these are two different hazards, and only one is covered.

## Scope Creep

- **[Medium] `app/core/config.py` and `.env.example` are touched but absent from `US-010-impact-analysis.md`'s survey** — Plan says (Files To Modify): "`app/core/config.py` — new setting(s) for the live-family cap... and the GeoLite2 database path" and (Risks): "`.env.example` gains `geoip_license_key` and a `geoip_database_path` setting." Neither file appears anywhere in `US-010-impact-analysis.md`'s "Affected files, by layer" section — the impact analysis's own survey is incomplete, not the plan's; the plan correctly identified work the impact analysis missed, but per this review's own precondition (the plan should build on a complete survey), this should be reconciled by updating `US-010-impact-analysis.md` rather than left as a plan-only addition with no upstream traceability record.
- **[Low] Plan's own `config.py` bullet is internally inconsistent with its Risks section and the task breakdown** — Plan says (Files To Modify): "new setting(s) for the live-family cap... and the GeoLite2 database path" — this omits `geoip_license_key`, which the plan's own Risks section names explicitly ("a new `geoip_license_key` setting") and which `US-010-task-breakdown.md`'s T4 row lists alongside `geoip_database_path` and `max_live_sessions_per_user`. A reader who only skims Files To Modify would miss one of three settings the plan elsewhere commits to adding.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage (every item that survey named is addressed) and correct task-breakdown layering order, so this doesn't Fail. However, the impact-analysis survey itself is incomplete (missing `config.py`/`.env.example`, surfaced by the plan rather than caught upstream), the plan's own Files To Modify section undercounts what its Risks section and the task breakdown both commit to, and the migration risk assessment doesn't address the write-heavy-table index-lock hazard `AGENTS.md` §4 exists to catch — all three should be resolved before IMPLEMENTATION begins.
