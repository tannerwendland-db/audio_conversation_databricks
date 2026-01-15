"""Audio processing service for Audio Conversation RAG System.

This module provides functionality for:
- Audio file format validation
- Audio conversion to WAV format
- Duration extraction
- Audio diarization via Databricks serving endpoints
"""

import base64
import io
import json
import logging
import math
from dataclasses import dataclass

import librosa
import soundfile as sf
from databricks.sdk import WorkspaceClient
from databricks.sdk.config import Config

from src.config import get_settings

logger = logging.getLogger(__name__)

# Speaker embedding matching threshold (0.75 per spec)
SPEAKER_SIMILARITY_THRESHOLD = 0.75

# Constants
ALLOWED_FORMATS = {".mp3", ".wav", ".m4a", ".flac"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB in bytes
TARGET_SAMPLE_RATE = 16000  # 16kHz
CHUNK_DURATION_SECONDS = 60  # 60-second chunks for diarization

# Databricks endpoint size limits
MAX_REQUEST_SIZE_BYTES = 16_777_216  # 16MB Databricks endpoint limit
BASE64_OVERHEAD_RATIO = 4 / 3  # Base64 increases size by ~33%
# 95% safety margin for max raw audio size
MAX_RAW_AUDIO_BYTES = int(MAX_REQUEST_SIZE_BYTES / BASE64_OVERHEAD_RATIO * 0.95)


class AudioValidationError(Exception):
    """Exception raised for audio file validation errors.

    This exception is raised when an audio file fails validation checks
    such as invalid format, incorrect file size, or missing filename.
    """

    pass


class AudioProcessingError(Exception):
    """Exception raised for audio processing errors.

    This exception is raised when audio processing operations fail,
    such as format conversion, duration extraction, or invalid audio data.
    """

    pass


@dataclass
class DiarizeResponse:
    """Response from the diarization service.

    Attributes:
        status: Either 'success' or 'error' indicating the operation result.
        dialog: The diarized dialog text with speaker labels if successful.
        transcription: The raw Whisper transcription without speaker labels.
        speaker_embeddings: Dict mapping speaker labels to embedding vectors (512-dim).
        error: Error message if the operation failed, None otherwise.
    """

    status: str
    dialog: str | None
    transcription: str | None
    speaker_embeddings: dict[str, list[float]] | None
    error: str | None


def validate_file_format(filename: str, file_size: int) -> bool:
    """Validate an audio file's format and size.

    Args:
        filename: The name of the audio file to validate.
        file_size: The size of the file in bytes.

    Returns:
        True if the file is valid.

    Raises:
        AudioValidationError: If the filename is empty, has no extension,
            has an invalid format, or the file size is invalid.
    """
    # Check for empty filename
    if not filename:
        raise AudioValidationError("Empty filename is not allowed")

    # Check for filename with only extension (no actual name)
    if filename.startswith(".") and filename.count(".") == 1:
        raise AudioValidationError("Invalid filename: name cannot be only an extension")

    # Extract and validate the file extension
    if "." not in filename:
        raise AudioValidationError(
            f"Invalid format: file has no extension. Allowed formats: {ALLOWED_FORMATS}"
        )

    extension = "." + filename.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_FORMATS:
        raise AudioValidationError(
            f"Invalid format: '{extension}' is not supported. "
            f"Allowed formats: {ALLOWED_FORMATS}"
        )

    # Validate file size
    if file_size <= 0:
        raise AudioValidationError(
            "Invalid file size: file size must be greater than 0"
        )

    if file_size > MAX_FILE_SIZE:
        raise AudioValidationError(
            f"File size ({file_size} bytes) exceeds maximum allowed size "
            f"({MAX_FILE_SIZE} bytes / 500MB)"
        )

    return True


def convert_to_wav(audio_bytes: bytes) -> tuple[bytes, float]:
    """Convert audio data to 16kHz WAV format.

    Args:
        audio_bytes: Raw audio data in any supported format.

    Returns:
        A tuple containing:
            - wav_bytes: The converted audio data in WAV format.
            - duration_seconds: The duration of the audio in seconds.

    Raises:
        AudioProcessingError: If the audio data is empty or cannot be processed.
    """
    if not audio_bytes:
        raise AudioProcessingError("Cannot process empty audio data")

    try:
        # Load audio from bytes using librosa
        audio_file = io.BytesIO(audio_bytes)
        audio_array, source_sr = librosa.load(audio_file, sr=None, mono=False)

        # Handle stereo audio - convert to mono
        if audio_array.ndim > 1:
            audio_array = librosa.to_mono(audio_array)

        # Resample to target sample rate if necessary
        if source_sr != TARGET_SAMPLE_RATE:
            audio_array = librosa.resample(
                audio_array, orig_sr=source_sr, target_sr=TARGET_SAMPLE_RATE
            )

        # Calculate duration based on resampled array
        duration_seconds = float(len(audio_array) / TARGET_SAMPLE_RATE)

        # Write to WAV format
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio_array, TARGET_SAMPLE_RATE, format="WAV")
        wav_buffer.seek(0)
        wav_bytes = wav_buffer.read()

        return wav_bytes, duration_seconds

    except Exception as e:
        logger.error(f"Failed to process audio: {e}", exc_info=True)
        raise AudioProcessingError(f"Failed to process audio: {e}") from e


