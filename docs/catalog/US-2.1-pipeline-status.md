# Pipeline Status: US-2.1

**Active story confirmed:** Yes — user explicitly requested continuing from `docs/stories/US-2.1-login.md` on 2026-08-31, after US-1.4 (previous active story) reached PR, was committed (`e3b42c4`), and was merged as PR #1.
**Last updated:** 2026-08-31

| Stage | Sub-step | Skill | Status | Verdict | Notes |
|---|---|---|---|---|---|
| CLARIFICATION | — | us-clarifier | Done | **Ready for Specification** (was "Not Ready", resolved by user 2026-08-31) | docs/decisions/US-2.1-open-decisions.md (7 items, all resolved), docs/evidence/US-2.1-clarification-report.md. Run retroactively — spec+review already existed outside this pipeline. |
| SPECIFICATION | — | story-spec-writer | Done | — | docs/specifications/US-2.1-spec.md revised 2026-08-31 to incorporate OD-1–OD-7; Open Questions section removed (all resolved) |
| SPEC_REVIEW | — | story-spec-reviewer | Done | **Pass with Issues** (accepted by user 2026-08-31) | docs/reviews/specifications/US-2.1-spec-review.md. OD-8 (empty-password → 422) raised here and folded back into FR-6. |
| DESIGN | API | openapi-designer | Done | — (2 Open Questions logged, deferred to PLANNING) | docs/designs/api/US-2.1-openapi.yaml, US-2.1-api-design.md |
| DESIGN | DB | db-designer | Done | — (2 items deferred to PLANNING: request_id nullability on unauthenticated route, module placement) | docs/designs/database/US-2.1-db-design.md, US-2.1-entity-model.md. New `users.last_login_at`, new `auth_audit_log` table |
| PLANNING | Impact analysis | impact-analyzer | Done | — | docs/impact-analysis/US-2.1-impact-analysis.md. Found `refresh_tokens` table gap (OD-9), resolved by user 2026-08-31 — build a minimal table now. DB design amended accordingly. |
| PLANNING | Plan | planner | Done | — | docs/plans/US-2.1-implementation-plan.md |
| PLANNING | Task breakdown | implementation-planner | Done | — | docs/plans/US-2.1-task-breakdown.md. T0a-T0e flagged unowned infra plumbing, same pattern accepted for US-1.4. |
| PLANNING | Plan review | plan-reviewer | Done | Pass with Issues (2 Low findings, both fixed same-day; OD-10 addendum added 2026-08-31) | docs/reviews/plans/US-2.1-plan-review.md |
| TESTS | — | test-writer | Done | — | docs/tests/US-2.1-ac-test-matrix.md (traceability matrix only; test code deferred to IMPLEMENTATION per task-breakdown sequencing, same as US-1.4) |
| IMPLEMENTATION | Schemas (T1) | schema-builder | Done | mypy clean | users/schemas.py (LoginRequest min_length, LoginResponse token_type/expires_in) |
| IMPLEMENTATION | Data layer (T2, T2b) | data-layer-builder | Done | imports clean | users/{models,repository,cache}.py (AuthAuditLog, RefreshToken, last_login_at, LoginThrottleCache); account/repository.py (reactivate_if_within_grace) |
| IMPLEMENTATION | Migration (T3) | migration-manager | Done, **verified** | upgrade/downgrade/upgrade proven clean via a standalone Postgres container; found and worked around a pre-existing env.py bug (account.models never imported, causing a spurious drop of account_lifecycle_audit_log) — fixed with user sign-off | migrations/versions/1cdc08e88be9_add_login_audit_and_refresh_tokens.py; migrations/env.py (1-line fix, user-approved) |
| IMPLEMENTATION | Service (T4b, T4) | service-and-router-builder | Done | imports clean | account/service.py (reactivate_account); users/service.py (authenticate_user reworked), users/exceptions.py (InvalidCredentialsError->ProblemError, AccountDeactivatedError, TooManyAttemptsError) |
| IMPLEMENTATION | Router/Deps (T5, T0e) | service-and-router-builder / direct | Done | routes registered, imports clean | users/router.py, users/dependencies.py; app/main.py (removed redundant handler, reworked validation-error handler to problem+json) |
| IMPLEMENTATION | Infra (T0a-T0d) | *(unowned, direct)* | Done | imports clean | core/config.py, cache_keys.py, security.py (dummy-verify, refresh-token gen); .env.example |
| IMPLEMENTATION | Tests (T6, T6b, T8) | test-writer | Done, **verified** | 39/39 + 6/6 + 25/25 pass on real Postgres+Valkey (testcontainers) | tests/unit/modules/users/test_users_service.py (extended), tests/unit/modules/account/test_account_service.py (extended), tests/integration/modules/users/test_users_router.py (extended). T7 dropped — no unit-test precedent exists for a cache gateway in this codebase (RevocationCache has none either); LoginThrottleCache verified via T8 integration tests instead, per AGENTS.md §5. |
| IMPLEMENTATION | Gate (T9) | gate-enforcer | Done | **PASS** — 7/7 pre-commit hooks green, mypy strict clean (81 files), lint-imports clean (6/6), 163/163 tests pass, 97.16% coverage (floor 85%), migration cycle proven | Fixed a machine-level environment blocker (Windows Application Control policy blocking mypy's/import-linter's compiled binaries) by reinstalling both as pure-Python builds — unrelated to this story's code. One pre-existing flaky test (US-1.4's concurrent-deactivation test) failed once under load, passed on isolation and full re-run. |
| VERIFICATION | — | implementation-verifier | Done | Pass | docs/verification/US-2.1-implementation-verification.md |
| SECURITY_REVIEW | — | security-reviewer | Done | Pass | docs/reviews/security/US-2.1-security-review.md |
| RECONCILIATION | — | reconciliation-reviewer | Done | Pass (1 gap found+fixed same-day: missing dummy-verify test, which caught a real always-True logic bug in verify_password_dummy) | docs/reviews/reconciliation/US-2.1-reconciliation.md |
| PR | — | pr-preparer | Done | Draft ready | docs/pr/US-2.1-pr-summary.md. Found+fixed (user-approved): 11 stale directory `.gitignore` files that had silently excluded every pipeline doc (including all of US-1.4's) from git since those directories were first created. |

## Blocking Stage (if any)

None. Story reached PR with every stage Pass. Draft ready for user review at `docs/pr/US-2.1-pr-summary.md`; nothing committed or pushed yet.
