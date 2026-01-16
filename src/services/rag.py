"""RAG (Retrieval Augmented Generation) service for the Audio Conversation RAG System.

This module provides a LangGraph-based RAG agent that retrieves relevant transcript
chunks and generates answers with source citations. It implements a multi-node
workflow with retrieval, grading, generation, and query rewriting capabilities.
"""

import logging
from typing import Any, TypedDict

from databricks_langchain import ChatDatabricks, DatabricksEmbeddings
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import TranscriptChunk
from src.services.embedding import similarity_search

logger = logging.getLogger(__name__)


class RAGError(Exception):
    """Exception raised for errors during RAG operations."""

    pass


class RAGAgentState(TypedDict, total=False):
    """State schema for the RAG agent workflow.

    Attributes:
        messages: List of conversation messages.
        retrieved_docs: List of TranscriptChunk objects retrieved from
            similarity search.
        source_citations: List of citation dictionaries with recording metadata.
        grade_decision: Decision from grading node ("relevant" or "not_relevant").
    """

    messages: list[BaseMessage]
    retrieved_docs: list[TranscriptChunk]
    source_citations: list[dict[str, Any]]
    grade_decision: str


def _get_llm() -> ChatDatabricks:
    """Get configured ChatDatabricks LLM instance.

    Returns:
        ChatDatabricks instance configured with the LLM endpoint.
    """
    settings = get_settings()
    logger.info(f"Initializing ChatDatabricks with endpoint: {settings.LLM_ENDPOINT}")
    return ChatDatabricks(endpoint=settings.LLM_ENDPOINT)


def _get_embeddings_model() -> DatabricksEmbeddings:
    """Get configured DatabricksEmbeddings instance.

    Returns:
        DatabricksEmbeddings instance configured with the embedding endpoint.
    """
    settings = get_settings()
    return DatabricksEmbeddings(endpoint=settings.EMBEDDING_ENDPOINT)


def _create_citation(chunk: TranscriptChunk) -> dict[str, Any]:
    """Create a citation dictionary from a TranscriptChunk.

    Args:
        chunk: The TranscriptChunk to create a citation for.

    Returns:
        Dictionary containing recording_id, recording_title, excerpt, and speaker.
    """
    return {
        "recording_id": chunk.recording.id,
        "recording_title": chunk.recording.title,
        "excerpt": chunk.content,
        "speaker": chunk.speaker,
    }


def format_context_with_citations(chunks: list[TranscriptChunk]) -> str:
    """Format retrieved chunks as context with citation markers.

    Creates a formatted string with each chunk's content and source information
    for use in the LLM prompt.

    Args:
        chunks: List of TranscriptChunk objects to format.

    Returns:
        Formatted string with chunk contents and source citations.
    """
    if not chunks:
        return ""

    formatted_parts = []
    for i, chunk in enumerate(chunks, start=1):
        recording_title = chunk.recording.title if chunk.recording else "Unknown"
        speaker_info = f" - {chunk.speaker}" if chunk.speaker else ""

        formatted_parts.append(
            f"[Source {i}: Recording: {recording_title}{speaker_info}]\n{chunk.content}\n"
        )

    return "\n".join(formatted_parts)


def _compute_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity score (0 to 1, higher is more similar).
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def _retrieve_node(
    state: RAGAgentState,
    session: Session,
    recording_ids: list[str] | None = None,
) -> dict[str, Any]:
    """LangGraph node for retrieving relevant transcript chunks.

    Extracts the query from the last message and performs similarity search
    to find relevant transcript chunks.

    Args:
        state: Current RAG agent state.
        session: SQLAlchemy database session.
        recording_ids: Optional list of recording IDs to filter results.

    Returns:
        State update dict with retrieved_docs.

    Raises:
        RAGError: If retrieval fails.
    """
    try:
        # Extract query from the last message
        messages = state.get("messages", [])
        if not messages:
            logger.warning("No messages in state for retrieval")
            return {"retrieved_docs": []}

        query = messages[-1].content
        logger.debug(f"Retrieving documents for query: {query[:100]}...")

        # Perform similarity search
        chunks = similarity_search(
            session=session,
            query=query,
            k=5,
            recording_ids=recording_ids,
        )

        logger.info(f"Retrieved {len(chunks)} relevant chunks")
        return {"retrieved_docs": chunks}

    except Exception as e:
        error_msg = f"Document retrieval failed: {e}"
        logger.error(error_msg, exc_info=True)
        raise RAGError(error_msg) from e


