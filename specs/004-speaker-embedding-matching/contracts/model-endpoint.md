# Model Endpoint Contract: Audio Diarization with Speaker Embeddings

**Endpoint**: `audio-transcription-diarization-endpoint`
**Type**: Databricks Model Serving (MLflow pyfunc)
**Version**: 2.0 (with speaker embedding support)

## Request Schema

### Input DataFrame

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| audio_base64 | string | Yes | Base64-encoded WAV audio data |
| reference_embeddings | string | No | JSON-serialized dict of speaker label → embedding vector |
| chunk_index | integer | No | 0-based index of current chunk (default: 0) |

### Example Request

```json
{
  "dataframe_records": [
    {
      "audio_base64": "<base64_encoded_wav>",
      "reference_embeddings": "{\"Interviewer\": [0.1, 0.2, ...], \"Respondent\": [0.3, 0.4, ...]}",
      "chunk_index": 1
    }
  ]
}
```

### First Chunk Request (no reference)

```json
{
  "dataframe_records": [
    {
      "audio_base64": "<base64_encoded_wav>"
    }
  ]
}
```

## Response Schema

### Output DataFrame

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| dialog | string | Yes | Diarized transcript with speaker labels |
| transcription | string | Yes | Raw Whisper transcription without speaker labels |
| speaker_embeddings | string | Yes | JSON-serialized dict of speaker label → embedding vector |
| status | string | No | "success" or "error" |
| error | string | Yes | Error message if status is "error" |

### Success Response

```json
{
  "predictions": [
    {
      "dialog": "Interviewer: Hello, how are you?\nRespondent: I'm doing well, thank you.",
      "transcription": "Hello, how are you? I'm doing well, thank you.",
      "speaker_embeddings": "{\"Interviewer\": [0.12, 0.34, ...], \"Respondent\": [0.56, 0.78, ...]}",
      "status": "success",
      "error": null
    }
  ]
}
```

### Error Response

```json
{
  "predictions": [
    {
      "dialog": null,
      "transcription": null,
      "speaker_embeddings": null,
      "status": "error",
      "error": "Failed to process audio: invalid format"
    }
  ]
}
```

## Speaker Embeddings Format

The `speaker_embeddings` field is a JSON-serialized dictionary:

```json
{
  "Interviewer": [0.123, 0.456, ..., 0.789],  // 512 floats
  "Respondent": [0.321, 0.654, ..., 0.987]    // 512 floats
}
```

- Keys: Speaker labels as assigned by diarization
- Values: 512-dimensional float arrays (pyannote embedding model output)

## Behavior

### First Chunk (chunk_index=0 or omitted)

1. Diarize audio to identify speakers
2. Extract embeddings for each speaker
3. Assign labels based on order of appearance (Interviewer first, then Respondent, Respondent2, etc.)
4. Return dialog, transcription, and speaker_embeddings

### Subsequent Chunks (chunk_index > 0 with reference_embeddings)

1. Diarize audio to identify speakers
2. Extract embeddings for each speaker in this chunk
3. Compare each speaker's embedding to reference_embeddings using cosine similarity
4. If similarity > 0.75: remap to matching reference label
5. If no match: assign new label (next available) and include in output embeddings
6. Return dialog with remapped labels, transcription, and updated speaker_embeddings

### Backward Compatibility

Requests without `reference_embeddings` or `chunk_index` fields work identically to v1:
- Speaker labels assigned fresh per chunk
- No cross-chunk matching performed
- `speaker_embeddings` still returned for potential future use

## Error Conditions

| Condition | Status | Error Message |
|-----------|--------|---------------|
| Empty audio | error | "Cannot process empty audio data" |
| Invalid base64 | error | "Failed to decode audio: invalid base64" |
| Invalid reference_embeddings JSON | error | "Failed to parse reference_embeddings: invalid JSON" |
| Embedding dimension mismatch | error | "Reference embedding dimension mismatch: expected 512" |
| Diarization failure | error | "Error performing speaker diarization: {details}" |

## Size Limits

- Maximum request payload: 16MB (Databricks limit)
- Maximum audio duration per request: ~10-12 minutes (depending on WAV compression)
- Embeddings add ~2KB per speaker to response
