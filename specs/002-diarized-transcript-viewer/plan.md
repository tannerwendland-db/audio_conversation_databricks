# Implementation Plan: Diarized Transcript Viewer and Reconstruction

**Branch**: `002-diarized-transcript-viewer` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-diarized-transcript-viewer/spec.md`

## Summary

Implement two key features: (1) A "View Transcript" button in the recording detail view that displays diarized transcripts using the existing custom renderer, and (2) An LLM-based transcript reconstruction step that aligns clean original transcript text with speaker attributions from diarization to improve text quality before embedding generation.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Dash, SQLAlchemy, LangChain, LangGraph, databricks-langchain, psycopg2
**Storage**: PostgreSQL (Databricks Lakebase) with pgvector extension; UC Volumes for audio files
**Testing**: pytest (unit, integration, contract test layers)
**Target Platform**: Web application (Dash)
**Project Type**: Single project (src/ directory structure)
**Performance Goals**: Reconstruction step adds no more than 30 seconds for a 30-minute recording
**Constraints**: Demo project - no production-grade observability required
**Scale/Scope**: Single-user demo application

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | PASS | Will write tests first for reconstruction service and UI components |
| II. Simplicity & YAGNI | PASS | Leveraging existing renderer, minimal new abstractions, LLM for reconstruction (existing LangChain infrastructure) |

**Technology Standards Compliance**:
- Python 3.11+: PASS
- LangChain for LLM orchestration: PASS (using existing DatabricksEmbeddings pattern)
- pytest for testing: PASS
- Type hints required: PASS
- Linting via ruff: PASS

## Project Structure

### Documentation (this feature)

```text
specs/002-diarized-transcript-viewer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no new API endpoints)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
├── models/
│   └── transcript.py         # Extended with reconstructed_dialog_json field
├── services/
│   ├── recording.py          # Pipeline updated with reconstruction step
│   ├── reconstruction.py     # NEW: LLM-based transcript reconstruction
│   └── embedding.py          # Minor update: prefer reconstructed_dialog_json
├── components/
│   ├── transcript.py         # Existing renderer (reuse as-is)
│   └── library.py            # Add "View Transcript" button to recording cards
└── app.py                    # Route configuration (if needed)

tests/
├── unit/
│   ├── services/
│   │   └── test_reconstruction.py  # NEW: Unit tests for reconstruction
│   └── components/
│       └── test_library.py         # Tests for view transcript button
└── integration/
    └── test_recording_pipeline.py  # Updated for reconstruction step
```

**Structure Decision**: Using existing single-project structure. New code goes into existing `src/services/` and `src/components/` directories. One new service module (`reconstruction.py`) for the LLM-based reconstruction logic.

## Complexity Tracking

> No constitution violations - this section is not needed.

## Implementation Overview

### Phase 1: Transcript Viewer (P1)

1. Add "View Transcript" button to recording cards in library component
2. Wire up navigation to existing transcript view with recording ID
3. Verify existing renderer works with current data

### Phase 2: Transcript Reconstruction (P1)

1. Add `reconstructed_dialog_json` field to Transcript model
2. Create reconstruction service with LLM-based alignment
3. Update processing pipeline to include reconstruction step
4. Update embedding service to prefer reconstructed content

### Key Design Decisions

1. **LLM for Reconstruction**: Use existing Databricks LLM endpoint via LangChain to align original transcript with diarized speaker turns. The LLM can semantically match garbled text to clean text.

2. **New Field vs. Overwriting**: Store reconstructed output in new `reconstructed_dialog_json` field to preserve raw diarization for debugging.

3. **Fallback Chain**: Display and embedding prefer reconstructed -> dialog_json -> diarized_text -> full_text.

4. **Minimal UI Changes**: Reuse existing transcript renderer; only add navigation button to library cards.
