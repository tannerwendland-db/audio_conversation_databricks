"""Add reconstructed_dialog_json column to transcripts

Revision ID: a1f269a0bcc1
Revises: 003
Create Date: 2026-01-05 12:41:05.308043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'a1f269a0bcc1'
down_revision: Union[str, None] = '928a3ece54d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reconstructed_dialog_json column for LLM-cleaned transcript text."""
    op.add_column(
        'transcripts',
        sa.Column('reconstructed_dialog_json', JSONB, nullable=True)
    )


def downgrade() -> None:
    """Remove reconstructed_dialog_json column."""
    op.drop_column('transcripts', 'reconstructed_dialog_json')