def get_audio_duration(audio_bytes: bytes) -> float:
    """Get the duration of audio data in seconds.

    Args:
        audio_bytes: Raw audio data.

    Returns:
        The duration of the audio in seconds.

    Raises:
        AudioProcessingError: If the audio data is empty or duration cannot be determined.
    """
    if not audio_bytes:
        raise AudioProcessingError("Cannot get duration of empty audio data")

    try:
        audio_file = io.BytesIO(audio_bytes)
        duration = librosa.get_duration(path=audio_file)
        return duration
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}", exc_info=True)
        raise AudioProcessingError(f"Failed to get audio duration: {e}") from e


def split_audio_into_chunks(
    wav_bytes: bytes,
    chunk_duration: int = CHUNK_DURATION_SECONDS,
) -> list[bytes]:
    """Split WAV audio into fixed-duration chunks.

    Args:
        wav_bytes: WAV audio data to split.
        chunk_duration: Duration of each chunk in seconds. Defaults to 60 seconds.

    Returns:
        A list of WAV byte chunks. The last chunk may be shorter than chunk_duration.

    Raises:
        AudioProcessingError: If the audio data is empty or cannot be processed.
    """
    if not wav_bytes:
        raise AudioProcessingError("Cannot split empty audio data")

    try:
        # Load the WAV audio
        audio_file = io.BytesIO(wav_bytes)
        audio_array, sample_rate = librosa.load(audio_file, sr=None, mono=True)

        # Calculate samples per chunk
        samples_per_chunk = chunk_duration * sample_rate
        total_samples = len(audio_array)

        chunks = []
        start_sample = 0

        while start_sample < total_samples:
            end_sample = min(start_sample + samples_per_chunk, total_samples)
            chunk_array = audio_array[start_sample:end_sample]

            # Convert chunk to WAV bytes
            chunk_buffer = io.BytesIO()
            sf.write(chunk_buffer, chunk_array, sample_rate, format="WAV")
            chunk_buffer.seek(0)
            chunks.append(chunk_buffer.read())

            start_sample = end_sample

        logger.info(f"Split audio into {len(chunks)} chunks of {chunk_duration}s each")
        return chunks

    except AudioProcessingError:
        raise
    except Exception as e:
        logger.error(f"Failed to split audio into chunks: {e}", exc_info=True)
        raise AudioProcessingError(f"Failed to split audio into chunks: {e}") from e


def _calculate_max_chunk_duration(wav_bytes: bytes) -> int | None:
    """Calculate maximum chunk duration in seconds that fits within endpoint size limit.

    Args:
        wav_bytes: WAV audio data to analyze.

    Returns:
        Maximum chunk duration in seconds, or None if no chunking is needed.
    """
    total_size = len(wav_bytes)
    if total_size <= MAX_RAW_AUDIO_BYTES:
        return None  # No chunking needed

    # Calculate bytes per second from the audio
    audio_file = io.BytesIO(wav_bytes)
    audio_array, sample_rate = librosa.load(audio_file, sr=None, mono=True)
    duration_seconds = len(audio_array) / sample_rate
    bytes_per_second = total_size / duration_seconds

    # Calculate max duration that fits within limit
    max_duration = int(MAX_RAW_AUDIO_BYTES / bytes_per_second)
    return max(60, max_duration)  # At least 60 seconds per chunk


