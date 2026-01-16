"""Streaming service for Server-Sent Events (SSE) in the Audio Conversation RAG System.

This module provides SSE endpoints and utilities for streaming RAG responses
token-by-token to the chat interface. It handles connection management,
token delivery, citation sending, and error handling.
"""

import json
import logging
from collections.abc import Generator
from typing import Any

from flask import Response, request

from src.db.session import get_session
from src.services.embedding import similarity_search
from src.services.rag import _get_llm, format_context_with_citations

logger = logging.getLogger(__name__)


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event with type and JSON data.

    Args:
        event_type: The event type (token, citations, done, error).
        data: The event data to serialize as JSON.

    Returns:
        SSE-formatted string with event type and data.
    """
    # Include event type in the data payload for client to distinguish
    data_with_type = {"type": event_type, **data}
    return f"data: {json.dumps(data_with_type)}\n\n"


def streaming_generate(
    query: str,
    context: str,
) -> Generator[str, None, None]:
    """Stream tokens from LLM generation.

    Uses ChatDatabricks.stream() to yield tokens incrementally.

    Args:
        query: The user's question.
        context: Formatted context with citations from retrieved documents.

    Yields:
        Token strings from the LLM response.
    """
    generation_prompt = (
        "You are a helpful assistant answering questions based on "
        "transcript excerpts from audio recordings.\n\n"
        "Use the following context to answer the user's question. "
        "Include citation numbers in brackets [1], [2], etc. "
        "to reference your sources.\n\n"
        f"Context:\n{context}\n\n"
        f"User Question: {query}\n\n"
        "Provide a clear, concise answer based on the context. "
        "If the context doesn't contain relevant information, say so."
    )

    logger.info("Initializing LLM for streaming generation")
    llm = _get_llm()
    logger.info("LLM initialized, starting token stream")

    token_count = 0
    for chunk in llm.stream(generation_prompt):
        if chunk.content:
            token_count += 1
            yield chunk.content

    logger.info(f"Streaming complete, yielded {token_count} tokens")


def stream_rag_response(
    query: str,
    session_id: str,
    recording_filter: list[str] | None = None,
) -> Generator[str, None, None]:
    """Stream RAG response tokens as SSE events.

    Executes retrieval synchronously, then streams generation tokens.
    After all tokens, sends citations and done events.

    Args:
        query: The user's question.
        session_id: Unique session identifier.
        recording_filter: Optional list of recording IDs to filter results.

    Yields:
        SSE-formatted event strings for token, citations, done, or error events.
    """
    logger.info(f"Starting streaming RAG response for session {session_id}")
    logger.info(f"Query: {query[:100]}...")
    if recording_filter:
        logger.info(f"Recording filter: {recording_filter}")

    session = get_session()
    try:
        # Synchronous retrieval
        logger.info("Starting similarity search")
        chunks = similarity_search(
            session=session,
            query=query,
            k=5,
            recording_ids=recording_filter,
        )
        logger.info(f"Similarity search complete, found {len(chunks)} chunks")

        if not chunks:
            logger.info("No relevant documents found for query")
            no_results_msg = "No relevant information found in the available transcripts."
            yield format_sse_event("token", {"content": no_results_msg})
            yield format_sse_event("citations", {"citations": []})
            yield format_sse_event("done", {})
            return

        # Build context and citations
        context = format_context_with_citations(chunks)
        citations = []
        for chunk in chunks:
            citations.append({
                "recording_id": chunk.recording.id if chunk.recording else None,
                "recording_title": chunk.recording.title if chunk.recording else "Unknown",
                "excerpt": chunk.content,
                "speaker": chunk.speaker,
            })

        # Stream tokens from LLM
        logger.info("Starting LLM token generation")
        for token in streaming_generate(query=query, context=context):
            yield format_sse_event("token", {"content": token})

        # Send citations after all tokens
        yield format_sse_event("citations", {"citations": citations})

        # Signal completion
        yield format_sse_event("done", {})

        logger.info(f"Completed streaming for session {session_id} with {len(citations)} citations")

    except Exception as e:
        logger.error(f"Error during streaming: {e}", exc_info=True)
        yield format_sse_event("error", {
            "message": str(e),
            "code": "GENERATION_FAILED",
        })
    finally:
        session.close()


def stream_chat_endpoint() -> Response:
    """Handle the /api/chat/stream POST endpoint.

    Parses the request body and returns an SSE stream of RAG response tokens.

    Returns:
        Flask Response with text/event-stream mimetype.
    """
    logger.info("stream_chat_endpoint() called")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request content-type: {request.content_type}")
    logger.info(f"Request content-length: {request.content_length}")
    raw_data = request.get_data(as_text=True)
    logger.info(f"Raw request body: {raw_data[:200]}")
    data = request.get_json(force=True, silent=True) or {}
    logger.info(f"Request data: query={data.get('query', '')[:50]}..., session_id={data.get('session_id', '')}")
    query = data.get("query", "")
    session_id = data.get("session_id", "")
    recording_filter = data.get("recording_filter")

    if not query:
        return Response(
            json.dumps({"error": "query is required"}),
            status=400,
            mimetype="application/json",
        )

    def generate() -> Generator[str, None, None]:
        logger.info("Generator started - client is consuming the stream")
        yield from stream_rag_response(
            query=query,
            session_id=session_id,
            recording_filter=recording_filter,
        )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