def _grade_node(state: RAGAgentState) -> dict[str, Any]:
    """LangGraph node for grading document relevance.

    Uses the LLM to assess whether retrieved documents are relevant
    to the user's query.

    Args:
        state: Current RAG agent state.

    Returns:
        State update dict with grade_decision ("relevant" or "not_relevant").
    """
    retrieved_docs = state.get("retrieved_docs", [])

    # If no documents retrieved, mark as not relevant
    if not retrieved_docs:
        logger.debug("No documents to grade, marking as not_relevant")
        return {"grade_decision": "not_relevant"}

    messages = state.get("messages", [])
    if not messages:
        return {"grade_decision": "not_relevant"}

    query = messages[-1].content

    # Build context from retrieved docs
    docs_text = "\n\n".join(
        f"Document {i + 1}: {doc.content}" for i, doc in enumerate(retrieved_docs)
    )

    # Create grading prompt
    grading_prompt = (
        "You are a grader assessing the relevance of retrieved documents "
        "to a user question.\n\n"
        f"User Question: {query}\n\n"
        f"Retrieved Documents:\n{docs_text}\n\n"
        "Determine if any of the retrieved documents contain information "
        "relevant to answering the user's question.\n"
        'Respond with ONLY one word: "relevant" if at least one document '
        'is relevant, or "not_relevant" if none are relevant.'
    )

    try:
        llm = _get_llm()
        response = llm.invoke([HumanMessage(content=grading_prompt)])
        decision = response.content.strip().lower()

        # Normalize the decision
        if "relevant" in decision and "not" not in decision:
            grade_decision = "relevant"
        else:
            grade_decision = "not_relevant"

        logger.debug(f"Document relevance grade: {grade_decision}")
        return {"grade_decision": grade_decision}

    except Exception as e:
        logger.warning(f"Grading failed, defaulting to relevant: {e}")
        # Default to relevant on error to avoid blocking the flow
        return {"grade_decision": "relevant"}


def _generate_node(state: RAGAgentState) -> dict[str, Any]:
    """LangGraph node for generating answers with citations.

    Uses the LLM to generate an answer based on retrieved documents,
    including proper source citations.

    Args:
        state: Current RAG agent state.

    Returns:
        State update dict with messages and source_citations.

    Raises:
        RAGError: If generation fails.
    """
    retrieved_docs = state.get("retrieved_docs", [])
    messages = state.get("messages", [])

    if not messages:
        return {"messages": [], "source_citations": []}

    query = messages[-1].content

    # Format context with citations
    context = format_context_with_citations(retrieved_docs)

    # Build generation prompt
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

    try:
        llm = _get_llm()
        response = llm.invoke([HumanMessage(content=generation_prompt)])

        # Create citations for each retrieved doc
        citations = [_create_citation(chunk) for chunk in retrieved_docs]

        logger.debug("Generated response with citations")
        return {
            "messages": [response],
            "source_citations": citations,
        }

    except Exception as e:
        error_msg = f"Answer generation failed: {e}"
        logger.error(error_msg, exc_info=True)
        raise RAGError(error_msg) from e


