"""Transcript SQLAlchemy model for Audio Conversation RAG System."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

# Use JSONB on PostgreSQL, JSON on other databases (SQLite for tests)
JsonType = JSON().with_variant(JSONB(), "postgresql")

if TYPE_CHECKING:
    from .recording import Recording


class Transcript(Base):
    """Model representing a transcript of an audio recording."""

    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    recording_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recordings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    diarized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dialog_json: Mapped[list[dict] | None] = mapped_column(JsonType, nullable=True)
    reconstructed_dialog_json: Mapped[list[dict] | None] = mapped_column(JsonType, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    recording: Mapped[Recording] = relationship("Recording", back_populates="transcript")
