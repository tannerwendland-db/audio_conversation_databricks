"""Unit tests for the audio service module.

This module provides comprehensive tests for audio file validation,
format conversion, and duration extraction functionality.

RED phase of TDD - these tests are written before implementation
and should fail initially.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestValidateFileFormat:
    """Tests for the validate_file_format() function.

    The function should accept MP3, WAV, M4A, and FLAC formats
    up to 500MB in size.
    """

    # Valid format tests
    @pytest.mark.parametrize(
        "filename,file_size",
        [
            ("recording.mp3", 1024),
            ("recording.wav", 1024),
            ("recording.m4a", 1024),
            ("recording.flac", 1024),
        ],
    )
    def test_valid_formats_are_accepted(self, filename: str, file_size: int) -> None:
        """Test that valid audio formats are accepted."""
        from src.services.audio import validate_file_format

        result = validate_file_format(filename, file_size)
        assert result is True

    @pytest.mark.parametrize(
        "filename",
        [
            "RECORDING.MP3",
            "Recording.Wav",
            "AUDIO.M4A",
            "music.FLAC",
            "Mixed.Mp3",
            "TEST.WaV",
        ],
    )
    def test_case_insensitivity_for_extensions(self, filename: str) -> None:
        """Test that file extension validation is case-insensitive."""
        from src.services.audio import validate_file_format

        result = validate_file_format(filename, 1024)
        assert result is True

    # Invalid format tests
    @pytest.mark.parametrize(
        "filename",
        [
            "document.txt",
            "report.pdf",
            "malware.exe",
            "image.png",
            "video.mp4",
            "archive.zip",
        ],
    )
    def test_invalid_formats_are_rejected(self, filename: str) -> None:
        """Test that non-audio formats are rejected."""
        from src.services.audio import AudioValidationError, validate_file_format

        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format(filename, 1024)

        assert "format" in str(exc_info.value).lower()

    def test_file_without_extension_is_rejected(self) -> None:
        """Test that files without extensions are rejected."""
        from src.services.audio import AudioValidationError, validate_file_format

        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format("audiofile", 1024)

        assert "format" in str(exc_info.value).lower()

    def test_empty_filename_is_rejected(self) -> None:
        """Test that empty filename is rejected."""
        from src.services.audio import AudioValidationError, validate_file_format

        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format("", 1024)

        assert "filename" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()

    def test_filename_with_only_extension_is_rejected(self) -> None:
        """Test that filename with only extension is rejected."""
        from src.services.audio import AudioValidationError, validate_file_format

        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format(".mp3", 1024)

        assert "filename" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    # File size tests
    def test_file_exactly_at_size_limit_is_accepted(self) -> None:
        """Test that file exactly at 500MB limit is accepted."""
        from src.services.audio import MAX_FILE_SIZE, validate_file_format

        # 500MB in bytes
        result = validate_file_format("recording.mp3", MAX_FILE_SIZE)
        assert result is True

    def test_file_over_size_limit_is_rejected(self) -> None:
        """Test that file over 500MB limit is rejected."""
        from src.services.audio import (
            MAX_FILE_SIZE,
            AudioValidationError,
            validate_file_format,
        )

        # 500MB + 1 byte
        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format("recording.mp3", MAX_FILE_SIZE + 1)

        assert "size" in str(exc_info.value).lower()

    def test_file_well_under_size_limit_is_accepted(self) -> None:
        """Test that small files are accepted."""
        from src.services.audio import validate_file_format

        # 1MB file
        result = validate_file_format("recording.wav", 1024 * 1024)
        assert result is True

    def test_zero_size_file_is_rejected(self) -> None:
        """Test that zero-size files are rejected."""
        from src.services.audio import AudioValidationError, validate_file_format

        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format("recording.mp3", 0)

        assert "size" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()

    def test_negative_size_is_rejected(self) -> None:
        """Test that negative file size is rejected."""
        from src.services.audio import AudioValidationError, validate_file_format

        with pytest.raises(AudioValidationError) as exc_info:
            validate_file_format("recording.mp3", -1)

        assert "size" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


class TestConvertToWav:
    """Tests for the convert_to_wav() function.

    The function should convert audio to 16kHz WAV format using librosa
    and return tuple[bytes, float] where float is duration.
    """

    @pytest.fixture
    def mock_audio_data(self) -> bytes:
        """Create mock audio data for testing."""
        return b"fake audio content for testing purposes"

    @pytest.fixture
    def mock_librosa_load(self) -> MagicMock:
        """Create a mock for librosa.load that returns valid audio data."""
        # Simulated audio: 1 second of samples at 44100 Hz
        audio_samples = np.zeros(44100, dtype=np.float32)
        return audio_samples, 44100

    def test_convert_to_wav_returns_tuple(self, mock_audio_data: bytes) -> None:
        """Test that convert_to_wav returns a tuple of (bytes, float)."""
        from src.services.audio import convert_to_wav

        mock_audio_array = np.zeros(16000, dtype=np.float32)  # 1 second at 16kHz

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.return_value = (mock_audio_array, 44100)
            mock_librosa.resample.return_value = mock_audio_array

            result = convert_to_wav(mock_audio_data)

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bytes)
            assert isinstance(result[1], float)

    def test_convert_to_wav_returns_correct_duration(self, mock_audio_data: bytes) -> None:
        """Test that convert_to_wav returns the correct duration."""
        from src.services.audio import TARGET_SAMPLE_RATE, convert_to_wav

        # 2 seconds of audio at 44100 Hz source
        source_sr = 44100
        duration_seconds = 2.0
        mock_audio_array = np.zeros(int(source_sr * duration_seconds), dtype=np.float32)
        resampled_array = np.zeros(int(TARGET_SAMPLE_RATE * duration_seconds), dtype=np.float32)

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.return_value = (mock_audio_array, source_sr)
            mock_librosa.resample.return_value = resampled_array

            _, duration = convert_to_wav(mock_audio_data)

            assert abs(duration - duration_seconds) < 0.01

    def test_convert_to_wav_resamples_to_16khz(self, mock_audio_data: bytes) -> None:
        """Test that audio is resampled to 16kHz."""
        from src.services.audio import TARGET_SAMPLE_RATE, convert_to_wav

        source_sr = 44100
        mock_audio_array = np.zeros(44100, dtype=np.float32)  # 1 second at 44100 Hz

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.return_value = (mock_audio_array, source_sr)
            mock_librosa.resample.return_value = np.zeros(TARGET_SAMPLE_RATE, dtype=np.float32)

            convert_to_wav(mock_audio_data)

            # Verify resample was called with target sample rate
            mock_librosa.resample.assert_called_once()
            call_kwargs = mock_librosa.resample.call_args
            # Check that target_sr is 16000
            assert call_kwargs.kwargs.get("target_sr") == TARGET_SAMPLE_RATE or (
                len(call_kwargs.args) >= 3 and call_kwargs.args[2] == TARGET_SAMPLE_RATE
            )

    def test_convert_to_wav_returns_valid_wav_bytes(self, mock_audio_data: bytes) -> None:
        """Test that the returned bytes represent a valid WAV file."""
        from src.services.audio import convert_to_wav

        mock_audio_array = np.zeros(16000, dtype=np.float32)

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.return_value = (mock_audio_array, 44100)
            mock_librosa.resample.return_value = mock_audio_array

            wav_bytes, _ = convert_to_wav(mock_audio_data)

            # WAV files start with "RIFF" header
            assert wav_bytes[:4] == b"RIFF"
            # WAV files contain "WAVE" format identifier
            assert b"WAVE" in wav_bytes[:12]

    def test_convert_to_wav_handles_invalid_audio_data(self) -> None:
        """Test that invalid audio data raises an appropriate error."""
        from src.services.audio import AudioProcessingError, convert_to_wav

        invalid_data = b"this is not audio data at all"

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.side_effect = Exception("Unable to load audio file")

            with pytest.raises(AudioProcessingError) as exc_info:
                convert_to_wav(invalid_data)

            assert "audio" in str(exc_info.value).lower()

    def test_convert_to_wav_handles_empty_audio_data(self) -> None:
        """Test that empty audio data raises an appropriate error."""
        from src.services.audio import AudioProcessingError, convert_to_wav

        with pytest.raises(AudioProcessingError) as exc_info:
            convert_to_wav(b"")

        assert "empty" in str(exc_info.value).lower() or "audio" in str(exc_info.value).lower()

    def test_convert_to_wav_preserves_audio_content(self, mock_audio_data: bytes) -> None:
        """Test that audio content is preserved after conversion."""
        from src.services.audio import TARGET_SAMPLE_RATE, convert_to_wav

        # Create audio with non-zero values
        source_sr = 44100
        mock_audio_array = np.sin(np.linspace(0, 2 * np.pi, source_sr)).astype(np.float32)
        resampled_array = np.sin(np.linspace(0, 2 * np.pi, TARGET_SAMPLE_RATE)).astype(np.float32)

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.return_value = (mock_audio_array, source_sr)
            mock_librosa.resample.return_value = resampled_array

            wav_bytes, _ = convert_to_wav(mock_audio_data)

            # Verify we got non-empty WAV data
            assert len(wav_bytes) > 44  # WAV header is 44 bytes minimum

    def test_convert_to_wav_handles_stereo_audio(self, mock_audio_data: bytes) -> None:
        """Test that stereo audio is handled correctly."""
        from src.services.audio import convert_to_wav

        # Stereo audio: 2 channels, 1 second at 44100 Hz
        source_sr = 44100
        stereo_audio = np.zeros((2, source_sr), dtype=np.float32)
        mono_resampled = np.zeros(16000, dtype=np.float32)

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.load.return_value = (stereo_audio, source_sr)
            mock_librosa.to_mono.return_value = np.zeros(source_sr, dtype=np.float32)
            mock_librosa.resample.return_value = mono_resampled

            result = convert_to_wav(mock_audio_data)

            # Should succeed without error
            assert isinstance(result, tuple)


class TestGetAudioDuration:
    """Tests for the get_audio_duration() function.

    The function should return the duration of audio data in seconds.
    """

    def test_get_duration_returns_float(self) -> None:
        """Test that get_audio_duration returns a float."""
        from src.services.audio import get_audio_duration

        mock_audio_data = b"fake audio content"

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.get_duration.return_value = 120.5

            result = get_audio_duration(mock_audio_data)

            assert isinstance(result, float)

    def test_get_duration_returns_correct_value(self) -> None:
        """Test that get_audio_duration returns the correct duration."""
        from src.services.audio import get_audio_duration

        mock_audio_data = b"fake audio content"
        expected_duration = 180.75  # 3 minutes 0.75 seconds

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.get_duration.return_value = expected_duration

            result = get_audio_duration(mock_audio_data)

            assert result == expected_duration

    @pytest.mark.parametrize(
        "duration_seconds",
        [
            0.5,  # Half a second
            1.0,  # One second
            60.0,  # One minute
            3600.0,  # One hour
            7200.5,  # Two hours and half a second
        ],
    )
    def test_get_duration_handles_various_lengths(self, duration_seconds: float) -> None:
        """Test that get_audio_duration handles various audio lengths."""
        from src.services.audio import get_audio_duration

        mock_audio_data = b"fake audio content"

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.get_duration.return_value = duration_seconds

            result = get_audio_duration(mock_audio_data)

            assert result == duration_seconds

    def test_get_duration_handles_invalid_audio(self) -> None:
        """Test that get_audio_duration raises error for invalid audio."""
        from src.services.audio import AudioProcessingError, get_audio_duration

        invalid_data = b"not valid audio"

        with patch("src.services.audio.librosa") as mock_librosa:
            mock_librosa.get_duration.side_effect = Exception("Invalid audio format")

            with pytest.raises(AudioProcessingError) as exc_info:
                get_audio_duration(invalid_data)

            assert "duration" in str(exc_info.value).lower() or "audio" in str(exc_info.value).lower()

    def test_get_duration_handles_empty_data(self) -> None:
        """Test that get_audio_duration raises error for empty data."""
        from src.services.audio import AudioProcessingError, get_audio_duration

        with pytest.raises(AudioProcessingError) as exc_info:
            get_audio_duration(b"")

        assert "empty" in str(exc_info.value).lower() or "audio" in str(exc_info.value).lower()


class TestAudioServiceConstants:
    """Tests for audio service constants and configuration."""

    def test_allowed_formats_contains_expected_extensions(self) -> None:
        """Test that ALLOWED_FORMATS contains all expected extensions."""
        from src.services.audio import ALLOWED_FORMATS

        expected_formats = {".mp3", ".wav", ".m4a", ".flac"}
        assert expected_formats == ALLOWED_FORMATS

    def test_max_file_size_is_500mb(self) -> None:
        """Test that MAX_FILE_SIZE is 500MB."""
        from src.services.audio import MAX_FILE_SIZE

        expected_size = 500 * 1024 * 1024  # 500MB in bytes
        assert expected_size == MAX_FILE_SIZE

    def test_target_sample_rate_is_16khz(self) -> None:
        """Test that TARGET_SAMPLE_RATE is 16kHz."""
        from src.services.audio import TARGET_SAMPLE_RATE

        assert TARGET_SAMPLE_RATE == 16000


class TestAudioValidationError:
    """Tests for the AudioValidationError exception class."""

    def test_audio_validation_error_is_exception(self) -> None:
        """Test that AudioValidationError is an Exception subclass."""
        from src.services.audio import AudioValidationError

        assert issubclass(AudioValidationError, Exception)

    def test_audio_validation_error_stores_message(self) -> None:
        """Test that AudioValidationError stores the error message."""
        from src.services.audio import AudioValidationError

        error_message = "Invalid file format: .txt"
        error = AudioValidationError(error_message)

        assert str(error) == error_message


class TestAudioProcessingError:
    """Tests for the AudioProcessingError exception class."""

    def test_audio_processing_error_is_exception(self) -> None:
        """Test that AudioProcessingError is an Exception subclass."""
        from src.services.audio import AudioProcessingError

        assert issubclass(AudioProcessingError, Exception)

    def test_audio_processing_error_stores_message(self) -> None:
        """Test that AudioProcessingError stores the error message."""
        from src.services.audio import AudioProcessingError

        error_message = "Failed to process audio file"
        error = AudioProcessingError(error_message)

        assert str(error) == error_message


