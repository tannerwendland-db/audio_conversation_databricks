"""Integration tests for vector store operations.

Tests for the embedding service functions that interact with the
transcript_chunks table for storing and retrieving document embeddings.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.models import Recording, TranscriptChunk


class TestStoreTranscriptChunksIntegration:
    """Integration tests for store_transcript_chunks() function."""

    @patch("src.services.embedding._get_embeddings_model")
    def test_stores_chunks_in_database(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that chunks are stored in the database with embeddings."""
        from src.services.embedding import store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [
            [0.1] * 1024,
            [0.2] * 1024,
        ]
        mock_get_embeddings.return_value = mock_embeddings_instance

        result = store_transcript_chunks(
            session=db_session,
            recording_id=sample_recording.id,
            chunks=["First chunk", "Second chunk"],
            title=sample_recording.title,
        )

        assert result == 2

        # Verify chunks in database
        stored = (
            db_session.query(TranscriptChunk)
            .filter_by(recording_id=sample_recording.id)
            .order_by(TranscriptChunk.chunk_index)
            .all()
        )
        assert len(stored) == 2
        assert stored[0].content == "First chunk"
        assert stored[0].chunk_index == 0
        assert stored[1].content == "Second chunk"
        assert stored[1].chunk_index == 1

    @patch("src.services.embedding._get_embeddings_model")
    def test_stores_speaker_metadata(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that speaker is extracted and stored."""
        from src.services.embedding import store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [
            [0.1] * 1024,
            [0.2] * 1024,
        ]
        mock_get_embeddings.return_value = mock_embeddings_instance

        chunks = [
            "[Interviewer 0:00:00] Hello there",
            "[Respondent 0:00:10] Hi, thanks for having me",
        ]
        store_transcript_chunks(
            session=db_session,
            recording_id=sample_recording.id,
            chunks=chunks,
            title=sample_recording.title,
        )

        stored = (
            db_session.query(TranscriptChunk)
            .filter_by(recording_id=sample_recording.id)
            .order_by(TranscriptChunk.chunk_index)
            .all()
        )
        assert stored[0].speaker == "Interviewer"
        assert stored[1].speaker == "Respondent"

    @patch("src.services.embedding._get_embeddings_model")
    def test_chunks_linked_to_recording(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that chunks are properly linked to the recording."""
        from src.services.embedding import store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [[0.1] * 1024]
        mock_get_embeddings.return_value = mock_embeddings_instance

        store_transcript_chunks(
            session=db_session,
            recording_id=sample_recording.id,
            chunks=["Test content"],
            title=sample_recording.title,
        )

        # Refresh recording to load relationship
        db_session.refresh(sample_recording)

        assert len(sample_recording.transcript_chunks) == 1
        assert sample_recording.transcript_chunks[0].content == "Test content"


class TestCascadeDeleteIntegration:
    """Integration tests for CASCADE delete behavior."""

    @patch("src.services.embedding._get_embeddings_model")
    def test_deleting_recording_cascades_to_chunks(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that deleting a recording also deletes its chunks."""
        from src.services.embedding import store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [
            [0.1] * 1024,
            [0.2] * 1024,
            [0.3] * 1024,
        ]
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Store some chunks
        store_transcript_chunks(
            session=db_session,
            recording_id=sample_recording.id,
            chunks=["Chunk 1", "Chunk 2", "Chunk 3"],
            title=sample_recording.title,
        )

        # Verify chunks exist
        recording_id = sample_recording.id
        chunks_before = (
            db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).count()
        )
        assert chunks_before == 3

        # Delete the recording
        db_session.delete(sample_recording)
        db_session.commit()

        # Verify chunks are also deleted
        chunks_after = (
            db_session.query(TranscriptChunk).filter_by(recording_id=recording_id).count()
        )
        assert chunks_after == 0


class TestDeleteRecordingChunksIntegration:
    """Integration tests for delete_recording_chunks() function."""

    @patch("src.services.embedding._get_embeddings_model")
    def test_deletes_all_chunks_for_recording(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that all chunks for a recording are deleted."""
        from src.services.embedding import (
            delete_recording_chunks,
            store_transcript_chunks,
        )

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [
            [0.1] * 1024,
            [0.2] * 1024,
        ]
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Store chunks
        store_transcript_chunks(
            session=db_session,
            recording_id=sample_recording.id,
            chunks=["Chunk 1", "Chunk 2"],
            title=sample_recording.title,
        )

        # Verify chunks exist
        assert (
            db_session.query(TranscriptChunk).filter_by(recording_id=sample_recording.id).count()
            == 2
        )

        # Delete chunks
        deleted_count = delete_recording_chunks(db_session, sample_recording.id)

        assert deleted_count == 2
        assert (
            db_session.query(TranscriptChunk).filter_by(recording_id=sample_recording.id).count()
            == 0
        )

    def test_returns_zero_for_nonexistent_recording(
        self,
        db_session: Session,
    ) -> None:
        """Test that zero is returned when no chunks exist."""
        from src.services.embedding import delete_recording_chunks

        result = delete_recording_chunks(db_session, "nonexistent-recording-id")

        assert result == 0


class TestEmbeddingModelConfiguration:
    """Tests for embedding model configuration."""

    @patch("src.services.embedding.DatabricksEmbeddings")
    def test_uses_correct_embedding_endpoint(
        self,
        mock_embeddings_class: MagicMock,
        test_settings,
    ) -> None:
        """Test that _get_embeddings_model uses the correct endpoint."""
        from src.services.embedding import _get_embeddings_model

        mock_embeddings_instance = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings_instance

        result = _get_embeddings_model()

        mock_embeddings_class.assert_called_once_with(endpoint=test_settings.EMBEDDING_ENDPOINT)
        assert result is mock_embeddings_instance