def _rewrite_node(state: RAGAgentState) -> dict[str, Any]:
    """LangGraph node for rewriting queries to improve retrieval.

    Uses the LLM to rewrite the user's query into a form that may
    yield better search results.

    Args:
        state: Current RAG agent state.

    Returns:
        State update dict with rewritten query in messages.
    """
    messages = state.get("messages", [])

    if not messages:
        return {"messages": []}

    original_query = messages[-1].content

    rewrite_prompt = (
        "You are a query rewriter. Your task is to improve the following "
        "query for better semantic search results.\n\n"
        f"Original Query: {original_query}\n\n"
        "Rewrite this query to be more specific and likely to match "
        "relevant document content. Return ONLY the rewritten query, "
        "nothing else."
    )

    try:
        llm = _get_llm()
        response = llm.invoke([HumanMessage(content=rewrite_prompt)])
        rewritten_query = response.content.strip()

        logger.debug(f"Rewrote query: {original_query[:50]}... -> {rewritten_query[:50]}...")

        return {"messages": [HumanMessage(content=rewritten_query)]}

    except Exception as e:
        logger.warning(f"Query rewrite failed, using original: {e}")
        return {"messages": messages}


def _route_after_grade(state: RAGAgentState) -> str:
    """Routing function after grading node.

    Determines whether to proceed to generation or rewrite based on
    the grading decision.

    Args:
        state: Current RAG agent state.

    Returns:
        Next node name: "generate" if relevant, "rewrite" if not.
    """
    grade_decision = state.get("grade_decision", "not_relevant")
    if grade_decision == "relevant":
        return "generate"
    return "rewrite"


