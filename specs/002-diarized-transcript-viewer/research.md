# Research: Diarized Transcript Viewer and Reconstruction

**Feature Branch**: `002-diarized-transcript-viewer`
**Date**: 2026-01-05

## Research Summary

This document captures research findings for implementing the LLM-based transcript reconstruction feature.

---

## 1. LLM-Based Transcript Reconstruction Approach

### Decision: Use ChatDatabricks with Structured Prompting

**Rationale**: The codebase already uses `ChatDatabricks` from `databricks_langchain` for LLM operations (see `src/services/rag.py:_get_llm()`). The reconstruction task is well-suited for LLM because:

1. **Semantic Understanding**: The LLM can understand that "gonna" in diarized text maps to "going to" in the original
2. **Context Preservation**: The LLM maintains conversational context when aligning speaker turns
3. **Fuzzy Matching**: Handles garbled text, incomplete words, and audio artifacts naturally
4. **Existing Infrastructure**: No new dependencies required

**Alternatives Considered**:

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Algorithmic (difflib) | Fast, no API costs | Cannot handle semantic variations, poor on garbled text | Rejected |
| Hybrid (algo + LLM) | Lower API costs for easy cases | Added complexity, maintenance burden | Rejected |
| LLM-only | Handles all cases, simple architecture | API costs, latency | **Selected** |

### Implementation Strategy

The reconstruction will use a single LLM call per transcript with a structured prompt:

```
Given:
1. Original transcript (clean, no speaker labels)
2. Diarized transcript (speaker labels, potentially garbled text)

Output:
Reconstructed dialog_json with:
- Speaker attributions from diarized text
- Clean text from original transcript aligned to each speaker turn
```

**Prompt Design Principles**:
- Provide clear examples of expected input/output format
- Request JSON output for easy parsing
- Include fallback instruction: preserve original diarized text for unaligned segments

---

## 2. Processing Pipeline Integration

### Decision: Insert Reconstruction Step Between Diarization and Embedding

**Current Pipeline** (from `src/services/recording.py:process_recording`):
1. Convert audio to WAV
2. Upload to UC Volumes
3. **Diarize** -> produces `dialog_json`, `diarized_text`, `full_text`
4. **Embed** -> chunks `dialog_json` and generates embeddings
5. Complete

**New Pipeline**:
1. Convert audio to WAV
2. Upload to UC Volumes
3. **Diarize** -> produces `dialog_json`, `diarized_text`, `full_text`
4. **Reconstruct** -> produces `reconstructed_dialog_json` (NEW)
5. **Embed** -> chunks `reconstructed_dialog_json` (updated priority)
6. Complete

**Rationale**: Reconstruction depends on diarization output and must complete before embedding to ensure embeddings use high-quality text.

**Alternatives Considered**:
- **Background job**: Rejected - adds complexity for a demo project
- **On-demand reconstruction**: Rejected - users expect immediate search after upload

---

## 3. Data Model Extension

### Decision: Add `reconstructed_dialog_json` Field to Transcript Model

**Rationale**: Preserves raw diarization output for debugging while providing a separate field for the enhanced version.

**Schema Change**:
```python
# In src/models/transcript.py
reconstructed_dialog_json: Mapped[list[dict] | None] = mapped_column(
    JSONB, nullable=True
)
```

**Migration Note**: User is truncating database, so no migration script needed.

**Alternatives Considered**:
- **Overwrite `dialog_json`**: Rejected - loses original for debugging
- **Separate table**: Rejected - over-engineering for this relationship

---

## 4. Fallback Strategy

### Decision: Prefer Reconstructed, Fall Back Gracefully

**Priority Order for Display/Embedding**:
1. `reconstructed_dialog_json` (if available)
2. `dialog_json` (raw diarization)
3. `diarized_text` (parsed on-demand)
4. `full_text` (raw transcription)

**Rationale**: This matches the existing fallback pattern in `src/components/transcript.py:load_transcript` callback (lines 640-648).

**Error Handling**:
- If LLM reconstruction fails: Log warning, set `reconstructed_dialog_json = None`, continue pipeline
- If reconstruction produces invalid JSON: Fall back to `dialog_json`

---

## 5. Existing Renderer Reuse

### Decision: No Changes to Transcript Renderer

**Finding**: The existing `src/components/transcript.py` already implements:
- Speaker turn grouping with distinct styling (`_create_speaker_block`)
- Dialog JSON parsing (`_convert_dialog_json_to_turns`)
- Search highlighting (`_highlight_matches_safe`)
- Full transcript view layout (`create_transcript_view`)

The renderer's `load_transcript` callback will be updated to check `reconstructed_dialog_json` first in its fallback chain.

---

## 6. View Transcript Button Placement

### Decision: Add Button to Library Recording Cards

**Location**: `src/components/library.py` - recording card component

**Implementation**: Add a "View Transcript" button/link that navigates to `/transcript/{recording_id}` route.

**Routing**: Existing `src/app.py` likely has route handling; verify and add if needed.

---

## 7. Performance Considerations

### LLM Call Performance

**Constraint**: Reconstruction should add no more than 30 seconds for a 30-minute recording.

**Analysis**:
- Typical dialog_json for 30 min: ~100-150 speaker turns, ~10-15K characters
- Single LLM call with structured prompt
- Expected latency: 5-15 seconds based on endpoint performance

**Mitigation if slow**:
- Chunk long transcripts and reconstruct in batches
- Use streaming if supported (not needed for demo)

---

## 8. Testing Strategy

### Unit Tests
- `test_reconstruction.py`: Test reconstruction service with mocked LLM responses
- Test JSON parsing, error handling, fallback behavior

### Integration Tests
- `test_recording_pipeline.py`: End-to-end test with reconstruction step
- Verify `reconstructed_dialog_json` is populated after processing

### Manual Verification
- Compare raw vs reconstructed text quality
- Verify speaker attributions are preserved

---

## Unresolved Items

None - all technical decisions resolved. Ready for Phase 1 design artifacts.
