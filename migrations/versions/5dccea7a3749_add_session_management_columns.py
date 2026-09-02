"""add_session_management_columns

Revision ID: 5dccea7a3749
Revises: cef55228a927
Create Date: 2026-09-02 10:55:02.198632

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5dccea7a3749"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "cef55228a927"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # add_column is not reached by env.py's Rewriter (only Create/DropTableOp
    # and Create/DropIndexOp are) - guarded per AGENTS.md §4/2c77dd65027b's
    # established pattern. The new composite index on refresh_tokens is a
    # separate migration (see 8f1a2b3c4d5e) - CREATE INDEX CONCURRENTLY
    # cannot run inside this migration's transaction.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("auth_audit_log")}
    if "target_family" not in columns:
        op.add_column("auth_audit_log", sa.Column("target_family", sa.Uuid(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("auth_audit_log")}
    if "target_family" in columns:
        op.drop_column("auth_audit_log", "target_family")
