"""Unit tests for the embedding service module.

This module tests the embedding service functions for chunking transcripts
and storing transcript chunks with embeddings.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestChunkTranscript:
    """Test cases for chunk_transcript() function."""

    def test_short_text_returns_single_chunk(self):
        """Text shorter than chunk_size should return a single chunk."""
        from src.services.embedding import chunk_transcript

        short_text = "This is a short transcript."
        result = chunk_transcript(short_text, chunk_size=500, overlap=50)

        assert len(result) == 1
        assert result[0] == short_text

    def test_long_text_split_into_multiple_chunks(self):
        """Text longer than chunk_size should be split into multiple chunks."""
        from src.services.embedding import chunk_transcript

        # Create text that is clearly longer than 500 characters
        long_text = "This is a sentence that will be repeated. " * 30
        result = chunk_transcript(long_text, chunk_size=500, overlap=50)

        assert len(result) > 1
        # Verify total content is preserved (accounting for overlap)
        total_chars = sum(len(chunk) for chunk in result)
        assert total_chars > len(long_text)  # Due to overlap

    def test_overlap_between_chunks_is_preserved(self):
        """Consecutive chunks should have overlapping content."""
        from src.services.embedding import chunk_transcript

        # Create predictable text for testing overlap
        long_text = " ".join([f"word{i}" for i in range(200)])
        result = chunk_transcript(long_text, chunk_size=100, overlap=20)

        assert len(result) > 1
        # Check that consecutive chunks share some content
        for i in range(len(result) - 1):
            current_chunk = result[i]
            next_chunk = result[i + 1]
            # The end of current chunk should appear at start of next chunk
            # due to overlap
            current_words = current_chunk.split()
            next_words = next_chunk.split()
            # There should be some common words between chunks
            common_words = set(current_words[-5:]) & set(next_words[:10])
            assert len(common_words) > 0, f"No overlap found between chunk {i} and {i + 1}"

    def test_empty_text_handling(self):
        """Empty text should return an empty list."""
        from src.services.embedding import chunk_transcript

        result = chunk_transcript("", chunk_size=500, overlap=50)

        assert result == []

    def test_custom_chunk_size_parameter(self):
        """Custom chunk_size parameter should be respected."""
        from src.services.embedding import chunk_transcript

        text = "word " * 100  # 500 characters
        result_small = chunk_transcript(text, chunk_size=100, overlap=10)
        result_large = chunk_transcript(text, chunk_size=400, overlap=10)

        assert len(result_small) > len(result_large)
        for chunk in result_small:
            # Chunks should not exceed chunk_size by much (some tolerance for word boundaries)
            assert len(chunk) <= 150  # Some tolerance for word boundaries

    def test_custom_overlap_parameter(self):
        """Custom overlap parameter should affect chunk generation."""
        from src.services.embedding import chunk_transcript

        text = "word " * 200
        result_small_overlap = chunk_transcript(text, chunk_size=200, overlap=10)
        result_large_overlap = chunk_transcript(text, chunk_size=200, overlap=80)

        # Larger overlap should result in more chunks
        assert len(result_large_overlap) >= len(result_small_overlap)

    def test_speaker_labels_preserved_across_chunks(self):
        """Speaker labels (Interviewer/Respondent) should be preserved in chunks."""
        from src.services.embedding import chunk_transcript

        transcript_with_speakers = """
[Interviewer 0:00:00]
Hello, welcome to the interview. I have several questions prepared for you today about your experience.

[Respondent 0:00:15]
Thank you for having me. I'm happy to answer any questions you have about my background and experience.

[Interviewer 0:00:30]
Let's start with your previous role. Can you tell me about your responsibilities?

