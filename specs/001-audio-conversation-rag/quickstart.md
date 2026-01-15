# Quickstart: Audio Conversation RAG System

**Feature**: 001-audio-conversation-rag
**Date**: 2025-12-12

## Prerequisites

### Local Development

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Databricks CLI v0.250.0+
- Access to a Databricks workspace with:
  - Unity Catalog enabled
  - Model Serving endpoints configured
  - Permissions to create Databricks Apps

### Infrastructure

- **PostgreSQL 17** (Lakebase) with pgvector extension
- **Databricks Secrets** scope with Postgres credentials
- **Unity Catalog Volume** for audio file storage
- **Model Serving Endpoints**:
  - `databricks-claude-sonnet-4-5` (LLM)
  - `databricks-gte-large-en` (Embeddings)
  - `audio-transcription-diarization-endpoint` (Custom PyFunc with Whisper + Pyannote)

---

## Setup

### 1. Clone and Install Dependencies

```bash
# Clone repository
git clone <repository-url>
cd audio_conversation_databricks

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# Install dev dependencies
uv pip install -r requirements-dev.txt
```

### 2. Configure Databricks CLI

```bash
# Configure Databricks CLI authentication
databricks configure

# Verify connection
databricks workspace list /
```

### 3. Set Up Databricks Secrets

```bash
# Create secrets scope
databricks secrets create-scope audio-rag-secrets

# Add PostgreSQL credentials
databricks secrets put-secret --scope audio-rag-secrets --key postgres-host
# Enter your Lakebase host when prompted

databricks secrets put-secret --scope audio-rag-secrets --key postgres-user
# Enter your database username

databricks secrets put-secret --scope audio-rag-secrets --key postgres-password
# Enter your database password
```

### 4. Create Unity Catalog Volume

```sql
-- Run in Databricks SQL or notebook
CREATE VOLUME IF NOT EXISTS main.default.audio_recordings;
```

Or via CLI:
```bash
databricks volumes create main.default audio_recordings
```

### 5. Initialize Database

```bash
# Set environment variables for local development
export POSTGRES_HOST=<your-lakebase-host>
export POSTGRES_USER=<your-username>
export POSTGRES_PASSWORD=<your-password>
export POSTGRES_DB=audio_rag

# Run Alembic migrations
make db-migrate
```

---

## Local Development

### Run Locally with Databricks Connect

```bash
# Prepare local environment (installs Databricks Connect)
make local-prepare

# Start the app locally
make run-local
```

The app will be available at `http://localhost:8000`.

### Run Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run only unit tests
make test-unit

# Run only integration tests (requires DB connection)
make test-integration
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type check
make typecheck
```

---

## Deployment

### Deploy to Databricks

```bash
# Deploy to development environment
make deploy-dev

# Deploy to production
make deploy-prod
```

### Manual Deployment Steps

```bash
# Validate bundle configuration
databricks bundle validate

# Deploy bundle
databricks bundle deploy -t dev

# Check deployment status
databricks apps get <app-name>
```

---

## Usage

### Upload a Recording

1. Navigate to the app URL in your Databricks workspace
2. Click "Upload Recording" or drag-and-drop an audio file
3. Supported formats: MP3, WAV, M4A, FLAC (max 500MB)
4. Wait for processing to complete (status shown in library)

### Chat with Recordings

1. Click the "Chat" tab
2. Type a question about your uploaded recordings
3. Example questions:
   - "What were the main concerns raised in customer calls?"
   - "Did any customer mention pricing issues?"
   - "Summarize the call from January 15th"
4. Responses include citations linking to source recordings

### View Transcripts

1. Click on any recording in the library
2. View full transcript with timestamps
3. Use search to find specific keywords
4. View auto-generated summary

### Manage Recordings

1. Rename: Click the edit icon next to recording title
2. Delete: Click delete icon (confirms before deletion)
3. Sort: Use dropdown to sort by date, title, or duration

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_HOST` | Lakebase PostgreSQL host | Yes |
| `POSTGRES_USER` | Database username | Yes |
| `POSTGRES_PASSWORD` | Database password | Yes |
| `POSTGRES_DB` | Database name (default: audio_rag) | Yes |
| `VOLUME_PATH` | UC Volume path for audio | Yes (in app.yaml) |

---

## Makefile Commands

```bash
make help              # Show all available commands

# Development
make install           # Install all dependencies
make run-local         # Run app locally
make local-prepare     # Prepare local environment

# Database
make db-migrate        # Run all pending migrations
make db-upgrade        # Alias for db-migrate
make db-downgrade      # Rollback last migration
make db-revision       # Create new migration

# Testing
make test              # Run all tests
make test-unit         # Run unit tests only
make test-integration  # Run integration tests
make test-cov          # Run tests with coverage report

# Code Quality
make lint              # Run linter (ruff)
make format            # Format code (ruff format)
make typecheck         # Run type checker (pyright)
make check             # Run all checks (lint + typecheck)

# Deployment
make deploy-dev        # Deploy to dev environment
make deploy-prod       # Deploy to production
make bundle-validate   # Validate bundle configuration
```

---

## Troubleshooting

### "Connection refused" to PostgreSQL

- Verify `POSTGRES_HOST` is correct
- Check Lakebase instance is running
- Ensure your IP is allowlisted in Lakebase firewall rules

### "Permission denied" on UC Volume

- Verify volume exists: `databricks volumes list main.default`
- Check app service principal has READ_WRITE on volume
- Verify volume is properly configured in app.yaml

### Diarization fails

- Check audio file is in WAV format (other formats converted automatically)
- Verify file size is under 500MB
- Check `audio-transcription-diarization-endpoint` is deployed and accessible
- Verify endpoint has GPU resources available (A10G required)
- For long files, chunking should handle automatically

### Chat returns no results

- Verify recordings have been fully processed (status: "completed")
- Check pgvector index exists in PostgreSQL
- Try a more specific query
- Check Claude endpoint is accessible

### Slow chat responses

- Check Claude endpoint provisioning (may need more throughput)
- Reduce number of retrieved chunks (k parameter)
- Consider smaller embedding chunks for faster retrieval

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Databricks App (Dash)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │  Upload  │  │  Library │  │   Chat   │  │ Transcript View  ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘│
└───────┼─────────────┼─────────────┼─────────────────┼──────────┘
        │             │             │                 │
        ▼             ▼             ▼                 ▼
┌───────────────────────────────────────────────────────────────┐
│                        Services Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │   Audio     │  │   Vector    │  │     Chat Agent          ││
│  │  Processor  │  │   Store     │  │    (LangGraph)          ││
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘│
└─────────┼────────────────┼─────────────────────┼──────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│  UC Volume   │  │  PostgreSQL  │  │   Databricks Model       │
│  (Audio)     │  │  + pgvector  │  │   Serving                │
└──────────────┘  └──────────────┘  │  - Claude Sonnet 4.5     │
                                    │  - GTE Large Embeddings  │
                                    │  - Diarization Endpoint  │
                                    └──────────────────────────┘
```

---

## Next Steps

After setup:

1. Upload a test audio file to verify end-to-end flow
2. Ask a question in chat to verify RAG pipeline
3. Review transcript quality and adjust chunking if needed
4. Configure model serving throughput for production load
