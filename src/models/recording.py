"""Recording model for storing audio recording metadata."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .speaker_embedding import SpeakerEmbedding
    from .transcript import Transcript
    from .transcript_chunk import TranscriptChunk


class ProcessingStatus(str, Enum):
    """Enum representing the processing status of a recording."""

    PENDING = "pending"
    CONVERTING = "converting"
    DIARIZING = "diarizing"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


class Recording(Base):
    """SQLAlchemy model for audio recordings.

    Stores metadata about uploaded audio files including their location
    in Databricks UC Volumes and processing status.
    """

    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    volume_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ProcessingStatus.PENDING.value
    )
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )

    # Relationships
    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="recording",
        cascade="all, delete-orphan",
        uselist=False,
    )
    transcript_chunks: Mapped[list["TranscriptChunk"]] = relationship(
        "TranscriptChunk",
        back_populates="recording",
        cascade="all, delete-orphan",
    )
    speaker_embeddings: Mapped[list["SpeakerEmbedding"]] = relationship(
        "SpeakerEmbedding",
        back_populates="recording",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Return string representation of the Recording."""
        return (
            f"<Recording(id={self.id!r}, title={self.title!r}, status={self.processing_status!r})>"
        )
