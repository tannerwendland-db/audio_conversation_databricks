"""SQLAlchemy models for the Audio Conversation RAG system."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


from .recording import ProcessingStatus, Recording
from .speaker_embedding import SpeakerEmbedding
from .transcript import Transcript
from .transcript_chunk import TranscriptChunk

__all__ = [
    "Base",
    "Recording",
    "ProcessingStatus",
    "SpeakerEmbedding",
    "Transcript",
    "TranscriptChunk",
]
