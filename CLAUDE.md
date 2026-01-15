# audio_conversation_databricks Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-12

## Active Technologies
- Python 3.11+ + Dash, SQLAlchemy, LangGraph, LangChain, psycopg2, databricks-sdk, databricks-langchain (001-audio-conversation-rag)
- PostgreSQL (Databricks Lakebase) with pgvector extension; UC Volumes for audio files (001-audio-conversation-rag)
- Python 3.11+ + Dash, SQLAlchemy, LangChain, LangGraph, databricks-langchain, psycopg2 (002-diarized-transcript-viewer)
- Python 3.11+ + Dash 3.3+, dash-bootstrap-components 2.0+, SQLAlchemy 2.0+, LangChain 0.3+ (003-multi-speaker-conversation)
- PostgreSQL (Databricks Lakebase) with pgvector; existing `dialog_json` field stores speaker turns (003-multi-speaker-conversation)
- Python 3.11+ + pyannote.audio 4.0.3, torch, MLflow (model); SQLAlchemy 2.0+, psycopg2 (app) (004-speaker-embedding-matching)

- Python 3.11+ + Dash, SQLAlchemy, LangGraph, LangChain, psycopg2, databricks-sdk (001-audio-conversation-rag)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 004-speaker-embedding-matching: Added Python 3.11+ + pyannote.audio 4.0.3, torch, MLflow (model); SQLAlchemy 2.0+, psycopg2 (app)
- 003-multi-speaker-conversation: Added Python 3.11+ + Dash 3.3+, dash-bootstrap-components 2.0+, SQLAlchemy 2.0+, LangChain 0.3+
- 002-diarized-transcript-viewer: Added Python 3.11+ + Dash, SQLAlchemy, LangChain, LangGraph, databricks-langchain, psycopg2


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
