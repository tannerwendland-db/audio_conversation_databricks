"""Integration tests for recording detail retrieval functionality.

This module tests the retrieval of individual recordings and their associated
transcripts for the Browse and Review Individual Recordings feature (User Story 3).

These tests are written in the RED phase of TDD - the service functions
in src/services/transcript.py do not exist yet and these tests are expected
to fail initially.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.models import Recording, Transcript


class TestGetTranscriptByRecordingId:
    """Tests for get_transcript_by_recording_id() function."""

    def test_returns_transcript_for_valid_recording_id(
        self, db_session: Session, sample_recording: Recording, sample_transcript: Transcript
    ) -> None:
        """Test that a transcript is returned for a valid recording with a transcript."""
        from src.services.transcript import get_transcript_by_recording_id

        result = get_transcript_by_recording_id(db_session, sample_recording.id)

        assert result is not None
        assert result.id == sample_transcript.id
        assert result.recording_id == sample_recording.id

    def test_returns_none_for_nonexistent_recording_id(self, db_session: Session) -> None:
        """Test that None is returned for a recording ID that does not exist."""
        from src.services.transcript import get_transcript_by_recording_id

        non_existent_id = str(uuid4())
        result = get_transcript_by_recording_id(db_session, non_existent_id)

        assert result is None

    def test_returns_none_for_recording_without_transcript(
        self, db_session: Session, sample_recording_pending: Recording
    ) -> None:
        """Test that None is returned for a recording that has no transcript."""
        from src.services.transcript import get_transcript_by_recording_id

        # sample_recording_pending has no associated transcript
        result = get_transcript_by_recording_id(db_session, sample_recording_pending.id)

        assert result is None

    def test_returns_transcript_with_all_fields(
        self, db_session: Session, sample_recording: Recording, sample_transcript: Transcript
    ) -> None:
        """Test that the returned transcript includes all expected fields."""
        from src.services.transcript import get_transcript_by_recording_id

        result = get_transcript_by_recording_id(db_session, sample_recording.id)

        assert result is not None
        assert result.full_text is not None
        assert result.diarized_text is not None
        assert result.language == "en"
        assert result.summary is not None
        assert result.created_at is not None

    def test_returns_transcript_with_correct_diarized_content(
        self, db_session: Session, sample_recording: Recording, sample_transcript: Transcript
    ) -> None:
        """Test that the returned transcript has the correct diarized text content."""
        from src.services.transcript import get_transcript_by_recording_id

        result = get_transcript_by_recording_id(db_session, sample_recording.id)

        assert result is not None
        assert "[SPEAKER_00" in result.diarized_text
        assert "[SPEAKER_01" in result.diarized_text
        assert "Hello everyone, welcome to the meeting" in result.diarized_text


class TestGetRecordingWithTranscript:
    """Tests for get_recording() with eager-loaded transcript relationship."""

    def test_returns_recording_for_valid_id(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that a recording is returned for a valid recording ID."""
        from src.services.recording import get_recording

        result = get_recording(db_session, sample_recording.id)

        assert result is not None
        assert result.id == sample_recording.id
        assert result.title == sample_recording.title

    def test_returns_none_for_nonexistent_recording_id(self, db_session: Session) -> None:
        """Test that None is returned for a recording ID that does not exist."""
        from src.services.recording import get_recording

        non_existent_id = str(uuid4())
        result = get_recording(db_session, non_existent_id)

        assert result is None

    def test_recording_transcript_is_accessible(
        self, db_session: Session, sample_recording: Recording, sample_transcript: Transcript
    ) -> None:
        """Test that the recording's transcript relationship is accessible.

        This test verifies that when a recording is retrieved, its associated
        transcript can be accessed via the transcript relationship without
        requiring an additional database query.
        """
        from src.services.recording import get_recording

        result = get_recording(db_session, sample_recording.id)

        assert result is not None
        assert result.transcript is not None
        assert result.transcript.id == sample_transcript.id
        assert result.transcript.recording_id == sample_recording.id

    def test_recording_transcript_is_none_when_no_transcript_exists(
        self, db_session: Session, sample_recording_pending: Recording
    ) -> None:
        """Test that transcript is None for recordings without a transcript."""
        from src.services.recording import get_recording

        result = get_recording(db_session, sample_recording_pending.id)

        assert result is not None
        assert result.transcript is None

    def test_recording_includes_all_metadata_fields(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that the retrieved recording includes all metadata fields."""
        from src.services.recording import get_recording

        result = get_recording(db_session, sample_recording.id)

        assert result is not None
        assert result.id is not None
        assert result.title is not None
        assert result.original_filename is not None
        assert result.volume_path is not None
        assert result.duration_seconds is not None
        assert result.processing_status is not None
        assert result.created_at is not None

    def test_transcript_diarized_text_is_accessible_via_recording(
        self, db_session: Session, sample_recording: Recording, sample_transcript: Transcript
    ) -> None:
        """Test that the diarized text can be accessed through the recording's transcript."""
        from src.services.recording import get_recording

        result = get_recording(db_session, sample_recording.id)

        assert result is not None
        assert result.transcript is not None
        assert result.transcript.diarized_text is not None
        assert "[SPEAKER_00" in result.transcript.diarized_text
        assert "Hello everyone, welcome to the meeting" in result.transcript.diarized_text
