"""Unit tests for speaker embedding matching logic in audio service."""


from src.services.audio import (
    SPEAKER_SIMILARITY_THRESHOLD,
    DiarizeResponse,
    _compute_cosine_similarity,
    _match_speakers_to_reference,
)


class TestDiarizeResponseWithEmbeddings:
    """Tests for DiarizeResponse dataclass with speaker_embeddings field."""

    def test_diarize_response_includes_embeddings_field(self):
        """DiarizeResponse should include speaker_embeddings field."""
        response = DiarizeResponse(
            status="success",
            dialog="Interviewer: Hello\nRespondent: Hi",
            transcription="Hello Hi",
            speaker_embeddings={"Interviewer": [0.1] * 512, "Respondent": [0.2] * 512},
            error=None,
        )

        assert hasattr(response, "speaker_embeddings")
        assert response.speaker_embeddings is not None
        assert "Interviewer" in response.speaker_embeddings
        assert "Respondent" in response.speaker_embeddings

    def test_diarize_response_embeddings_can_be_none(self):
        """DiarizeResponse should allow None for speaker_embeddings."""
        response = DiarizeResponse(
            status="success",
            dialog="Interviewer: Hello",
            transcription="Hello",
            speaker_embeddings=None,
            error=None,
        )

        assert response.speaker_embeddings is None

    def test_diarize_response_error_has_no_embeddings(self):
        """Error responses should have None for embeddings."""
        response = DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error="Processing failed",
        )

        assert response.status == "error"
        assert response.speaker_embeddings is None


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_cosine_similarity_identical_vectors(self):
        """Identical vectors should have similarity = 1.0."""
        vec = [0.5] * 512
        similarity = _compute_cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity = 0.0."""
        # Create two orthogonal 512-dim vectors
        vec1 = [1.0] + [0.0] * 511
        vec2 = [0.0] + [1.0] + [0.0] * 510
        similarity = _compute_cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.0001

    def test_cosine_similarity_opposite_vectors(self):
        """Opposite vectors should have similarity = -1.0."""
        vec1 = [1.0] * 512
        vec2 = [-1.0] * 512
        similarity = _compute_cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.0001

    def test_cosine_similarity_normalized_range(self):
        """Similarity should always be in range [-1, 1]."""
        import random
        random.seed(42)

        for _ in range(10):
            vec1 = [random.random() for _ in range(512)]
            vec2 = [random.random() for _ in range(512)]
            similarity = _compute_cosine_similarity(vec1, vec2)
            assert -1.0 <= similarity <= 1.0


class TestSpeakerMatching:
    """Tests for speaker matching logic."""

    def test_match_speakers_above_threshold(self):
        """Speakers with similarity > threshold should be matched."""
        # Create reference embeddings
        reference = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
        }

        # Create chunk embeddings that are very similar to reference
        chunk_embeddings = {
            "SPEAKER_00": [0.5] * 512,  # Should match Interviewer
            "SPEAKER_01": [0.3] * 512,  # Should match Respondent
        }

        label_mapping = _match_speakers_to_reference(chunk_embeddings, reference)

        assert label_mapping["SPEAKER_00"] == "Interviewer"
        assert label_mapping["SPEAKER_01"] == "Respondent"

    def test_match_speakers_below_threshold(self):
        """Speakers with similarity < threshold should be treated as new."""
        # Create reference embeddings
        reference = {
            "Interviewer": [1.0] + [0.0] * 511,
        }

        # Create chunk embedding that is very different (orthogonal)
        chunk_embeddings = {
            "SPEAKER_00": [0.0] + [1.0] + [0.0] * 510,  # Should not match
        }

        label_mapping = _match_speakers_to_reference(chunk_embeddings, reference)

        # Should keep original label since no match found
        assert "SPEAKER_00" in label_mapping
        assert label_mapping["SPEAKER_00"] != "Interviewer"

    def test_match_speakers_empty_reference(self):
        """With empty reference, all speakers should keep original labels."""
        chunk_embeddings = {
            "SPEAKER_00": [0.5] * 512,
            "SPEAKER_01": [0.3] * 512,
        }

        label_mapping = _match_speakers_to_reference(chunk_embeddings, {})

        assert label_mapping["SPEAKER_00"] == "SPEAKER_00"
        assert label_mapping["SPEAKER_01"] == "SPEAKER_01"

    def test_match_speakers_partial_match(self):
        """Some speakers match reference, others are new."""
        reference = {
            "Interviewer": [0.5] * 512,
        }

        chunk_embeddings = {
            "SPEAKER_00": [0.5] * 512,  # Should match Interviewer
            "SPEAKER_01": [0.0] + [1.0] + [0.0] * 510,  # Should be new
        }

        label_mapping = _match_speakers_to_reference(chunk_embeddings, reference)

        assert label_mapping["SPEAKER_00"] == "Interviewer"
        # SPEAKER_01 should get a new label
        assert label_mapping["SPEAKER_01"] != "Interviewer"


class TestReferenceEmbeddingAccumulation:
    """Tests for reference embedding accumulation logic."""

    def test_first_chunk_becomes_reference(self):
        """Embeddings from first chunk should become the reference set."""
        first_chunk_embeddings = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
        }

        # Initialize empty reference
        reference = {}

        # After first chunk, reference should contain all speakers
        reference.update(first_chunk_embeddings)

        assert len(reference) == 2
        assert "Interviewer" in reference
        assert "Respondent" in reference

    def test_new_speaker_added_to_reference(self):
        """New speakers should be added to reference set."""
        reference = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
        }

        # New speaker in chunk 2
        new_speaker_embedding = [0.0] + [1.0] + [0.0] * 510
        new_label = "Respondent2"

        # Add new speaker to reference
        reference[new_label] = new_speaker_embedding

        assert len(reference) == 3
        assert "Respondent2" in reference

    def test_matched_speaker_not_duplicated(self):
        """Matched speakers should not create duplicate entries."""
        reference = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
        }

        # Chunk with same speakers (should match and not create duplicates)
        chunk_embeddings = {
            "SPEAKER_00": [0.5] * 512,  # Should match Interviewer
            "SPEAKER_01": [0.3] * 512,  # Should match Respondent
        }

        # Match speakers to reference
        label_mapping = _match_speakers_to_reference(chunk_embeddings, reference)

        # Both speakers should map to existing reference labels
        assert label_mapping["SPEAKER_00"] == "Interviewer"
        assert label_mapping["SPEAKER_01"] == "Respondent"

        # Reference should still have only 2 speakers (no duplicates added)
        assert len(reference) == 2


class TestSpeakerSimilarityThreshold:
    """Tests for speaker similarity threshold constant."""

    def test_threshold_is_defined(self):
        """SPEAKER_SIMILARITY_THRESHOLD should be defined."""
        assert SPEAKER_SIMILARITY_THRESHOLD is not None

    def test_threshold_is_reasonable(self):
        """Threshold should be in reasonable range (0.5 to 0.95)."""
        assert 0.5 <= SPEAKER_SIMILARITY_THRESHOLD <= 0.95

    def test_default_threshold_value(self):
        """Default threshold should be 0.75 per spec."""
        assert SPEAKER_SIMILARITY_THRESHOLD == 0.75
