"""admin_users_email_display_name_trgm_index

Revision ID: 1b2b1d52dd71
Revises: a5edc35c8e96
Create Date: 2026-09-02 13:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b2b1d52dd71"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "a5edc35c8e96"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMAIL_INDEX_NAME = "ix_users_email_trgm"
_DISPLAY_NAME_INDEX_NAME = "ix_users_display_name_trgm"


def upgrade() -> None:
    """Upgrade schema.

    `users` is written on every registration/login/profile-update
    (US-3.1-db-design.md) - a plain `CREATE INDEX` would lock the table
    against those writes for the build duration. `CONCURRENTLY` cannot
    run inside a transaction, so this migration is deliberately alone
    (plan-review finding, US-3.1-plan-review.md), wrapped in
    `autocommit_block()` per AGENTS.md §4, mirroring
    db8cbd5e3697_add_refresh_tokens_family_lookup_index_.py's identical
    precedent. `CREATE EXTENSION IF NOT EXISTS` is already idempotent at
    the SQL level - no separate `sa.inspect()` guard needed, same
    reasoning as `if_not_exists=True` on `create_index`.

    Two separate trigram indexes (not one composite) because FR-1's `q`
    search is `email ILIKE %q% OR display_name ILIKE %q%` - a GIN
    trigram index accelerates each column's own ILIKE independently, not
    a two-column OR as a single composite index.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        op.create_index(
            _EMAIL_INDEX_NAME,
            "users",
            ["email"],
            unique=False,
            postgresql_concurrently=True,
            postgresql_using="gin",
            postgresql_ops={"email": "gin_trgm_ops"},
            if_not_exists=True,
        )
        op.create_index(
            _DISPLAY_NAME_INDEX_NAME,
            "users",
            ["display_name"],
            unique=False,
            postgresql_concurrently=True,
            postgresql_using="gin",
            postgresql_ops={"display_name": "gin_trgm_ops"},
            if_not_exists=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.drop_index(
            _DISPLAY_NAME_INDEX_NAME,
            table_name="users",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            _EMAIL_INDEX_NAME,
            table_name="users",
            postgresql_concurrently=True,
            if_exists=True,
        )
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
