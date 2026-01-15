# Quickstart: Speaker Embedding Matching

**Feature**: 004-speaker-embedding-matching

## Prerequisites

- Python 3.11+
- Access to Databricks workspace with Model Serving
- PostgreSQL database with pgvector extension enabled
- HuggingFace token with pyannote model access

## Deployment Order

**IMPORTANT**: Components must be deployed in this order:

1. **Model** (Databricks Model Serving) - deploys embedding extraction capability
2. **App** (database migration + code) - consumes embedding-enabled endpoint

## Step 1: Deploy Model Changes

### 1.1 Update the Notebook

Edit `notebooks/audio_diarization_pyfunc.py` to include:

1. Load `pyannote/embedding` model in `load_context()`
2. Add embedding extraction methods
3. Update input/output schemas
4. Add speaker matching logic

### 1.2 Register New Model Version

```python
# In Databricks notebook
with mlflow.start_run() as run:
    model_info = mlflow.pyfunc.log_model(
        artifact_path=model_name,
        python_model=AudioTranscriptionDiarizationModel(),  # Updated class
        signature=signature,  # Updated schema
        pip_requirements=pip_requirements,
        registered_model_name=model_name
    )
    mlflow_client.set_registered_model_alias(model_name, "recent", model_info.registered_model_version)
```

### 1.3 Update Serving Endpoint

The endpoint will automatically use the new model version when you update the alias.

### 1.4 Verify Model Deployment

```python
from databricks.sdk import WorkspaceClient
import base64
import json

client = WorkspaceClient()

# Test with first chunk (no reference)
response = client.serving_endpoints.query(
    name="audio-transcription-diarization-endpoint",
    dataframe_records=[{"audio_base64": "<test_audio_base64>"}]
)

# Verify speaker_embeddings in response
result = response.predictions[0]
assert "speaker_embeddings" in result
assert result["status"] == "success"
embeddings = json.loads(result["speaker_embeddings"])
print(f"Extracted embeddings for {len(embeddings)} speakers")
```

## Step 2: Deploy App Changes

### 2.1 Run Database Migration

```bash
# From project root
cd /Users/tanner.wendland/projects/audio_conversation_databricks
alembic upgrade head
```

Verify migration:

```sql
-- Connect to database and verify
SELECT table_name FROM information_schema.tables WHERE table_name = 'speaker_embeddings';
```

### 2.2 Verify App Code

The following files should be updated:

- `src/models/speaker_embedding.py` (new)
- `src/models/recording.py` (relationship added)
- `src/models/__init__.py` (import added)
- `src/services/audio.py` (embedding handling)
- `src/services/recording.py` (embedding persistence)

### 2.3 Run Tests

```bash
# Unit tests
pytest tests/unit/test_speaker_embedding_model.py -v
pytest tests/unit/services/test_embedding_matching.py -v

# Integration tests (requires database)
pytest tests/integration/test_speaker_embedding_storage.py -v
```

## Step 3: End-to-End Verification

### 3.1 Upload a Long Recording

Upload an audio file > 16MB (requires chunking) through the app.

### 3.2 Verify Consistent Labels

Check the transcript viewer:
- First speaker should be "Interviewer" throughout
- Second speaker should be "Respondent" throughout
- No label swapping between chunks

### 3.3 Verify Embedding Storage

```sql
SELECT
    r.title,
    se.speaker_label,
    array_length(se.embedding_vector::real[], 1) as embedding_dims
FROM speaker_embeddings se
JOIN recordings r ON r.id = se.recording_id
ORDER BY r.created_at DESC
LIMIT 10;
```

Expected output: Each recording has 2-5 rows, each with 512-dimensional embeddings.

## Troubleshooting

### Model returns empty speaker_embeddings

- Verify pyannote/embedding model is loaded in `load_context()`
- Check HuggingFace token has access to embedding model

### Speaker labels still swapping

- Verify `reference_embeddings` is being passed to subsequent chunks
- Check similarity threshold (default 0.75) - may need adjustment
- Review logs for similarity scores

### Database migration fails

- Ensure pgvector extension is enabled: `CREATE EXTENSION IF NOT EXISTS vector;`
- Verify PostgreSQL version supports pgvector (9.6+)

### Tests fail with import errors

- Run `pip install pgvector` in app environment
- Ensure `src/models/__init__.py` imports `SpeakerEmbedding`

## Configuration

### Similarity Threshold

The default threshold is 0.75. To adjust:

```python
# In audio.py
SPEAKER_SIMILARITY_THRESHOLD = 0.75  # Adjust as needed
```

Lower threshold = more aggressive matching (risk: merging different speakers)
Higher threshold = more conservative (risk: splitting same speaker)

## Rollback

### Model Rollback

```python
# Set alias back to previous version
mlflow_client.set_registered_model_alias(model_name, "recent", previous_version)
```

### App Rollback

```bash
# Revert migration
alembic downgrade -1

# Revert code changes
git checkout HEAD~1 -- src/models/ src/services/audio.py
```
