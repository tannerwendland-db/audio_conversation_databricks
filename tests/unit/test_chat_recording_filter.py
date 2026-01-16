"""Unit tests for chat recording filter functionality.

This module tests the recording filter feature for the chat interface,
including dropdown population, multi-select support, filtered query submission,
and similarity search with multiple recording IDs.

NOTE: This is a TDD test file. The tests are written BEFORE the implementation
exists. Tests will fail until the implementation is created.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestRecordingFilterDropdown:
    """Test cases for recording filter dropdown functionality."""

    @patch("src.components.chat.list_recordings")
    @patch("src.components.chat.get_session")
    def test_filter_dropdown_options_populated_from_recordings(
        self,
        mock_get_session: MagicMock,
        mock_list_recordings: MagicMock,
    ):
        """Filter dropdown options should be populated from completed recordings."""
        from src.components.chat import populate_recording_filter_options

        # Setup mock recordings
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_recording_1 = MagicMock()
        mock_recording_1.id = "uuid-rec-001"
        mock_recording_1.title = "Customer Interview A"
        mock_recording_1.duration_seconds = 300.0
        mock_recording_1.processing_status = "completed"

        mock_recording_2 = MagicMock()
        mock_recording_2.id = "uuid-rec-002"
        mock_recording_2.title = "Product Feedback B"
        mock_recording_2.duration_seconds = 600.0
        mock_recording_2.processing_status = "completed"

        mock_recording_3 = MagicMock()
        mock_recording_3.id = "uuid-rec-003"
        mock_recording_3.title = "Pending Recording"
        mock_recording_3.duration_seconds = 120.0
        mock_recording_3.processing_status = "pending"

        mock_list_recordings.return_value = [
            mock_recording_1,
            mock_recording_2,
            mock_recording_3,
        ]

        # Execute - simulating callback trigger
        options = populate_recording_filter_options("test-session-id")

        # Verify only completed recordings are returned
        assert len(options) == 2
        option_values = [opt["value"] for opt in options]
        assert "uuid-rec-001" in option_values
        assert "uuid-rec-002" in option_values
        assert "uuid-rec-003" not in option_values

    @patch("src.components.chat.list_recordings")
    @patch("src.components.chat.get_session")
    def test_filter_dropdown_excludes_failed_recordings(
        self,
        mock_get_session: MagicMock,
        mock_list_recordings: MagicMock,
    ):
        """Filter dropdown should exclude recordings with failed status."""
        from src.components.chat import populate_recording_filter_options

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_recording_completed = MagicMock()
        mock_recording_completed.id = "uuid-rec-001"
        mock_recording_completed.title = "Completed Recording"
        mock_recording_completed.duration_seconds = 300.0
        mock_recording_completed.processing_status = "completed"

        mock_recording_failed = MagicMock()
        mock_recording_failed.id = "uuid-rec-002"
        mock_recording_failed.title = "Failed Recording"
        mock_recording_failed.duration_seconds = 300.0
        mock_recording_failed.processing_status = "failed"

        mock_list_recordings.return_value = [
            mock_recording_completed,
            mock_recording_failed,
        ]

        options = populate_recording_filter_options("test-session-id")

        assert len(options) == 1
        assert options[0]["value"] == "uuid-rec-001"


class TestFilteredQuerySubmission:
    """Test cases for filtered query submission functionality."""

    @patch("src.services.rag.build_rag_graph")
    def test_query_with_single_recording_filter(
        self,
        mock_build_graph: MagicMock,
    ):
        """rag_query with single recording filter should pass it to build_rag_graph."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="Filtered answer")],
            "retrieved_docs": [],
            "source_citations": [],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()

        # Execute with single recording filter (as a list)
        rag_query(
            session=mock_session,
            query="What was discussed?",
            session_id="session-001",
            recording_filter=["uuid-rec-001"],
        )

        # Verify recording_filter was passed to build_rag_graph
        mock_build_graph.assert_called_once()
        call_kwargs = mock_build_graph.call_args.kwargs
        assert "recording_filter" in call_kwargs
        assert call_kwargs["recording_filter"] == ["uuid-rec-001"]

    @patch("src.services.rag.build_rag_graph")
    def test_query_with_multiple_recording_filters(
        self,
        mock_build_graph: MagicMock,
    ):
        """rag_query with multiple filters should pass list to build_rag_graph."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="Multi-filtered answer")],
            "retrieved_docs": [],
            "source_citations": [],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()
        recording_ids = ["uuid-rec-001", "uuid-rec-002", "uuid-rec-003"]

        # Execute with multiple recording filters
        rag_query(
            session=mock_session,
            query="Compare the interviews",
            session_id="session-002",
            recording_filter=recording_ids,
        )

        # Verify multiple recording IDs were passed
        mock_build_graph.assert_called_once()
        call_kwargs = mock_build_graph.call_args.kwargs
        assert call_kwargs["recording_filter"] == recording_ids

    @patch("src.services.rag.build_rag_graph")
    def test_query_with_no_filter_searches_all(
        self,
        mock_build_graph: MagicMock,
    ):
        """rag_query with no recording filter should search all recordings."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="Unfiltered answer")],
            "retrieved_docs": [],
            "source_citations": [],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()

        # Execute without recording filter
        rag_query(
            session=mock_session,
            query="General question",
            session_id="session-003",
            recording_filter=None,
        )

        # Verify recording_filter was None
        mock_build_graph.assert_called_once()
        call_kwargs = mock_build_graph.call_args.kwargs
        assert call_kwargs.get("recording_filter") is None


