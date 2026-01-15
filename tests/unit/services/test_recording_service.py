"""Unit tests for recording service speaker embedding functions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.models import ProcessingStatus, Recording
from src.models.speaker_embedding import SpeakerEmbedding
from src.services.recording import (
    delete_speaker_embeddings,
    save_speaker_embeddings,
)


class TestSaveSpearkerEmbeddings:
    """Tests for save_speaker_embeddings function."""

    def test_save_embeddings_creates_records(self, db_session: Session):
        """save_speaker_embeddings should create SpeakerEmbedding records."""
        # Create a recording first
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording",
            original_filename="test.wav",
            volume_path="/Volumes/test/test.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Save embeddings
        embeddings = {
            "Interviewer": [0.1] * 512,
            "Respondent": [0.2] * 512,
        }

        result = save_speaker_embeddings(db_session, recording.id, embeddings)

        # Verify records were created
        assert len(result) == 2
        assert all(isinstance(r, SpeakerEmbedding) for r in result)

        # Verify data is correct
        labels = {r.speaker_label for r in result}
        assert labels == {"Interviewer", "Respondent"}

        for r in result:
            assert r.recording_id == recording.id
            assert len(r.embedding_vector) == 512

    def test_save_embeddings_replaces_existing(self, db_session: Session):
        """save_speaker_embeddings should replace existing embeddings."""
        # Create a recording
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording",
            original_filename="test.wav",
            volume_path="/Volumes/test/test.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Save initial embeddings
        initial_embeddings = {
            "Interviewer": [0.1] * 512,
        }
        save_speaker_embeddings(db_session, recording.id, initial_embeddings)

        # Verify initial count
        count = db_session.query(SpeakerEmbedding).filter_by(
            recording_id=recording.id
        ).count()
        assert count == 1

        # Save new embeddings (should replace)
        new_embeddings = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.6] * 512,
            "Respondent2": [0.7] * 512,
        }
        result = save_speaker_embeddings(db_session, recording.id, new_embeddings)

        # Verify new count - should be 3, not 4
        assert len(result) == 3
        final_count = db_session.query(SpeakerEmbedding).filter_by(
            recording_id=recording.id
        ).count()
        assert final_count == 3

    def test_save_embeddings_with_empty_dict(self, db_session: Session):
        """save_speaker_embeddings with empty dict should create no records."""
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording",
            original_filename="test.wav",
            volume_path="/Volumes/test/test.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        result = save_speaker_embeddings(db_session, recording.id, {})

        assert result == []

    def test_save_embeddings_invalid_recording_id(self, db_session: Session):
        """save_speaker_embeddings with invalid recording_id should raise."""
        embeddings = {"Interviewer": [0.1] * 512}

        with pytest.raises(ValueError, match="Recording not found"):
            save_speaker_embeddings(db_session, "nonexistent-id", embeddings)


class TestDeleteSpeakerEmbeddings:
    """Tests for delete_speaker_embeddings function."""

    def test_delete_embeddings_removes_all(self, db_session: Session):
        """delete_speaker_embeddings should remove all embeddings for recording."""
        # Create a recording with embeddings
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording",
            original_filename="test.wav",
            volume_path="/Volumes/test/test.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Add embeddings
        for i, label in enumerate(["Interviewer", "Respondent", "Respondent2"]):
            embedding = SpeakerEmbedding(
                id=str(uuid4()),
                recording_id=recording.id,
                speaker_label=label,
                embedding_vector=[0.1 * i] * 512,
            )
            db_session.add(embedding)
        db_session.commit()

        # Verify embeddings exist
        count_before = db_session.query(SpeakerEmbedding).filter_by(
            recording_id=recording.id
        ).count()
        assert count_before == 3

        # Delete embeddings
        deleted_count = delete_speaker_embeddings(db_session, recording.id)

        # Verify deletion
        assert deleted_count == 3
        count_after = db_session.query(SpeakerEmbedding).filter_by(
            recording_id=recording.id
        ).count()
        assert count_after == 0

    def test_delete_embeddings_returns_zero_when_none_exist(self, db_session: Session):
        """delete_speaker_embeddings should return 0 when no embeddings exist."""
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording",
            original_filename="test.wav",
            volume_path="/Volumes/test/test.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        deleted_count = delete_speaker_embeddings(db_session, recording.id)

        assert deleted_count == 0

    def test_delete_embeddings_only_affects_target_recording(self, db_session: Session):
        """delete_speaker_embeddings should not affect other recordings."""
        # Create two recordings
        recording1 = Recording(
            id=str(uuid4()),
            title="Recording 1",
            original_filename="test1.wav",
            volume_path="/Volumes/test/test1.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        recording2 = Recording(
            id=str(uuid4()),
            title="Recording 2",
            original_filename="test2.wav",
            volume_path="/Volumes/test/test2.wav",
            duration_seconds=60.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add_all([recording1, recording2])
        db_session.commit()

        # Add embeddings to both recordings
        for recording in [recording1, recording2]:
            embedding = SpeakerEmbedding(
                id=str(uuid4()),
                recording_id=recording.id,
                speaker_label="Interviewer",
                embedding_vector=[0.1] * 512,
            )
            db_session.add(embedding)
        db_session.commit()

        # Delete embeddings from recording1 only
        delete_speaker_embeddings(db_session, recording1.id)

        # Verify recording1 embeddings are deleted
        count1 = db_session.query(SpeakerEmbedding).filter_by(
            recording_id=recording1.id
        ).count()
        assert count1 == 0

        # Verify recording2 embeddings are intact
        count2 = db_session.query(SpeakerEmbedding).filter_by(
            recording_id=recording2.id
        ).count()
        assert count2 == 1
