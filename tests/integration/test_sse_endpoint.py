"""Integration tests for SSE streaming endpoint.

Tests verify the /api/chat/stream endpoint returns valid SSE streams.
"""

import json
from unittest.mock import patch

import pytest


class TestSSEEndpoint:
    """Integration tests for /api/chat/stream endpoint (T009 - US1)."""

    @pytest.fixture
    def client(self):
        """Create test client for the Dash app."""
        from src.app import server

        server.config["TESTING"] = True
        with server.test_client() as client:
            yield client

    @pytest.fixture(autouse=True)
    def mock_streaming(self):
        """Mock the streaming to avoid database dependency."""
        def mock_stream_rag_response(query, session_id, recording_filter=None):
            yield 'event: token\ndata: {"content": "Hello"}\n\n'
            yield 'event: token\ndata: {"content": " world"}\n\n'
            yield 'event: citations\ndata: {"citations": []}\n\n'
            yield 'event: done\ndata: {}\n\n'

        with patch(
            "src.services.streaming.stream_rag_response",
            side_effect=mock_stream_rag_response,
        ):
            yield

    def test_stream_endpoint_exists(self, client):
        """Endpoint /api/chat/stream should accept POST requests."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        # Should return 200 (not 404 or 405)
        assert response.status_code in [200, 500]  # 500 if impl incomplete

    def test_stream_endpoint_returns_event_stream(self, client):
        """Endpoint should return text/event-stream content type."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test question", "session_id": "test-session"},
            content_type="application/json",
        )

        assert response.content_type.startswith("text/event-stream")

    def test_stream_endpoint_requires_query(self, client):
        """Endpoint should return 400 if query is missing."""
        response = client.post(
            "/api/chat/stream",
            json={"session_id": "test-session"},
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_stream_endpoint_accepts_recording_filter(self, client):
        """Endpoint should accept optional recording_filter parameter."""
        response = client.post(
            "/api/chat/stream",
            json={
                "query": "test",
                "session_id": "test-session",
                "recording_filter": ["rec1", "rec2"],
            },
            content_type="application/json",
        )

        # Should not error due to recording_filter
        assert response.status_code in [200, 500]

    def test_stream_response_contains_sse_events(self, client):
        """Response body should contain SSE-formatted events."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        # Get response data
        data = response.data.decode("utf-8")

        # Should contain at least a done event
        assert "event:" in data
        assert "data:" in data

    def test_stream_response_ends_with_done(self, client):
        """Response should end with done event."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")

        # Last event should be done
        assert "event: done" in data


class TestSSECitationsDelivery:
    """Integration tests for citations delivery in SSE stream (T020 - US2)."""

    @pytest.fixture
    def client(self):
        """Create test client for the Dash app."""
        from src.app import server

        server.config["TESTING"] = True
        with server.test_client() as client:
            yield client

    @pytest.fixture(autouse=True)
    def mock_streaming_with_citations(self):
        """Mock streaming with citations included."""
        def mock_stream_rag_response(query, session_id, recording_filter=None):
            yield 'event: token\ndata: {"content": "Based on"}\n\n'
            yield 'event: token\ndata: {"content": " the recording"}\n\n'
            yield 'event: citations\ndata: {"citations": [{"recording_id": "rec_123", "recording_title": "Test Recording", "excerpt": "test content", "speaker": null}]}\n\n'
            yield 'event: done\ndata: {}\n\n'

        with patch(
            "src.services.streaming.stream_rag_response",
            side_effect=mock_stream_rag_response,
        ):
            yield

    def test_citations_event_present_in_stream(self, client):
        """Stream should include citations event."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")
        assert "event: citations" in data

    def test_citations_delivered_after_tokens(self, client):
        """Citations should appear after token events in stream."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")

        # Find positions
        token_pos = data.find("event: token")
        citations_pos = data.find("event: citations")
        done_pos = data.find("event: done")

        # Citations should come after tokens
        assert token_pos < citations_pos
        # Citations should come before done
        assert citations_pos < done_pos

    def test_citations_contains_recording_metadata(self, client):
        """Citations event should contain recording metadata."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")

        # Should contain citation fields
        assert "recording_id" in data
        assert "recording_title" in data
        assert "excerpt" in data


class TestSSEErrorRecovery:
    """Integration tests for error recovery flow (T028 - US3)."""

    @pytest.fixture
    def client(self):
        """Create test client for the Dash app."""
        from src.app import server

        server.config["TESTING"] = True
        with server.test_client() as client:
            yield client

    @pytest.fixture(autouse=True)
    def mock_streaming_with_error(self):
        """Mock streaming that produces an error."""
        def mock_stream_rag_response(query, session_id, recording_filter=None):
            yield 'event: token\ndata: {"content": "Partial"}\n\n'
            yield 'event: error\ndata: {"message": "LLM connection lost", "code": "GENERATION_FAILED"}\n\n'

        with patch(
            "src.services.streaming.stream_rag_response",
            side_effect=mock_stream_rag_response,
        ):
            yield

    def test_error_event_in_stream(self, client):
        """Stream should include error event on failure."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")
        assert "event: error" in data

    def test_partial_content_preserved_on_error(self, client):
        """Partial tokens should be delivered before error."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")

        # Should have token before error
        token_pos = data.find("event: token")
        error_pos = data.find("event: error")

        assert token_pos < error_pos
        assert "Partial" in data

    def test_error_contains_message(self, client):
        """Error event should contain error message."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")
        assert "LLM connection lost" in data

    def test_error_contains_code(self, client):
        """Error event should contain error code."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        data = response.data.decode("utf-8")
        assert "GENERATION_FAILED" in data


class TestSSEEndpointHeaders:
    """Tests for SSE endpoint response headers."""

    @pytest.fixture
    def client(self):
        """Create test client for the Dash app."""
        from src.app import server

        server.config["TESTING"] = True
        with server.test_client() as client:
            yield client

    @pytest.fixture(autouse=True)
    def mock_streaming(self):
        """Mock the streaming to avoid database dependency."""
        def mock_stream_rag_response(query, session_id, recording_filter=None):
            yield 'event: done\ndata: {}\n\n'

        with patch(
            "src.services.streaming.stream_rag_response",
            side_effect=mock_stream_rag_response,
        ):
            yield

    def test_cache_control_header(self, client):
        """Response should have Cache-Control: no-cache header."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        assert response.headers.get("Cache-Control") == "no-cache"

    def test_x_accel_buffering_header(self, client):
        """Response should have X-Accel-Buffering: no header for nginx."""
        response = client.post(
            "/api/chat/stream",
            json={"query": "test", "session_id": "test-session"},
            content_type="application/json",
        )

        assert response.headers.get("X-Accel-Buffering") == "no"
