# App Internal Contracts: Speaker Embedding Handling

**Module**: `src/services/audio.py`
**Date**: 2026-01-14

## DiarizeResponse (Modified)

### Current Definition

```python
@dataclass
class DiarizeResponse:
    status: str
    dialog: str | None
    transcription: str | None
    error: str | None
```

### Updated Definition

```python
@dataclass
class DiarizeResponse:
    status: str
    dialog: str | None
    transcription: str | None
    speaker_embeddings: dict[str, list[float]] | None  # NEW
    error: str | None
```

### Field Description

| Field | Type | Description |
|-------|------|-------------|
| status | str | "success" or "error" |
| dialog | str \| None | Combined diarized transcript from all chunks |
| transcription | str \| None | Combined raw transcription from all chunks |
| speaker_embeddings | dict[str, list[float]] \| None | Final speaker embeddings (accumulated from all chunks) |
| error | str \| None | Error message if status is "error" |

## Internal Functions

### _diarize_single_chunk (Modified)

```python
def _diarize_single_chunk(
    wav_bytes: bytes,
    client: WorkspaceClient,
    endpoint_name: str,
    reference_embeddings: dict[str, list[float]] | None = None,
    chunk_index: int = 0,
) -> DiarizeResponse:
    """
    Send a single audio chunk to Databricks serving endpoint for diarization.

    Args:
        wav_bytes: WAV audio data to diarize.
        client: WorkspaceClient instance.
        endpoint_name: Name of the diarization endpoint.
        reference_embeddings: Optional dict of label -> embedding for cross-chunk matching.
        chunk_index: 0-based index of current chunk (for logging/debugging).

    Returns:
        DiarizeResponse containing dialog, transcription, speaker_embeddings, and status.
    """
```

### diarize_audio (Modified Behavior)

```python
def diarize_audio(wav_bytes: bytes | None) -> DiarizeResponse:
    """
    Send audio to Databricks serving endpoint for diarization.

    For audio requiring chunking:
    1. Process chunk 0 to get initial speaker embeddings
    2. For chunks 1..N, pass accumulated reference_embeddings
    3. Update reference set with any new speakers detected
    4. Combine dialogs and transcriptions
    5. Return final accumulated speaker_embeddings

    Args:
        wav_bytes: WAV audio data to diarize. Can be None or empty.

    Returns:
        DiarizeResponse with combined results and final speaker embeddings.
    """
```

## SpeakerEmbedding Model

### SQLAlchemy Model

```python
# src/models/speaker_embedding.py

from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from . import Base

class SpeakerEmbedding(Base):
    """SQLAlchemy model for speaker voice embeddings."""

    __tablename__ = "speaker_embeddings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    recording_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_vector: Mapped[list[float]] = mapped_column(
        Vector(512), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    recording: Mapped["Recording"] = relationship(
        "Recording", back_populates="speaker_embeddings"
    )
```

## Recording Service Extensions

### save_speaker_embeddings

```python
def save_speaker_embeddings(
    session: Session,
    recording_id: str,
    embeddings: dict[str, list[float]],
) -> list[SpeakerEmbedding]:
    """
    Persist speaker embeddings for a recording.

    Replaces any existing embeddings for the recording (per spec clarification:
    re-processing replaces embeddings).

    Args:
        session: SQLAlchemy session.
        recording_id: ID of the parent recording.
        embeddings: Dict mapping speaker labels to embedding vectors.

    Returns:
        List of created SpeakerEmbedding instances.
    """
```

### delete_speaker_embeddings

```python
def delete_speaker_embeddings(
    session: Session,
    recording_id: str,
) -> int:
    """
    Delete all speaker embeddings for a recording.

    Args:
        session: SQLAlchemy session.
        recording_id: ID of the recording.

    Returns:
        Number of embeddings deleted.
    """
```

## Error Handling

### New Exception Types

None required. Existing `AudioProcessingError` covers embedding-related failures.

### Error Flow

1. Model endpoint returns error → `DiarizeResponse.status = "error"`
2. Embedding parsing fails → `DiarizeResponse.status = "error"`, log warning
3. Database save fails → Raise existing SQLAlchemy exceptions, caught at service layer

## Testing Contracts

### Unit Test Expectations

```python
# test_embedding_matching.py

def test_cosine_similarity_identical_vectors():
    """Identical vectors should have similarity = 1.0"""

def test_cosine_similarity_orthogonal_vectors():
    """Orthogonal vectors should have similarity = 0.0"""

def test_match_speakers_above_threshold():
    """Speakers with similarity > 0.75 should be matched"""

def test_match_speakers_below_threshold():
    """Speakers with similarity < 0.75 should be treated as new"""

def test_diarize_response_includes_embeddings():
    """DiarizeResponse should include speaker_embeddings field"""
```

### Integration Test Expectations

```python
# test_speaker_embedding_storage.py

def test_save_embeddings_creates_records():
    """Embeddings should be persisted to speaker_embeddings table"""

def test_save_embeddings_replaces_existing():
    """Re-saving embeddings should replace old ones"""

def test_cascade_delete_removes_embeddings():
    """Deleting recording should cascade delete embeddings"""
```
