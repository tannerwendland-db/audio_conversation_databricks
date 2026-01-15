# Implementation Plan: Audio Conversation RAG System

**Branch**: `001-audio-conversation-rag` | **Date**: 2025-12-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-audio-conversation-rag/spec.md`

## Summary

Build a Databricks App that enables teams to upload customer call recordings, process them through a custom diarization endpoint for transcription with speaker identification, store vectorized chunks in PostgreSQL with pgvector, and provide a conversational RAG interface powered by Claude Sonnet 4.5 for querying across all recordings.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Dash, SQLAlchemy, LangGraph, LangChain, psycopg2, databricks-sdk, databricks-langchain
**Storage**: PostgreSQL (Databricks Lakebase) with pgvector extension; UC Volumes for audio files
**Testing**: pytest
**Target Platform**: Databricks Apps (serverless)
**Project Type**: Single Python application (Databricks App)
**Performance Goals**: Audio processing <5min for 30min files; Chat responses <10s; 50 concurrent users
**Constraints**: 500MB max audio file size; WAV format required for diarization endpoint
**Scale/Scope**: Team-wide access; ~50 users; indefinite retention

**AI Models**:
1. **LLM**: `databricks-claude-sonnet-4-5` - Main conversational AI for RAG responses
2. **Diarization**: `audio-transcription-diarization-endpoint` - Custom PyFunc model accepting base64-encoded WAV audio in `dataframe_records` format with `audio_base64` column; returns transcription with speaker labels (Interviewer/Respondent)
3. **Embeddings**: Databricks embedding model for vectorizing diarized transcript chunks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Test-First Development (NON-NEGOTIABLE)

| Requirement | Compliance |
|-------------|------------|
| Write tests first | WILL COMPLY - Tests written before implementation for all features |
| Tests MUST fail initially | WILL COMPLY - Red-Green-Refactor cycle enforced |
| Implement minimally | WILL COMPLY - Only code needed to pass tests |
| Test coverage >= 80% | WILL COMPLY - Target 80%+ for new code |
| Integration tests for external services | WILL COMPLY - Integration tests for Databricks endpoints, PostgreSQL, LangChain |

### II. Simplicity & YAGNI

| Requirement | Compliance |
|-------------|------------|
| Build only what's needed | WILL COMPLY - Following spec exactly, no speculative features |
| Minimize abstractions | WILL COMPLY - Direct implementations using LangChain patterns |
| Prefer standard solutions | WILL COMPLY - LangGraph for agents, langchain-postgres for vectors, Alembic for migrations |
| Delete unused code | WILL COMPLY - No dead code |

### Technology Standards Compliance

| Standard | Compliance |
|----------|------------|
| Python 3.11+ | COMPLIANT |
| LangChain orchestration | COMPLIANT - Using LangGraph |
| pytest for testing | COMPLIANT |
| Type hints on functions | WILL COMPLY |
| Linting (ruff) | WILL COMPLY |
| Formatting (ruff format) | WILL COMPLY |

**Gate Status**: PASS - No violations. Ready for Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-audio-conversation-rag/
├── plan.md              # This file
├── research.md          # Technical research and decisions
├── data-model.md        # Database schema and entity definitions
├── quickstart.md        # Setup and run instructions
├── contracts/           # API contract definitions
│   └── api.yaml         # OpenAPI spec for internal services
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── app.py               # Dash application entry point
├── config.py            # Environment and app configuration
├── models/              # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── recording.py     # Recording entity
│   └── transcript.py    # Transcript entity
├── services/            # Business logic layer
│   ├── __init__.py
│   ├── audio.py         # Audio upload, conversion, diarization
│   ├── embedding.py     # Text chunking and vectorization
│   └── rag.py           # LangGraph RAG agent
├── components/          # Dash UI components
│   ├── __init__.py
│   ├── upload.py        # Audio upload component
│   ├── chat.py          # Chat interface component
│   ├── library.py       # Recording library component
│   └── transcript.py    # Transcript viewer component
└── db/                  # Database utilities
    ├── __init__.py
    └── session.py       # SQLAlchemy session management

alembic/                 # Database migrations
├── alembic.ini
├── env.py
└── versions/
    └── 001_initial_schema.py

tests/
├── conftest.py          # Pytest fixtures
├── unit/                # Unit tests
│   ├── test_audio.py
│   ├── test_embedding.py
│   └── test_rag.py
├── integration/         # Integration tests
│   ├── test_db.py
│   ├── test_diarization.py
│   └── test_vector_store.py
└── contract/            # Contract tests
    └── test_api_contracts.py

scripts/                 # Utility scripts
└── diarize.py           # Existing diarization test script

notebooks/               # Databricks notebooks
└── audio_diarization_pyfunc.py  # Diarization model notebook

app.yaml                 # Databricks App configuration
Makefile                 # Common development tasks
pyproject.toml           # Python project config (uv)
requirements.txt         # Dependencies
```

**Structure Decision**: Single Databricks App with modular Python structure. Services layer separates business logic from UI components. Alembic at root for standard migration workflow. Tests organized by type (unit/integration/contract) per constitution requirements.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations identified. Design follows constitution principles.
