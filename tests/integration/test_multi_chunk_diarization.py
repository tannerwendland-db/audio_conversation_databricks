"""Integration tests for multi-chunk diarization with consistent speaker labels."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.services.audio import diarize_audio


class TestMultiChunkDiarizationWithEmbeddings:
    """Tests for multi-chunk diarization with speaker embedding matching."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = MagicMock()
        settings.DIARIZATION_ENDPOINT = "test-endpoint"
        settings.DIARIZATION_TIMEOUT_SECONDS = 300
        settings.ENABLE_AUDIO_CHUNKING = False
        return settings

    @pytest.fixture
    def sample_embeddings(self):
        """Sample speaker embeddings for testing."""
        return {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
        }

    def test_single_chunk_returns_embeddings(self, mock_settings, sample_embeddings):
        """Single chunk diarization should return speaker embeddings."""
        mock_response = MagicMock()
        mock_response.predictions = [{
            "dialog": "Interviewer: Hello\nRespondent: Hi there",
            "transcription": "Hello Hi there",
            "speaker_embeddings": json.dumps(sample_embeddings),
            "status": "success",
            "error": None,
        }]

        with patch("src.services.audio.get_settings", return_value=mock_settings), \
             patch("src.services.audio.WorkspaceClient") as mock_client_class:

            mock_client = MagicMock()
            mock_client.serving_endpoints.query.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Small audio that won't need chunking
            wav_bytes = b"RIFF" + b"\x00" * 1000

            result = diarize_audio(wav_bytes)

            assert result.status == "success"
            assert result.speaker_embeddings is not None
            assert "Interviewer" in result.speaker_embeddings
            assert "Respondent" in result.speaker_embeddings

    def test_multi_chunk_maintains_consistent_labels(self, mock_settings, sample_embeddings):
        """Multi-chunk diarization should maintain consistent speaker labels."""
        # Mock responses for two chunks
        chunk1_response = MagicMock()
        chunk1_response.predictions = [{
            "dialog": "Interviewer: Welcome to the show\nRespondent: Thank you for having me",
            "transcription": "Welcome to the show Thank you for having me",
            "speaker_embeddings": json.dumps(sample_embeddings),
            "status": "success",
            "error": None,
        }]

        # Chunk 2 - model returns with matching performed
        chunk2_response = MagicMock()
        chunk2_response.predictions = [{
            "dialog": "Interviewer: Let's discuss your project\nRespondent: Sure, I'd love to",
            "transcription": "Let's discuss your project Sure, I'd love to",
            "speaker_embeddings": json.dumps(sample_embeddings),
            "status": "success",
            "error": None,
        }]

        mock_settings.ENABLE_AUDIO_CHUNKING = True

        with patch("src.services.audio.get_settings", return_value=mock_settings), \
             patch("src.services.audio.WorkspaceClient") as mock_client_class, \
             patch("src.services.audio.split_audio_into_chunks") as mock_split:

            mock_client = MagicMock()
            # Return different responses for each chunk
            mock_client.serving_endpoints.query.side_effect = [
                chunk1_response,
                chunk2_response,
            ]
            mock_client_class.return_value = mock_client

            # Mock chunking to return two chunks
            mock_split.return_value = [b"chunk1_audio", b"chunk2_audio"]

            wav_bytes = b"RIFF" + b"\x00" * 20000000  # Large audio

            result = diarize_audio(wav_bytes)

            assert result.status == "success"
            assert result.dialog is not None

            # Verify reference embeddings were passed to second chunk
            calls = mock_client.serving_endpoints.query.call_args_list
            assert len(calls) == 2

            # First chunk should not have reference_embeddings
            first_call_data = calls[0][1]["dataframe_records"][0]
            assert first_call_data.get("reference_embeddings") in (None, "", "{}")

            # Second chunk should have reference_embeddings from first chunk
            second_call_data = calls[1][1]["dataframe_records"][0]
            assert "reference_embeddings" in second_call_data
            ref_embeddings = json.loads(second_call_data["reference_embeddings"])
            assert "Interviewer" in ref_embeddings
            assert "Respondent" in ref_embeddings

    def test_combined_dialog_preserves_speaker_labels(self, mock_settings, sample_embeddings):
        """Combined dialog from multiple chunks should have consistent speaker labels."""
        chunk1_response = MagicMock()
        chunk1_response.predictions = [{
            "dialog": "Interviewer: Part one",
            "transcription": "Part one",
            "speaker_embeddings": json.dumps(sample_embeddings),
            "status": "success",
            "error": None,
        }]

        chunk2_response = MagicMock()
        chunk2_response.predictions = [{
            "dialog": "Respondent: Part two",
            "transcription": "Part two",
            "speaker_embeddings": json.dumps(sample_embeddings),
            "status": "success",
            "error": None,
        }]

        mock_settings.ENABLE_AUDIO_CHUNKING = True

        with patch("src.services.audio.get_settings", return_value=mock_settings), \
             patch("src.services.audio.WorkspaceClient") as mock_client_class, \
             patch("src.services.audio.split_audio_into_chunks") as mock_split:

            mock_client = MagicMock()
            mock_client.serving_endpoints.query.side_effect = [
                chunk1_response,
                chunk2_response,
            ]
            mock_client_class.return_value = mock_client

            mock_split.return_value = [b"chunk1", b"chunk2"]

            wav_bytes = b"RIFF" + b"\x00" * 20000000

            result = diarize_audio(wav_bytes)

            assert result.status == "success"
            assert "Interviewer: Part one" in result.dialog
            assert "Respondent: Part two" in result.dialog

    def test_final_embeddings_include_all_speakers(self, mock_settings):
        """Final response should include embeddings for all speakers across chunks."""
        chunk1_embeddings = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
        }

        # Chunk 2 has a new speaker
        chunk2_embeddings = {
            "Interviewer": [0.5] * 512,
            "Respondent": [0.3] * 512,
            "Respondent2": [0.1] * 512,  # New speaker
        }

        chunk1_response = MagicMock()
        chunk1_response.predictions = [{
            "dialog": "Interviewer: Hello\nRespondent: Hi",
            "transcription": "Hello Hi",
            "speaker_embeddings": json.dumps(chunk1_embeddings),
            "status": "success",
            "error": None,
        }]

        chunk2_response = MagicMock()
        chunk2_response.predictions = [{
            "dialog": "Respondent2: I'm new here",
            "transcription": "I'm new here",
            "speaker_embeddings": json.dumps(chunk2_embeddings),
            "status": "success",
            "error": None,
        }]

        mock_settings.ENABLE_AUDIO_CHUNKING = True

        with patch("src.services.audio.get_settings", return_value=mock_settings), \
             patch("src.services.audio.WorkspaceClient") as mock_client_class, \
             patch("src.services.audio.split_audio_into_chunks") as mock_split:

            mock_client = MagicMock()
            mock_client.serving_endpoints.query.side_effect = [
                chunk1_response,
                chunk2_response,
            ]
            mock_client_class.return_value = mock_client

            mock_split.return_value = [b"chunk1", b"chunk2"]

            wav_bytes = b"RIFF" + b"\x00" * 20000000

            result = diarize_audio(wav_bytes)

            assert result.status == "success"
            assert result.speaker_embeddings is not None
            # Should have all 3 speakers
            assert len(result.speaker_embeddings) == 3
            assert "Interviewer" in result.speaker_embeddings
            assert "Respondent" in result.speaker_embeddings
            assert "Respondent2" in result.speaker_embeddings
