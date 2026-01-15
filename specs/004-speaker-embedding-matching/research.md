# Research: Speaker Embedding Matching

**Feature**: 004-speaker-embedding-matching
**Date**: 2026-01-14

## Research Topics

### 1. Pyannote Embedding Model Selection

**Decision**: Use `pyannote/embedding` model (or the embeddings accessible from the speaker-diarization pipeline)

**Rationale**:
- Pyannote 4.x speaker-diarization-3.1 pipeline internally uses speaker embeddings but doesn't expose them directly
- The `pyannote/embedding` model can be loaded separately to extract embeddings from audio segments
- Alternative: `wespeaker` models are also compatible with pyannote ecosystem
- Embeddings are typically 192-512 dimensional vectors (depends on model)

**Alternatives Considered**:
- `speechbrain/spkrec-ecapa-voxceleb`: Good accuracy but different ecosystem, adds complexity
- `resemblyzer`: Simpler API but less accurate than pyannote for diarization scenarios
- Using internal pipeline embeddings: Would require modifying pyannote internals, not maintainable

**Implementation Note**: The pyannote embedding model produces 512-dimensional vectors by default.

### 2. Embedding Extraction Strategy

**Decision**: Extract embeddings per-speaker by isolating audio segments from diarization output

**Rationale**:
- Diarization already identifies speaker segments with timestamps
- For each speaker, concatenate or average embeddings from their segments
- Only use segments > 1 second for reliable embeddings (per spec FR-007)

**Approach**:
1. Run diarization to get speaker segments
2. For each unique speaker, extract audio from their segments
3. Pass speaker audio through embedding model
4. Average multiple segment embeddings per speaker for robustness

**Alternatives Considered**:
- Single embedding from longest segment: Less robust to noise
- Weighted average by segment duration: More complex, marginal benefit

### 3. Cosine Similarity Threshold

**Decision**: Use 0.75 as default threshold, configurable

**Rationale**:
- Literature suggests 0.7-0.85 range for speaker verification tasks
- 0.75 balances false positives (merging different speakers) vs false negatives (splitting same speaker)
- Should be configurable to allow tuning based on real-world performance

**Testing Strategy**:
- Start with 0.75
- Log similarity scores during processing for analysis
- Adjust based on production feedback

### 4. Reference Embedding Accumulation

**Decision**: Build reference set incrementally across chunks

**Rationale**:
- Chunk 1: All speakers become reference embeddings
- Chunk N (N>1):
  - Compare each speaker to reference set
  - If match found (similarity > threshold): remap label
  - If no match: add as new speaker to reference set
- This handles speakers appearing in later chunks (spec User Story 2)

**Edge Cases**:
- Speaker only in first chunk: Reference embedding exists, no issue
- Speaker appears in chunk 3 but not 2: Still matches reference from chunk 1
- New speaker in chunk 2: Gets new label, added to reference for chunk 3+

### 5. MLflow Model Schema Changes

**Decision**: Add optional input fields and new output field

**Rationale**:
- Backward compatible: existing callers don't need to change
- `reference_embeddings` input is optional (empty/null for first chunk)
- `speaker_embeddings` output always included for transparency

**Schema Design**:
```python
# Input (extended)
input_schema = Schema([
    ColSpec("string", "audio_base64"),
    ColSpec("string", "reference_embeddings"),  # Optional, JSON
    ColSpec("integer", "chunk_index"),          # Optional, default 0
])

# Output (extended)
output_schema = Schema([
    ColSpec("string", "dialog"),
    ColSpec("string", "transcription"),
    ColSpec("string", "speaker_embeddings"),    # NEW: JSON dict
    ColSpec("string", "status"),
    ColSpec("string", "error"),
])
```

### 6. Database Schema for pgvector

**Decision**: Use `vector(512)` column type with pgvector extension

**Rationale**:
- pgvector already enabled in the database (see migration 001)
- Native vector type enables future similarity queries if needed
- 512 dimensions matches pyannote embedding model output

**Schema**:
```sql
CREATE TABLE speaker_embeddings (
    id UUID PRIMARY KEY,
    recording_id VARCHAR(36) REFERENCES recordings(id) ON DELETE CASCADE,
    speaker_label VARCHAR(50) NOT NULL,
    embedding_vector vector(512) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_speaker_embeddings_recording ON speaker_embeddings(recording_id);
```

### 7. Chunk Processing Order

**Decision**: Sequential processing, strictly ordered

**Rationale**:
- Spec FR-010 requires sequential processing
- Reference set builds incrementally
- Cannot parallelize chunk processing for this feature
- App already processes chunks sequentially (see `diarize_audio()` in audio.py)

**No changes needed**: Current implementation already processes chunks in order.

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| Which embedding model? | pyannote/embedding (512-dim) |
| Similarity threshold? | 0.75 default, configurable |
| How to handle new speakers? | Add to reference set with new label |
| Storage format? | pgvector vector(512) column |
| Model vs App responsibility? | Model extracts & matches; App stores & orchestrates |

## Dependencies Verified

- `pyannote.audio==4.0.3`: Already in model requirements
- `pgvector`: Already enabled in database
- `torch`: Already in model requirements (needed for embedding extraction)
