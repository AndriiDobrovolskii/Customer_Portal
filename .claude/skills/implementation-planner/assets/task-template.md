# Task Breakdown — <StoryId>

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | schema-builder | schemas | — | app/modules/<module>/schemas.py | mypy clean; extra="forbid" present on inbound schemas |
| T2 | data-layer-builder | models/repository/cache | — | app/modules/<module>/models.py, repository.py[, cache.py] | mypy clean; no session.query() |
| T3 | migration-manager | migration | T2 | migrations/versions/<hash>_*.py | alembic upgrade head && alembic downgrade -1 && alembic upgrade head |
| T4 | service-and-router-builder (service) | service | T1, T3 | app/modules/<module>/service.py, exceptions.py | grep confirms zero fastapi/starlette imports |
| T5 | service-and-router-builder (router) | router | T4 | app/modules/<module>/router.py, dependencies.py | grep confirms zero sqlalchemy/models/repository imports |
| T6 | gate-enforcer | — | T1–T5 (+ test-writer) | — | pre-commit run --all-files; mypy app tests; lint-imports; pytest --cov |

Replace the example rows with the story's actual tasks. Keep the column order and header fixed so `story-orchestrator` and `plan-reviewer` can parse it consistently across stories.

**Field notes:**
- **Task ID** — sequential, `T1`, `T2`, ... in dependency order (not necessarily execution order if two tasks can run in parallel — note parallel-eligible tasks in a comment).
- **Skill to Invoke** — exactly one of the five execution skills, or `gate-enforcer`. Never a pipeline/review skill (those aren't part of this breakdown).
- **Layer** — the AGENTS.md §3 layer this task's output lives in.
- **Depends On** — Task IDs that must complete first; `—` if none.
- **Files Touched** — exact paths, not a module name alone.
- **Verification Command** — a concrete, runnable check specific to this task, not a restatement of "run the tests."
