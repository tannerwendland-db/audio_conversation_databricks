"""Integration tests for the diarize_audio function.

This module tests the diarization service that sends audio to the
Databricks serving endpoint for transcription with speaker labels.

Tests cover:
- Successful diarization with correct endpoint calls
- Error response handling from the endpoint
- Exception handling when endpoint fails
- Invalid response format handling
- Empty audio bytes handling
"""

import base64
from unittest.mock import MagicMock, patch


class TestDiarizeAudioSuccess:
    """Test cases for successful diarize_audio calls."""

    def test_diarize_audio_calls_correct_endpoint(
        self, mock_databricks_client: MagicMock, test_settings
    ):
        """Test that diarize_audio calls serving_endpoints.query with correct endpoint name."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [wav_bytes]
            with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
                mock_ws_class.return_value = mock_databricks_client
                mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                    predictions=[
                        {
                            "dialog": "Interviewer: Hello\nRespondent: Hi",
                            "transcription": "Hello Hi",
                        }
                    ]
                )

                diarize_audio(wav_bytes)

                # Verify the endpoint was called with correct endpoint name
                mock_databricks_client.serving_endpoints.query.assert_called_once()
                call_kwargs = mock_databricks_client.serving_endpoints.query.call_args
                assert call_kwargs.kwargs.get("name") == test_settings.DIARIZATION_ENDPOINT

    def test_diarize_audio_sends_base64_encoded_wav(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio sends WAV bytes as base64 in correct format."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"
        expected_base64 = base64.b64encode(wav_bytes).decode("utf-8")

        with patch("src.services.audio.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [wav_bytes]
            with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
                mock_ws_class.return_value = mock_databricks_client
                mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                    predictions=[
                        {
                            "dialog": "Interviewer: Hello\nRespondent: Hi",
                            "transcription": "Hello Hi",
                        }
                    ]
                )

                diarize_audio(wav_bytes)

                # Verify the call was made with base64-encoded audio in dataframe_records format
                call_kwargs = mock_databricks_client.serving_endpoints.query.call_args
                dataframe_records = call_kwargs.kwargs.get("dataframe_records")

                assert dataframe_records is not None
                assert len(dataframe_records) == 1
                assert dataframe_records[0]["audio_base64"] == expected_base64

    def test_diarize_audio_parses_response_correctly(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio correctly parses the endpoint response."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"
        expected_dialog = "Interviewer: What is your name?\nRespondent: My name is John."
        expected_transcription = "What is your name? My name is John."

        with patch("src.services.audio.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [wav_bytes]
            with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
                mock_ws_class.return_value = mock_databricks_client
                mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                    predictions=[
                        {"dialog": expected_dialog, "transcription": expected_transcription}
                    ]
                )

                result = diarize_audio(wav_bytes)

                assert result.status == "success"
                assert result.dialog == expected_dialog
                assert result.transcription == expected_transcription
                assert result.error is None

    def test_diarize_audio_returns_diarized_text_string(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio returns the diarized text as a string."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"
        dialog = (
            "Interviewer: Hello, welcome to the interview.\n"
            "Respondent: Thank you for having me.\n"
            "Interviewer: Let's begin with your background.\n"
            "Respondent: I have 10 years of experience."
        )
        transcription = (
            "Hello, welcome to the interview. Thank you for having me. "
            "Let's begin with your background. I have 10 years of experience."
        )

        with patch("src.services.audio.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [wav_bytes]
            with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
                mock_ws_class.return_value = mock_databricks_client
                mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                    predictions=[{"dialog": dialog, "transcription": transcription}]
                )

                result = diarize_audio(wav_bytes)

                assert isinstance(result.dialog, str)
                assert "Interviewer:" in result.dialog
                assert "Respondent:" in result.dialog


class TestDiarizeAudioErrorHandling:
    """Test cases for diarize_audio error handling."""

    def test_diarize_audio_handles_error_response(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio handles error responses from the endpoint."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [wav_bytes]
            with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
                mock_ws_class.return_value = mock_databricks_client
                # Simulate an error response from the endpoint
                mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                    predictions=[{"error": "Model inference failed", "status": "error"}]
                )

                result = diarize_audio(wav_bytes)

                assert result.status == "error"
                assert result.error is not None
                assert "Model inference failed" in result.error

    def test_diarize_audio_handles_endpoint_exception(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio handles exceptions from the endpoint."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [wav_bytes]
            with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
                mock_ws_class.return_value = mock_databricks_client
                mock_databricks_client.serving_endpoints.query.side_effect = Exception(
                    "Connection timeout"
                )

                result = diarize_audio(wav_bytes)

                assert result.status == "error"
                assert result.error is not None
                assert "Connection timeout" in result.error

    def test_diarize_audio_handles_invalid_response_format(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio handles invalid response formats gracefully."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client
            # Return a response with unexpected format
            mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                predictions=None
            )

            result = diarize_audio(wav_bytes)

            assert result.status == "error"
            assert result.error is not None

    def test_diarize_audio_handles_empty_predictions(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio handles empty predictions list."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client
            mock_databricks_client.serving_endpoints.query.return_value = MagicMock(predictions=[])

            result = diarize_audio(wav_bytes)

            assert result.status == "error"
            assert result.error is not None

    def test_diarize_audio_handles_missing_transcription_key(
        self, mock_databricks_client: MagicMock
    ):
        """Test that diarize_audio handles response missing transcription key."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client
            # Response has predictions but no transcription key
            mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                predictions=[{"other_key": "some value"}]
            )

            result = diarize_audio(wav_bytes)

            assert result.status == "error"
            assert result.error is not None

    def test_diarize_audio_handles_empty_audio_bytes(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio handles empty audio bytes input."""
        from src.services.audio import diarize_audio

        wav_bytes = b""

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client

            result = diarize_audio(wav_bytes)

            assert result.status == "error"
            assert result.error is not None
            # Should not call the endpoint with empty bytes
            mock_databricks_client.serving_endpoints.query.assert_not_called()

    def test_diarize_audio_handles_none_audio_bytes(self, mock_databricks_client: MagicMock):
        """Test that diarize_audio handles None audio bytes input."""
        from src.services.audio import diarize_audio

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client

            result = diarize_audio(None)

            assert result.status == "error"
            assert result.error is not None
            # Should not call the endpoint with None
            mock_databricks_client.serving_endpoints.query.assert_not_called()


class TestDiarizeAudioResponseFormat:
    """Test cases for validating the DiarizeResponse structure."""

    def test_diarize_response_has_required_fields(self, mock_databricks_client: MagicMock):
        """Test that the response object has all required fields per api.yaml contract."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client
            mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                predictions=[{"dialog": "Interviewer: Test", "transcription": "Test"}]
            )

            result = diarize_audio(wav_bytes)

            # Verify all required fields from api.yaml DiarizeResponse
            assert hasattr(result, "dialog")
            assert hasattr(result, "transcription")
            assert hasattr(result, "status")
            assert hasattr(result, "error")

    def test_diarize_response_status_is_valid_enum(self, mock_databricks_client: MagicMock):
        """Test that status field contains valid enum value."""
        from src.services.audio import diarize_audio

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt test audio data"

        with patch("src.services.audio.WorkspaceClient") as mock_ws_class:
            mock_ws_class.return_value = mock_databricks_client
            mock_databricks_client.serving_endpoints.query.return_value = MagicMock(
                predictions=[{"dialog": "Interviewer: Test", "transcription": "Test"}]
            )

            result = diarize_audio(wav_bytes)

            assert result.status in ["success", "error"]
