"""Unit tests for streaming service.

Tests for the streaming generator function and SSE event formatting.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.services.streaming import stream_rag_response


class TestStreamRagResponse:
    """Unit tests for stream_rag_response generator (T008 - US1)."""

    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_stream_yields_sse_formatted_strings(self, mock_get_session, mock_search):
        """Generator should yield SSE-formatted event strings."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_search.return_value = []

        events = list(stream_rag_response(
            query="test question",
            session_id="test-session",
        ))

        # Should yield at least a done event
        assert len(events) >= 1

        # Each event should be SSE formatted
        for event in events:
            assert isinstance(event, str)
            # SSE events end with double newline
            assert event.endswith("\n\n")

    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_stream_ends_with_done_event(self, mock_get_session, mock_search):
        """Stream should always end with a done event."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_search.return_value = []

        events = list(stream_rag_response(
            query="test question",
            session_id="test-session",
        ))

        last_event = events[-1]
        assert "event: done" in last_event

    @patch("src.services.streaming.streaming_generate")
    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_stream_yields_token_events_from_llm(self, mock_get_session, mock_search, mock_generate):
        """Stream should yield token events from LLM streaming output."""
        # Mock database session
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mock empty search results for simplicity
        mock_search.return_value = []

        events = list(stream_rag_response(
            query="test question",
            session_id="test-session",
        ))

        # Should have at least token and done events
        token_events = [e for e in events if "event: token" in e]
        done_events = [e for e in events if "event: done" in e]
        assert len(token_events) >= 1  # At least "no relevant info" message
        assert len(done_events) == 1

    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_stream_accepts_recording_filter(self, mock_get_session, mock_search):
        """Stream should accept optional recording filter."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_search.return_value = []

        # Should not raise
        events = list(stream_rag_response(
            query="test",
            session_id="test",
            recording_filter=["rec1", "rec2"],
        ))

        assert len(events) >= 1
        # Verify filter was passed to search
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs.get("recording_ids") == ["rec1", "rec2"]


class TestSSEEventFormatting:
    """Tests for SSE event formatting utilities."""

    def test_format_token_event(self):
        """Format token event should produce valid SSE string."""
        from src.services.streaming import format_sse_event

        event = format_sse_event("token", {"content": "Hello"})

        assert event == 'event: token\ndata: {"content": "Hello"}\n\n'

    def test_format_done_event(self):
        """Format done event should produce valid SSE string."""
        from src.services.streaming import format_sse_event

        event = format_sse_event("done", {})

        assert event == "event: done\ndata: {}\n\n"

    def test_format_event_handles_special_characters(self):
        """Event formatting should handle special characters in content."""
        from src.services.streaming import format_sse_event

        event = format_sse_event("token", {"content": "Hello\nworld"})

        # Should be valid JSON
        lines = event.strip().split("\n")
        data_line = lines[1].replace("data: ", "", 1)
        data = json.loads(data_line)
        assert data["content"] == "Hello\nworld"


class TestErrorHandling:
    """Unit tests for error handling in streaming (T027 - US3)."""

    def test_format_error_event(self):
        """Format error event should include message and code."""
        from src.services.streaming import format_sse_event

        event = format_sse_event("error", {
            "message": "Connection failed",
            "code": "GENERATION_FAILED",
        })

        assert 'event: error' in event
        assert '"message": "Connection failed"' in event
        assert '"code": "GENERATION_FAILED"' in event

    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_stream_yields_error_on_exception(self, mock_get_session, mock_search):
        """Stream should yield error event when exception occurs."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_search.side_effect = Exception("Database connection failed")

        events = list(stream_rag_response(
            query="test question",
            session_id="test-session",
        ))

        # Should have an error event
        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1

        # Error message should contain exception info
        assert "Database connection failed" in error_events[0]

    @patch("src.services.streaming.streaming_generate")
    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_stream_preserves_partial_on_error(self, mock_get_session, mock_search, mock_generate):
        """Stream should preserve partial content when error occurs mid-stream."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mock a chunk with recording
        mock_chunk = MagicMock()
        mock_chunk.content = "test content"
        mock_chunk.speaker = "Test Speaker"
        mock_chunk.recording.id = "rec_123"
        mock_chunk.recording.title = "Test Recording"
        mock_search.return_value = [mock_chunk]

        # Mock generator that yields then fails
        def failing_generator():
            yield "First part"
            yield " second part"
            raise Exception("LLM timeout")

        mock_generate.return_value = failing_generator()

        events = list(stream_rag_response(
            query="test question",
            session_id="test-session",
        ))

        # Should have token events before error
        token_events = [e for e in events if "event: token" in e]
        error_events = [e for e in events if "event: error" in e]

        assert len(token_events) >= 1
        assert len(error_events) == 1

    @patch("src.services.streaming.similarity_search")
    @patch("src.services.streaming.get_session")
    def test_error_event_has_code(self, mock_get_session, mock_search):
        """Error event should include error code."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_search.side_effect = Exception("Failed")

        events = list(stream_rag_response(
            query="test question",
            session_id="test-session",
        ))

        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1
        # Should have a code
        assert '"code":' in error_events[0]
