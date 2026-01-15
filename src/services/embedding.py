"""Embedding service for the Audio Conversation RAG System.

This module provides functions for chunking transcripts, generating embeddings,
storing chunks in the database, and performing similarity search for RAG.
"""

import logging
import re

from databricks_langchain import DatabricksEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import Recording, TranscriptChunk

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Exception raised for errors during embedding operations."""

    pass


def chunk_transcript(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split transcript text into overlapping chunks.

    Uses LangChain's RecursiveCharacterTextSplitter to split text into
    chunks of approximately chunk_size characters with overlap between
    consecutive chunks for context preservation.

    Args:
        text: The transcript text to chunk.
        chunk_size: Maximum size of each chunk in characters. Defaults to 500.
        overlap: Number of overlapping characters between chunks. Defaults to 50.

    Returns:
        A list of text chunks. Returns empty list for empty or whitespace-only text.

    Raises:
        ValueError: If chunk_size <= 0, overlap < 0, or overlap >= chunk_size.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    # Handle empty or whitespace-only text
    if not text or not text.strip():
        logger.debug("Empty or whitespace-only text provided to chunk_transcript")
        return []

    logger.debug(f"Chunking transcript with input length {len(text)} characters")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = text_splitter.split_text(text)
    logger.info(f"Created {len(chunks)} chunks from transcript")
    return chunks


def chunk_dialog(
    dialog: list[dict],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Chunk dialog by speaker turns with speaker context preservation.

    Each chunk includes speaker prefix for embedding context.
    Long turns are split while maintaining speaker attribution.

    Args:
        dialog: List of dicts with 'speaker' and 'text' keys.
        chunk_size: Maximum characters per chunk. Defaults to 500.
        overlap: Overlap between chunks for long turns. Defaults to 50.

    Returns:
        List of chunk strings with speaker context.

    Raises:
        ValueError: If chunk_size <= 0, overlap < 0, or overlap >= chunk_size.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    if not dialog:
        return []

    chunks = []

    for turn in dialog:
        speaker = turn.get("speaker", "Unknown")
        text = turn.get("text", "")

        if not text:
            continue

        prefix = f"[{speaker}]: "
        full_text = prefix + text

        # If turn fits in one chunk
        if len(full_text) <= chunk_size:
            chunks.append(full_text)
        else:
            # Split long turn using text splitter but maintain speaker prefix
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size - len(prefix),
                chunk_overlap=overlap,
                length_function=len,
                is_separator_regex=False,
            )
            sub_chunks = text_splitter.split_text(text)
            for sub_chunk in sub_chunks:
                chunks.append(prefix + sub_chunk)

    logger.info(f"Created {len(chunks)} chunks from dialog")
    return chunks


def _extract_speaker(text: str) -> str | None:
    """Extract the first speaker label from chunk text.

    Looks for patterns like:
    - "[Interviewer]: text..." (new format from chunk_dialog)
    - "[Interviewer 0:00:00]" (legacy format with timestamp)

    Args:
        text: The chunk text to search for speaker labels.

    Returns:
        The speaker name (e.g., "Interviewer", "Respondent") or None if not found.
    """
    # New format: [Speaker]: text...
    new_pattern = r"^\[(\w+)\]:"
    match = re.match(new_pattern, text)
    if match:
        return match.group(1)

    # Legacy format: [Interviewer 0:00:00] or [Respondent 1:30:45]
    legacy_pattern = r"\[(Interviewer|Respondent)\s+\d+:\d+:\d+\]"
    match = re.search(legacy_pattern, text)
    if match:
        return match.group(1)

    return None


def _get_embeddings_model() -> DatabricksEmbeddings:
    """Get configured DatabricksEmbeddings instance.

    Returns:
        DatabricksEmbeddings instance configured with the embedding endpoint.
    """
    settings = get_settings()
    return DatabricksEmbeddings(endpoint=settings.EMBEDDING_ENDPOINT)


def store_transcript_chunks(
    session: Session,
    recording_id: str,
    chunks: list[str],
    title: str,
) -> int:
    """Store transcript chunks with embeddings in the database.

    Generates embeddings for the provided text chunks and stores them
    in the transcript_chunks table with proper FK to the recording.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the parent recording.
        chunks: List of text chunks to embed and store.
        title: Title of the recording (for logging).

    Returns:
        The number of chunks stored.

    Raises:
        EmbeddingError: If embedding generation or storage fails.
    """
    if not chunks:
        logger.debug("No chunks provided to store_transcript_chunks")
        return 0

    try:
        # Generate embeddings for all chunks in batch
        embeddings_model = _get_embeddings_model()
        embeddings = embeddings_model.embed_documents(chunks)

        logger.debug(
            f"Generated {len(embeddings)} embeddings for recording {recording_id}"
        )

        # Create TranscriptChunk objects
        chunk_objects = []
        chunk_pairs = zip(chunks, embeddings, strict=True)
        for i, (chunk_text, embedding) in enumerate(chunk_pairs):
            speaker = _extract_speaker(chunk_text)
            chunk_obj = TranscriptChunk(
                recording_id=recording_id,
                chunk_index=i,
                content=chunk_text,
                speaker=speaker,
                embedding=embedding,
            )
            chunk_objects.append(chunk_obj)

        # Bulk insert
        session.add_all(chunk_objects)
        session.flush()

        logger.info(
            f"Stored {len(chunk_objects)} transcript chunks "
            f"for recording {recording_id}"
        )
        return len(chunk_objects)

    except Exception as e:
        error_msg = f"Failed to store chunks for recording {recording_id}: {e}"
        logger.error(error_msg, exc_info=True)
        raise EmbeddingError(error_msg) from e


def similarity_search(
    session: Session,
    query: str,
    k: int = 5,
    recording_ids: list[str] | None = None,
) -> list[TranscriptChunk]:
    """Find transcript chunks most similar to the query.

    Uses cosine similarity with pgvector to find the k most similar
    chunks to the query embedding.

    Args:
        session: SQLAlchemy database session.
        query: The search query text.
        k: Number of results to return. Defaults to 5.
        recording_ids: Optional list of recording IDs to filter results.
            If provided, only returns chunks from those recordings.
            If None or empty list, searches across all recordings.

    Returns:
        List of TranscriptChunk objects ordered by similarity (most similar first).

    Raises:
        EmbeddingError: If embedding generation or search fails.
    """
    try:
        # Generate embedding for query
        embeddings_model = _get_embeddings_model()
        query_embedding = embeddings_model.embed_query(query)

        # Format embedding as PostgreSQL array literal
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Determine if we need to filter by recording IDs
        # None or empty list means search all recordings
        if recording_ids:
            # Filter by recording_ids using ANY() with array parameter
            stmt = text("""
                SELECT id, recording_id, chunk_index, content, speaker,
                       embedding, created_at
                FROM transcript_chunks
                WHERE recording_id = ANY(:recording_ids)
                ORDER BY embedding <=> :query_embedding
                LIMIT :k
            """)
            result = session.execute(
                stmt,
                {
                    "recording_ids": recording_ids,
                    "query_embedding": embedding_str,
                    "k": k,
                },
            )
        else:
            # Search across all recordings
            stmt = text("""
                SELECT id, recording_id, chunk_index, content, speaker,
                       embedding, created_at
                FROM transcript_chunks
                ORDER BY embedding <=> :query_embedding
                LIMIT :k
            """)
            result = session.execute(
                stmt, {"query_embedding": embedding_str, "k": k}
            )

        # Convert rows to TranscriptChunk objects
        chunks = []
        for row in result:
            chunk = TranscriptChunk(
                id=row.id,
                recording_id=row.recording_id,
                chunk_index=row.chunk_index,
                content=row.content,
                speaker=row.speaker,
                embedding=list(row.embedding) if row.embedding else [],
                created_at=row.created_at,
            )
            chunks.append(chunk)

        # Fetch and set the recording relationship for each chunk
        if chunks:
            chunk_recording_ids = list(set(c.recording_id for c in chunks))
            recordings = (
                session.query(Recording)
                .filter(Recording.id.in_(chunk_recording_ids))
                .all()
            )
            recording_map = {r.id: r for r in recordings}
            for chunk in chunks:
                chunk.recording = recording_map.get(chunk.recording_id)

        logger.debug(f"Similarity search returned {len(chunks)} results")
        return chunks

    except Exception as e:
        error_msg = f"Similarity search failed: {e}"
        logger.error(error_msg, exc_info=True)
        raise EmbeddingError(error_msg) from e


def delete_recording_chunks(session: Session, recording_id: str) -> int:
    """Delete all transcript chunks for a recording.

    Note: With CASCADE delete on the FK, this is typically not needed as
    deleting the recording will cascade to chunks. This function is provided
    for cases where you want to re-process a recording's embeddings.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording whose chunks should be deleted.

    Returns:
        The number of chunks deleted.
    """
    stmt = text(
        """
        DELETE FROM transcript_chunks
        WHERE recording_id = :recording_id
        """
    )
    result = session.execute(stmt, {"recording_id": recording_id})
    session.flush()

    deleted_count = result.rowcount
    logger.info(f"Deleted {deleted_count} chunks for recording {recording_id}")
    return deleted_count
