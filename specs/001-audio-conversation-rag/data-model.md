# Data Model: Audio Conversation RAG System

**Feature**: 001-audio-conversation-rag
**Date**: 2025-12-17

## Overview

PostgreSQL database with pgvector extension hosted on Databricks Lakebase. Standard PostgreSQL authentication via environment variables. Migrations managed with Alembic.

## Entity Relationship Diagram

```
┌─────────────────────────────────────────┐
│              recordings                  │
├─────────────────────────────────────────┤
│ id (PK)           UUID                  │
│ title             VARCHAR(255)          │
│ original_filename VARCHAR(255)          │
│ volume_path       VARCHAR(500)          │
│ duration_seconds  FLOAT                 │
│ processing_status VARCHAR(50)           │
│ uploaded_by       VARCHAR(255)          │
│ created_at        TIMESTAMP             │
│ updated_at        TIMESTAMP             │
└──────────────────┬──────────────────────┘
                   │ 1
                   │
                   │ 1
┌──────────────────▼──────────────────────┐
│              transcripts                 │
├─────────────────────────────────────────┤
│ id (PK)           UUID                  │
│ recording_id (FK) UUID                  │
│ full_text         TEXT                  │
│ language          VARCHAR(10)           │
│ diarized_text     TEXT                  │
│ summary           TEXT                  │
│ created_at        TIMESTAMP             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│      langchain_pg_embedding              │
│      (managed by langchain-postgres)     │
├─────────────────────────────────────────┤
│ id (PK)           UUID                  │
│ collection_id (FK) UUID                 │
│ embedding         VECTOR(1024)          │
│ document          TEXT                  │
│ cmetadata         JSONB                 │
└─────────────────────────────────────────┘
```

## Entities

### Recording

Represents an uploaded audio file.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `title` | VARCHAR(255) | NOT NULL | Display title (auto-generated or user-provided) |
| `original_filename` | VARCHAR(255) | NOT NULL | Original uploaded filename |
| `volume_path` | VARCHAR(500) | NOT NULL | UC Volume path to audio file |
| `duration_seconds` | FLOAT | NULLABLE | Audio duration in seconds |
| `processing_status` | VARCHAR(50) | NOT NULL, DEFAULT 'pending' | Current processing state |
| `uploaded_by` | VARCHAR(255) | NULLABLE | Databricks user who uploaded |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Upload timestamp |
| `updated_at` | TIMESTAMP | NULLABLE | Last modification timestamp |

**Processing Status Values**:
- `pending` - Uploaded, awaiting processing
- `converting` - Converting to WAV format
- `diarizing` - Sending to diarization endpoint
- `embedding` - Generating vector embeddings
- `completed` - Successfully processed
- `failed` - Processing failed (check error in transcript)

**Indexes**:
- `idx_recordings_status` on `processing_status`
- `idx_recordings_created_at` on `created_at DESC`

### Transcript

Stores transcription and diarization results.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `recording_id` | UUID | FOREIGN KEY, UNIQUE | Reference to recording |
| `full_text` | TEXT | NOT NULL | Plain text transcription |
| `language` | VARCHAR(10) | NULLABLE | Detected language code |
| `diarized_text` | TEXT | NULLABLE | Text with speaker labels |
| `summary` | TEXT | NULLABLE | LLM-generated summary |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Relationships**:
- One-to-one with `recordings` via `recording_id`
- Cascade delete when recording is deleted

### Vector Embeddings (langchain-postgres managed)

The `langchain_pg_embedding` table is managed by `langchain-postgres`. We configure it but don't define the schema directly.

**Metadata Schema** (stored in `cmetadata` JSONB):
```json
{
  "recording_id": "uuid-string",
  "recording_title": "Call with Customer XYZ",
  "chunk_index": 0,
  "speaker": "Interviewer|Respondent|null",
  "source_type": "transcript"
}
```

## SQLAlchemy Models

### Recording Model

```python
# src/models/recording.py
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    CONVERTING = "converting"
    DIARIZING = "diarizing"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    volume_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ProcessingStatus.PENDING.value
    )
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )

    transcript: Mapped[Optional["Transcript"]] = relationship(
        "Transcript", back_populates="recording", cascade="all, delete-orphan"
    )
```

### Transcript Model

```python
# src/models/transcript.py
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .recording import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    recording_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recordings.id", ondelete="CASCADE"), unique=True
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    diarized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    recording: Mapped["Recording"] = relationship("Recording", back_populates="transcript")
```

## Alembic Migration

```python
# alembic/versions/001_initial_schema.py
"""Initial schema for audio conversation RAG.

Revision ID: 001
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa

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
        sa.Column("processing_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("uploaded_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # Create indexes for recordings
    op.create_index("idx_recordings_status", "recordings", ["processing_status"])
    op.create_index("idx_recordings_created_at", "recordings", ["created_at"])

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
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transcripts")
    op.drop_index("idx_recordings_created_at", table_name="recordings")
    op.drop_index("idx_recordings_status", table_name="recordings")
    op.drop_table("recordings")
```

## Vector Store Configuration

```python
# src/services/embedding.py
from langchain_postgres import PGVector
from databricks_langchain import DatabricksEmbeddings
import os

def get_vector_store() -> PGVector:
    """Get configured PGVector store."""
    embeddings = DatabricksEmbeddings(
        endpoint="databricks-gte-large-en"  # Or other embedding endpoint
    )

    connection_string = (
        f"postgresql+psycopg://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:5432/"
        f"{os.getenv('POSTGRES_DB')}"
    )

    return PGVector(
        embeddings=embeddings,
        collection_name="transcript_chunks",
        connection=connection_string,
        use_jsonb=True,
    )
```

## Validation Rules

### Recording

| Field | Validation |
|-------|------------|
| `title` | Required, max 255 chars, non-empty after trim |
| `original_filename` | Required, max 255 chars, must have valid extension |
| `volume_path` | Required, must start with `/Volumes/` |
| `duration_seconds` | If present, must be > 0 |
| `processing_status` | Must be valid ProcessingStatus value |

### Transcript

| Field | Validation |
|-------|------------|
| `recording_id` | Required, must reference existing recording |
| `full_text` | Required, non-empty |
| `language` | If present, must be valid ISO 639-1 code |

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_HOST` | Lakebase PostgreSQL host | `lakebase-xxx.databricks.com` |
| `POSTGRES_USER` | Database username | `audio_rag_user` |
| `POSTGRES_PASSWORD` | Database password | (from Databricks secret) |
| `POSTGRES_DB` | Database name | `audio_rag` |
