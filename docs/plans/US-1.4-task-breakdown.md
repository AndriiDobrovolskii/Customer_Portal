# Task Breakdown — US-1.4

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T0a | *(none — see Open Question below)* | infra | — | `pyproject.toml` (`[project] dependencies`, add `redis>=5.0`) | `pip install -e .` (or project's install command) succeeds; import `redis.asyncio` resolves |
| T0b | *(none — see Open Question below)* | infra | T0a | `app/core/config.py` (`valkey_url` setting) | `mypy app/core/config.py` clean; `Settings().valkey_url` resolves from `.env`/default |
| T0c | *(none — see Open Question below)* | infra | T0a | `app/main.py` (`lifespan`: create/dispose Valkey client, `app.state.valkey_client`) | app starts locally (`uvicorn app.main:app`) without error; shutdown disposes cleanly |
| T0d | *(none — see Open Question below)* | infra | T0c | `app/db/dependencies.py` (`get_valkey_client`) | `mypy` clean; grep confirms it mirrors `get_db_session`'s request-scoped shape |
| T0e | *(none — see Open Question below)* | infra | T0a | `app/core/cache_keys.py` (new — `revoke_before` prefix helper) | `mypy` clean; no business logic beyond key formatting (grep: no `import` of any `app.modules.*`) |
| T0f | *(none — see Open Question below)* | infra | T0e, T0d | `app/core/revocation_cache.py` (new — `RevocationCache` gateway; corrected here from the plan's original `account/cache.py`, see impact-analysis Addendum 2) | mypy clean; grep confirms no `import` of any `app.modules.*`; write includes a TTL (grep: `ex=`) |
| T1 | schema-builder | schemas | — | `app/modules/account/schemas.py` (`DeactivateAccountRequest`, `DeactivateAccountResponse`) | mypy clean; `extra="forbid"` present on `DeactivateAccountRequest` |
| T2 | schema-builder | schemas | — | `app/modules/users/schemas.py` (extend `UserStatus` with `ACTIVE`, `DEACTIVATED`) | mypy clean; grep confirms `PENDING_VERIFICATION` untouched, only new members added |
| T3 | data-layer-builder | models/repository | — | `app/modules/account/models.py` (`AccountLifecycleAuditLog`), `repository.py` | mypy clean; `grep -L "session.query"` on repository.py |
| T4 | data-layer-builder | models | — | `app/modules/users/models.py` (add `deactivated_at` column) | mypy clean; `Mapped[datetime \| None]` present, no `server_default` (per db-design.md) |
| T5 | migration-manager | migration | T3, T4 | `migrations/versions/<hash>_add_account_deactivation.py` | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all succeed |
| T6 | service-and-router-builder (service) | service | T1, T2, T3, T5, T0f | `app/modules/account/service.py`, `app/modules/account/exceptions.py` (`AlreadyDeactivatedError`, `InvalidPasswordError` — both local, no cross-module import; see plan Architectural Change 7, revised) | grep confirms zero `fastapi`/`starlette`/`HTTPException` imports in `service.py`; grep confirms zero `app.modules.users` imports anywhere in `account/` |
| T7 | service-and-router-builder (service) | service | T5, T0f | `app/modules/users/service.py` (extend `get_authenticated_user` with `revoke_before` check; new `Protocol` for the cache-read collaborator; fail-closed on read error per plan Architectural Change 4) | grep confirms zero `fastapi`/`starlette` imports; mypy clean on new `Protocol`; unit test proves a raising fake is rejected, not accepted |
| T8 | service-and-router-builder (router) | router/dependencies | T6 | `app/modules/account/router.py`, `app/modules/account/dependencies.py`, **and registering `account_router` in `app/api/v1/router.py`** (missed by both impact-analysis and the plan — see impact-analysis Addendum 2) | grep confirms zero `sqlalchemy`/`models`/`repository` imports in `router.py`; `app.openapi()["paths"]` contains `/api/v1/account/deactivate` |
| T9 | service-and-router-builder (dependencies) | dependencies | T7, T0f | `app/modules/users/dependencies.py` (inject cache-read collaborator into `get_user_service`) | grep confirms `AccountServiceDep`-style typed injection, no raw client construction |
| T10 | *(none — see Open Question below)* | test infra | T0c | `tests/conftest.py` (Valkey testcontainer fixture, flushed/namespaced per test) | fixture used successfully by T11/T12's first passing run |
| T11 | test-writer | tests | T6 | `tests/unit/modules/account/test_account_service.py` | `pytest tests/unit/modules/account/ -v` all pass |
| T12 | test-writer | tests | T7 | `tests/unit/modules/users/test_users_service.py` (extended) | `pytest tests/unit/modules/users/ -v` all pass |
| T13 | test-writer | tests | T8, T10 | `tests/integration/modules/account/test_account_router.py` | `pytest tests/integration/modules/account/ -v` all pass against real PG+Valkey |
| T14 | gate-enforcer | — | T0a–T13 | — | `pre-commit run --all-files`; `mypy app tests`; `lint-imports`; `pytest --cov=app --cov-report=term-missing --cov-fail-under=85` |

**Parallel-eligible:** T1 ∥ T2 ∥ T4 (independent schema/model edits); T3 has no dependency on T1/T2/T4. T11 ∥ T12 once their respective service tasks (T6/T7) land.

## Open Question: T0a–T0f, T10 have no owning execution skill

This project's five execution skills (`schema-builder`, `data-layer-builder`, `migration-manager`, `service-and-router-builder`, plus `gate-enforcer`) are all scoped to a module's own `app/modules/<module>/` files or a migration. None of them own:

- `pyproject.toml` dependency additions,
- `app/core/config.py` / `app/main.py` / `app/db/dependencies.py` (shared app wiring, not module-scoped),
- new cross-module `app/core/cache_keys.py` and `app/core/revocation_cache.py`,
- `tests/conftest.py` shared fixture additions.

Per this skill's own constraint 4 ("flag as an open question rather than inventing scope"), these are named here rather than silently assigned to one of the five skills. Recommendation: treat T0a–T0f and T10 as direct, unassisted implementation steps (no skill invocation) since they're one-time infra plumbing this story happens to be first to need — not a gap worth creating a sixth execution skill for, given `US-2.1`/`US-2.2`/`US-2.3` will only ever *read* this infra, not repeat building it. `plan-reviewer` should confirm this framing before `story-orchestrator` proceeds.
