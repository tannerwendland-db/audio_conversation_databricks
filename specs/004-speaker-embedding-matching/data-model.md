# Data Model: Speaker Embedding Matching

**Feature**: 004-speaker-embedding-matching
**Date**: 2026-01-14

## Entities

### SpeakerEmbedding (NEW)

Stores voice fingerprint vectors for speakers identified in a recording.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| recording_id | VARCHAR(36) | FK → recordings.id, ON DELETE CASCADE | Parent recording |
| speaker_label | VARCHAR(50) | NOT NULL | Label assigned to speaker (e.g., "Interviewer", "Respondent") |
| embedding_vector | vector(512) | NOT NULL | Voice fingerprint from pyannote embedding model |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | When embedding was extracted |

**Indexes**:
- `idx_speaker_embeddings_recording` on `recording_id` - for efficient lookup by recording

**Relationships**:
- Many-to-one with Recording (one recording has multiple speaker embeddings)

### Recording (MODIFIED)

Existing entity, updated to include relationship to speaker embeddings.

**New Relationship**:
```python
speaker_embeddings: Mapped[list["SpeakerEmbedding"]] = relationship(
    "SpeakerEmbedding",
    back_populates="recording",
    cascade="all, delete-orphan",
)
```

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────────┐
│   Recording     │       │  SpeakerEmbedding   │
├─────────────────┤       ├─────────────────────┤
│ id (PK)         │──┐    │ id (PK)             │
│ title           │  │    │ recording_id (FK)   │──┘
│ original_file   │  └───<│ speaker_label       │
│ volume_path     │       │ embedding_vector    │
│ duration        │       │ created_at          │
│ status          │       └─────────────────────┘
│ ...             │
└─────────────────┘
        │
        │ 1:1
        ▼
┌─────────────────┐
│   Transcript    │
└─────────────────┘
```

## State Transitions

### Recording Processing Status

No changes to existing states. Speaker embeddings are stored as part of the "DIARIZING" → "EMBEDDING" transition.

```
PENDING → CONVERTING → DIARIZING → EMBEDDING → COMPLETED
                          │              │
                          │              └── Speaker embeddings persisted
                          └── Dialog extracted with speaker labels
```

## Validation Rules

1. **Speaker Label Uniqueness**: Within a recording, speaker labels must be unique (enforced at application level)
2. **Embedding Dimension**: Vector must be exactly 512 dimensions (enforced by pgvector type)
3. **Recording Existence**: recording_id must reference an existing recording (enforced by FK)
4. **Non-Empty Embedding**: embedding_vector cannot be NULL or zero vector

## Migration Strategy

**Migration File**: `alembic/versions/004_add_speaker_embeddings_table.py`

```sql
-- Upgrade
CREATE TABLE speaker_embeddings (
    id VARCHAR(36) PRIMARY KEY,
    recording_id VARCHAR(36) NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    speaker_label VARCHAR(50) NOT NULL,
    embedding_vector vector(512) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_speaker_embeddings_recording ON speaker_embeddings(recording_id);

-- Downgrade
DROP INDEX idx_speaker_embeddings_recording;
DROP TABLE speaker_embeddings;
```

## Data Volume Estimates

- Embeddings per recording: 2-5 (based on spec FR-009)
- Embedding size: 512 floats × 4 bytes = 2KB per embedding
- Storage per recording: 4-10KB for embeddings
- Negligible impact on database size

## Query Patterns

### Primary Queries

1. **Get embeddings for recording** (used during re-processing check):
   ```sql
   SELECT * FROM speaker_embeddings WHERE recording_id = ?;
   ```

2. **Delete embeddings before re-processing**:
   ```sql
   DELETE FROM speaker_embeddings WHERE recording_id = ?;
   ```

3. **Insert new embeddings** (batch insert after processing):
   ```sql
   INSERT INTO speaker_embeddings (id, recording_id, speaker_label, embedding_vector, created_at)
   VALUES (?, ?, ?, ?, NOW());
   ```

### Future Query (not implemented in this feature)

Cross-recording speaker identification (potential future use):
```sql
SELECT recording_id, speaker_label,
       1 - (embedding_vector <=> ?) as similarity
FROM speaker_embeddings
WHERE 1 - (embedding_vector <=> ?) > 0.75
ORDER BY similarity DESC;
```
