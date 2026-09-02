"""admin_users_invitation_tokens_and_audit_columns

Revision ID: a5edc35c8e96
Revises: db8cbd5e3697
Create Date: 2026-09-02 13:30:33.073977

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5edc35c8e96"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "db8cbd5e3697"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `create_table`/`create_index` below are guarded by the Rewriter in
    migrations/env.py (`if_not_exists=True`). `add_column` is not reached
    by the Rewriter (env.py: it only covers Create/DropTableOp and
    Create/DropIndexOp) so each is guarded explicitly here, per
    AGENTS.md §4.
    """
    op.create_table(
        "invitation_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_invitation_tokens_user_id"),
        "invitation_tokens",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_users_status_created_at",
        "users",
        ["status", "created_at"],
        unique=False,
        if_not_exists=True,
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    account_lifecycle_columns = {
        column["name"] for column in inspector.get_columns("account_lifecycle_audit_log")
    }
    if "reason" not in account_lifecycle_columns:
        op.add_column("account_lifecycle_audit_log", sa.Column("reason", sa.Text(), nullable=True))

    admin_audit_columns = {column["name"] for column in inspector.get_columns("admin_audit_log")}
    if "field" not in admin_audit_columns:
        op.add_column("admin_audit_log", sa.Column("field", sa.String(length=64), nullable=True))
    if "old_value" not in admin_audit_columns:
        op.add_column("admin_audit_log", sa.Column("old_value", sa.Text(), nullable=True))
    if "new_value" not in admin_audit_columns:
        op.add_column("admin_audit_log", sa.Column("new_value", sa.Text(), nullable=True))
    if "reason" not in admin_audit_columns:
        op.add_column("admin_audit_log", sa.Column("reason", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_status_created_at", table_name="users", if_exists=True)

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    admin_audit_columns = {column["name"] for column in inspector.get_columns("admin_audit_log")}
    if "reason" in admin_audit_columns:
        op.drop_column("admin_audit_log", "reason")
    if "new_value" in admin_audit_columns:
        op.drop_column("admin_audit_log", "new_value")
    if "old_value" in admin_audit_columns:
        op.drop_column("admin_audit_log", "old_value")
    if "field" in admin_audit_columns:
        op.drop_column("admin_audit_log", "field")

    account_lifecycle_columns = {
        column["name"] for column in inspector.get_columns("account_lifecycle_audit_log")
    }
    if "reason" in account_lifecycle_columns:
        op.drop_column("account_lifecycle_audit_log", "reason")

    op.drop_index(
        op.f("ix_invitation_tokens_user_id"), table_name="invitation_tokens", if_exists=True
    )
    op.drop_table("invitation_tokens", if_exists=True)
