"""Unit tests for transcript reconstruction service.

This module tests the LLM-based transcript reconstruction service for
User Story 2: Automatic Transcript Reconstruction.

These tests are written in the TDD RED phase - the reconstruction service
does not exist yet and these tests are expected to fail initially.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestReconstructTranscript:
    """Tests for the reconstruct_transcript() function."""

    @pytest.fixture
    def sample_full_text(self) -> str:
        """Sample clean transcript from Whisper."""
        return (
            "Thank you for joining us today. Can you tell us about your experience? "
            "Of course. I've been working in this field for about ten years now. "
            "The challenges we face have evolved significantly over time."
        )

    @pytest.fixture
    def sample_dialog_json(self) -> list[dict[str, Any]]:
        """Sample diarized dialog JSON with some garbled text."""
        return [
            {"speaker": "Interviewer", "text": "Thank you fer joining us today"},
            {"speaker": "Interviewer", "text": "Can you tell us bout your experience"},
            {"speaker": "Respondent", "text": "Of course I've been workin in this field"},
            {"speaker": "Respondent", "text": "fer bout ten years now"},
            {"speaker": "Respondent", "text": "The challenges we face have evolve significantly"},
        ]

    @pytest.fixture
    def expected_reconstructed_json(self) -> list[dict[str, Any]]:
        """Expected output after LLM reconstruction."""
        return [
            {"speaker": "Interviewer", "text": "Thank you for joining us today."},
            {"speaker": "Interviewer", "text": "Can you tell us about your experience?"},
            {"speaker": "Respondent", "text": "Of course. I've been working in this field"},
            {"speaker": "Respondent", "text": "for about ten years now."},
            {
                "speaker": "Respondent",
                "text": "The challenges we face have evolved significantly over time.",
            },
        ]

    @pytest.fixture
    def mock_llm_response(self, expected_reconstructed_json: list[dict[str, Any]]) -> str:
        """Mock LLM response with reconstructed JSON."""
        return json.dumps(expected_reconstructed_json)

    def test_reconstruct_transcript_returns_list_of_dicts(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
        mock_llm_response: str,
    ) -> None:
        """Test that reconstruct_transcript returns a list of dicts."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content=mock_llm_response)
            mock_get_llm.return_value = mock_llm

            from src.services.reconstruction import reconstruct_transcript

            result = reconstruct_transcript(sample_full_text, sample_dialog_json)

            assert isinstance(result, list)
            assert all(isinstance(item, dict) for item in result)

    def test_reconstruct_transcript_preserves_speaker_attributions(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
        mock_llm_response: str,
    ) -> None:
        """Test that speaker attributions are preserved in output."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content=mock_llm_response)
            mock_get_llm.return_value = mock_llm

            from src.services.reconstruction import reconstruct_transcript

            result = reconstruct_transcript(sample_full_text, sample_dialog_json)

            # Check that each result has speaker and text keys
            for item in result:
                assert "speaker" in item
                assert "text" in item

            # Check that speaker values are preserved
            speakers = {item["speaker"] for item in result}
            assert "Interviewer" in speakers
            assert "Respondent" in speakers

    def test_reconstruct_transcript_calls_llm_with_prompt(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
        mock_llm_response: str,
    ) -> None:
        """Test that LLM is called with appropriate prompt."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content=mock_llm_response)
            mock_get_llm.return_value = mock_llm

            from src.services.reconstruction import reconstruct_transcript

            reconstruct_transcript(sample_full_text, sample_dialog_json)

            # LLM should be invoked at least once
            assert mock_llm.invoke.called

    def test_reconstruct_transcript_with_empty_dialog_returns_empty(
        self,
        sample_full_text: str,
    ) -> None:
        """Test that empty dialog_json returns empty list."""
        from src.services.reconstruction import reconstruct_transcript

        result = reconstruct_transcript(sample_full_text, [])

        assert result == []

    def test_reconstruct_transcript_with_empty_full_text_returns_original(
        self,
        sample_dialog_json: list[dict[str, Any]],
    ) -> None:
        """Test that empty full_text returns original dialog_json."""
        from src.services.reconstruction import reconstruct_transcript

        result = reconstruct_transcript("", sample_dialog_json)

        # Should return original when nothing to reconstruct from
        assert result == sample_dialog_json


class TestReconstructTranscriptErrorHandling:
    """Tests for error handling in reconstruction service."""

    @pytest.fixture
    def sample_full_text(self) -> str:
        """Sample clean transcript text."""
        return "Hello world. This is a test transcript."

    @pytest.fixture
    def sample_dialog_json(self) -> list[dict[str, Any]]:
        """Sample dialog JSON."""
        return [
            {"speaker": "Interviewer", "text": "Hello world"},
            {"speaker": "Respondent", "text": "This is a test transcript"},
        ]

    def test_returns_original_on_llm_exception(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
    ) -> None:
        """Test that LLM exceptions result in returning original dialog_json."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = Exception("LLM error")
            mock_get_llm.return_value = mock_llm

            from src.services.reconstruction import reconstruct_transcript

            result = reconstruct_transcript(sample_full_text, sample_dialog_json)

            # Should return original dialog_json on error
            assert result == sample_dialog_json

    def test_returns_original_on_invalid_json_response(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
    ) -> None:
        """Test that invalid JSON from LLM results in returning original."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content="not valid json")
            mock_get_llm.return_value = mock_llm

            from src.services.reconstruction import reconstruct_transcript

            result = reconstruct_transcript(sample_full_text, sample_dialog_json)

            # Should return original on JSON parse error
            assert result == sample_dialog_json

    def test_returns_original_on_malformed_json_structure(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
    ) -> None:
        """Test that malformed JSON structure returns original."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            # Valid JSON but wrong structure (not a list of speaker/text dicts)
            mock_llm.invoke.return_value = MagicMock(content='{"invalid": "structure"}')
            mock_get_llm.return_value = mock_llm

            from src.services.reconstruction import reconstruct_transcript

            result = reconstruct_transcript(sample_full_text, sample_dialog_json)

            # Should return original on invalid structure
            assert result == sample_dialog_json

    def test_logs_warning_on_fallback(
        self,
        sample_full_text: str,
        sample_dialog_json: list[dict[str, Any]],
    ) -> None:
        """Test that warnings are logged when falling back to original."""
        with patch("src.services.reconstruction._get_llm") as mock_get_llm:
            with patch("src.services.reconstruction.logger") as mock_logger:
                mock_llm = MagicMock()
                mock_llm.invoke.side_effect = Exception("LLM error")
                mock_get_llm.return_value = mock_llm

                from src.services.reconstruction import reconstruct_transcript

                reconstruct_transcript(sample_full_text, sample_dialog_json)

                # Should log a warning
                assert mock_logger.warning.called or mock_logger.error.called
