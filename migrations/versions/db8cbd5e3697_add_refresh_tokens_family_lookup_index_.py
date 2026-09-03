"""add_refresh_tokens_family_lookup_index_concurrently

Revision ID: db8cbd5e3697
Revises: 5dccea7a3749
Create Date: 2026-09-02 10:55:53.770733

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db8cbd5e3697"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "5dccea7a3749"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "ix_refresh_tokens_user_id_family_id_issued_at"


def upgrade() -> None:
    """Upgrade schema.

    `refresh_tokens` is written on every login and every refresh-token
    rotation (US-2.6-db-design.md) - a plain `CREATE INDEX` would lock the
    table against those writes for the build duration. `CONCURRENTLY`
    cannot run inside a transaction, so this migration is deliberately
    alone (plan-review finding, US-2.6-plan-review.md), wrapped in
    `autocommit_block()` per AGENTS.md §4 / migration-manager's
    postgres-hazards.md (a).
    """
    with op.get_context().autocommit_block():
        op.create_index(
            _INDEX_NAME,
            "refresh_tokens",
            ["user_id", "family_id", "issued_at"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.drop_index(
            _INDEX_NAME,
            table_name="refresh_tokens",
            postgresql_concurrently=True,
            if_exists=True,
        )
