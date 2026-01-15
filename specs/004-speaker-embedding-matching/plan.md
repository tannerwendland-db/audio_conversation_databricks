# Implementation Plan: Speaker Embedding Matching for Cross-Chunk Alignment

**Branch**: `004-speaker-embedding-matching` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-speaker-embedding-matching/spec.md`

## Summary

Implement speaker embedding extraction and matching to maintain consistent speaker labels when processing long audio recordings in chunks (due to 16MB Databricks endpoint payload limits). The solution uses voice fingerprinting via pyannote embedding model to compare speakers across chunks, remapping labels in subsequent chunks to match the reference set from chunk 1.

**Key Architectural Decision**: Model and App changes are separated since the MLflow model is deployed independently to Databricks Model Serving before the app consumes it.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pyannote.audio 4.0.3, torch, MLflow (model); SQLAlchemy 2.0+, psycopg2 (app)
**Storage**: PostgreSQL (Databricks Lakebase) with pgvector extension
**Testing**: pytest (unit + integration)
**Target Platform**: Databricks Model Serving (GPU) for model; Linux server for app
**Project Type**: Hybrid - MLflow pyfunc model (notebook) + Dash web application

**Performance Goals**: Processing time increase ≤20% vs current non-aligned processing
**Constraints**: 16MB Databricks endpoint request limit; sequential chunk processing required
**Scale/Scope**: 2-5 speakers per recording; embeddings ~512 floats per speaker

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Test-First Development | PASS | Tests will be written before implementation for both model embedding logic and app storage/matching |
| Simplicity & YAGNI | PASS | Minimal changes: add embedding extraction to existing model, add one new table to app |
| Type hints on all functions | WILL COMPLY | All new code will include type hints |
| Use LangChain built-ins | N/A | Feature doesn't involve LangChain orchestration |

## Project Structure

### Documentation (this feature)

```text
specs/004-speaker-embedding-matching/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

**Deployment Order**: Model changes must be deployed first, then app changes.

```text
# MODEL CHANGES (deployed to Databricks Model Serving)
notebooks/
└── audio_diarization_pyfunc.py    # Modified: add embedding extraction & return

# APP CHANGES (deployed after model)
src/
├── models/
│   ├── recording.py               # Existing: add relationship to speaker_embeddings
│   └── speaker_embedding.py       # NEW: SpeakerEmbedding model
├── services/
│   └── audio.py                   # Modified: handle embeddings from model response,
│                                  #           implement cross-chunk matching logic

alembic/
└── versions/
    └── 004_add_speaker_embeddings_table.py  # NEW: migration

tests/
├── unit/
│   ├── test_speaker_embedding_model.py      # NEW: test SpeakerEmbedding entity
│   └── services/
│       └── test_embedding_matching.py       # NEW: test cosine similarity & remapping
└── integration/
    └── test_speaker_embedding_storage.py    # NEW: test embedding persistence
```

**Structure Decision**: Single project layout (existing). Model code lives in `notebooks/` for Databricks deployment; app code in `src/` for web application.

## Component Breakdown

### Component 1: MLflow Model Enhancement (DEPLOY FIRST)

**Location**: `notebooks/audio_diarization_pyfunc.py`

**Changes**:
1. Load pyannote embedding model in `load_context()`
2. Add `_extract_speaker_embeddings()` method to extract embeddings per speaker
3. Modify output schema to include `speaker_embeddings` field (JSON-serialized dict mapping speaker labels to embedding vectors)
4. Accept optional `reference_embeddings` in input to enable cross-chunk matching
5. Add `_match_speakers()` method using cosine similarity
6. Return consistent speaker labels when reference embeddings provided

**New Input Schema**:
```
audio_base64: string (required)
reference_embeddings: string (optional, JSON-serialized dict of label -> embedding)
chunk_index: int (optional, 0 for first chunk)
```

**New Output Schema**:
```
dialog: string
transcription: string
speaker_embeddings: string (JSON-serialized dict of label -> embedding list)
status: string
error: string
```

### Component 2: App Database Model (DEPLOY AFTER MODEL)

**Location**: `src/models/speaker_embedding.py` (new)

**Entity**: `SpeakerEmbedding`
- `id`: UUID primary key
- `recording_id`: FK to recordings (with cascade delete)
- `speaker_label`: string (e.g., "Interviewer", "Respondent")
- `embedding_vector`: vector(512) using pgvector
- `created_at`: timestamp

### Component 3: App Audio Service Enhancement

**Location**: `src/services/audio.py`

**Changes**:
1. Modify `DiarizeResponse` to include `speaker_embeddings` field
2. Modify `_diarize_single_chunk()` to:
   - Pass reference embeddings to model endpoint (for chunks > 0)
   - Extract returned embeddings from response
3. Modify `diarize_audio()` to:
   - Track reference embeddings across chunks
   - Accumulate embeddings from first chunk as reference set
   - Pass reference to subsequent chunk calls
   - Handle new speaker detection (add to reference set)

### Component 4: App Storage Service

**Location**: `src/services/recording.py` (existing, extend)

**Changes**:
1. After successful diarization, persist speaker embeddings to database
2. On re-processing, delete existing embeddings before storing new ones

## Complexity Tracking

No constitution violations requiring justification. The design is minimal:
- One new database table
- Model enhancement returns embeddings alongside existing output
- App orchestrates chunk-to-chunk embedding passing
