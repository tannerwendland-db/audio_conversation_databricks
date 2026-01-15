"""Add dialog_json column to transcripts

Revision ID: 928a3ece54d0
Revises: 003
Create Date: 2026-01-05 12:44:48.941296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '928a3ece54d0'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add dialog_json JSONB column for structured dialog data."""
    op.add_column(
        'transcripts',
        sa.Column('dialog_json', JSONB, nullable=True)
    )


def downgrade() -> None:
    """Remove dialog_json column."""
    op.drop_column('transcripts', 'dialog_json')