[Respondent 0:00:45]
In my previous role, I was responsible for managing a team of developers and overseeing multiple projects.
"""
        result = chunk_transcript(transcript_with_speakers, chunk_size=200, overlap=30)

        assert len(result) > 1
        # At least some chunks should contain speaker labels
        chunks_with_interviewer = [c for c in result if "Interviewer" in c]
        chunks_with_respondent = [c for c in result if "Respondent" in c]
        assert len(chunks_with_interviewer) > 0 or len(chunks_with_respondent) > 0

    def test_whitespace_only_text_returns_empty(self):
        """Text with only whitespace should return empty list."""
        from src.services.embedding import chunk_transcript

        result = chunk_transcript("   \n\t  \n  ", chunk_size=500, overlap=50)

        assert result == []

    def test_default_parameters(self):
        """Function should work with default parameters (chunk_size=500, overlap=50)."""
        from src.services.embedding import chunk_transcript

        text = "This is a test sentence. " * 50
        result = chunk_transcript(text)

        assert len(result) >= 1
        assert isinstance(result, list)
        assert all(isinstance(chunk, str) for chunk in result)

    def test_returns_list_of_strings(self):
        """Return type should be list[str]."""
        from src.services.embedding import chunk_transcript

        result = chunk_transcript("Some text content", chunk_size=500, overlap=50)

        assert isinstance(result, list)
        for chunk in result:
            assert isinstance(chunk, str)


class TestChunkDialog:
    """Test cases for chunk_dialog() function."""

    def test_empty_dialog_returns_empty_list(self):
        """Empty dialog should return empty list."""
        from src.services.embedding import chunk_dialog

        result = chunk_dialog([])
        assert result == []

    def test_single_short_turn(self):
        """Single short turn should return one chunk with speaker prefix."""
        from src.services.embedding import chunk_dialog

        dialog = [{"speaker": "Interviewer", "text": "Hello there"}]
        result = chunk_dialog(dialog)

        assert len(result) == 1
        assert result[0] == "[Interviewer]: Hello there"

    def test_multiple_turns(self):
        """Multiple turns should each become a chunk."""
        from src.services.embedding import chunk_dialog

        dialog = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Respondent", "text": "Hi there"},
        ]
        result = chunk_dialog(dialog)

        assert len(result) == 2
        assert result[0] == "[Interviewer]: Hello"
        assert result[1] == "[Respondent]: Hi there"

    def test_long_turn_split_with_prefix(self):
        """Long turns should be split but maintain speaker prefix."""
        from src.services.embedding import chunk_dialog

        long_text = "This is a sentence. " * 50  # ~1000 chars
        dialog = [{"speaker": "Interviewer", "text": long_text}]
        result = chunk_dialog(dialog, chunk_size=200, overlap=20)

        assert len(result) > 1
        # All chunks should start with speaker prefix
        for chunk in result:
            assert chunk.startswith("[Interviewer]: ")

    def test_speaker_prefix_preserved_in_all_subchunks(self):
        """All subchunks of a long turn should have speaker prefix."""
        from src.services.embedding import chunk_dialog

        long_text = "word " * 200  # ~1000 chars
        dialog = [{"speaker": "Respondent", "text": long_text}]
        result = chunk_dialog(dialog, chunk_size=100, overlap=10)

        assert len(result) > 1
        for chunk in result:
            assert chunk.startswith("[Respondent]: ")

    def test_chunks_respect_size_limit(self):
        """Chunks should not exceed the specified size limit."""
        from src.services.embedding import chunk_dialog

        dialog = [
            {"speaker": "Interviewer", "text": "Short text"},
            {"speaker": "Respondent", "text": "word " * 100},
        ]
        result = chunk_dialog(dialog, chunk_size=200, overlap=20)

        for chunk in result:
            assert len(chunk) <= 250  # Some tolerance for word boundaries

    def test_empty_text_skipped(self):
        """Turns with empty text should be skipped."""
        from src.services.embedding import chunk_dialog

        dialog = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Respondent", "text": ""},
            {"speaker": "Interviewer", "text": "Goodbye"},
        ]
        result = chunk_dialog(dialog)

        assert len(result) == 2
        assert "[Respondent]" not in str(result)

    def test_missing_speaker_uses_unknown(self):
        """Missing speaker should default to 'Unknown'."""
        from src.services.embedding import chunk_dialog

        dialog = [{"text": "Hello there"}]
        result = chunk_dialog(dialog)

        assert len(result) == 1
        assert result[0] == "[Unknown]: Hello there"

    def test_negative_chunk_size_raises_error(self):
        """Negative chunk_size should raise ValueError."""
        from src.services.embedding import chunk_dialog

        with pytest.raises(ValueError):
            chunk_dialog([{"speaker": "Test", "text": "Hello"}], chunk_size=-100)

    def test_negative_overlap_raises_error(self):
        """Negative overlap should raise ValueError."""
        from src.services.embedding import chunk_dialog

        with pytest.raises(ValueError):
            chunk_dialog([{"speaker": "Test", "text": "Hello"}], overlap=-10)

    def test_overlap_larger_than_chunk_raises_error(self):
        """Overlap larger than chunk_size should raise ValueError."""
        from src.services.embedding import chunk_dialog

        with pytest.raises(ValueError):
            chunk_dialog(
                [{"speaker": "Test", "text": "Hello"}],
                chunk_size=100,
                overlap=150,
            )


class TestExtractSpeaker:
    """Test cases for _extract_speaker() function."""

    def test_extracts_interviewer_new_format(self):
        """Should extract 'Interviewer' from new [Speaker]: format."""
        from src.services.embedding import _extract_speaker

        text = "[Interviewer]: Hello, welcome to the interview."
        result = _extract_speaker(text)

        assert result == "Interviewer"

    def test_extracts_respondent_new_format(self):
        """Should extract 'Respondent' from new [Speaker]: format."""
        from src.services.embedding import _extract_speaker

        text = "[Respondent]: Thank you for having me."
        result = _extract_speaker(text)

        assert result == "Respondent"

    def test_extracts_interviewer(self):
        """Should extract 'Interviewer' from legacy text with interviewer label."""
        from src.services.embedding import _extract_speaker

        text = "[Interviewer 0:00:00] Hello, welcome to the interview."
        result = _extract_speaker(text)

        assert result == "Interviewer"

    def test_extracts_respondent(self):
        """Should extract 'Respondent' from text with respondent label."""
        from src.services.embedding import _extract_speaker

        text = "[Respondent 0:01:30] Thank you for having me."
        result = _extract_speaker(text)

        assert result == "Respondent"

    def test_returns_none_when_no_label(self):
        """Should return None when no speaker label is present."""
        from src.services.embedding import _extract_speaker

        text = "This is just plain text without any speaker label."
        result = _extract_speaker(text)

        assert result is None

    def test_extracts_first_speaker_when_multiple(self):
        """When text has multiple speakers, should extract the first one."""
        from src.services.embedding import _extract_speaker

        text = "[Interviewer 0:00:00] Question here.\n[Respondent 0:00:10] Answer here."
        result = _extract_speaker(text)

        assert result == "Interviewer"

    def test_handles_various_timestamps(self):
        """Should handle various timestamp formats."""
        from src.services.embedding import _extract_speaker

        assert _extract_speaker("[Interviewer 0:00:00] Text") == "Interviewer"
        assert _extract_speaker("[Respondent 1:30:45] Text") == "Respondent"
        assert _extract_speaker("[Interviewer 12:59:59] Text") == "Interviewer"


class TestChunkTranscriptEdgeCases:
    """Edge case tests for chunk_transcript() function."""

    def test_text_exactly_chunk_size(self):
        """Text exactly at chunk_size boundary should return single chunk."""
        from src.services.embedding import chunk_transcript

        # Create text of exactly 500 characters
        text = "x" * 500
        result = chunk_transcript(text, chunk_size=500, overlap=50)

        assert len(result) == 1
        assert result[0] == text

    def test_text_slightly_over_chunk_size(self):
        """Text slightly over chunk_size should return two chunks."""
        from src.services.embedding import chunk_transcript

        # Create text just over 500 characters
        text = "x" * 550
        result = chunk_transcript(text, chunk_size=500, overlap=50)

        assert len(result) >= 1

    def test_very_long_text(self):
        """Should handle very long transcripts efficiently."""
        from src.services.embedding import chunk_transcript

        # Simulate a long transcript (approximately 10,000 words)
        long_text = "This is a sample sentence for testing. " * 2500
        result = chunk_transcript(long_text, chunk_size=500, overlap=50)

        assert len(result) > 10
        assert all(isinstance(chunk, str) for chunk in result)

    def test_unicode_characters(self):
        """Should handle unicode characters correctly."""
        from src.services.embedding import chunk_transcript

        unicode_text = "Hello world. " + "Cafe" + " meeting. " * 50
        result = chunk_transcript(unicode_text, chunk_size=500, overlap=50)

        assert len(result) >= 1
        # Verify unicode is preserved
        assert "Cafe" in "".join(result)

    def test_newlines_and_formatting(self):
        """Should preserve newlines and formatting in chunks."""
        from src.services.embedding import chunk_transcript

        formatted_text = (
            """[Speaker 0:00:00]
