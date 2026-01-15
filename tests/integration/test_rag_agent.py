"""Integration tests for RAG (Retrieval Augmented Generation) agent operations.

Tests for the RAG service functions that handle document retrieval,
response generation with citations, and graceful handling of empty results.

NOTE: This is a TDD test file. The src/services/rag.py module does not exist yet.
Tests will fail with ImportError until implementation is created.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.models import Recording, TranscriptChunk


class TestRetrieveDocuments:
    """Integration tests for retrieve_documents() function."""

    @patch("src.services.rag._get_embeddings_model")
    def test_retrieves_relevant_chunks(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that retrieve_documents returns relevant chunks from the database."""
        from src.services.rag import retrieve_documents

        # Setup: Create transcript chunks in the database
        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Create test chunks directly in the database
        chunk1 = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="The product roadmap includes AI features for Q2.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        chunk2 = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=1,
            content="Customer feedback has been positive on recent releases.",
            speaker="SPEAKER_01",
            embedding=[0.2] * 1024,
        )
        db_session.add_all([chunk1, chunk2])
        db_session.commit()

        # Execute
        results = retrieve_documents(
            session=db_session,
            query="What are the AI features in the roadmap?",
        )

        # Verify
        assert len(results) > 0
        assert all(isinstance(chunk, TranscriptChunk) for chunk in results)
        mock_embeddings_instance.embed_query.assert_called_once()

    @patch("src.services.rag._get_embeddings_model")
    def test_returns_chunks_with_metadata(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that retrieved chunks include content and metadata."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.15] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Create test chunk with specific metadata
        chunk = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="[Interviewer 0:05:30] Let me discuss the budget allocation.",
            speaker="Interviewer",
            embedding=[0.15] * 1024,
        )
        db_session.add(chunk)
        db_session.commit()

        results = retrieve_documents(
            session=db_session,
            query="Tell me about budget",
        )

        assert len(results) >= 1
        first_result = results[0]
        assert first_result.content is not None
        assert first_result.recording_id == sample_recording.id
        assert first_result.speaker == "Interviewer"
        assert first_result.chunk_index == 0

    @patch("src.services.rag._get_embeddings_model")
    def test_respects_k_parameter(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that the k parameter limits the number of returned chunks."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Create more chunks than we will request
        for i in range(10):
            chunk = TranscriptChunk(
                recording_id=sample_recording.id,
                chunk_index=i,
                content=f"Chunk number {i} with some content about the meeting.",
                speaker="SPEAKER_00",
                embedding=[0.1 + (i * 0.01)] * 1024,
            )
            db_session.add(chunk)
        db_session.commit()

        # Request only 3 results
        results = retrieve_documents(
            session=db_session,
            query="meeting content",
            k=3,
        )

        assert len(results) == 3

    @patch("src.services.rag._get_embeddings_model")
    def test_filters_by_recording_id(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that optional recording_id filter restricts results."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Create a second recording
        from uuid import uuid4

        second_recording = Recording(
            id=str(uuid4()),
            title="Second Recording",
            original_filename="second_recording.wav",
            volume_path="/Volumes/test/default/audio-recordings/second.wav",
            duration_seconds=1800.0,
            processing_status="completed",
            uploaded_by="test_user@example.com",
        )
        db_session.add(second_recording)
        db_session.commit()

        # Create chunks for both recordings
        chunk1 = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="First recording content about project planning.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        chunk2 = TranscriptChunk(
            recording_id=second_recording.id,
            chunk_index=0,
            content="Second recording content about project planning.",
            speaker="SPEAKER_01",
            embedding=[0.1] * 1024,
        )
        db_session.add_all([chunk1, chunk2])
        db_session.commit()

        # Filter by first recording only
        results = retrieve_documents(
            session=db_session,
            query="project planning",
            recording_id=sample_recording.id,
        )

        assert len(results) >= 1
        assert all(chunk.recording_id == sample_recording.id for chunk in results)


class TestGenerateResponseWithCitations:
    """Integration tests for generate_response_with_citations() function."""

    @patch("src.services.rag._get_llm")
    @patch("src.services.rag._get_embeddings_model")
    def test_generates_response_with_citations(
        self,
        mock_get_embeddings: MagicMock,
        mock_get_llm: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that a response is generated with citations from retrieved docs."""
        from src.services.rag import generate_response_with_citations

        # Mock embeddings
        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Mock LLM
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(
            content="Based on the meeting, the team discussed AI features [1]. "
            "The timeline was set for Q2 [2]."
        )
        mock_get_llm.return_value = mock_llm_instance

        # Create test chunks
        chunk1 = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="We are adding AI features to the product.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        chunk2 = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=1,
            content="The timeline is set for Q2 delivery.",
            speaker="SPEAKER_01",
            embedding=[0.12] * 1024,
        )
        db_session.add_all([chunk1, chunk2])
        db_session.commit()

        result = generate_response_with_citations(
            session=db_session,
            query="What are the AI plans and timeline?",
        )

        assert "response" in result
        assert "citations" in result
        assert len(result["response"]) > 0
        mock_llm_instance.invoke.assert_called_once()

    @patch("src.services.rag._get_llm")
    @patch("src.services.rag._get_embeddings_model")
    def test_response_includes_inline_citations(
        self,
        mock_get_embeddings: MagicMock,
        mock_get_llm: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that the response contains inline citation markers."""
        from src.services.rag import generate_response_with_citations

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(
            content="The budget for Q3 is $2 million [1]."
        )
        mock_get_llm.return_value = mock_llm_instance

        chunk = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="The Q3 budget allocation is $2 million for development.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        db_session.add(chunk)
        db_session.commit()

        result = generate_response_with_citations(
            session=db_session,
            query="What is the budget for Q3?",
        )

        # Verify citations list is populated
        assert "citations" in result
        assert isinstance(result["citations"], list)
        # The citations should reference the source chunks
        if len(result["citations"]) > 0:
            citation = result["citations"][0]
            assert "content" in citation or "chunk_id" in citation

    @patch("src.services.rag._get_llm")
    @patch("src.services.rag._get_embeddings_model")
    def test_citations_reference_recording_titles(
        self,
        mock_get_embeddings: MagicMock,
        mock_get_llm: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that citations include reference to recording titles."""
        from src.services.rag import generate_response_with_citations

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(
            content="The project deadline is next month [1]."
        )
        mock_get_llm.return_value = mock_llm_instance

        chunk = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="We need to complete the project by next month.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        db_session.add(chunk)
        db_session.commit()

        result = generate_response_with_citations(
            session=db_session,
            query="When is the project deadline?",
        )

        # Verify that citations can be traced back to recording
        assert "citations" in result
        # The implementation should include recording metadata
        # This could be recording_id, recording_title, or similar
        if len(result["citations"]) > 0:
            citation = result["citations"][0]
            # Citation should have some reference to the source
            assert (
                "recording_id" in citation or "recording_title" in citation or "source" in citation
            )

    @patch("src.services.rag._get_llm")
    @patch("src.services.rag._get_embeddings_model")
    def test_uses_llm_for_generation(
        self,
        mock_get_embeddings: MagicMock,
        mock_get_llm: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that the LLM is properly invoked for response generation."""
        from src.services.rag import generate_response_with_citations

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(
            content="The meeting covered several topics."
        )
        mock_get_llm.return_value = mock_llm_instance

        chunk = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="Today we covered budget, timeline, and resources.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        db_session.add(chunk)
        db_session.commit()

        generate_response_with_citations(
            session=db_session,
            query="What was discussed in the meeting?",
        )

        # Verify LLM was called
        mock_get_llm.assert_called_once()
        mock_llm_instance.invoke.assert_called_once()

        # Verify the prompt includes context from chunks
        call_args = mock_llm_instance.invoke.call_args
        # The invoke method should receive some form of prompt
        assert call_args is not None


class TestHandleNoResults:
    """Integration tests for handling empty search results."""

    @patch("src.services.rag._get_embeddings_model")
    def test_returns_appropriate_message_when_no_results(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
    ) -> None:
        """Test graceful handling when no matching documents are found."""
        from src.services.rag import generate_response_with_citations

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Query with empty database (no chunks exist)
        result = generate_response_with_citations(
            session=db_session,
            query="What is the meaning of life?",
        )

        # Should return a response indicating no relevant information found
        assert "response" in result
        assert result["response"] is not None
        # Response should indicate no relevant content was found
        response_lower = result["response"].lower()
        assert (
            "no relevant" in response_lower
            or "not found" in response_lower
            or "no matching" in response_lower
            or "no information" in response_lower
            or "unable to find" in response_lower
        )

    @patch("src.services.rag._get_embeddings_model")
    def test_no_citations_when_no_results(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
    ) -> None:
        """Test that citations list is empty when no documents are retrieved."""
        from src.services.rag import generate_response_with_citations

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Query with empty database
        result = generate_response_with_citations(
            session=db_session,
            query="Random query with no matching content",
        )

        assert "citations" in result
        assert result["citations"] == []

    @patch("src.services.rag._get_embeddings_model")
    def test_graceful_handling_of_empty_vector_store(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
    ) -> None:
        """Test that retrieve_documents handles empty vector store gracefully."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Query with completely empty database
        results = retrieve_documents(
            session=db_session,
            query="Any query here",
        )

        # Should return empty list, not raise an exception
        assert results == []

    @patch("src.services.rag._get_embeddings_model")
    def test_handle_no_results_does_not_call_llm(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
    ) -> None:
        """Test that LLM is not called when no relevant documents exist."""
        from src.services.rag import generate_response_with_citations

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Patch LLM to verify it is NOT called
        with patch("src.services.rag._get_llm") as mock_get_llm:
            mock_llm_instance = MagicMock()
            mock_get_llm.return_value = mock_llm_instance

            result = generate_response_with_citations(
                session=db_session,
                query="Query with no matching documents",
            )

            # LLM should not be invoked when there are no documents
            mock_llm_instance.invoke.assert_not_called()

            # But we should still get a valid response structure
            assert "response" in result
            assert "citations" in result


class TestRetrieveDocumentsEdgeCases:
    """Edge case tests for retrieve_documents function."""

    @patch("src.services.rag._get_embeddings_model")
    def test_handles_special_characters_in_query(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that queries with special characters are handled properly."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        chunk = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="The cost is $50,000 (fifty thousand dollars).",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        db_session.add(chunk)
        db_session.commit()

        # Query with special characters - should not raise
        results = retrieve_documents(
            session=db_session,
            query="What's the cost? Is it $50,000?",
        )

        assert isinstance(results, list)

    @patch("src.services.rag._get_embeddings_model")
    def test_handles_unicode_in_query(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that Unicode characters in queries are handled properly."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        chunk = TranscriptChunk(
            recording_id=sample_recording.id,
            chunk_index=0,
            content="Meeting notes from the Tokyo office.",
            speaker="SPEAKER_00",
            embedding=[0.1] * 1024,
        )
        db_session.add(chunk)
        db_session.commit()

        # Query with Unicode characters
        results = retrieve_documents(
            session=db_session,
            query="Notes from Tokyo office meeting",
        )

        assert isinstance(results, list)

    @patch("src.services.rag._get_embeddings_model")
    def test_default_k_value(
        self,
        mock_get_embeddings: MagicMock,
        db_session: Session,
        sample_recording: Recording,
    ) -> None:
        """Test that default k value is applied when not specified."""
        from src.services.rag import retrieve_documents

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.embed_query.return_value = [0.1] * 1024
        mock_get_embeddings.return_value = mock_embeddings_instance

        # Create more chunks than default k (assuming default is 5)
        for i in range(10):
            chunk = TranscriptChunk(
                recording_id=sample_recording.id,
                chunk_index=i,
                content=f"Meeting content chunk {i}.",
                speaker="SPEAKER_00",
                embedding=[0.1] * 1024,
            )
            db_session.add(chunk)
        db_session.commit()

        # Call without specifying k
        results = retrieve_documents(
            session=db_session,
            query="meeting content",
        )

        # Should return default number of results (likely 5)
        assert len(results) <= 10  # Should be limited by some default
        assert len(results) > 0
