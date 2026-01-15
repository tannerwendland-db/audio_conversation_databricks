"""Initial schema for Audio Conversation RAG System.

Revision ID: 001
Revises: None
Create Date: 2025-12-17

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create recordings table
    op.create_table(
        "recordings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("volume_path", sa.String(500), nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column(
            "processing_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("uploaded_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # Create indexes on recordings
    op.create_index(
        "idx_recordings_status",
        "recordings",
        ["processing_status"],
    )
    op.create_index(
        "idx_recordings_created_at",
        "recordings",
        ["created_at"],
    )

    # Create transcripts table
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "recording_id",
            sa.String(36),
            sa.ForeignKey("recordings.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("full_text", sa.Text, nullable=False),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("diarized_text", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Drop transcripts table
    op.drop_table("transcripts")

    # Drop indexes on recordings
    op.drop_index("idx_recordings_created_at", table_name="recordings")
    op.drop_index("idx_recordings_status", table_name="recordings")

    # Drop recordings table
    op.drop_table("recordings")
