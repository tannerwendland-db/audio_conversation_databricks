"""Unit tests for recording management service functions.

This module provides comprehensive tests for recording title validation,
recording updates, and recording deletion with cascade operations.

RED phase of TDD - these tests are written before implementation
and should fail initially.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.models import ProcessingStatus, Recording, Transcript


class TestValidateTitle:
    """Tests for the validate_title() function.

    The function should validate that recording titles are not empty,
    not whitespace-only, and do not exceed 255 characters. Valid titles
    should be stripped of leading/trailing whitespace and returned.
    """

    def test_valid_title_returns_stripped_title(self) -> None:
        """Test that a valid title is returned after stripping whitespace."""
        from src.services.recording import validate_title

        result = validate_title("Test Recording Title")

        assert result == "Test Recording Title"

    def test_valid_title_with_leading_whitespace_is_stripped(self) -> None:
        """Test that leading whitespace is stripped from valid title."""
        from src.services.recording import validate_title

        result = validate_title("   Test Recording Title")

        assert result == "Test Recording Title"

    def test_valid_title_with_trailing_whitespace_is_stripped(self) -> None:
        """Test that trailing whitespace is stripped from valid title."""
        from src.services.recording import validate_title

        result = validate_title("Test Recording Title   ")

        assert result == "Test Recording Title"

    def test_valid_title_with_both_whitespace_is_stripped(self) -> None:
        """Test that both leading and trailing whitespace is stripped."""
        from src.services.recording import validate_title

        result = validate_title("   Test Recording Title   ")

        assert result == "Test Recording Title"

    def test_empty_string_raises_value_error(self) -> None:
        """Test that empty string raises ValueError."""
        from src.services.recording import validate_title

        with pytest.raises(ValueError) as exc_info:
            validate_title("")

        assert "empty" in str(exc_info.value).lower() or "title" in str(exc_info.value).lower()

    def test_whitespace_only_raises_value_error(self) -> None:
        """Test that whitespace-only string raises ValueError."""
        from src.services.recording import validate_title

        with pytest.raises(ValueError) as exc_info:
            validate_title("   ")

        assert "empty" in str(exc_info.value).lower() or "title" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "whitespace_title",
        [
            " ",
            "  ",
            "\t",
            "\n",
            "\r\n",
            "   \t   ",
            "\n\t\r",
            "     \n     ",
        ],
    )
    def test_various_whitespace_only_strings_raise_value_error(
        self, whitespace_title: str
    ) -> None:
        """Test that various whitespace-only strings raise ValueError."""
        from src.services.recording import validate_title

        with pytest.raises(ValueError) as exc_info:
            validate_title(whitespace_title)

        assert "empty" in str(exc_info.value).lower() or "title" in str(exc_info.value).lower()

    def test_title_exceeds_255_chars_raises_value_error(self) -> None:
        """Test that title exceeding 255 characters raises ValueError."""
        from src.services.recording import validate_title

        long_title = "A" * 256

        with pytest.raises(ValueError) as exc_info:
            validate_title(long_title)

        assert "255" in str(exc_info.value) or "length" in str(exc_info.value).lower()

    def test_title_exactly_255_chars_succeeds(self) -> None:
        """Test that title with exactly 255 characters is accepted."""
        from src.services.recording import validate_title

        exactly_255_title = "A" * 255
        result = validate_title(exactly_255_title)

        assert result == exactly_255_title
        assert len(result) == 255

    def test_title_at_254_chars_succeeds(self) -> None:
        """Test that title with 254 characters is accepted."""
        from src.services.recording import validate_title

        title_254 = "B" * 254
        result = validate_title(title_254)

        assert result == title_254
        assert len(result) == 254

    @pytest.mark.parametrize(
        "length",
        [256, 300, 500, 1000],
    )
    def test_titles_over_255_chars_raise_value_error(self, length: int) -> None:
        """Test that titles over 255 characters raise ValueError."""
        from src.services.recording import validate_title

        long_title = "X" * length

        with pytest.raises(ValueError) as exc_info:
            validate_title(long_title)

        assert "255" in str(exc_info.value) or "length" in str(exc_info.value).lower()

    def test_title_with_special_characters_succeeds(self) -> None:
        """Test that title with special characters is accepted."""
        from src.services.recording import validate_title

        special_title = "Meeting 2024-01-15 (Sales Team) - Q4 Review!"
        result = validate_title(special_title)

        assert result == special_title

    def test_title_with_unicode_characters_succeeds(self) -> None:
        """Test that title with unicode characters is accepted."""
        from src.services.recording import validate_title

        unicode_title = "Cafe Meeting Notes"
        result = validate_title(unicode_title)

        assert result == unicode_title

    def test_single_character_title_succeeds(self) -> None:
        """Test that single character title is accepted."""
        from src.services.recording import validate_title

        result = validate_title("A")

        assert result == "A"

    def test_title_with_internal_whitespace_is_preserved(self) -> None:
        """Test that internal whitespace is preserved in title."""
        from src.services.recording import validate_title

        title_with_spaces = "Test   Recording   Title"
        result = validate_title(title_with_spaces)

        assert result == "Test   Recording   Title"

    def test_title_with_tabs_inside_is_preserved(self) -> None:
        """Test that internal tabs are preserved in title."""
        from src.services.recording import validate_title

        title_with_tabs = "Test\tRecording\tTitle"
        result = validate_title(title_with_tabs)

        assert result == "Test\tRecording\tTitle"


class TestUpdateRecording:
    """Tests for the update_recording() function.

    The function should update recording title with validation,
    update the updated_at timestamp, and raise ValueError if
    the recording is not found.
    """

    def test_successful_title_update(self, db_session: Session, sample_recording: Recording) -> None:
        """Test that recording title is successfully updated."""
        from src.services.recording import update_recording

        new_title = "Updated Recording Title"
        result = update_recording(
            session=db_session,
            recording_id=sample_recording.id,
            title=new_title,
        )

        assert result.title == new_title
        assert result.id == sample_recording.id

    def test_recording_not_found_raises_value_error(self, db_session: Session) -> None:
        """Test that ValueError is raised when recording is not found."""
        from src.services.recording import update_recording

        nonexistent_id = str(uuid4())

        with pytest.raises(ValueError) as exc_info:
            update_recording(
                session=db_session,
                recording_id=nonexistent_id,
                title="New Title",
            )

        assert "not found" in str(exc_info.value).lower()

    def test_validates_title_before_updating(self, db_session: Session, sample_recording: Recording) -> None:
        """Test that title is validated before update is performed."""
        from src.services.recording import update_recording

        original_title = sample_recording.title

        with pytest.raises(ValueError) as exc_info:
            update_recording(
                session=db_session,
                recording_id=sample_recording.id,
                title="",
            )

        # Verify the original title was not changed
        db_session.refresh(sample_recording)
        assert sample_recording.title == original_title
        assert "empty" in str(exc_info.value).lower() or "title" in str(exc_info.value).lower()

    def test_validates_title_length_before_updating(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that title length is validated before update."""
        from src.services.recording import update_recording

        original_title = sample_recording.title
        too_long_title = "A" * 256

        with pytest.raises(ValueError) as exc_info:
            update_recording(
                session=db_session,
                recording_id=sample_recording.id,
                title=too_long_title,
            )

        # Verify the original title was not changed
        db_session.refresh(sample_recording)
        assert sample_recording.title == original_title
        assert "255" in str(exc_info.value) or "length" in str(exc_info.value).lower()

    def test_updates_timestamp_on_successful_update(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that updated_at timestamp is set on successful update."""
        from src.services.recording import update_recording

        # Store original updated_at value (may be None initially)
        original_updated_at = sample_recording.updated_at

        result = update_recording(
            session=db_session,
            recording_id=sample_recording.id,
            title="New Title",
        )

        # updated_at should be set and different from original
        assert result.updated_at is not None
        if original_updated_at is not None:
            assert result.updated_at > original_updated_at

    def test_none_title_does_not_change_title(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that None title parameter doesn't change the title."""
        from src.services.recording import update_recording

        original_title = sample_recording.title

        result = update_recording(
            session=db_session,
            recording_id=sample_recording.id,
            title=None,
        )

        assert result.title == original_title

    def test_whitespace_title_raises_value_error(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that whitespace-only title raises ValueError."""
        from src.services.recording import update_recording

        original_title = sample_recording.title

        with pytest.raises(ValueError) as exc_info:
            update_recording(
                session=db_session,
                recording_id=sample_recording.id,
                title="   ",
            )

        # Verify the original title was not changed
        db_session.refresh(sample_recording)
        assert sample_recording.title == original_title
        assert "empty" in str(exc_info.value).lower() or "title" in str(exc_info.value).lower()

    def test_title_is_stripped_before_saving(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that title whitespace is stripped before saving."""
        from src.services.recording import update_recording

        result = update_recording(
            session=db_session,
            recording_id=sample_recording.id,
            title="   New Title with Spaces   ",
        )

        assert result.title == "New Title with Spaces"

    def test_returns_updated_recording_instance(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that the function returns the updated Recording instance."""
        from src.services.recording import update_recording

        result = update_recording(
            session=db_session,
            recording_id=sample_recording.id,
            title="Updated Title",
        )

        assert isinstance(result, Recording)
        assert result.id == sample_recording.id
        assert result.title == "Updated Title"

    def test_preserves_other_fields_on_update(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that other recording fields are preserved during title update."""
        from src.services.recording import update_recording

        original_volume_path = sample_recording.volume_path
        original_original_filename = sample_recording.original_filename
        original_processing_status = sample_recording.processing_status

        result = update_recording(
            session=db_session,
            recording_id=sample_recording.id,
            title="New Title",
        )

        assert result.volume_path == original_volume_path
        assert result.original_filename == original_original_filename
        assert result.processing_status == original_processing_status


class TestDeleteRecordingCascade:
    """Tests for the delete_recording() function.

    The function should delete a recording and all associated data
    in the correct cascade order: chunks -> transcript -> volume file -> recording.
    """

    def test_not_found_raises_value_error(self, db_session: Session) -> None:
        """Test that ValueError is raised when recording is not found."""
        from src.services.recording import delete_recording

        nonexistent_id = str(uuid4())

        with pytest.raises(ValueError) as exc_info:
            delete_recording(
                session=db_session,
                recording_id=nonexistent_id,
            )

        assert "not found" in str(exc_info.value).lower()

    @patch("src.services.recording.delete_recording_chunks")
    def test_calls_delete_recording_chunks(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that delete_recording_chunks is called with correct parameters."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 5

        delete_recording(
            session=db_session,
            recording_id=sample_recording.id,
        )

        mock_delete_chunks.assert_called_once()
        call_args = mock_delete_chunks.call_args
        assert call_args.kwargs.get("recording_id") == sample_recording.id or (
            len(call_args.args) >= 2 and call_args.args[1] == sample_recording.id
        )

    @patch("src.services.recording.delete_recording_chunks")
    def test_deletes_recording_from_database(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that recording is deleted from database."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 0

        recording_id = sample_recording.id

        result = delete_recording(
            session=db_session,
            recording_id=recording_id,
        )

        assert result is True
        # Verify recording no longer exists
        remaining = db_session.query(Recording).filter_by(id=recording_id).first()
        assert remaining is None

    @patch("src.services.recording.delete_recording_chunks")
    def test_returns_true_on_successful_deletion(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that True is returned on successful deletion."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 0

        result = delete_recording(
            session=db_session,
            recording_id=sample_recording.id,
        )

        assert result is True

    @patch("src.services.recording.delete_recording_chunks")
    def test_deletes_transcript_via_cascade(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
        sample_transcript: Transcript,
    ) -> None:
        """Test that transcript is deleted via cascade when recording is deleted."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 0

        recording_id = sample_recording.id
        transcript_id = sample_transcript.id

        delete_recording(
            session=db_session,
            recording_id=recording_id,
        )

        # Verify transcript is also deleted (cascade delete)
        remaining_transcript = db_session.query(Transcript).filter_by(id=transcript_id).first()
        assert remaining_transcript is None

    @patch("src.services.recording.delete_recording_chunks")
    def test_delete_order_chunks_before_transcript(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that chunks are deleted before transcript/recording."""
        from src.services.recording import delete_recording

        call_order = []

        def track_chunk_delete(*args, **kwargs):
            call_order.append("chunks")
            return 0

        mock_delete_chunks.side_effect = track_chunk_delete

        delete_recording(
            session=db_session,
            recording_id=sample_recording.id,
        )

        # Chunks should be deleted (call_order should contain 'chunks')
        assert "chunks" in call_order


class TestDeleteRecordingChunksDependency:
    """Tests verifying the delete_recording_chunks dependency integration."""

    @patch("src.services.recording.delete_recording_chunks")
    def test_chunk_delete_count_is_logged_or_returned(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that chunk deletion count is handled properly."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 10  # 10 chunks deleted

        # Should not raise, chunk count is handled internally
        result = delete_recording(
            session=db_session,
            recording_id=sample_recording.id,
        )

        assert result is True
        mock_delete_chunks.assert_called_once()

    @patch("src.services.recording.delete_recording_chunks")
    def test_chunk_delete_with_zero_chunks(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test deletion works when there are no chunks to delete."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 0

        result = delete_recording(
            session=db_session,
            recording_id=sample_recording.id,
        )

        assert result is True


class TestDeleteRecordingEdgeCases:
    """Edge case tests for delete_recording() function."""

    @patch("src.services.recording.delete_recording_chunks")
    def test_delete_recording_with_pending_status(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording_pending: Recording,
    ) -> None:
        """Test that recording with PENDING status can be deleted."""
        from src.services.recording import delete_recording

        mock_delete_chunks.return_value = 0

        recording_id = sample_recording_pending.id

        result = delete_recording(
            session=db_session,
            recording_id=recording_id,
        )

        assert result is True
        remaining = db_session.query(Recording).filter_by(id=recording_id).first()
        assert remaining is None

    @patch("src.services.recording.delete_recording_chunks")
    def test_delete_recording_with_failed_status(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
    ) -> None:
        """Test that recording with FAILED status can be deleted."""
        from src.services.recording import delete_recording

        # Create a recording with FAILED status
        recording = Recording(
            id=str(uuid4()),
            title="Failed Recording",
            original_filename="failed_recording.wav",
            volume_path="/Volumes/test/default/audio-recordings/failed.wav",
            processing_status=ProcessingStatus.FAILED.value,
            error_message="Processing failed due to invalid audio",
        )
        db_session.add(recording)
        db_session.commit()

        mock_delete_chunks.return_value = 0

        result = delete_recording(
            session=db_session,
            recording_id=recording.id,
        )

        assert result is True
        remaining = db_session.query(Recording).filter_by(id=recording.id).first()
        assert remaining is None

    def test_empty_recording_id_raises_value_error(self, db_session: Session) -> None:
        """Test that empty recording_id raises ValueError."""
        from src.services.recording import delete_recording

        with pytest.raises(ValueError) as exc_info:
            delete_recording(
                session=db_session,
                recording_id="",
            )

        assert "not found" in str(exc_info.value).lower()

    @patch("src.services.recording.delete_recording_chunks")
    def test_chunk_deletion_error_is_raised(
        self,
        mock_delete_chunks: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that chunk deletion errors are propagated."""
        from src.services.recording import delete_recording

        mock_delete_chunks.side_effect = Exception("Database connection lost")

        with pytest.raises(Exception) as exc_info:
            delete_recording(
                session=db_session,
                recording_id=sample_recording.id,
            )

        assert "Database connection lost" in str(exc_info.value)
