"""Integration tests for database operations on recordings and transcripts.

This module tests the recording service functions that perform CRUD operations
on Recording and Transcript models using the database session.

These tests are written in the RED phase of TDD - the service functions
in src/services/recording.py do not exist yet and these tests are expected
to fail initially.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import ProcessingStatus, Recording, Transcript


class TestCreateRecording:
    """Tests for create_recording() function."""

    def test_creates_recording_with_all_fields(self, db_session: Session) -> None:
        """Test that create_recording creates a recording with all provided fields."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="Team Standup Meeting",
            original_filename="standup_2024-01-20.wav",
            volume_path="/Volumes/catalog/schema/recordings/standup_2024-01-20.wav",
            uploaded_by="alice@example.com",
            duration_seconds=1800.5,
        )

        assert recording.title == "Team Standup Meeting"
        assert recording.original_filename == "standup_2024-01-20.wav"
        assert recording.volume_path == "/Volumes/catalog/schema/recordings/standup_2024-01-20.wav"
        assert recording.uploaded_by == "alice@example.com"
        assert recording.duration_seconds == 1800.5

    def test_default_status_is_pending(self, db_session: Session) -> None:
        """Test that a new recording has PENDING status by default."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="New Recording",
            original_filename="new_recording.mp3",
            volume_path="/Volumes/catalog/schema/recordings/new_recording.mp3",
        )

        assert recording.processing_status == ProcessingStatus.PENDING.value

    def test_returns_recording_with_generated_uuid(self, db_session: Session) -> None:
        """Test that create_recording returns a Recording with a valid UUID."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="UUID Test Recording",
            original_filename="uuid_test.wav",
            volume_path="/Volumes/catalog/schema/recordings/uuid_test.wav",
        )

        assert recording.id is not None
        assert isinstance(recording.id, str)
        assert len(recording.id) == 36  # Standard UUID format with hyphens

    def test_handles_optional_uploaded_by_as_none(self, db_session: Session) -> None:
        """Test that uploaded_by can be None."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="Anonymous Upload",
            original_filename="anonymous.wav",
            volume_path="/Volumes/catalog/schema/recordings/anonymous.wav",
            uploaded_by=None,
        )

        assert recording.uploaded_by is None

    def test_handles_optional_duration_seconds_as_none(self, db_session: Session) -> None:
        """Test that duration_seconds can be None (duration not yet known)."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="Unknown Duration Recording",
            original_filename="unknown_duration.wav",
            volume_path="/Volumes/catalog/schema/recordings/unknown_duration.wav",
            duration_seconds=None,
        )

        assert recording.duration_seconds is None

    def test_recording_is_persisted_to_database(self, db_session: Session) -> None:
        """Test that the created recording is persisted and can be queried."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="Persisted Recording",
            original_filename="persisted.wav",
            volume_path="/Volumes/catalog/schema/recordings/persisted.wav",
        )

        # Query the database to verify persistence
        queried = db_session.query(Recording).filter_by(id=recording.id).first()
        assert queried is not None
        assert queried.title == "Persisted Recording"

    def test_created_at_is_set_automatically(self, db_session: Session) -> None:
        """Test that created_at timestamp is set automatically."""
        from src.services.recording import create_recording

        recording = create_recording(
            session=db_session,
            title="Timestamp Test",
            original_filename="timestamp.wav",
            volume_path="/Volumes/catalog/schema/recordings/timestamp.wav",
        )

        assert recording.created_at is not None


class TestUpdateRecordingStatus:
    """Tests for update_recording_status() function."""

    def test_updates_status_from_pending_to_converting(
        self, db_session: Session, sample_recording_pending: Recording
    ) -> None:
        """Test updating status from PENDING to CONVERTING."""
        from src.services.recording import update_recording_status

        updated = update_recording_status(
            session=db_session,
            recording_id=sample_recording_pending.id,
            status=ProcessingStatus.CONVERTING,
        )

        assert updated.processing_status == ProcessingStatus.CONVERTING.value

    def test_updates_status_from_converting_to_diarizing(self, db_session: Session) -> None:
        """Test updating status from CONVERTING to DIARIZING."""
        from src.services.recording import update_recording_status

        # Create a recording in CONVERTING state
        recording = Recording(
            title="Converting Recording",
            original_filename="converting.wav",
            volume_path="/Volumes/catalog/schema/recordings/converting.wav",
            processing_status=ProcessingStatus.CONVERTING.value,
        )
        db_session.add(recording)
        db_session.commit()
        db_session.refresh(recording)

        updated = update_recording_status(
            session=db_session,
            recording_id=recording.id,
            status=ProcessingStatus.DIARIZING,
        )

        assert updated.processing_status == ProcessingStatus.DIARIZING.value

    def test_updates_status_through_full_flow_to_completed(
        self, db_session: Session, sample_recording_pending: Recording
    ) -> None:
        """Test updating status through the complete processing flow."""
        from src.services.recording import update_recording_status

        recording_id = sample_recording_pending.id

        # PENDING -> CONVERTING
        update_recording_status(db_session, recording_id, ProcessingStatus.CONVERTING)
        # CONVERTING -> DIARIZING
        update_recording_status(db_session, recording_id, ProcessingStatus.DIARIZING)
        # DIARIZING -> EMBEDDING
        update_recording_status(db_session, recording_id, ProcessingStatus.EMBEDDING)
        # EMBEDDING -> COMPLETED
        updated = update_recording_status(db_session, recording_id, ProcessingStatus.COMPLETED)

        assert updated.processing_status == ProcessingStatus.COMPLETED.value

    def test_updates_to_failed_status(
        self, db_session: Session, sample_recording_pending: Recording
    ) -> None:
        """Test updating status to FAILED."""
        from src.services.recording import update_recording_status

        updated = update_recording_status(
            session=db_session,
            recording_id=sample_recording_pending.id,
            status=ProcessingStatus.FAILED,
        )

        assert updated.processing_status == ProcessingStatus.FAILED.value

    def test_recording_not_found_raises_exception(self, db_session: Session) -> None:
        """Test that updating a non-existent recording raises an exception."""
        from src.services.recording import update_recording_status

        non_existent_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(ValueError, match="Recording not found"):
            update_recording_status(
                session=db_session,
                recording_id=non_existent_id,
                status=ProcessingStatus.CONVERTING,
            )

    def test_updated_at_is_set_on_status_change(
        self, db_session: Session, sample_recording_pending: Recording
    ) -> None:
        """Test that updated_at timestamp is set when status changes."""
        from src.services.recording import update_recording_status

        original_updated_at = sample_recording_pending.updated_at

        updated = update_recording_status(
            session=db_session,
            recording_id=sample_recording_pending.id,
            status=ProcessingStatus.CONVERTING,
        )

        # updated_at should be set (was None or changed)
        assert updated.updated_at is not None or updated.updated_at != original_updated_at


class TestCreateTranscript:
    """Tests for create_transcript() function."""

    def test_creates_transcript_linked_to_recording(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that create_transcript creates a transcript linked to a recording."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="This is the full transcript text of the recording.",
        )

        assert transcript.recording_id == sample_recording.id
        assert transcript.full_text == "This is the full transcript text of the recording."

    def test_sets_all_fields_correctly(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that all transcript fields are set correctly."""
        from src.services.recording import create_transcript

        diarized = "[SPEAKER_00 0:00:00] Hello. [SPEAKER_01 0:00:02] Hi there."
        full_text = "Hello. Hi there."
        summary = "A brief greeting exchange between two speakers."

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text=full_text,
            diarized_text=diarized,
            language="en",
            summary=summary,
        )

        assert transcript.full_text == full_text
        assert transcript.diarized_text == diarized
        assert transcript.language == "en"
        assert transcript.summary == summary

    def test_handles_optional_diarized_text_as_none(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that diarized_text can be None."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="Transcript without diarization.",
            diarized_text=None,
        )

        assert transcript.diarized_text is None

    def test_handles_optional_language_as_none(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that language can be None."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="Transcript without language detection.",
            language=None,
        )

        assert transcript.language is None

    def test_handles_optional_summary_as_none(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that summary can be None."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="Transcript without summary.",
            summary=None,
        )

        assert transcript.summary is None

    def test_recording_not_found_raises_exception(self, db_session: Session) -> None:
        """Test that creating a transcript for a non-existent recording raises an exception."""
        from src.services.recording import create_transcript

        non_existent_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(ValueError, match="Recording not found"):
            create_transcript(
                session=db_session,
                recording_id=non_existent_id,
                full_text="Orphan transcript text.",
            )

    def test_duplicate_transcript_raises_integrity_error(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that creating a duplicate transcript for a recording raises IntegrityError.

        The Transcript model has a UNIQUE constraint on recording_id, so each
        recording can only have one transcript.
        """
        from src.services.recording import create_transcript

        # Create first transcript
        create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="First transcript.",
        )

        # Attempt to create second transcript for same recording
        with pytest.raises(IntegrityError):
            create_transcript(
                session=db_session,
                recording_id=sample_recording.id,
                full_text="Duplicate transcript.",
            )

    def test_transcript_is_persisted_to_database(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that the created transcript is persisted and can be queried."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="Persisted transcript text.",
        )

        # Query the database to verify persistence
        queried = db_session.query(Transcript).filter_by(id=transcript.id).first()
        assert queried is not None
        assert queried.full_text == "Persisted transcript text."

    def test_transcript_has_generated_uuid(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that create_transcript returns a Transcript with a valid UUID."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="UUID test transcript.",
        )

        assert transcript.id is not None
        assert isinstance(transcript.id, str)
        assert len(transcript.id) == 36  # Standard UUID format with hyphens

    def test_created_at_is_set_automatically(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that created_at timestamp is set automatically."""
        from src.services.recording import create_transcript

        transcript = create_transcript(
            session=db_session,
            recording_id=sample_recording.id,
            full_text="Timestamp test transcript.",
        )

        assert transcript.created_at is not None
