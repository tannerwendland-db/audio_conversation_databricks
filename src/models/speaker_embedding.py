"""SpeakerEmbedding model for storing speaker voice fingerprints."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .recording import Recording


class SpeakerEmbedding(Base):
    """SQLAlchemy model for speaker voice embeddings.

    Stores voice fingerprint vectors extracted from audio recordings
    for cross-chunk speaker identification and matching.
    """

    __tablename__ = "speaker_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    recording_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    recording: Mapped["Recording"] = relationship("Recording", back_populates="speaker_embeddings")

    def __repr__(self) -> str:
        """Return string representation of the SpeakerEmbedding."""
        return (
            f"<SpeakerEmbedding(id={self.id!r}, recording_id={self.recording_id!r}, "
            f"speaker_label={self.speaker_label!r})>"
        )
