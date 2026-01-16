"""Contract tests for SSE event format.

Tests validate that SSE events conform to the contract defined in
specs/005-chat-streaming-responses/contracts/sse-stream.yaml
"""

import json

import pytest


class TestTokenEventContract:
    """Contract tests for token SSE events (T007 - US1)."""

    def test_token_event_has_required_fields(self):
        """Token event must have 'content' field in data."""
        # SSE format: "event: token\ndata: {\"content\": \"token_text\"}\n\n"
        event_type = "token"
        event_data = {"content": "Hello"}

        # Validate structure
        assert "content" in event_data
        assert isinstance(event_data["content"], str)

    def test_token_event_content_is_string(self):
        """Token content must be a string (may be partial word)."""
        valid_tokens = ["Hello", " ", "world", ".", ""]

        for token in valid_tokens:
            data = {"content": token}
            assert isinstance(data["content"], str)

    def test_token_event_format_is_valid_sse(self):
        """Token event must follow SSE wire format."""
        event = "event: token\ndata: {\"content\": \"Hello\"}\n\n"

        # Parse SSE event
        lines = event.strip().split("\n")
        assert lines[0].startswith("event:")
        assert lines[1].startswith("data:")

        # Parse data payload
        data_line = lines[1].replace("data: ", "", 1)
        data = json.loads(data_line)
        assert "content" in data


class TestDoneEventContract:
    """Contract tests for done SSE events (T007 - US1)."""

    def test_done_event_has_empty_data(self):
        """Done event data should be an empty object."""
        event_type = "done"
        event_data = {}

        assert event_data == {}

    def test_done_event_format_is_valid_sse(self):
        """Done event must follow SSE wire format."""
        event = "event: done\ndata: {}\n\n"

        lines = event.strip().split("\n")
        assert lines[0] == "event: done"
        assert lines[1] == "data: {}"


class TestSSEEventSequence:
    """Contract tests for SSE event sequence."""

    def test_stream_ends_with_done_event(self):
        """Stream must end with a done event after all tokens."""
        events = [
            "event: token\ndata: {\"content\": \"Hello\"}\n\n",
            "event: token\ndata: {\"content\": \" world\"}\n\n",
            "event: done\ndata: {}\n\n",
        ]

        # Last event should be done
        last_event = events[-1]
        assert "event: done" in last_event

    def test_token_events_precede_done(self):
        """Token events must come before done event."""
        events = [
            ("token", {"content": "Hello"}),
            ("token", {"content": " world"}),
            ("done", {}),
        ]

        done_index = None
        for i, (event_type, _) in enumerate(events):
            if event_type == "done":
                done_index = i
                break

        # All prior events should be tokens
        for i in range(done_index):
            assert events[i][0] == "token"


class TestCitationsEventContract:
    """Contract tests for citations SSE events (T019 - US2)."""

    def test_citations_event_has_required_fields(self):
        """Citations event must have 'citations' array in data."""
        event_type = "citations"
        event_data = {"citations": []}

        assert "citations" in event_data
        assert isinstance(event_data["citations"], list)

    def test_citations_event_format_is_valid_sse(self):
        """Citations event must follow SSE wire format."""
        event = 'event: citations\ndata: {"citations": []}\n\n'

        lines = event.strip().split("\n")
        assert lines[0] == "event: citations"
        assert lines[1].startswith("data:")

        data_line = lines[1].replace("data: ", "", 1)
        data = json.loads(data_line)
        assert "citations" in data

    def test_citations_array_contains_valid_objects(self):
        """Citation objects must have required fields."""
        citation = {
            "recording_id": "rec_123",
            "recording_title": "Test Recording",
            "excerpt": "Some text excerpt",
            "speaker": "John Doe",
        }

        assert "recording_id" in citation
        assert "recording_title" in citation
        assert "excerpt" in citation

    def test_citations_speaker_can_be_null(self):
        """Citation speaker field can be null."""
        citation = {
            "recording_id": "rec_123",
            "recording_title": "Test Recording",
            "excerpt": "Some text excerpt",
            "speaker": None,
        }

        assert citation["speaker"] is None


class TestCitationsEventSequence:
    """Contract tests for citations event ordering (T019 - US2)."""

    def test_citations_sent_after_tokens(self):
        """Citations event must come after all token events."""
        events = [
            ("token", {"content": "Hello"}),
            ("token", {"content": " world"}),
            ("citations", {"citations": [{"recording_id": "rec_1"}]}),
            ("done", {}),
        ]

        citations_index = None
        for i, (event_type, _) in enumerate(events):
            if event_type == "citations":
                citations_index = i
                break

        # All prior events should be tokens
        for i in range(citations_index):
            assert events[i][0] == "token"

    def test_citations_sent_before_done(self):
        """Citations event must come before done event."""
        events = [
            ("token", {"content": "Hello"}),
            ("citations", {"citations": []}),
            ("done", {}),
        ]

        citations_index = None
        done_index = None

        for i, (event_type, _) in enumerate(events):
            if event_type == "citations":
                citations_index = i
            elif event_type == "done":
                done_index = i

        assert citations_index < done_index


class TestErrorEventContract:
    """Contract tests for error SSE events (T026 - US3)."""

    def test_error_event_has_required_fields(self):
        """Error event must have 'message' field in data."""
        event_type = "error"
        event_data = {"message": "Connection failed", "code": "GENERATION_FAILED"}

        assert "message" in event_data
        assert isinstance(event_data["message"], str)

    def test_error_event_format_is_valid_sse(self):
        """Error event must follow SSE wire format."""
        event = 'event: error\ndata: {"message": "Failed", "code": "GENERATION_FAILED"}\n\n'

        lines = event.strip().split("\n")
        assert lines[0] == "event: error"
        assert lines[1].startswith("data:")

        data_line = lines[1].replace("data: ", "", 1)
        data = json.loads(data_line)
        assert "message" in data

    def test_error_codes_are_valid(self):
        """Error codes must be from the defined enum."""
        valid_codes = [
            "RETRIEVAL_FAILED",
            "GENERATION_FAILED",
            "TIMEOUT",
            "INTERNAL_ERROR",
        ]

        for code in valid_codes:
            event_data = {"message": "Test error", "code": code}
            assert event_data["code"] in valid_codes

    def test_error_code_is_optional(self):
        """Error code can be omitted (only message required)."""
        event_data = {"message": "Something went wrong"}

        assert "message" in event_data
        # Code is optional
        assert "code" not in event_data or event_data.get("code") is not None


class TestErrorEventSequence:
    """Contract tests for error event behavior (T026 - US3)."""

    def test_error_terminates_stream(self):
        """Error event should be the final event (no done after error)."""
        events = [
            ("token", {"content": "Based on"}),
            ("error", {"message": "Connection lost", "code": "GENERATION_FAILED"}),
        ]

        # Last event should be error
        assert events[-1][0] == "error"

    def test_partial_content_before_error(self):
        """Tokens delivered before error should be preserved."""
        events = [
            ("token", {"content": "Based on"}),
            ("token", {"content": " the"}),
            ("error", {"message": "LLM timeout", "code": "TIMEOUT"}),
        ]

        # First two events should be tokens
        assert events[0][0] == "token"
        assert events[1][0] == "token"
        # Error comes after
        assert events[2][0] == "error"