class TestBuildRagGraphWithMultipleIds:
    """Test cases for build_rag_graph with multiple recording IDs."""

    @patch("src.services.rag.StateGraph")
    def test_build_rag_graph_accepts_list_recording_filter(
        self,
        mock_state_graph: MagicMock,
    ):
        """build_rag_graph should accept recording_filter as list[str] | None."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        recording_ids = ["uuid-001", "uuid-002"]

        # Should not raise an error
        build_rag_graph(session=mock_session, recording_filter=recording_ids)

    @patch("src.services.rag.StateGraph")
    def test_build_rag_graph_passes_recording_ids_to_retrieve_node(
        self,
        mock_state_graph: MagicMock,
    ):
        """build_rag_graph should pass recording_ids to the retrieve node closure."""
        from src.services.rag import build_rag_graph

        mock_graph_instance = MagicMock()
        mock_state_graph.return_value = mock_graph_instance

        mock_session = MagicMock()
        recording_ids = ["uuid-001", "uuid-002", "uuid-003"]

        build_rag_graph(session=mock_session, recording_filter=recording_ids)

        # Verify add_node was called with 'retrieve'
        add_node_calls = mock_graph_instance.add_node.call_args_list
        node_names = [call[0][0] for call in add_node_calls]
        assert "retrieve" in node_names


class TestSimilaritySearchWithMultipleIds:
    """Test cases for similarity_search with multiple recording IDs."""

    @patch("src.services.embedding._get_embeddings_model")
    def test_similarity_search_with_single_recording_id_in_list(
        self,
        mock_get_embeddings: MagicMock,
    ):
        """similarity_search with single recording_id in list should filter."""
        from src.services.embedding import similarity_search

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 768
        mock_get_embeddings.return_value = mock_embeddings

        mock_session = MagicMock()
        mock_session.execute.return_value = iter([])

        # Execute with single recording ID in list form
        similarity_search(
            session=mock_session,
            query="test query",
            k=5,
            recording_ids=["uuid-single"],
        )

        # Verify the query was executed
        mock_session.execute.assert_called_once()

    @patch("src.services.embedding._get_embeddings_model")
    def test_similarity_search_with_multiple_recording_ids(
        self,
        mock_get_embeddings: MagicMock,
    ):
        """similarity_search with multiple recording_ids should use IN clause."""
        from src.services.embedding import similarity_search

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 768
        mock_get_embeddings.return_value = mock_embeddings

        mock_session = MagicMock()
        mock_session.execute.return_value = iter([])

        recording_ids = ["uuid-001", "uuid-002", "uuid-003"]

        # Execute with multiple recording IDs
        similarity_search(
            session=mock_session,
            query="test query",
            k=5,
            recording_ids=recording_ids,
        )

        # Verify the query was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args

        # The SQL should use IN clause for multiple IDs
        sql_text = str(call_args[0][0])
        assert "IN" in sql_text.upper() or "ANY" in sql_text.upper()

    @patch("src.services.embedding._get_embeddings_model")
    def test_similarity_search_with_empty_list_searches_all(
        self,
        mock_get_embeddings: MagicMock,
    ):
        """similarity_search with empty recording_ids list should search all."""
        from src.services.embedding import similarity_search

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 768
        mock_get_embeddings.return_value = mock_embeddings

        mock_session = MagicMock()
        mock_session.execute.return_value = iter([])

        # Execute with empty list
        similarity_search(
            session=mock_session,
            query="test query",
            k=5,
            recording_ids=[],
        )

        # Verify query was executed without recording filter
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])

        # SQL should NOT have recording_id filter when empty list
        # Check that WHERE clause doesn't contain recording_id or uses no filter
        assert "WHERE" not in sql_text.upper() or "recording_id" not in sql_text.lower()

    @patch("src.services.embedding._get_embeddings_model")
    def test_similarity_search_with_none_searches_all(
        self,
        mock_get_embeddings: MagicMock,
    ):
        """similarity_search with None recording_ids should search all."""
        from src.services.embedding import similarity_search

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 768
        mock_get_embeddings.return_value = mock_embeddings

        mock_session = MagicMock()
        mock_session.execute.return_value = iter([])

        # Execute with None
        similarity_search(
            session=mock_session,
            query="test query",
            k=5,
            recording_ids=None,
        )

        # Verify query was executed
        mock_session.execute.assert_called_once()


class TestRetrieveNodeWithMultipleIds:
    """Test cases for _retrieve_node with multiple recording IDs."""

    @patch("src.services.rag.similarity_search")
    def test_retrieve_node_with_recording_ids_list(
        self,
        mock_similarity_search: MagicMock,
    ):
        """_retrieve_node should pass recording_ids list to similarity_search."""
        from src.services.rag import _retrieve_node

        mock_similarity_search.return_value = []

        mock_session = MagicMock()
        recording_ids = ["uuid-001", "uuid-002"]
        state: dict[str, Any] = {
            "messages": [MagicMock(content="Test query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        _retrieve_node(state, session=mock_session, recording_ids=recording_ids)

        mock_similarity_search.assert_called_once()
        call_kwargs = mock_similarity_search.call_args.kwargs
        assert call_kwargs.get("recording_ids") == recording_ids

    @patch("src.services.rag.similarity_search")
    def test_retrieve_node_with_none_searches_all(
        self,
        mock_similarity_search: MagicMock,
    ):
        """_retrieve_node with None recording_ids should search all recordings."""
        from src.services.rag import _retrieve_node

        mock_similarity_search.return_value = []

        mock_session = MagicMock()
        state: dict[str, Any] = {
            "messages": [MagicMock(content="Test query")],
            "retrieved_docs": [],
            "source_citations": [],
        }

        _retrieve_node(state, session=mock_session, recording_ids=None)

        mock_similarity_search.assert_called_once()
        call_kwargs = mock_similarity_search.call_args.kwargs
        assert call_kwargs.get("recording_ids") is None


class TestChatCallbackWithRecordingFilter:
    """Test cases for chat callback integration with recording filter."""

    def test_chat_callback_passes_selected_recordings_in_sse_payload(
        self,
    ):
        """Chat callback should include selected recording IDs in SSE payload."""
        from src.components.chat import handle_chat_submit

        selected_recordings = ["uuid-rec-001", "uuid-rec-002"]

        # Simulate chat submission with filter
        result = handle_chat_submit(
            n_clicks=1,
            user_input="What was discussed?",
            message_history=[],
            session_id="test-session",
            selected_recordings=selected_recordings,
            stream_state=None,
        )

        # Result tuple: (url, sse_options, history, rendered, input, stream_state)
        sse_options = result[1]

        # Verify SSE payload contains recording_filter
        assert sse_options is not None
        assert "payload" in sse_options
        payload = sse_options["payload"]
        assert payload.get("recording_filter") == selected_recordings

    def test_chat_callback_with_no_filter_omits_recording_filter_from_payload(
        self,
    ):
        """Chat callback with no filter should not include recording_filter in SSE payload."""
        from src.components.chat import handle_chat_submit

        # Simulate chat submission without filter (None)
        result = handle_chat_submit(
            n_clicks=1,
            user_input="General question",
            message_history=[],
            session_id="test-session",
            selected_recordings=None,
            stream_state=None,
        )

        # Result tuple: (url, sse_options, history, rendered, input, stream_state)
        sse_options = result[1]

        # Verify SSE payload does not contain recording_filter (searches all)
        assert sse_options is not None
        assert "payload" in sse_options
        payload = sse_options["payload"]
        assert "recording_filter" not in payload


class TestRecordingFilterIntegration:
    """Integration tests for recording filter across components."""

    @pytest.mark.parametrize(
        "filter_input,expected_behavior",
        [
            (None, "search_all"),
            ([], "search_all"),
            (["uuid-001"], "filter_single"),
            (["uuid-001", "uuid-002"], "filter_multiple"),
            (["uuid-001", "uuid-002", "uuid-003"], "filter_multiple"),
        ],
    )
    @patch("src.services.rag.build_rag_graph")
    def test_recording_filter_behavior_matrix(
        self,
        mock_build_graph: MagicMock,
        filter_input: list[str] | None,
        expected_behavior: str,
    ):
        """Test recording filter behavior across different input scenarios."""
        from src.services.rag import rag_query

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "messages": [MagicMock(content="Test answer")],
            "retrieved_docs": [],
            "source_citations": [],
        }
        mock_build_graph.return_value = mock_graph

        mock_session = MagicMock()

        rag_query(
            session=mock_session,
            query="Test query",
            session_id="test-session",
            recording_filter=filter_input,
        )

        mock_build_graph.assert_called_once()
        call_kwargs = mock_build_graph.call_args.kwargs
        actual_filter = call_kwargs.get("recording_filter")

        if expected_behavior == "search_all":
            # Empty list or None should result in searching all
            assert actual_filter is None or actual_filter == []
        elif expected_behavior == "filter_single":
            assert actual_filter == filter_input
            assert len(actual_filter) == 1
        elif expected_behavior == "filter_multiple":
            assert actual_filter == filter_input
            assert len(actual_filter) > 1