def _compute_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors.

    Args:
        vec1: First embedding vector.
        vec2: Second embedding vector.

    Returns:
        Cosine similarity in range [-1, 1].
    """
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def _match_speakers_to_reference(
    chunk_embeddings: dict[str, list[float]],
    reference_embeddings: dict[str, list[float]],
) -> dict[str, str]:
    """Match speaker embeddings from a chunk to reference embeddings.

    Args:
        chunk_embeddings: Dict mapping speaker labels to embeddings from current chunk.
        reference_embeddings: Dict mapping speaker labels to reference embeddings.

    Returns:
        Dict mapping chunk speaker labels to matched reference labels (or original if no match).
    """
    label_mapping: dict[str, str] = {}

    if not reference_embeddings:
        # No reference - keep original labels
        for label in chunk_embeddings:
            label_mapping[label] = label
        return label_mapping

    # Track which reference labels have been matched to avoid double-matching
    used_reference_labels: set[str] = set()

    for chunk_label, chunk_vec in chunk_embeddings.items():
        best_match: str | None = None
        best_similarity: float = -1.0

        for ref_label, ref_vec in reference_embeddings.items():
            if ref_label in used_reference_labels:
                continue

            similarity = _compute_cosine_similarity(chunk_vec, ref_vec)
            logger.debug(
                f"Similarity between {chunk_label} and {ref_label}: {similarity:.4f}"
            )

            if similarity > SPEAKER_SIMILARITY_THRESHOLD and similarity > best_similarity:
                best_match = ref_label
                best_similarity = similarity

        if best_match:
            label_mapping[chunk_label] = best_match
            used_reference_labels.add(best_match)
            logger.info(
                f"Matched speaker {chunk_label} to {best_match} "
                f"(similarity: {best_similarity:.4f})"
            )
        else:
            # No match found - keep original label
            label_mapping[chunk_label] = chunk_label
            logger.info(
                f"No match for speaker {chunk_label} - treating as new speaker"
            )

    return label_mapping


def _diarize_single_chunk(
    wav_bytes: bytes,
    client: WorkspaceClient,
    endpoint_name: str,
    reference_embeddings: dict[str, list[float]] | None = None,
    chunk_index: int = 0,
) -> DiarizeResponse:
    """Send a single audio chunk to Databricks serving endpoint for diarization.

    Args:
        wav_bytes: WAV audio data to diarize.
        client: WorkspaceClient instance.
        endpoint_name: Name of the diarization endpoint.
        reference_embeddings: Optional dict of label -> embedding for cross-chunk matching.
        chunk_index: 0-based index of current chunk (for logging/debugging).

    Returns:
        DiarizeResponse containing dialog, transcription, speaker_embeddings, and status.
    """
    # Encode audio to base64
    audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")

    # Build request payload
    request_data: dict = {"audio_base64": audio_base64}

    # Add reference embeddings for cross-chunk matching (chunks > 0)
    if reference_embeddings and chunk_index > 0:
        request_data["reference_embeddings"] = json.dumps(reference_embeddings)
        request_data["chunk_index"] = chunk_index
        logger.debug(
            f"Chunk {chunk_index}: Passing {len(reference_embeddings)} reference embeddings"
        )

    # Call the serving endpoint
    response = client.serving_endpoints.query(
        name=endpoint_name,
        dataframe_records=[request_data]
    )

    # Validate response format
    if response.predictions is None:
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error="Invalid response: predictions is None",
        )

    if len(response.predictions) == 0:
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error="Invalid response: predictions list is empty",
        )

    prediction = response.predictions[0]

    # Check for error in response (check value, not just key existence)
    if prediction.get("error"):
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error=prediction.get("error", "Unknown error from endpoint"),
        )

    # Check for dialog in response (diarized text with speaker labels)
    if "dialog" not in prediction:
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error="Invalid response: missing 'dialog' key in prediction",
        )

    # Extract speaker embeddings from response (if present)
    speaker_embeddings: dict[str, list[float]] | None = None
    if "speaker_embeddings" in prediction and prediction["speaker_embeddings"]:
        try:
            speaker_embeddings = json.loads(prediction["speaker_embeddings"])
            logger.debug(
                f"Chunk {chunk_index}: Extracted embeddings for "
                f"{len(speaker_embeddings)} speakers"
            )
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse speaker_embeddings: {e}")

    return DiarizeResponse(
        status="success",
        dialog=prediction["dialog"],
        transcription=prediction.get("transcription"),
        speaker_embeddings=speaker_embeddings,
        error=None,
    )


def diarize_audio(wav_bytes: bytes | None) -> DiarizeResponse:
    """Send audio to Databricks serving endpoint for diarization.

    For audio requiring chunking:
    1. Process chunk 0 to get initial speaker embeddings
    2. For chunks 1..N, pass accumulated reference_embeddings
    3. Update reference set with any new speakers detected
    4. Combine dialogs and transcriptions
    5. Return final accumulated speaker_embeddings

    Args:
        wav_bytes: WAV audio data to diarize. Can be None or empty.

    Returns:
        DiarizeResponse with combined results and final speaker embeddings.
    """
    # Handle empty or None input
    if not wav_bytes:
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error="Cannot diarize empty or None audio bytes",
        )

    try:
        settings = get_settings()
        client = WorkspaceClient(
            config=Config(http_timeout_seconds=settings.DIARIZATION_TIMEOUT_SECONDS)
        )

        # Determine chunking strategy
        if settings.ENABLE_AUDIO_CHUNKING:
            # Fixed 60-second chunks (existing behavior)
            chunks = split_audio_into_chunks(wav_bytes, CHUNK_DURATION_SECONDS)
            logger.info(f"Processing {len(chunks)} audio chunks (60s each)")
        else:
            # Hybrid approach: try full audio, fall back to size-based chunking
            max_chunk_duration = _calculate_max_chunk_duration(wav_bytes)

            if max_chunk_duration is None:
                # Audio fits within endpoint limit - send as single request
                chunks = [wav_bytes]
                logger.info(
                    "Processing full audio as single request (chunking disabled)"
                )
            else:
                # Audio too large - chunk to maximum safe size
                chunks = split_audio_into_chunks(wav_bytes, max_chunk_duration)
                logger.info(
                    f"Audio exceeds 16MB limit - processing {len(chunks)} chunks "
                    f"({max_chunk_duration}s each)"
                )

        dialogs = []
        transcriptions = []
        # Track reference embeddings across chunks for consistent speaker labels
        reference_embeddings: dict[str, list[float]] = {}

        for i, chunk in enumerate(chunks):
            logger.info(f"Diarizing chunk {i + 1}/{len(chunks)}")

            # Pass reference embeddings to subsequent chunks
            result = _diarize_single_chunk(
                chunk,
                client,
                settings.DIARIZATION_ENDPOINT,
                reference_embeddings=reference_embeddings if i > 0 else None,
                chunk_index=i,
            )

            if result.status == "error":
                return DiarizeResponse(
                    status="error",
                    dialog=None,
                    transcription=None,
                    speaker_embeddings=None,
                    error=f"Chunk {i + 1} failed: {result.error}",
                )

            if result.dialog:
                dialogs.append(result.dialog)
            if result.transcription:
                transcriptions.append(result.transcription)

            # Accumulate speaker embeddings
            if result.speaker_embeddings:
                if i == 0:
                    # First chunk - all speakers become reference
                    reference_embeddings = result.speaker_embeddings.copy()
                    logger.info(
                        f"Chunk 0: Initialized reference with "
                        f"{len(reference_embeddings)} speakers: "
                        f"{list(reference_embeddings.keys())}"
                    )
                else:
                    # Subsequent chunks - add any new speakers to reference
                    for label, embedding in result.speaker_embeddings.items():
                        if label not in reference_embeddings:
                            reference_embeddings[label] = embedding
                            logger.info(
                                f"Chunk {i}: Added new speaker {label} to reference"
                            )

        # Combine all dialogs and transcriptions
        combined_dialog = "\n".join(dialogs)
        combined_transcription = " ".join(transcriptions) if transcriptions else None

        return DiarizeResponse(
            status="success",
            dialog=combined_dialog,
            transcription=combined_transcription,
            speaker_embeddings=reference_embeddings if reference_embeddings else None,
            error=None,
        )

    except AudioProcessingError as e:
        logger.error(f"Audio processing failed: {e}", exc_info=True)
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Diarization failed: {e}", exc_info=True)
        return DiarizeResponse(
            status="error",
            dialog=None,
            transcription=None,
            speaker_embeddings=None,
            error=str(e),
        )
