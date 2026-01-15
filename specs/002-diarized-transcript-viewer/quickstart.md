# Quickstart: Diarized Transcript Viewer and Reconstruction

**Feature Branch**: `002-diarized-transcript-viewer`
**Date**: 2026-01-05

## Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- Databricks workspace with configured serving endpoints:
  - `LLM_ENDPOINT` (e.g., `databricks-claude-sonnet-4-5`)
  - `EMBEDDING_ENDPOINT` (e.g., `databricks-gte-large-en`)
  - `DIARIZATION_ENDPOINT` (audio transcription/diarization model)
- Environment variables configured (see `.env.example`)

## Setup

1. **Install dependencies** (if not already):
   ```bash
   pip install -e .
   ```

2. **Truncate database** (as specified by user):
   ```bash
   # Connect to PostgreSQL and run:
   TRUNCATE TABLE transcript_chunks, transcripts, recordings CASCADE;
   ```

3. **Apply schema changes**:
   ```sql
   ALTER TABLE transcripts
   ADD COLUMN IF NOT EXISTS reconstructed_dialog_json JSONB;
   ```

## Testing the Feature

### 1. View Transcript Button

After processing a recording:

1. Navigate to the Library page
2. Find a completed recording
3. Click "View Transcript" button
4. Verify the transcript displays with speaker grouping and styling

### 2. Transcript Reconstruction

Upload a new audio file and observe:

1. Recording processes through standard pipeline
2. After diarization, reconstruction step runs
3. Check database: `reconstructed_dialog_json` should be populated
4. Transcript view should show cleaner text

### Manual Verification

```python
from src.db.session import get_session
from src.models import Recording

session = get_session()
recording = session.query(Recording).first()

# Check transcript fields
transcript = recording.transcript
print("Original:", transcript.full_text[:200])
print("Diarized JSON:", transcript.dialog_json[:2] if transcript.dialog_json else None)
print("Reconstructed:", transcript.reconstructed_dialog_json[:2] if transcript.reconstructed_dialog_json else None)
```

## Running Tests

```bash
# Unit tests
pytest tests/unit/services/test_reconstruction.py -v

# Integration tests
pytest tests/integration/test_recording_pipeline.py -v

# All tests
pytest tests/ -v
```

## Key Files Modified

| File | Change |
|------|--------|
| `src/models/transcript.py` | Added `reconstructed_dialog_json` field |
| `src/services/reconstruction.py` | NEW: LLM-based reconstruction service |
| `src/services/recording.py` | Updated pipeline with reconstruction step |
| `src/services/embedding.py` | Prefer `reconstructed_dialog_json` for chunking |
| `src/components/library.py` | Added "View Transcript" button |
| `src/components/transcript.py` | Updated fallback to prefer reconstructed data |

## Troubleshooting

### Reconstruction not populating

1. Check LLM endpoint is accessible
2. Review logs for reconstruction errors
3. Verify `full_text` and `dialog_json` are populated before reconstruction

### Transcript view not showing

1. Verify recording status is COMPLETED
2. Check transcript record exists with non-null content
3. Verify route `/transcript/{id}` is configured

### Poor reconstruction quality

1. Check if `full_text` contains quality content
2. Review reconstruction prompt in `src/services/reconstruction.py`
3. Try adjusting LLM temperature or prompt structure
