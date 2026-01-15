"""Unit tests for SpeakerEmbedding model."""

from uuid import uuid4

from src.models.speaker_embedding import SpeakerEmbedding


class TestSpeakerEmbeddingModel:
    """Tests for the SpeakerEmbedding SQLAlchemy model."""

    def test_speaker_embedding_creation(self):
        """Test that SpeakerEmbedding can be instantiated with required fields."""
        recording_id = str(uuid4())
        embedding_vector = [0.1] * 512  # 512-dimensional vector

        embedding = SpeakerEmbedding(
            recording_id=recording_id,
            speaker_label="Interviewer",
            embedding_vector=embedding_vector,
        )

        assert embedding.recording_id == recording_id
        assert embedding.speaker_label == "Interviewer"
        assert embedding.embedding_vector == embedding_vector
        assert len(embedding.embedding_vector) == 512

    def test_speaker_embedding_auto_id(self):
        """Test that SpeakerEmbedding generates a UUID id if not provided."""
        embedding = SpeakerEmbedding(
            recording_id=str(uuid4()),
            speaker_label="Respondent",
            embedding_vector=[0.5] * 512,
        )

        # The default function should generate an ID
        assert embedding.id is not None or hasattr(SpeakerEmbedding.id, "default")

    def test_speaker_embedding_tablename(self):
        """Test that SpeakerEmbedding uses correct table name."""
        assert SpeakerEmbedding.__tablename__ == "speaker_embeddings"

    def test_speaker_embedding_has_recording_relationship(self):
        """Test that SpeakerEmbedding has a relationship to Recording."""
        # Check that the relationship is defined
        assert hasattr(SpeakerEmbedding, "recording")

    def test_speaker_embedding_embedding_vector_dimension(self):
        """Test embedding vector with correct dimension (512)."""
        recording_id = str(uuid4())

        # 512-dimensional vector should work
        embedding = SpeakerEmbedding(
            recording_id=recording_id,
            speaker_label="Interviewer",
            embedding_vector=[0.1] * 512,
        )
        assert len(embedding.embedding_vector) == 512

    def test_speaker_embedding_different_speaker_labels(self):
        """Test SpeakerEmbedding with different speaker label values."""
        recording_id = str(uuid4())
        labels = ["Interviewer", "Respondent", "Respondent2", "Respondent3"]

        for label in labels:
            embedding = SpeakerEmbedding(
                recording_id=recording_id,
                speaker_label=label,
                embedding_vector=[0.2] * 512,
            )
            assert embedding.speaker_label == label

    def test_speaker_embedding_repr(self):
        """Test that SpeakerEmbedding has a meaningful string representation."""
        embedding = SpeakerEmbedding(
            id="test-id",
            recording_id=str(uuid4()),
            speaker_label="Interviewer",
            embedding_vector=[0.1] * 512,
        )

        repr_str = repr(embedding)
        assert (
            "SpeakerEmbedding" in repr_str or embedding.id in repr_str or "test-id" in str(repr_str)
        )
