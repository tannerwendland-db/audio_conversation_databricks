"""Integration tests for speaker embedding storage and cascade delete behavior."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from src.models import ProcessingStatus, Recording
from src.models.speaker_embedding import SpeakerEmbedding


class TestSpeakerEmbeddingCascadeDelete:
    """Tests for speaker embedding cascade delete behavior."""

    def test_cascade_delete_removes_embeddings(self, db_session: Session):
        """Test that deleting a recording cascades to delete its speaker embeddings."""
        # Create a recording
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording for Cascade Delete",
            original_filename="test_cascade.wav",
            volume_path="/Volumes/test/cascade_test.wav",
            duration_seconds=120.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Create speaker embeddings for the recording
        # Note: Using list representation since SQLite doesn't have pgvector
        embedding1 = SpeakerEmbedding(
            id=str(uuid4()),
            recording_id=recording.id,
            speaker_label="Interviewer",
            embedding_vector=[0.1] * 512,
        )
        embedding2 = SpeakerEmbedding(
            id=str(uuid4()),
            recording_id=recording.id,
            speaker_label="Respondent",
            embedding_vector=[0.2] * 512,
        )
        db_session.add_all([embedding1, embedding2])
        db_session.commit()

        # Verify embeddings were created
        embeddings = db_session.query(SpeakerEmbedding).filter_by(recording_id=recording.id).all()
        assert len(embeddings) == 2

        # Delete the recording
        db_session.delete(recording)
        db_session.commit()

        # Verify embeddings were cascade deleted
        remaining_embeddings = (
            db_session.query(SpeakerEmbedding).filter_by(recording_id=recording.id).all()
        )
        assert len(remaining_embeddings) == 0

    def test_save_embeddings_creates_records(self, db_session: Session):
        """Test that embeddings can be persisted to the speaker_embeddings table."""
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

        # Create embeddings
        embeddings_data = {
            "Interviewer": [0.1] * 512,
            "Respondent": [0.3] * 512,
        }

        for label, vector in embeddings_data.items():
            embedding = SpeakerEmbedding(
                id=str(uuid4()),
                recording_id=recording.id,
                speaker_label=label,
                embedding_vector=vector,
            )
            db_session.add(embedding)
        db_session.commit()

        # Verify embeddings were saved
        saved_embeddings = (
            db_session.query(SpeakerEmbedding).filter_by(recording_id=recording.id).all()
        )
        assert len(saved_embeddings) == 2

        labels = {e.speaker_label for e in saved_embeddings}
        assert labels == {"Interviewer", "Respondent"}

        for embedding in saved_embeddings:
            assert len(embedding.embedding_vector) == 512

    def test_save_embeddings_replaces_existing(self, db_session: Session):
        """Test that re-saving embeddings replaces old ones."""
        # Create a recording
        recording = Recording(
            id=str(uuid4()),
            title="Test Recording for Replace",
            original_filename="test_replace.wav",
            volume_path="/Volumes/test/test_replace.wav",
            duration_seconds=90.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Create initial embeddings
        initial_embedding = SpeakerEmbedding(
            id=str(uuid4()),
            recording_id=recording.id,
            speaker_label="Interviewer",
            embedding_vector=[0.1] * 512,
        )
        db_session.add(initial_embedding)
        db_session.commit()

        # Verify initial embedding
        embeddings = db_session.query(SpeakerEmbedding).filter_by(recording_id=recording.id).all()
        assert len(embeddings) == 1
        assert embeddings[0].speaker_label == "Interviewer"

        # Delete existing embeddings (simulating re-processing)
        db_session.query(SpeakerEmbedding).filter_by(recording_id=recording.id).delete()
        db_session.commit()

        # Save new embeddings
        new_embeddings_data = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.6] * 512,
            "Respondent2": [0.7] * 512,
        }

        for label, vector in new_embeddings_data.items():
            embedding = SpeakerEmbedding(
                id=str(uuid4()),
                recording_id=recording.id,
                speaker_label=label,
                embedding_vector=vector,
            )
            db_session.add(embedding)
        db_session.commit()

        # Verify new embeddings replaced old ones
        final_embeddings = (
            db_session.query(SpeakerEmbedding).filter_by(recording_id=recording.id).all()
        )
        assert len(final_embeddings) == 3

        labels = {e.speaker_label for e in final_embeddings}
        assert labels == {"Interviewer", "Respondent", "Respondent2"}

    def test_recording_relationship_to_speaker_embeddings(self, db_session: Session):
        """Test that Recording.speaker_embeddings relationship works."""
        # Create a recording
        recording = Recording(
            id=str(uuid4()),
            title="Test Relationship Recording",
            original_filename="test_rel.wav",
            volume_path="/Volumes/test/test_rel.wav",
            duration_seconds=45.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Create embeddings
        embedding = SpeakerEmbedding(
            id=str(uuid4()),
            recording_id=recording.id,
            speaker_label="Interviewer",
            embedding_vector=[0.25] * 512,
        )
        db_session.add(embedding)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(recording)

        # Access embeddings through relationship
        assert hasattr(recording, "speaker_embeddings")
        assert len(recording.speaker_embeddings) == 1
        assert recording.speaker_embeddings[0].speaker_label == "Interviewer"

    def test_embedding_relationship_to_recording(self, db_session: Session):
        """Test that SpeakerEmbedding.recording relationship works."""
        # Create a recording
        recording = Recording(
            id=str(uuid4()),
            title="Test Back-Reference Recording",
            original_filename="test_backref.wav",
            volume_path="/Volumes/test/test_backref.wav",
            duration_seconds=30.0,
            processing_status=ProcessingStatus.COMPLETED.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(recording)
        db_session.commit()

        # Create embedding
        embedding = SpeakerEmbedding(
            id=str(uuid4()),
            recording_id=recording.id,
            speaker_label="Respondent",
            embedding_vector=[0.4] * 512,
        )
        db_session.add(embedding)
        db_session.commit()

        # Refresh and check back-reference
        db_session.refresh(embedding)

        assert embedding.recording is not None
        assert embedding.recording.id == recording.id
        assert embedding.recording.title == "Test Back-Reference Recording"
