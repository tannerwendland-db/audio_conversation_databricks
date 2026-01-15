# Research: Audio Conversation RAG System

**Feature**: 001-audio-conversation-rag
**Date**: 2025-12-12

## Table of Contents

1. [Databricks Apps Architecture](#databricks-apps-architecture)
2. [Whisper Transcription on Databricks](#whisper-transcription-on-databricks)
3. [LangGraph RAG Agent Pattern](#langgraph-rag-agent-pattern)
4. [pgvector Integration](#pgvector-integration)
5. [Technology Decisions Summary](#technology-decisions-summary)

---

## Databricks Apps Architecture

### Decision: Use Dash framework with Databricks App deployment

**Rationale**:
- Dash is officially supported by Databricks Apps
- Native integration with Databricks SDK for UC Volumes and Model Serving
- OAuth 2.0 authentication handled automatically
- Serverless compute with no infrastructure management

**Alternatives Considered**:
- Streamlit: Also supported but Dash offers more control over layout and components
- Custom Flask: More work, less Databricks integration out of the box
- Gradio: Has limitations with UC Volume access in Databricks Apps

### Project Structure

```yaml
# app.yaml - Databricks App Configuration
command:
  - python
  - app.py

env:
  - name: POSTGRES_HOST
    valueFrom: postgres-host
  - name: POSTGRES_USER
    valueFrom: postgres-user
  - name: POSTGRES_PASSWORD
    valueFrom: postgres-password
  - name: POSTGRES_DB
    value: audio_rag
  - name: VOLUME_PATH
    value: '/Volumes/main/default/audio-recordings'

resources:
  secrets:
    - key: postgres-host
      scope: audio-rag-secrets
    - key: postgres-user
      scope: audio-rag-secrets
    - key: postgres-password
      scope: audio-rag-secrets

  volumes:
    - path: /Volumes/main/default/audio-recordings
      permission: READ_WRITE

  serving_endpoints:
    - name: databricks-claude-sonnet-4-5
      permission: QUERY
    - name: databricks-gte-large-en
      permission: QUERY
```

### Authentication Flow

- Databricks Apps use OAuth 2.0 with combined app + user identity
- Service principal handles M2M communication
- User permissions inherited from Databricks workspace
- No additional auth implementation needed for team-wide access

### File Upload Pattern

```python
from databricks.sdk import WorkspaceClient
import base64

w = WorkspaceClient()
volume_path = os.getenv('VOLUME_PATH')

def upload_audio(filename: str, content: bytes) -> str:
    """Upload audio file to UC Volume."""
    file_path = f"{volume_path}/{filename}"
    w.files.upload(file_path, content, overwrite=True)
    return file_path

def download_audio(file_path: str) -> bytes:
    """Download audio file from UC Volume."""
    response = w.files.download(file_path)
    return response.contents
```

---

## Audio Transcription with Speaker Diarization

### Decision: Use custom `audio-transcription-diarization-endpoint` deployed in Databricks

**Rationale**:
- Pre-deployed custom PyFunc model combining Whisper + Pyannote for speaker diarization
- GPU-accelerated inference (A10 GPU)
- Automatic speaker identification (Interviewer/Respondent labels)
- Exists in Databricks workspace - no additional deployment needed

**Alternatives Considered**:
- system.ai.whisper_large_v3: No speaker diarization support
- External API (OpenAI): No diarization, data leaves Databricks
- Separate Whisper + Pyannote calls: More complex, custom diarization endpoint already handles this

### Endpoint Details

**Endpoint Name**: `audio-transcription-diarization-endpoint`
**Input Format**: `dataframe_records` with `audio_base64` column
**Audio Format**: WAV file, base64-encoded
**GPU**: A10G (24GB memory)

### Client Code Pattern

```python
import base64
from databricks.sdk import WorkspaceClient

def diarize_audio(audio_bytes: bytes) -> dict:
    """Send audio to diarization endpoint."""
    w = WorkspaceClient()

    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    response = w.serving_endpoints.query(
        name="audio-transcription-diarization-endpoint",
        inputs={"audio_base64": audio_b64},
    )

    # Response contains predictions with transcription, status, error
    if hasattr(response, "predictions") and response.predictions:
        return response.predictions[0]
    return str(response)
```

### Output Format

```json
{
  "transcription": "Interviewer: Hello, how can I help you today?\nRespondent: I'm having issues with my account...",
  "status": "success",
  "error": null
}
```

**Speaker Labels**:
- `Interviewer`: First speaker detected
- `Respondent`: Second speaker detected
- `Respondent{N}`: Additional speakers if more than 2

### Audio Format Conversion

The diarization endpoint requires WAV format. For other formats (MP3, M4A, FLAC), convert before sending:

```python
import io
import librosa
import soundfile as sf

def convert_to_wav(audio_bytes: bytes, source_format: str) -> bytes:
    """Convert audio to WAV format at 16kHz mono."""
    # Load audio regardless of format
    y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)

    # Write as WAV
    buffer = io.BytesIO()
    sf.write(buffer, y, 16000, format='WAV')
    return buffer.getvalue()
```

### Large File Handling

For files larger than the endpoint can handle in one request, chunk the audio:

```python
import librosa
import soundfile as sf
import io

def chunk_audio(audio_bytes: bytes, chunk_duration_sec: int = 300) -> list[bytes]:
    """Split audio into chunks of specified duration."""
    y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000)

    chunk_samples = sr * chunk_duration_sec
    overlap_samples = sr * 5  # 5 second overlap for context

    chunks = []
    for i in range(0, len(y), chunk_samples - overlap_samples):
        chunk = y[i:i + chunk_samples]
        if len(chunk) > sr:  # Min 1 second
            buffer = io.BytesIO()
            sf.write(buffer, chunk, sr, format='WAV')
            chunks.append(buffer.getvalue())

    return chunks
```

---

## LangGraph RAG Agent Pattern

### Decision: Use LangGraph StateGraph with InMemorySaver

**Rationale**:
- LangGraph is the LangChain standard for stateful agents
- InMemorySaver provides session-only memory (spec requirement)
- Built-in support for conditional routing and self-correction
- Easy integration with custom LLM endpoints

**Alternatives Considered**:
- Raw LangChain: Less control over conversation flow
- Custom agent loop: Violates "prefer standard solutions" principle
- ReAct agent: Overkill for RAG; we don't need tool calling

### Agent State Design

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class RAGAgentState(TypedDict):
    """State for conversational RAG agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    retrieved_docs: list  # Current retrieval results
    source_citations: list[dict]  # Citation metadata for response
```

### Graph Architecture

```
START → retrieve → grade_relevance → [conditional]
                                      ├─ relevant → generate → END
                                      └─ irrelevant → rewrite_query → retrieve
```

Nodes:
1. **retrieve**: Query pgvector for relevant transcript chunks
2. **grade_relevance**: Use LLM to assess document relevance
3. **rewrite_query**: Reformulate unclear queries
4. **generate**: Produce response with citations

### Claude Integration via Databricks

```python
from databricks_langchain import ChatDatabricks

llm = ChatDatabricks(
    endpoint="databricks-claude-sonnet-4-5",
    temperature=0.1,  # Low for factual accuracy
    max_tokens=1024,
)
```

### Session Memory (Not Persisted)

```python
from langgraph.checkpoint.memory import InMemorySaver
import uuid

# Create checkpointer - memory cleared on app restart
checkpointer = InMemorySaver()

# Compile graph with memory
graph = builder.compile(checkpointer=checkpointer)

# Per-session thread ID
def get_session_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}

# Usage in Dash callback
session_id = str(uuid.uuid4())  # New session per browser tab
response = graph.invoke(
    {"messages": [HumanMessage(content=user_query)]},
    config=get_session_config(session_id)
)
```

### Citation Format

```python
GENERATION_PROMPT = """Answer based on these transcript excerpts:

{context}

Cite sources using format: [Recording: {title}, {timestamp}]

Question: {question}

Answer:"""

def format_context_with_citations(docs: list) -> str:
    """Format retrieved docs for LLM context."""
    return "\n\n".join([
        f"[Source {i}]\n"
        f"Recording: {doc.metadata['recording_title']}\n"
        f"Time: {doc.metadata['timestamp']}\n"
        f"Content: {doc.page_content}"
        for i, doc in enumerate(docs)
    ])
```

---

## pgvector Integration

### Decision: Use langchain-postgres with PGVector

**Rationale**:
- Official LangChain integration for pgvector
- Supports metadata filtering (by recording, timestamp, etc.)
- MMR search for result diversity
- Works with any PostgreSQL 17 + pgvector

**Alternatives Considered**:
- Databricks Vector Search: Would require Delta Lake, more complex
- Pinecone/Weaviate: External service, additional cost
- Raw psycopg2: No LangChain integration, more code

### Connection Setup

```python
from langchain_postgres import PGVector
from databricks_langchain import DatabricksEmbeddings
import os

# Embeddings via Databricks
embeddings = DatabricksEmbeddings(
    endpoint="databricks-gte-large-en"
)

# Vector store connection
connection_string = (
    f"postgresql+psycopg://{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:5432/"
    f"{os.getenv('POSTGRES_DB')}"
)

vector_store = PGVector(
    embeddings=embeddings,
    collection_name="transcript_chunks",
    connection=connection_string,
    use_jsonb=True,  # For metadata filtering
)
```

### Document Schema

```python
from langchain.schema import Document

def create_transcript_chunks(
    recording_id: str,
    recording_title: str,
    transcript: dict,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> list[Document]:
    """Create vectorizable chunks from transcript."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    # Combine segments into full text with timestamps
    full_text = transcript["text"]
    chunks = splitter.split_text(full_text)

    documents = []
    for i, chunk in enumerate(chunks):
        # Find approximate timestamp for chunk
        timestamp = estimate_timestamp(chunk, transcript["segments"])

        documents.append(Document(
            page_content=chunk,
            metadata={
                "recording_id": recording_id,
                "recording_title": recording_title,
                "chunk_index": i,
                "timestamp": timestamp,
                "source_type": "transcript"
            }
        ))

    return documents
```

### Retrieval with Filtering

```python
# As retriever for LangGraph
retriever = vector_store.as_retriever(
    search_type="mmr",  # Maximum Marginal Relevance
    search_kwargs={
        "k": 5,  # Return top 5
        "fetch_k": 20,  # Consider top 20 for MMR
    }
)

# With metadata filter (e.g., specific recording)
def search_specific_recording(query: str, recording_id: str):
    return vector_store.similarity_search(
        query,
        k=5,
        filter={"recording_id": {"$eq": recording_id}}
    )
```

### Database Schema (Alembic Migration)

```python
# alembic/versions/001_initial_schema.py
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade():
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Recordings table
    op.create_table(
        'recordings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('volume_path', sa.String(500), nullable=False),
        sa.Column('duration_seconds', sa.Float),
        sa.Column('processing_status', sa.String(50), default='pending'),
        sa.Column('uploaded_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )

    # Transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('recording_id', sa.String(36), sa.ForeignKey('recordings.id')),
        sa.Column('full_text', sa.Text, nullable=False),
        sa.Column('language', sa.String(10)),
        sa.Column('segments_json', sa.JSON),  # Store raw Whisper segments
        sa.Column('summary', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # langchain_pg_embedding table created automatically by PGVector
    # but we can customize it if needed

def downgrade():
    op.drop_table('transcripts')
    op.drop_table('recordings')
```

---

## Technology Decisions Summary

| Component | Decision | Rationale |
|-----------|----------|-----------|
| **Web Framework** | Dash | User specified; Databricks-supported; good for data apps |
| **Database ORM** | SQLAlchemy + Alembic | User specified; standard Python ORM with migrations |
| **Vector Store** | pgvector (langchain-postgres) | User specified PostgreSQL; native LangChain integration |
| **Embeddings** | databricks-gte-large-en | User specified; available in workspace |
| **LLM** | Claude Sonnet 4.5 (databricks-claude-sonnet-4-5) | User specified; via Databricks Model Serving |
| **Transcription + Diarization** | `audio-transcription-diarization-endpoint` | User specified; Custom PyFunc with Whisper + Pyannote |
| **Agent Framework** | LangGraph | Constitution: prefer standard solutions; LangChain standard |
| **Session Memory** | InMemorySaver | Spec: session-only; simplest option |
| **Package Manager** | uv | User specified; fast Python package management |
| **Task Runner** | Makefile | User specified; human-friendly commands |
| **Deployment** | Databricks Asset Bundles | Standard Databricks deployment pattern |
| **Secrets** | Databricks Secrets | Native integration; password-based auth per user spec |

### Dependencies (requirements.txt)

```text
# Core
dash>=3.3.0
dash-bootstrap-components>=2.0.0
plotly>=6.5.0

# Database
sqlalchemy>=2.0.0
psycopg[binary]>=3.0.0
alembic>=1.13.0
pgvector>=0.2.0

# AI/ML
langchain>=0.3.0
langchain-postgres>=0.0.8
langgraph>=0.2.0
databricks-langchain>=0.1.0
databricks-sdk>=0.30.0

# Audio processing
librosa>=0.10.0
soundfile>=0.12.0

# Utilities
python-dotenv>=1.0.0
pydantic>=2.0.0
```

### Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `POSTGRES_HOST` | Databricks Secret | Lakebase PostgreSQL host |
| `POSTGRES_USER` | Databricks Secret | Database username |
| `POSTGRES_PASSWORD` | Databricks Secret | Database password |
| `POSTGRES_DB` | app.yaml | Database name (audio_rag) |
| `VOLUME_PATH` | app.yaml | UC Volume path for audio files |
| `DATABRICKS_HOST` | Auto-injected | Workspace URL |
| `DATABRICKS_CLIENT_ID` | Auto-injected | App service principal |
| `DATABRICKS_CLIENT_SECRET` | Auto-injected | App service principal secret |
