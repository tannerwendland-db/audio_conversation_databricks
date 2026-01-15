"""Unit tests for the RAG (Retrieval Augmented Generation) service module.

This module tests the RAG service functions for building a LangGraph-based
RAG agent that retrieves relevant transcript chunks and generates answers
with source citations.

NOTE: This is a TDD test file. The tests are written BEFORE the implementation
exists in src/services/rag.py. Tests will fail with ImportError until the
implementation is created.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestRAGAgentState:
    """Test cases for RAGAgentState TypedDict schema."""

    def test_state_has_required_fields(self):
        """RAGAgentState should define messages, retrieved_docs, and source_citations fields."""
        from src.services.rag import RAGAgentState

        # Verify the TypedDict has the expected annotations
        annotations = RAGAgentState.__annotations__

        assert "messages" in annotations
        assert "retrieved_docs" in annotations
        assert "source_citations" in annotations

    def test_state_messages_is_list(self):
        """The messages field should accept a list type."""
        from src.services.rag import RAGAgentState

        annotations = RAGAgentState.__annotations__

        # Check that messages annotation indicates list type
        messages_type = annotations["messages"]
        assert "list" in str(messages_type).lower() or hasattr(messages_type, "__origin__")

    def test_state_retrieved_docs_is_list(self):
        """The retrieved_docs field should accept a list type."""
        from src.services.rag import RAGAgentState

        annotations = RAGAgentState.__annotations__

        # Check that retrieved_docs annotation indicates list type
        docs_type = annotations["retrieved_docs"]
        assert "list" in str(docs_type).lower() or hasattr(docs_type, "__origin__")

    def test_state_source_citations_is_list(self):
        """The source_citations field should accept a list type."""
        from src.services.rag import RAGAgentState

        annotations = RAGAgentState.__annotations__

        # Check that source_citations annotation indicates list type
        citations_type = annotations["source_citations"]
        assert "list" in str(citations_type).lower() or hasattr(citations_type, "__origin__")

    def test_state_can_be_instantiated(self):
        """RAGAgentState should be instantiable as a dict."""
        from src.services.rag import RAGAgentState

        # TypedDict should be usable as a regular dict
        state: RAGAgentState = {
            "messages": [],
            "retrieved_docs": [],
            "source_citations": [],
        }

        assert state["messages"] == []
        assert state["retrieved_docs"] == []
        assert state["source_citations"] == []


class TestFormatContextWithCitations:
    """Test cases for format_context_with_citations() function."""

    def test_formats_single_document_with_citation(self):
        """Single document should be formatted with recording citation."""
        from src.services.rag import format_context_with_citations

        mock_chunk = MagicMock()
        mock_chunk.content = "This is the transcript content."
        mock_chunk.recording.title = "Interview Recording"
        mock_chunk.speaker = "Interviewer"

        result = format_context_with_citations([mock_chunk])

        assert "Interview Recording" in result
        assert "This is the transcript content." in result

    def test_formats_multiple_documents(self):
        """Multiple documents should all be included in the formatted output."""
        from src.services.rag import format_context_with_citations

        mock_chunk1 = MagicMock()
        mock_chunk1.content = "First chunk content."
        mock_chunk1.recording.title = "Recording One"
        mock_chunk1.speaker = "Interviewer"

        mock_chunk2 = MagicMock()
        mock_chunk2.content = "Second chunk content."
        mock_chunk2.recording.title = "Recording Two"
        mock_chunk2.speaker = "Respondent"

        result = format_context_with_citations([mock_chunk1, mock_chunk2])

        assert "First chunk content." in result
        assert "Second chunk content." in result
        assert "Recording One" in result
        assert "Recording Two" in result

    def test_handles_empty_documents(self):
        """Empty document list should return empty or placeholder string."""
        from src.services.rag import format_context_with_citations

        result = format_context_with_citations([])

        # Should either be empty or a meaningful message
        assert result == "" or "no" in result.lower() or "empty" in result.lower()

    def test_includes_recording_title_in_citation(self):
        """Citation format should include [Recording: title] or similar format."""
        from src.services.rag import format_context_with_citations

        mock_chunk = MagicMock()
        mock_chunk.content = "Sample content here."
        mock_chunk.recording.title = "Customer Interview 2024"
        mock_chunk.speaker = None

        result = format_context_with_citations([mock_chunk])

        # Should include the recording title in citation format
        assert "Customer Interview 2024" in result
        # Check for citation-like formatting
        assert "[" in result or "Source:" in result or "Recording:" in result

    def test_includes_speaker_when_available(self):
        """Speaker information should be included when available."""
        from src.services.rag import format_context_with_citations

        mock_chunk = MagicMock()
        mock_chunk.content = "I think the product is great."
        mock_chunk.recording.title = "Product Feedback"
        mock_chunk.speaker = "Respondent"

        result = format_context_with_citations([mock_chunk])

        assert "Respondent" in result

    def test_handles_none_speaker(self):
        """Should handle None speaker gracefully."""
        from src.services.rag import format_context_with_citations

        mock_chunk = MagicMock()
        mock_chunk.content = "Content without speaker info."
        mock_chunk.recording.title = "Unknown Speaker Recording"
        mock_chunk.speaker = None

        result = format_context_with_citations([mock_chunk])

        # Should not raise an error and should include the content
        assert "Content without speaker info." in result
        assert "Unknown Speaker Recording" in result

    def test_excerpt_formatting(self):
        """Content should be formatted as an excerpt with proper structure."""
        from src.services.rag import format_context_with_citations

        mock_chunk = MagicMock()
        mock_chunk.content = "This is a longer piece of content that should be formatted."
        mock_chunk.recording.title = "Test Recording"
        mock_chunk.speaker = "Interviewer"

        result = format_context_with_citations([mock_chunk])

        # Result should be a string with structured content
        assert isinstance(result, str)
        assert len(result) > 0
        # Content should be preserved
        assert "This is a longer piece of content that should be formatted." in result

    def test_returns_string_type(self):
        """Return type should always be a string."""
        from src.services.rag import format_context_with_citations

        mock_chunk = MagicMock()
        mock_chunk.content = "Test content."
        mock_chunk.recording.title = "Test"
        mock_chunk.speaker = None

        result = format_context_with_citations([mock_chunk])

        assert isinstance(result, str)


class TestBuildRagGraph:
    """Test cases for build_rag_graph() function."""

    @patch("src.services.rag.StateGraph")
    def test_returns_compiled_graph(self, mock_state_graph: MagicMock):
        """build_rag_graph should return a compiled StateGraph."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_compiled = MagicMock()
        mock_graph_instance.compile.return_value = mock_compiled
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        result = build_rag_graph(session=mock_session)

        mock_graph_instance.compile.assert_called_once()
        assert result == mock_compiled

    @patch("src.services.rag.StateGraph")
    def test_graph_has_retrieve_node(self, mock_state_graph: MagicMock):
        """The graph should have a 'retrieve' node for document retrieval."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        build_rag_graph(session=mock_session)

        # Verify add_node was called with 'retrieve'
        add_node_calls = mock_graph_instance.add_node.call_args_list
        node_names = [call[0][0] for call in add_node_calls]
        assert "retrieve" in node_names

    @patch("src.services.rag.StateGraph")
    def test_graph_has_grade_node(self, mock_state_graph: MagicMock):
        """The graph should have a 'grade' node for relevance grading."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        build_rag_graph(session=mock_session)

        # Verify add_node was called with 'grade'
        add_node_calls = mock_graph_instance.add_node.call_args_list
        node_names = [call[0][0] for call in add_node_calls]
        assert "grade" in node_names

    @patch("src.services.rag.StateGraph")
    def test_graph_has_generate_node(self, mock_state_graph: MagicMock):
        """The graph should have a 'generate' node for answer generation."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        build_rag_graph(session=mock_session)

        # Verify add_node was called with 'generate'
        add_node_calls = mock_graph_instance.add_node.call_args_list
        node_names = [call[0][0] for call in add_node_calls]
        assert "generate" in node_names

    @patch("src.services.rag.StateGraph")
    def test_graph_has_rewrite_node(self, mock_state_graph: MagicMock):
        """The graph should have a 'rewrite' node for query rewriting."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        build_rag_graph(session=mock_session)

        # Verify add_node was called with 'rewrite'
        add_node_calls = mock_graph_instance.add_node.call_args_list
        node_names = [call[0][0] for call in add_node_calls]
        assert "rewrite" in node_names

    @patch("src.services.rag.StateGraph")
    def test_graph_has_edges_defined(self, mock_state_graph: MagicMock):
        """The graph should have edges connecting the nodes."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        build_rag_graph(session=mock_session)

        # Verify edges were added
        assert (
            mock_graph_instance.add_edge.called or mock_graph_instance.add_conditional_edges.called
        )

    @patch("src.services.rag.StateGraph")
    def test_graph_has_entry_point(self, mock_state_graph: MagicMock):
        """The graph should have an entry point defined."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        build_rag_graph(session=mock_session)

        # Verify set_entry_point was called
        assert mock_graph_instance.set_entry_point.called

    @patch("src.services.rag.StateGraph")
    def test_accepts_session_parameter(self, mock_state_graph: MagicMock):
        """build_rag_graph should accept a database session parameter."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        # Should not raise an error
        build_rag_graph(session=mock_session)

    @patch("src.services.rag.StateGraph")
    def test_accepts_optional_recording_filter(self, mock_state_graph: MagicMock):
        """build_rag_graph should accept an optional recording_filter parameter."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        # Should not raise an error with recording_filter
        build_rag_graph(session=mock_session, recording_filter="some-uuid-123")


