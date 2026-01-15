"""Integration tests for recording deletion with cascade functionality.

This module tests the delete_recording() function that performs cascade deletion
of a recording and all its associated data:
1. Delete transcript chunks (embeddings) - explicit call to delete_recording_chunks()
2. Delete transcript (via FK cascade when recording deleted)
3. Delete recording

These tests are written in the RED phase of TDD - the delete_recording function
in src/services/recording.py does not exist yet and these tests are expected
to fail initially.
"""

from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

from src.models import ProcessingStatus, Recording, Transcript, TranscriptChunk


class TestDeleteRecordingIntegration:
    """Integration tests for delete_recording() function cascade behavior."""

    def test_delete_removes_recording_from_database(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that delete_recording removes the recording from the database."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        result = delete_recording(db_session, recording_id)

        assert result is True
        queried = db_session.query(Recording).filter_by(id=recording_id).first()
        assert queried is None

    def test_delete_removes_transcript_via_cascade(
        self,
        db_session: Session,
        sample_recording: Recording,
        sample_transcript: Transcript,
    ) -> None:
        """Test that deleting a recording cascades to remove its transcript."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id
        transcript_id = sample_transcript.id

        # Verify transcript exists before deletion
        assert db_session.query(Transcript).filter_by(id=transcript_id).first() is not None

        delete_recording(db_session, recording_id)

        # Verify transcript is deleted
        queried_transcript = db_session.query(Transcript).filter_by(id=transcript_id).first()
        assert queried_transcript is None

        # Also verify by recording_id
        orphan_transcripts = (
            db_session.query(Transcript).filter_by(recording_id=recording_id).first()
        )
        assert orphan_transcripts is None

    def test_delete_removes_transcript_chunks(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that deleting a recording removes all associated transcript chunks."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Create transcript chunks for the recording
        # Note: We create simple chunks with mock embeddings for testing
        mock_embedding = [0.1] * 1024  # 1024-dimensional embedding
        for i in range(3):
            chunk = TranscriptChunk(
                recording_id=recording_id,
                chunk_index=i,
                content=f"Test chunk content {i}",
                speaker="SPEAKER_00" if i % 2 == 0 else "SPEAKER_01",
                embedding=mock_embedding,
            )
            db_session.add(chunk)
        db_session.commit()

        # Verify chunks exist before deletion
        chunks_before = db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).all()
        assert len(chunks_before) == 3

        delete_recording(db_session, recording_id)

        # Verify all chunks are deleted
        chunks_after = db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).all()
        assert chunks_after == []

    def test_full_cascade_delete_removes_all_associated_data(
        self,
        db_session: Session,
        sample_recording: Recording,
        sample_transcript: Transcript,
    ) -> None:
        """Test full cascade - recording, transcript, and chunks all removed."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id
        transcript_id = sample_transcript.id

        # Create transcript chunks
        mock_embedding = [0.1] * 1024
        chunk_ids = []
        for i in range(2):
            chunk = TranscriptChunk(
                recording_id=recording_id,
                chunk_index=i,
                content=f"Full cascade test chunk {i}",
                speaker="SPEAKER_00",
                embedding=mock_embedding,
            )
            db_session.add(chunk)
            db_session.flush()
            chunk_ids.append(chunk.id)
        db_session.commit()

        result = delete_recording(db_session, recording_id)

        assert result is True

        # Verify recording is gone
        assert db_session.query(Recording).filter_by(id=recording_id).first() is None

        # Verify transcript is gone
        assert db_session.query(Transcript).filter_by(id=transcript_id).first() is None

        # Verify all chunks are gone
        for chunk_id in chunk_ids:
            assert db_session.query(TranscriptChunk).filter_by(id=chunk_id).first() is None

    def test_delete_recording_with_no_transcript(self, db_session: Session) -> None:
        """Test deleting a recording that has no associated transcript."""
        from src.services.recording import delete_recording

        # Create a recording without a transcript
        recording = Recording(
            id=str(uuid4()),
            title="Recording Without Transcript",
            original_filename="no_transcript.wav",
            volume_path="/Volumes/test/default/audio-recordings/no_transcript.wav",
            duration_seconds=300.0,
            processing_status=ProcessingStatus.PENDING.value,
            uploaded_by="test@example.com",
            created_at=datetime.utcnow(),
        )
        db_session.add(recording)
        db_session.commit()
        recording_id = recording.id

        result = delete_recording(db_session, recording_id)

        assert result is True
        assert db_session.query(Recording).filter_by(id=recording_id).first() is None

    def test_delete_recording_with_no_chunks(
        self,
        db_session: Session,
        sample_recording: Recording,
        sample_transcript: Transcript,
    ) -> None:
        """Test deleting a recording that has a transcript but no chunks."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Verify no chunks exist for this recording
        chunks = db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).all()
        assert len(chunks) == 0

        result = delete_recording(db_session, recording_id)

        assert result is True
        assert db_session.query(Recording).filter_by(id=recording_id).first() is None
        assert db_session.query(Transcript).filter_by(recording_id=recording_id).first() is None

    def test_recording_not_found_raises_value_error(self, db_session: Session) -> None:
        """Test that attempting to delete a non-existent recording raises ValueError."""
        import pytest

        from src.services.recording import delete_recording

        non_existent_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(ValueError) as exc_info:
            delete_recording(db_session, non_existent_id)

        assert "not found" in str(exc_info.value).lower()


class TestDeleteRecordingDatabaseState:
    """Tests verifying database integrity during and after deletion."""

    def test_foreign_key_cascade_on_transcript(
        self,
        db_session: Session,
        sample_recording: Recording,
        sample_transcript: Transcript,
    ) -> None:
        """Verify that the transcript FK cascade works correctly."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Query to check transcript exists via relationship
        recording_before = db_session.query(Recording).filter_by(id=recording_id).first()
        assert recording_before is not None
        assert recording_before.transcript is not None
        assert recording_before.transcript.id == sample_transcript.id

        delete_recording(db_session, recording_id)

        # Verify no orphan transcripts exist
        all_transcripts = db_session.query(Transcript).filter_by(recording_id=recording_id).all()
        assert all_transcripts == []

    def test_foreign_key_cascade_on_chunks(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Verify that the chunks FK cascade works correctly."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Create chunks
        mock_embedding = [0.5] * 1024
        for i in range(5):
            chunk = TranscriptChunk(
                recording_id=recording_id,
                chunk_index=i,
                content=f"Cascade test chunk number {i}",
                speaker=f"SPEAKER_{i % 3:02d}",
                embedding=mock_embedding,
            )
            db_session.add(chunk)
        db_session.commit()

        # Verify chunks exist via relationship
        recording_before = db_session.query(Recording).filter_by(id=recording_id).first()
        assert recording_before is not None
        assert len(recording_before.transcript_chunks) == 5

        delete_recording(db_session, recording_id)

        # Verify no orphan chunks exist
        all_chunks = db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).all()
        assert all_chunks == []

    def test_other_recordings_unaffected_by_delete(self, db_session: Session) -> None:
        """Verify that deleting one recording does not affect other recordings."""
        from src.services.recording import delete_recording

        # Create two recordings
        recording_to_delete = Recording(
            id=str(uuid4()),
            title="Recording To Delete",
            original_filename="to_delete.wav",
            volume_path="/Volumes/test/default/audio-recordings/to_delete.wav",
            duration_seconds=100.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.utcnow(),
        )
        recording_to_keep = Recording(
            id=str(uuid4()),
            title="Recording To Keep",
            original_filename="to_keep.wav",
            volume_path="/Volumes/test/default/audio-recordings/to_keep.wav",
            duration_seconds=200.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.utcnow(),
        )
        db_session.add_all([recording_to_delete, recording_to_keep])
        db_session.commit()

        # Add transcripts for both
        transcript_to_delete = Transcript(
            id=str(uuid4()),
            recording_id=recording_to_delete.id,
            full_text="Transcript to delete",
            language="en",
        )
        transcript_to_keep = Transcript(
            id=str(uuid4()),
            recording_id=recording_to_keep.id,
            full_text="Transcript to keep",
            language="en",
        )
        db_session.add_all([transcript_to_delete, transcript_to_keep])
        db_session.commit()

        # Add chunks for both
        mock_embedding = [0.3] * 1024
        for i in range(2):
            chunk_delete = TranscriptChunk(
                recording_id=recording_to_delete.id,
                chunk_index=i,
                content=f"Delete chunk {i}",
                embedding=mock_embedding,
            )
            chunk_keep = TranscriptChunk(
                recording_id=recording_to_keep.id,
                chunk_index=i,
                content=f"Keep chunk {i}",
                embedding=mock_embedding,
            )
            db_session.add_all([chunk_delete, chunk_keep])
        db_session.commit()

        delete_id = recording_to_delete.id
        keep_id = recording_to_keep.id

        delete_recording(db_session, delete_id)

        # Verify deleted recording is gone
        assert db_session.query(Recording).filter_by(id=delete_id).first() is None
        assert db_session.query(Transcript).filter_by(recording_id=delete_id).first() is None
        assert db_session.query(TranscriptChunk).filter_by(recording_id=delete_id).all() == []

        # Verify kept recording is intact
        kept_recording = db_session.query(Recording).filter_by(id=keep_id).first()
        assert kept_recording is not None
        assert kept_recording.title == "Recording To Keep"

        kept_transcript = db_session.query(Transcript).filter_by(recording_id=keep_id).first()
        assert kept_transcript is not None
        assert kept_transcript.full_text == "Transcript to keep"

        kept_chunks = db_session.query(TranscriptChunk).filter_by(recording_id=keep_id).all()
        assert len(kept_chunks) == 2

    def test_session_state_after_successful_delete(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Verify session state is clean after successful deletion."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        delete_recording(db_session, recording_id)

        # Session should not have pending changes
        assert not db_session.new
        assert not db_session.dirty
        assert not db_session.deleted

    def test_database_integrity_with_multiple_chunks(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test deletion works correctly with many transcript chunks."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Create many chunks (simulating a long recording)
        mock_embedding = [0.2] * 1024
        num_chunks = 100
        for i in range(num_chunks):
            chunk = TranscriptChunk(
                recording_id=recording_id,
                chunk_index=i,
                content=f"Long recording chunk content number {i} with some text",
                speaker=f"SPEAKER_{i % 4:02d}",
                embedding=mock_embedding,
            )
            db_session.add(chunk)
        db_session.commit()

        # Verify all chunks were created
        chunks_count_before = (
            db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).count()
        )
        assert chunks_count_before == num_chunks

        result = delete_recording(db_session, recording_id)

        assert result is True

        # Verify all chunks are gone
        chunks_count_after = (
            db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).count()
        )
        assert chunks_count_after == 0


class TestDeleteRecordingErrorHandling:
    """Tests for error handling during recording deletion."""

    def test_delete_with_invalid_uuid_format(self, db_session: Session) -> None:
        """Test that invalid UUID format raises ValueError."""
        import pytest

        from src.services.recording import delete_recording

        invalid_id = "not-a-valid-uuid"

        with pytest.raises(ValueError) as exc_info:
            delete_recording(db_session, invalid_id)

        assert "not found" in str(exc_info.value).lower()

    def test_delete_returns_correct_type(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that delete_recording returns a boolean."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        result = delete_recording(db_session, recording_id)

        assert isinstance(result, bool)
        assert result is True

    def test_delete_nonexistent_raises_value_error(self, db_session: Session) -> None:
        """Test that deleting a non-existent recording raises ValueError."""
        import pytest

        from src.services.recording import delete_recording

        non_existent_id = str(uuid4())

        with pytest.raises(ValueError) as exc_info:
            delete_recording(db_session, non_existent_id)

        assert "not found" in str(exc_info.value).lower()


class TestDeleteRecordingChunksExplicit:
    """Tests verifying explicit chunk deletion before cascade."""

    def test_delete_recording_calls_delete_recording_chunks(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that delete_recording explicitly calls delete_recording_chunks."""
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Create some chunks
        mock_embedding = [0.1] * 1024
        for i in range(3):
            chunk = TranscriptChunk(
                recording_id=recording_id,
                chunk_index=i,
                content=f"Explicit delete test chunk {i}",
                embedding=mock_embedding,
            )
            db_session.add(chunk)
        db_session.commit()

        with patch("src.services.recording.delete_recording_chunks") as mock_delete_chunks:
            mock_delete_chunks.return_value = 3
            delete_recording(db_session, recording_id)

            mock_delete_chunks.assert_called_once_with(db_session, recording_id)

    def test_chunks_deleted_before_recording(
        self, db_session: Session, sample_recording: Recording
    ) -> None:
        """Test that chunks are deleted before the recording itself.

        This is important for ensuring proper cleanup order, even though
        FK cascade would handle it. Explicit deletion allows for better
        error handling and logging.
        """
        from src.services.recording import delete_recording

        recording_id = sample_recording.id

        # Create chunks
        mock_embedding = [0.1] * 1024
        chunk = TranscriptChunk(
            recording_id=recording_id,
            chunk_index=0,
            content="Order test chunk",
            embedding=mock_embedding,
        )
        db_session.add(chunk)
        db_session.commit()

        # Track call order
        call_order = []

        def track_delete_chunks(session, rec_id):
            call_order.append("delete_chunks")
            # Actually delete the chunks
            from src.services.embedding import delete_recording_chunks

            return delete_recording_chunks(session, rec_id)

        def track_session_delete(obj):
            if isinstance(obj, Recording):
                call_order.append("delete_recording")
            original_delete(obj)

        original_delete = db_session.delete

        with (
            patch(
                "src.services.recording.delete_recording_chunks",
                side_effect=track_delete_chunks,
            ),
            patch.object(db_session, "delete", side_effect=track_session_delete),
        ):
            delete_recording(db_session, recording_id)

        # Verify chunks were deleted before recording
        assert "delete_chunks" in call_order
        assert "delete_recording" in call_order
        assert call_order.index("delete_chunks") < call_order.index("delete_recording")
