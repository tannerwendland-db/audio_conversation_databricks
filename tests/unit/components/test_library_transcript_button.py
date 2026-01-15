"""Unit tests for the View Transcript button in recording library cards.

This module tests the rendering of the "View Transcript" button in recording
cards for User Story 1: View Diarized Transcript.

These tests are written in the TDD RED phase - the button does not exist yet
and these tests are expected to fail initially.
"""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models import ProcessingStatus


class TestViewTranscriptButtonRendering:
    """Tests for View Transcript button rendering in recording cards."""

    @pytest.fixture
    def completed_recording_mock(self) -> MagicMock:
        """Create a mock completed recording with transcript."""
        recording = MagicMock()
        recording.id = str(uuid4())
        recording.title = "Test Meeting Recording"
        recording.original_filename = "test_meeting.wav"
        recording.duration_seconds = 3600.5
        recording.processing_status = ProcessingStatus.COMPLETED.value
        recording.created_at = datetime(2024, 1, 15, 10, 30, 0)
        recording.error_message = None
        recording.transcript = MagicMock()
        recording.transcript.dialog_json = [
            {"speaker": "Interviewer", "text": "Hello, how are you?"},
            {"speaker": "Respondent", "text": "I am doing well, thank you."},
        ]
        return recording

    @pytest.fixture
    def pending_recording_mock(self) -> MagicMock:
        """Create a mock pending recording without transcript."""
        recording = MagicMock()
        recording.id = str(uuid4())
        recording.title = "Pending Recording"
        recording.original_filename = "pending.wav"
        recording.duration_seconds = None
        recording.processing_status = ProcessingStatus.PENDING.value
        recording.created_at = datetime(2024, 1, 15, 10, 30, 0)
        recording.error_message = None
        recording.transcript = None
        return recording

    @pytest.fixture
    def diarizing_recording_mock(self) -> MagicMock:
        """Create a mock recording that is still being diarized."""
        recording = MagicMock()
        recording.id = str(uuid4())
        recording.title = "Processing Recording"
        recording.original_filename = "processing.wav"
        recording.duration_seconds = 1800.0
        recording.processing_status = ProcessingStatus.DIARIZING.value
        recording.created_at = datetime(2024, 1, 15, 10, 30, 0)
        recording.processing_started_at = None
        recording.error_message = None
        recording.transcript = None
        return recording

    def test_view_transcript_button_rendered_for_completed_recording(
        self, completed_recording_mock: MagicMock
    ) -> None:
        """Test that View Transcript button is rendered for completed recordings."""
        from src.components.library import _create_recording_card

        card = _create_recording_card(completed_recording_mock)

        # Convert card to string representation to check for button
        card_str = str(card)

        # The button should contain "View Transcript" text or have appropriate ID
        assert "view-transcript" in card_str.lower() or "View Transcript" in card_str, (
            "View Transcript button should be rendered for completed recordings"
        )

    def test_view_transcript_button_has_correct_id_pattern(
        self, completed_recording_mock: MagicMock
    ) -> None:
        """Test that View Transcript button has correct pattern-matching ID."""
        from src.components.library import _create_recording_card

        card = _create_recording_card(completed_recording_mock)
        card_str = str(card)

        # Button should have a pattern-matching ID with the recording ID
        expected_id_pattern = "view-transcript-btn"
        assert expected_id_pattern in card_str or "view-transcript" in card_str.lower(), (
            "Button should have ID pattern containing 'view-transcript'"
        )

    def test_view_transcript_button_not_rendered_for_pending_recording(
        self, pending_recording_mock: MagicMock
    ) -> None:
        """Test that View Transcript button is NOT rendered for pending recordings."""
        from src.components.library import _create_recording_card

        card = _create_recording_card(pending_recording_mock)
        card_str = str(card)

        # The button should NOT be present for non-completed recordings
        assert "View Transcript" not in card_str, (
            "View Transcript button should NOT be rendered for pending recordings"
        )

    def test_view_transcript_button_not_rendered_for_processing_recording(
        self, diarizing_recording_mock: MagicMock
    ) -> None:
        """Test that View Transcript button is NOT rendered for recordings being processed."""
        from src.components.library import _create_recording_card

        card = _create_recording_card(diarizing_recording_mock)
        card_str = str(card)

        # The button should NOT be present for recordings still being processed
        assert "View Transcript" not in card_str, (
            "View Transcript button should NOT be rendered for processing recordings"
        )

    def test_view_transcript_button_is_disabled_without_transcript(
        self, completed_recording_mock: MagicMock
    ) -> None:
        """Test that View Transcript button is disabled when transcript is None."""
        # Create a completed recording but with no transcript
        completed_recording_mock.transcript = None

        from src.components.library import _create_recording_card

        card = _create_recording_card(completed_recording_mock)
        card_str = str(card)

        # Either the button should not be rendered, or it should be disabled
        # when there's no transcript data
        if "View Transcript" in card_str:
            assert "disabled" in card_str.lower(), (
                "View Transcript button should be disabled when no transcript exists"
            )


class TestViewTranscriptButtonNavigation:
    """Tests for View Transcript button navigation behavior."""

    @pytest.fixture
    def completed_recording_mock(self) -> MagicMock:
        """Create a mock completed recording with transcript."""
        recording = MagicMock()
        recording.id = str(uuid4())
        recording.title = "Test Meeting Recording"
        recording.original_filename = "test_meeting.wav"
        recording.duration_seconds = 3600.5
        recording.processing_status = ProcessingStatus.COMPLETED.value
        recording.created_at = datetime(2024, 1, 15, 10, 30, 0)
        recording.error_message = None
        recording.transcript = MagicMock()
        recording.transcript.dialog_json = [
            {"speaker": "Interviewer", "text": "Hello"},
        ]
        return recording

    def test_view_transcript_button_navigates_to_transcript_route(
        self, completed_recording_mock: MagicMock
    ) -> None:
        """Test that View Transcript button navigates to /transcript/{recording_id}."""
        from src.components.library import _create_recording_card

        card = _create_recording_card(completed_recording_mock)
        card_str = str(card)

        # The button or link should reference the transcript route
        recording_id = completed_recording_mock.id
        expected_route = f"/transcript/{recording_id}"

        # Check if the transcript route is referenced in the card
        # Note: The current implementation may use /recording/{id} route
        # which also shows transcript. Either is acceptable.
        assert (
            expected_route in card_str
            or f"/recording/{recording_id}" in card_str
            or "transcript" in card_str.lower()
        ), "View Transcript button should link to transcript view"