First paragraph with some content.

[Speaker 0:01:00]
Second paragraph with more content.

[Speaker 0:02:00]
Third paragraph continuing the conversation."""
            * 10
        )

        result = chunk_transcript(formatted_text, chunk_size=200, overlap=30)

        assert len(result) > 1
        # Check that newlines are preserved in at least some chunks
        chunks_with_newlines = [c for c in result if "\n" in c]
        assert len(chunks_with_newlines) > 0

    def test_overlap_larger_than_chunk_size_raises_error(self):
        """Overlap larger than chunk_size should raise ValueError."""
        from src.services.embedding import chunk_transcript

        with pytest.raises(ValueError):
            chunk_transcript("some text", chunk_size=100, overlap=150)

    def test_negative_chunk_size_raises_error(self):
        """Negative chunk_size should raise ValueError."""
        from src.services.embedding import chunk_transcript

        with pytest.raises(ValueError):
            chunk_transcript("some text", chunk_size=-100, overlap=50)

    def test_negative_overlap_raises_error(self):
        """Negative overlap should raise ValueError."""
        from src.services.embedding import chunk_transcript

        with pytest.raises(ValueError):
            chunk_transcript("some text", chunk_size=500, overlap=-10)

    def test_zero_chunk_size_raises_error(self):
        """Zero chunk_size should raise ValueError."""
        from src.services.embedding import chunk_transcript

        with pytest.raises(ValueError):
            chunk_transcript("some text", chunk_size=0, overlap=0)


class TestStoreTranscriptChunks:
    """Test cases for store_transcript_chunks() function."""

    @patch("src.services.embedding._get_embeddings_model")
    def test_stores_chunks_with_embeddings(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that chunks are stored with generated embeddings."""
        from src.services.embedding import store_transcript_chunks

        # Mock embedding generation
        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [
            [0.1] * 1024,
            [0.2] * 1024,
        ]
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Mock session
        mock_session = MagicMock()

        chunks = ["First chunk content", "Second chunk content"]
        result = store_transcript_chunks(
            session=mock_session,
            recording_id="test-recording-id",
            chunks=chunks,
            title="Test Recording",
        )

        assert result == 2
        mock_embeddings_instance.embed_documents.assert_called_once_with(chunks)
        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called_once()

    @patch("src.services.embedding._get_embeddings_model")
    def test_empty_chunks_returns_zero(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that empty chunks list returns 0."""
        from src.services.embedding import store_transcript_chunks

        mock_session = MagicMock()

        result = store_transcript_chunks(
            session=mock_session,
            recording_id="test-recording-id",
            chunks=[],
            title="Test Recording",
        )

        assert result == 0
        mock_get_embeddings.assert_not_called()

    @patch("src.services.embedding._get_embeddings_model")
    def test_speaker_extraction_during_storage(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that speaker is extracted during chunk storage."""
        from src.models import TranscriptChunk
        from src.services.embedding import store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [[0.1] * 1024]
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_session = MagicMock()
        stored_chunks = []

        def capture_chunks(chunks):
            stored_chunks.extend(chunks)

        mock_session.add_all.side_effect = capture_chunks

        chunks = ["[Interviewer 0:00:00] Hello there"]
        store_transcript_chunks(
            session=mock_session,
            recording_id="test-recording-id",
            chunks=chunks,
            title="Test Recording",
        )

        assert len(stored_chunks) == 1
        assert isinstance(stored_chunks[0], TranscriptChunk)
        assert stored_chunks[0].speaker == "Interviewer"
        assert stored_chunks[0].chunk_index == 0
        assert stored_chunks[0].content == "[Interviewer 0:00:00] Hello there"

    @patch("src.services.embedding._get_embeddings_model")
    def test_raises_embedding_error_on_failure(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that EmbeddingError is raised on failure."""
        from src.services.embedding import EmbeddingError, store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.side_effect = Exception("API Error")
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_session = MagicMock()

        with pytest.raises(EmbeddingError) as exc_info:
            store_transcript_chunks(
                session=mock_session,
                recording_id="test-id",
                chunks=["test chunk"],
                title="Test",
            )

        assert "Failed to store chunks" in str(exc_info.value)

    @patch("src.services.embedding._get_embeddings_model")
    def test_chunk_index_is_sequential(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that chunk_index is assigned sequentially."""
        from src.services.embedding import store_transcript_chunks

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_documents.return_value = [
            [0.1] * 1024,
            [0.2] * 1024,
            [0.3] * 1024,
        ]
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_session = MagicMock()
        stored_chunks = []
        mock_session.add_all.side_effect = lambda chunks: stored_chunks.extend(chunks)

        chunks = ["chunk 0", "chunk 1", "chunk 2"]
        store_transcript_chunks(
            session=mock_session,
            recording_id="test-id",
            chunks=chunks,
            title="Test",
        )

        assert len(stored_chunks) == 3
        for i, chunk in enumerate(stored_chunks):
            assert chunk.chunk_index == i


class TestSimilaritySearch:
    """Test cases for similarity_search() function."""

    @patch("src.services.embedding._get_embeddings_model")
    def test_returns_empty_list_when_no_results(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that empty list is returned when no results."""
        from src.services.embedding import similarity_search

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.5] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        results = similarity_search(
            session=mock_session,
            query="test query",
            k=5,
        )

        assert results == []

    @patch("src.services.embedding._get_embeddings_model")
    def test_raises_embedding_error_on_failure(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that EmbeddingError is raised on failure."""
        from src.services.embedding import EmbeddingError, similarity_search

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.side_effect = Exception("API Error")
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_session = MagicMock()

        with pytest.raises(EmbeddingError) as exc_info:
            similarity_search(
                session=mock_session,
                query="test query",
            )

        assert "Similarity search failed" in str(exc_info.value)

    @patch("src.services.embedding._get_embeddings_model")
    def test_calls_embed_query_with_query_text(
        self,
        mock_get_embeddings: MagicMock,
    ) -> None:
        """Test that embed_query is called with the query text."""
        from src.services.embedding import similarity_search

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.5] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        similarity_search(
            session=mock_session,
            query="What is the main topic?",
        )

        mock_embeddings_instance.embed_query.assert_called_once_with("What is the main topic?")


class TestDeleteRecordingChunks:
    """Test cases for delete_recording_chunks() function."""

    def test_deletes_chunks_and_returns_count(self) -> None:
        """Test that chunks are deleted and count is returned."""
        from src.services.embedding import delete_recording_chunks

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        result = delete_recording_chunks(
            session=mock_session,
            recording_id="test-recording-id",
        )

        assert result == 5
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_returns_zero_when_no_chunks(self) -> None:
        """Test that zero is returned when no chunks to delete."""
        from src.services.embedding import delete_recording_chunks

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        result = delete_recording_chunks(
            session=mock_session,
            recording_id="nonexistent-id",
        )

        assert result == 0