def build_rag_graph(
    session: Session,
    recording_filter: list[str] | None = None,
) -> Any:
    """Build and compile the RAG LangGraph workflow.

    Creates a graph with retrieve, grade, generate, and rewrite nodes
    connected by conditional edges based on relevance grading.

    Args:
        session: SQLAlchemy database session for retrieval operations.
        recording_filter: Optional list of recording IDs to filter retrieval results.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    # Create the graph with our state schema
    graph = StateGraph(RAGAgentState)

    # Create node functions that capture session and recording_filter
    def retrieve_node(state: RAGAgentState) -> dict[str, Any]:
        return _retrieve_node(state, session=session, recording_ids=recording_filter)

    def grade_node(state: RAGAgentState) -> dict[str, Any]:
        return _grade_node(state)

    def generate_node(state: RAGAgentState) -> dict[str, Any]:
        return _generate_node(state)

    def rewrite_node(state: RAGAgentState) -> dict[str, Any]:
        return _rewrite_node(state)

    # Add nodes
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("generate", generate_node)
    graph.add_node("rewrite", rewrite_node)

    # Set entry point
    graph.set_entry_point("retrieve")

    # Add edges
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        _route_after_grade,
        {
            "generate": "generate",
            "rewrite": "rewrite",
        },
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", END)

    return graph.compile()


def retrieve_documents(
    session: Session,
    query: str,
    k: int = 5,
    recording_id: str | None = None,
) -> list[TranscriptChunk]:
    """Retrieve relevant transcript chunks for a query.

    Generates query embeddings and performs vector similarity search.
    Uses Python-based similarity computation for compatibility with
    non-pgvector databases (e.g., SQLite for testing).

    Args:
        session: SQLAlchemy database session.
        query: The search query text.
        k: Number of results to return. Defaults to 5.
        recording_id: Optional recording ID to filter results.

    Returns:
        List of TranscriptChunk objects ordered by similarity.
    """
    # Generate embedding for query
    embeddings_model = _get_embeddings_model()
    query_embedding = embeddings_model.embed_query(query)

    # Query chunks using ORM (compatible with SQLite and PostgreSQL)
    query_obj = session.query(TranscriptChunk)

    if recording_id:
        query_obj = query_obj.filter(TranscriptChunk.recording_id == recording_id)

    # Get all matching chunks
    all_chunks = query_obj.all()

    if not all_chunks:
        logger.debug("No chunks found in database")
        return []

    # Compute similarity scores and sort
    chunks_with_scores = []
    for chunk in all_chunks:
        # Check if embedding exists (handle numpy arrays and lists)
        if chunk.embedding is not None and len(chunk.embedding) > 0:
            # Convert embedding to list if needed
            embedding = list(chunk.embedding)
            similarity = _compute_cosine_similarity(query_embedding, embedding)
            chunks_with_scores.append((chunk, similarity))

    # Sort by similarity (descending) and take top k
    chunks_with_scores.sort(key=lambda x: x[1], reverse=True)
    top_chunks = [chunk for chunk, _ in chunks_with_scores[:k]]

    logger.debug(f"retrieve_documents returned {len(top_chunks)} results")
    return top_chunks


def generate_response_with_citations(
    session: Session,
    query: str,
    recording_id: str | None = None,
    k: int = 5,
) -> dict[str, Any]:
    """Generate a response with citations for a query.

    Retrieves relevant documents and generates an LLM response with
    proper source citations. Handles empty results gracefully.

    Args:
        session: SQLAlchemy database session.
        query: The user's question.
        recording_id: Optional recording ID to filter retrieval.
        k: Number of documents to retrieve. Defaults to 5.

    Returns:
        Dictionary with "response" (str) and "citations" (list of dicts).
    """
    # Retrieve relevant documents
    chunks = retrieve_documents(
        session=session,
        query=query,
        k=k,
        recording_id=recording_id,
    )

    # Handle empty results - don't call LLM
    if not chunks:
        logger.info("No relevant documents found for query")
        return {
            "response": "No relevant information found in the available transcripts.",
            "citations": [],
        }

    # Format context
    context = format_context_with_citations(chunks)

    # Build prompt
    generation_prompt = (
        "You are a helpful assistant answering questions based on "
        "transcript excerpts from audio recordings.\n\n"
        "Use the following context to answer the user's question. "
        "Include citation numbers in brackets [1], [2], etc. "
        "to reference your sources.\n\n"
        f"Context:\n{context}\n\n"
        f"User Question: {query}\n\n"
        "Provide a clear, concise answer based on the context."
    )

    # Generate response
    llm = _get_llm()
    response = llm.invoke([HumanMessage(content=generation_prompt)])

    # Create citations
    citations = []
    for chunk in chunks:
        citation = {
            "recording_id": chunk.recording_id,
            "recording_title": chunk.recording.title if chunk.recording else "Unknown",
            "content": chunk.content,
            "chunk_id": chunk.id,
            "source": chunk.recording.title if chunk.recording else "Unknown",
        }
        if chunk.speaker:
            citation["speaker"] = chunk.speaker
        citations.append(citation)

    return {
        "response": response.content,
        "citations": citations,
    }


def rag_query(
    session: Session,
    query: str,
    session_id: str,
    recording_filter: list[str] | None = None,
) -> dict[str, Any]:
    """Execute a RAG query using the full graph workflow.

    Builds and invokes the RAG graph to process the query through
    retrieval, grading, and generation stages.

    Args:
        session: SQLAlchemy database session.
        query: The user's question.
        session_id: Unique session identifier for tracking.
        recording_filter: Optional list of recording IDs to filter results.

    Returns:
        Dictionary with "answer" (str) and "citations" (list of dicts).
    """
    logger.info(f"Processing RAG query for session {session_id}")

    # Build the graph
    graph = build_rag_graph(session=session, recording_filter=recording_filter)

    # Create initial state
    initial_state: RAGAgentState = {
        "messages": [HumanMessage(content=query)],
        "retrieved_docs": [],
        "source_citations": [],
    }

    # Invoke the graph
    result = graph.invoke(initial_state)

    # Extract answer from result
    messages = result.get("messages", [])
    answer = messages[-1].content if messages else "Unable to generate an answer."

    citations = result.get("source_citations", [])

    logger.info(f"RAG query completed with {len(citations)} citations")

    return {
        "answer": answer,
        "citations": citations,
    }
