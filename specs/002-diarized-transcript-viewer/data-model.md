# Data Model: Diarized Transcript Viewer and Reconstruction

**Feature Branch**: `002-diarized-transcript-viewer`
**Date**: 2026-01-05

## Entity Changes

### Transcript (Extended)

The existing `Transcript` model is extended with one new field.

**Location**: `src/models/transcript.py`

#### Current Schema

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | String(36) | No | Primary key (UUID) |
| recording_id | String(36) | No | FK to recordings.id |
| full_text | Text | No | Raw Whisper transcription (no speaker labels) |
| language | String(10) | Yes | Detected language code |
| diarized_text | Text | Yes | Raw diarized output with speaker labels/timestamps |
| dialog_json | JSONB | Yes | Rolled-up speaker turns from diarization |
| summary | Text | Yes | Generated summary |
| created_at | DateTime | No | Creation timestamp |

#### New Field

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| **reconstructed_dialog_json** | JSONB | Yes | LLM-reconstructed speaker turns with clean text |

#### Field Details

**reconstructed_dialog_json**:
- Same structure as `dialog_json`: `list[{"speaker": str, "text": str}]`
- Contains speaker attributions from diarization aligned with clean text from `full_text`
- Populated by reconstruction service after diarization completes
- Takes priority over `dialog_json` for display and embedding when available

#### Relationships

No changes to relationships:
- One-to-one with Recording (via `recording_id` FK)
- Cascade delete from Recording

---

## Data Flow

### Processing Pipeline (Updated)

```
Audio Upload
    │
    ▼
┌─────────────────────┐
│  Convert to WAV     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Upload to Volumes  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Diarize Audio      │──────────────────┐
│  (Databricks)       │                  │
└─────────────────────┘                  │
    │                                    │
    │  Outputs:                          │
    │  - full_text (clean)               │
    │  - diarized_text (raw w/speakers)  │
    │  - dialog_json (parsed turns)      │
    │                                    │
    ▼                                    │
┌─────────────────────┐                  │
│  Reconstruct        │◄─────────────────┘
│  (LLM-based)        │
└─────────────────────┘
    │
    │  Output:
    │  - reconstructed_dialog_json
    │
    ▼
┌─────────────────────┐
│  Generate Embeddings│
│  (prefers reconstructed)
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Store Transcript   │
│  Chunks (pgvector)  │
└─────────────────────┘
```

### Fallback Priority

Display and embedding use this priority chain:

1. `reconstructed_dialog_json` - Best quality (if available)
2. `dialog_json` - Diarized but potentially garbled
3. `diarized_text` - Parsed on-demand
4. `full_text` - Raw transcription (no speakers)

---

## JSON Schema

### dialog_json / reconstructed_dialog_json Structure

```json
[
  {
    "speaker": "Interviewer",
    "text": "Thank you for joining us today. Can you tell us about your experience?"
  },
  {
    "speaker": "Respondent",
    "text": "Of course. I've been working in this field for about ten years now."
  }
]
```

**Validation Rules**:
- Array of objects
- Each object must have `speaker` (string) and `text` (string)
- `speaker` values: typically "Interviewer", "Respondent", or "SPEAKER_XX"
- `text` must be non-empty string

---

## Migration Notes

**No database migration required**: User is truncating the existing database before deploying this feature.

For future reference, the migration SQL would be:

```sql
ALTER TABLE transcripts
ADD COLUMN reconstructed_dialog_json JSONB;
```

---

## State Transitions

### Recording Processing Status

No changes to existing `ProcessingStatus` enum:
- PENDING
- CONVERTING
- UPLOADING
- DIARIZING
- EMBEDDING (reconstruction happens within this phase)
- COMPLETED
- FAILED

**Note**: Reconstruction is considered part of the EMBEDDING phase to avoid adding a new status for this demo project.
