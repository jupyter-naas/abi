"""add opencode tables

Revision ID: 20260413_add_opencode_tables
Revises:
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260413_add_opencode_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opencode_sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("opencode_id", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("workdir", sa.Text(), nullable=False),
        sa.Column("abi_thread_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_opencode_sessions_opencode_id", "opencode_sessions", ["opencode_id"]
    )

    op.create_table(
        "opencode_messages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("parts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["opencode_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opencode_file_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("diff", sa.Text(), nullable=True),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["opencode_messages.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["opencode_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("opencode_file_events")
    op.drop_table("opencode_messages")
    op.drop_index("ix_opencode_sessions_opencode_id", table_name="opencode_sessions")
    op.drop_table("opencode_sessions")
