"""Add error_message column to recordings table.

Revision ID: 002
Revises: 001
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recordings",
        sa.Column("error_message", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recordings", "error_message")
