# PostgreSQL Migration Hazards — Skeletons

No exemplar for (a)/(b) exists in this repo yet (`migrations/versions/` currently has no concurrent-index or enum-alter migration) — these are built directly from `AGENTS.md` §4, not copied from in-repo code.

## (a) `CREATE INDEX CONCURRENTLY`

Must be alone in its own migration — it cannot run inside the transaction Alembic wraps every migration in by default.

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_users_pending_email",
            "users",
            ["pending_email"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_users_pending_email",
            table_name="users",
            postgresql_concurrently=True,
            if_exists=True,
        )
```

A failed `CONCURRENTLY` build leaves an **invalid** index behind — `if_not_exists=True` avoids a hard failure on retry, but doesn't fix a prior invalid index; if one is suspected, that's an operational cleanup (`DROP INDEX CONCURRENTLY` then retry), not something this migration's guard can detect for you.

## (b) `ALTER TYPE ... ADD VALUE`

PG15 will not let a transaction use an enum value it just added — split across two migrations (or two separate non-transactional statements if truly the same deploy):

```python
# Migration N: add the value only.
def upgrade() -> None:
    op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'SUSPENDED'")


def downgrade() -> None:
    # PostgreSQL has no ALTER TYPE ... DROP VALUE. Document the limitation
    # rather than pretending to reverse it — a real downgrade here means
    # recreating the type without the value, which is its own migration
    # with its own data-safety review; do not silently no-op downgrade().
    raise NotImplementedError(
        "Removing an enum value requires recreating the type; see migration <id> for the plan."
    )


# Migration N+1 (a separate deploy or, at minimum, a separate revision): use
# the new value in application logic / a backfill.
```

## (c) Idempotent, batched backfill

```python
def upgrade() -> None:
    bind = op.get_bind()
    while True:
        result = bind.execute(
            sa.text(
                "UPDATE users SET status = 'PENDING_VERIFICATION' "
                "WHERE id IN (SELECT id FROM users WHERE status IS NULL LIMIT 500) "
                "RETURNING id"
            )
        )
        if result.rowcount == 0:
            break
```

`WHERE status IS NULL` makes a re-run of this migration (e.g. after a partial failure) a no-op past the point it already reached — this is what "idempotent" means for a backfill, distinct from the `if_not_exists`/`if_exists` guards that make DDL idempotent.

## (d) Expand → migrate → contract

For a destructive change (dropping a column the current release still reads), split across releases rather than one migration:

1. **Expand** — add the new column/table alongside the old one; both are populated.
2. **Migrate** — deploy application code that reads/writes only the new shape; backfill any remaining old rows.
3. **Contract** — a later migration (a later release, once nothing reads the old column) drops it.

Never collapse this into one migration just because it's technically possible in a single transaction — the hazard is the *application code* still running against the old shape during a rolling deploy, not the SQL itself.
