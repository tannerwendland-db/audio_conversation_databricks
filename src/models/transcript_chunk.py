"""TranscriptChunk SQLAlchemy model for vector storage."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .recording import Recording


class TranscriptChunk(Base):
    """Model for transcript chunks with vector embeddings.

    Stores chunked transcript text with associated embeddings for
    similarity search. Linked to recordings with CASCADE delete.
    """

    __tablename__ = "transcript_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    recording_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    recording: Mapped["Recording"] = relationship("Recording", back_populates="transcript_chunks")

    def __repr__(self) -> str:
        """Return string representation of the TranscriptChunk."""
        return (
            f"<TranscriptChunk(id={self.id!r}, recording_id={self.recording_id!r}, "
            f"chunk_index={self.chunk_index})>"
        )