class TestRetrieveNode:
    """Test cases for the retrieve node function."""

    @patch("src.services.rag.similarity_search")
    def test_retrieve_calls_similarity_search(self, mock_search: MagicMock):
        """Retrieve node should call similarity_search with the query."""
        from src.services.rag import _retrieve_node

        mock_search.return_value = []

        mock_session = MagicMock()
        state: dict[str, Any] = {
            "messages": [MagicMock(content="What is the main topic?")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        _retrieve_node(state, session=mock_session)

        mock_search.assert_called_once()

    @patch("src.services.rag.similarity_search")
    def test_retrieve_updates_state_with_docs(self, mock_search: MagicMock):
        """Retrieve node should update state with retrieved documents."""
        from src.services.rag import _retrieve_node

        mock_chunk = MagicMock()
        mock_chunk.content = "Retrieved content"
        mock_search.return_value = [mock_chunk]

        mock_session = MagicMock()
        state: dict[str, Any] = {
            "messages": [MagicMock(content="Test query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        result = _retrieve_node(state, session=mock_session)

        assert "retrieved_docs" in result
        assert len(result["retrieved_docs"]) == 1

    @patch("src.services.rag.similarity_search")
    def test_retrieve_handles_empty_results(self, mock_search: MagicMock):
        """Retrieve node should handle empty search results gracefully."""
        from src.services.rag import _retrieve_node

        mock_search.return_value = []

        mock_session = MagicMock()
        state: dict[str, Any] = {
            "messages": [MagicMock(content="Unknown topic query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        result = _retrieve_node(state, session=mock_session)

        assert "retrieved_docs" in result
        assert result["retrieved_docs"] == []


class TestGradeNode:
    """Test cases for the grade node function."""

    @patch("src.services.rag._get_llm")
    def test_grade_returns_relevant_decision(self, mock_get_llm: MagicMock):
        """Grade node should return a decision about document relevance."""
        from src.services.rag import _grade_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="relevant")
        mock_get_llm.return_value = mock_llm

        mock_chunk = MagicMock()
        mock_chunk.content = "Relevant content about the topic"

        state: dict[str, Any] = {
            "messages": [MagicMock(content="What is the topic?")],
            "retrieved_docs": [mock_chunk],
            "source_citations": [],
        }

        result = _grade_node(state)

        assert "grade_decision" in result or isinstance(result, dict)

    @patch("src.services.rag._get_llm")
    def test_grade_handles_empty_docs(self, mock_get_llm: MagicMock):
        """Grade node should handle case when no documents were retrieved."""
        from src.services.rag import _grade_node

        state: dict[str, Any] = {
            "messages": [MagicMock(content="Query with no results")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        result = _grade_node(state)

        # Should indicate no relevant docs or trigger rewrite
        assert isinstance(result, dict)


class TestGenerateNode:
    """Test cases for the generate node function."""

    @patch("src.services.rag._get_llm")
    @patch("src.services.rag.format_context_with_citations")
    def test_generate_produces_answer(
        self,
        mock_format: MagicMock,
        mock_get_llm: MagicMock,
    ):
        """Generate node should produce an answer based on retrieved docs."""
        from src.services.rag import _generate_node

        mock_format.return_value = "[Recording: Test] Content here."
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Generated answer text.")
        mock_get_llm.return_value = mock_llm

        mock_chunk = MagicMock()
        mock_chunk.content = "Source content"
        mock_chunk.recording.id = "rec-123"
        mock_chunk.recording.title = "Test Recording"
        mock_chunk.speaker = "Interviewer"

        state: dict[str, Any] = {
            "messages": [MagicMock(content="What is the answer?")],
            "retrieved_docs": [mock_chunk],
            "source_citations": [],
        }

        result = _generate_node(state)

        assert "messages" in result or "answer" in str(result)
        mock_llm.invoke.assert_called_once()

    @patch("src.services.rag._get_llm")
    @patch("src.services.rag.format_context_with_citations")
    def test_generate_includes_citations(
        self,
        mock_format: MagicMock,
        mock_get_llm: MagicMock,
    ):
        """Generate node should include source citations in the result."""
        from src.services.rag import _generate_node

        mock_format.return_value = "[Recording: Interview] Sample content."
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Answer with citation.")
        mock_get_llm.return_value = mock_llm

        mock_chunk = MagicMock()
        mock_chunk.content = "Interview content"
        mock_chunk.recording.id = "rec-456"
        mock_chunk.recording.title = "Customer Interview"
        mock_chunk.speaker = "Respondent"

        state: dict[str, Any] = {
            "messages": [MagicMock(content="What did the customer say?")],
            "retrieved_docs": [mock_chunk],
            "source_citations": [],
        }

        result = _generate_node(state)

        assert "source_citations" in result
        assert len(result["source_citations"]) > 0


class TestRewriteNode:
    """Test cases for the rewrite node function."""

    @patch("src.services.rag._get_llm")
    def test_rewrite_modifies_query(self, mock_get_llm: MagicMock):
        """Rewrite node should modify the query for better retrieval."""
        from src.services.rag import _rewrite_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Improved query text")
        mock_get_llm.return_value = mock_llm

        state: dict[str, Any] = {
            "messages": [MagicMock(content="vague query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        result = _rewrite_node(state)

        assert "messages" in result
        mock_llm.invoke.assert_called_once()

    @patch("src.services.rag._get_llm")
    def test_rewrite_preserves_state_structure(self, mock_get_llm: MagicMock):
        """Rewrite node should preserve the overall state structure."""
        from src.services.rag import _rewrite_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Rewritten query")
        mock_get_llm.return_value = mock_llm

        state: dict[str, Any] = {
            "messages": [MagicMock(content="original query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        result = _rewrite_node(state)

        # Result should be a dict with state updates
        assert isinstance(result, dict)


class TestCitationGeneration:
    """Test cases for citation generation functionality."""

    def test_citation_includes_recording_id(self):
        """Generated citation should include the recording ID."""
        from src.services.rag import _create_citation

        mock_chunk = MagicMock()
        mock_chunk.recording.id = "uuid-12345"
        mock_chunk.recording.title = "Test Recording"
        mock_chunk.content = "Excerpt content here."
        mock_chunk.speaker = "Interviewer"

        result = _create_citation(mock_chunk)

        assert result["recording_id"] == "uuid-12345"

    def test_citation_includes_recording_title(self):
        """Generated citation should include the recording title."""
        from src.services.rag import _create_citation

        mock_chunk = MagicMock()
        mock_chunk.recording.id = "uuid-67890"
        mock_chunk.recording.title = "Customer Feedback Session"
        mock_chunk.content = "Some feedback content."
        mock_chunk.speaker = "Respondent"

        result = _create_citation(mock_chunk)

        assert result["recording_title"] == "Customer Feedback Session"

    def test_citation_includes_excerpt(self):
        """Generated citation should include an excerpt from the content."""
        from src.services.rag import _create_citation

        mock_chunk = MagicMock()
        mock_chunk.recording.id = "uuid-111"
        mock_chunk.recording.title = "Recording"
        mock_chunk.content = "This is the excerpt that should be included."
        mock_chunk.speaker = None

        result = _create_citation(mock_chunk)

        assert "excerpt" in result
        assert "This is the excerpt" in result["excerpt"]

    def test_citation_includes_speaker(self):
        """Generated citation should include the speaker when available."""
        from src.services.rag import _create_citation

        mock_chunk = MagicMock()
        mock_chunk.recording.id = "uuid-222"
        mock_chunk.recording.title = "Interview"
        mock_chunk.content = "Speaker content."
        mock_chunk.speaker = "Interviewer"

        result = _create_citation(mock_chunk)

        assert result["speaker"] == "Interviewer"

    def test_citation_handles_none_speaker(self):
        """Generated citation should handle None speaker."""
        from src.services.rag import _create_citation

        mock_chunk = MagicMock()
        mock_chunk.recording.id = "uuid-333"
        mock_chunk.recording.title = "Recording"
        mock_chunk.content = "Content."
        mock_chunk.speaker = None

        result = _create_citation(mock_chunk)

        assert result["speaker"] is None

    def test_citation_returns_dict(self):
        """Citation should be returned as a dictionary."""
        from src.services.rag import _create_citation

        mock_chunk = MagicMock()
        mock_chunk.recording.id = "uuid-444"
        mock_chunk.recording.title = "Test"
        mock_chunk.content = "Content."
        mock_chunk.speaker = "Respondent"

        result = _create_citation(mock_chunk)

        assert isinstance(result, dict)
        assert "recording_id" in result
        assert "recording_title" in result
        assert "excerpt" in result
        assert "speaker" in result


class TestRAGErrorHandling:
    """Test cases for error handling in the RAG system."""

    @patch("src.services.rag.similarity_search")
    def test_retrieve_handles_search_error(self, mock_search: MagicMock):
        """Retrieve node should handle errors from similarity search gracefully."""
        from src.services.rag import RAGError, _retrieve_node

        mock_search.side_effect = Exception("Database connection error")

        mock_session = MagicMock()
        state: dict[str, Any] = {
            "messages": [MagicMock(content="Test query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        with pytest.raises(RAGError) as exc_info:
            _retrieve_node(state, session=mock_session)

        assert "retrieval" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    @patch("src.services.rag._get_llm")
    def test_generate_handles_llm_error(self, mock_get_llm: MagicMock):
        """Generate node should handle LLM errors gracefully."""
        from src.services.rag import RAGError, _generate_node

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("LLM API error")
        mock_get_llm.return_value = mock_llm

        state: dict[str, Any] = {
            "messages": [MagicMock(content="Test query")],
            "retrieved_docs": [MagicMock()],
            "source_citations": [],
        }

        with pytest.raises(RAGError) as exc_info:
            _generate_node(state)

        assert (
            "generation" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()
        )


class TestRAGQuery:
    """Test cases for the main RAG query function."""

    @patch("src.services.rag.build_rag_graph")
    def test_query_returns_response(self, mock_build_graph: MagicMock):
        """rag_query should return a response with answer and citations."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="The answer is...")],
            "retrieved_docs": [],
            "source_citations": [
                {
                    "recording_id": "rec-1",
                    "recording_title": "Interview",
                    "excerpt": "sample",
                    "speaker": "Interviewer",
                }
            ],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()
        result = rag_query(
            session=mock_session,
            query="What is the answer?",
            session_id="session-123",
        )

        assert "answer" in result
        assert "citations" in result

    @patch("src.services.rag.build_rag_graph")
    def test_query_accepts_recording_filter(self, mock_build_graph: MagicMock):
        """rag_query should accept an optional recording_filter parameter."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="Answer")],
            "retrieved_docs": [],
            "source_citations": [],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()
        rag_query(
            session=mock_session,
            query="Test query",
            session_id="session-456",
            recording_filter="recording-uuid-789",
        )

        mock_build_graph.assert_called_once()
        # Verify recording_filter was passed
        call_kwargs = mock_build_graph.call_args.kwargs
        assert "recording_filter" in call_kwargs
        assert call_kwargs["recording_filter"] == "recording-uuid-789"

    @patch("src.services.rag.build_rag_graph")
    def test_query_response_matches_contract(self, mock_build_graph: MagicMock):
        """rag_query response should match the API contract schema."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="Detailed answer here.")],
            "retrieved_docs": [],
            "source_citations": [
                {
                    "recording_id": "uuid-abc",
                    "recording_title": "Customer Call",
                    "excerpt": "The customer mentioned...",
                    "speaker": "Respondent",
                }
            ],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()
        result = rag_query(
            session=mock_session,
            query="What did the customer say?",
            session_id="session-789",
        )

        # Validate response structure per API contract
        assert isinstance(result["answer"], str)
        assert isinstance(result["citations"], list)

        if result["citations"]:
            citation = result["citations"][0]
            assert "recording_id" in citation
            assert "recording_title" in citation
            assert "excerpt" in citation
            assert "speaker" in citation
