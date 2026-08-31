# Pipeline Status: US-004

**Active story confirmed:** Yes — user confirmed 2026-08-30 (previous active-story.yaml pointed to US-002, stale/inferred; US-001–003 already implemented outside this pipeline).
**Last updated:** 2026-08-30

| Stage | Sub-step | Skill | Status | Verdict | Notes |
|---|---|---|---|---|---|
| CLARIFICATION | — | us-clarifier | Pre-existing — not run in this pipeline | — | docs/specifications/US-004-deactivate-account-spec.md cites source story |
| SPECIFICATION | — | story-spec-writer | Pre-existing — not run in this pipeline | — | docs/specifications/US-004-deactivate-account-spec.md |
| SPEC_REVIEW | — | story-spec-reviewer | Done | Pass | docs/reviews/specifications/US-004-spec-review.md:7 |
| DESIGN | API | openapi-designer | Done | — (no formal verdict; see Open Questions) | docs/designs/api/US-004-openapi.yaml, US-004-api-design.md. Logged: revocation-substrate mismatch (Valkey `revoke_before` vs. current `user_sessions.revoked_at`), deferred to PLANNING |
| DESIGN | DB | db-designer | Done | — (deferred items logged) | docs/designs/database/US-004-db-design.md, US-004-entity-model.md. New `users.deactivated_at`, new `account_lifecycle_audit_log` table. Deferred to PLANNING: revocation substrate, module placement (`app/modules/account/`) |
| PLANNING | Impact analysis | impact-analyzer | Done | — | docs/impact-analysis/US-004-impact-analysis.md. New `account` module + first-time Valkey infra (client dep, lifespan pool, config, test fixtures) |
| PLANNING | Plan | planner | Done | Pass | docs/plans/US-004-implementation-plan.md. Dependency sign-off APPROVED 2026-08-30: `redis>=5.0` |
| PLANNING | Task breakdown | implementation-planner | Done | — | docs/plans/US-004-task-breakdown.md. 14 tasks + T0a-e/T10 flagged as unowned infra plumbing (no skill in the 5-skill roster covers app-wide wiring) |
| PLANNING | Plan review | plan-reviewer | Done | Pass (re-review; initial was Fail, fixed) | docs/reviews/plans/US-004-plan-review.md |
| TESTS | Traceability matrix | test-writer | Done | — | docs/tests/US-004-traceability-matrix.md. 17 test cases planned; test *code* deferred to T11-T13 alongside its layer (see matrix's sequencing note) |
| IMPLEMENTATION | Infra (T0a-T0e) | *(unowned, direct)* | Done | mypy clean, `import app.main` clean | pyproject.toml (redis>=5.0), config.py, main.py lifespan, db/dependencies.py, core/cache_keys.py |
| IMPLEMENTATION | Schemas (T1,T2) | schema-builder | Done | mypy clean | account/schemas.py, users/schemas.py (UserStatus +ACTIVE/+DEACTIVATED) |
| IMPLEMENTATION | Data layer (T3,T4) | data-layer-builder | Done | mypy clean | account/models.py, repository.py, cache.py; users/models.py (deactivated_at) |
| IMPLEMENTATION | Migration (T5) | migration-manager | Done, **verified** | chain valid (`alembic heads`); upgrade/downgrade/upgrade cycle proven via tests/conftest.py's testcontainer fixture across multiple full pytest runs, no errors | migrations/versions/7e371ad49a0a_add_account_deactivation.py |
| IMPLEMENTATION | Service/Router (T6-T9) | service-and-router-builder | Done | mypy/ruff/lint-imports clean | account/service.py, account/exceptions.py, users/service.py (revoke_before + fail-closed), account/router.py, account/dependencies.py, users/dependencies.py, api/v1/router.py registration |
| IMPLEMENTATION | Tests (T10-T13) | test-writer | Done, **verified** | 145/145 pass, 96.84% coverage (threshold 85%), 3 consecutive clean full-suite runs | tests/conftest.py (Valkey fixture), test_account_service.py, test_users_service.py (extended), test_account_router.py |
| IMPLEMENTATION | Gate (T14) | gate-enforcer | Done | **PASS** — all 7 pre-commit hooks green (ruff lint/format, mypy strict, lint-imports 6/6, pytest 145/145, no-mock-in-integration, secrets) plus all Part B runtime-rule/§6.7 spot-checks | Docker was started mid-session (was down, not absent); two bugs found and fixed during real-infra verification: a fixture teardown using the wrong event loop, and a test helper relying on Postgres transaction-frozen `now()` for timestamps it needed to compare against wall-clock time |
| VERIFICATION | — | implementation-verifier | Done | Pass | docs/verification/US-004-verification-report.md |
| SECURITY_REVIEW | — | security-reviewer | Done | Pass | docs/security/US-004-security-review.md |
| RECONCILIATION | — | reconciliation-reviewer | Done | Pass | docs/reconciliation/US-004-reconciliation-report.md. Found+fixed: traceability matrix test-name drift (not a coverage gap) |
| PR | — | pr-preparer | Done | Draft ready | docs/pr/US-004-pr-description.md. Flagged: exclude pre-existing unrelated `.claude/skills/*` changes from this story's commit |

## Blocking Stage (if any)

None. Story reached PR with every stage Pass. Committed on `feat/us-004-deactivate-account` (`e3b42c4`), pushed, PR opened: https://github.com/AndriiDobrovolskii/Customer_Portal/pull/1. Pre-existing unrelated `.claude/skills/*` changes were left untouched/uncommitted, per the commit-hygiene flag.
