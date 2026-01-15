"""Recording service for Audio Conversation RAG System.

This module provides CRUD operations for Recording and Transcript models,
handling database persistence and retrieval of audio recording metadata
and their associated transcripts.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models import ProcessingStatus, Recording, Transcript
from src.models.speaker_embedding import SpeakerEmbedding
from src.services.audio import (
    convert_to_wav,
    diarize_audio,
)
from src.services.dialog_parser import process_dialog
from src.services.embedding import (
    chunk_dialog,
    delete_recording_chunks,
    store_transcript_chunks,
)
from src.services.reconstruction import reconstruct_transcript

logger = logging.getLogger(__name__)


def create_recording(
    session: Session,
    title: str,
    original_filename: str,
    volume_path: str,
    uploaded_by: str | None = None,
    duration_seconds: float | None = None,
) -> Recording:
    """Create and persist a new Recording instance.

    Args:
        session: SQLAlchemy database session.
        title: Title of the recording.
        original_filename: Original name of the uploaded audio file.
        volume_path: Path to the audio file in Databricks UC Volumes.
        uploaded_by: Email or identifier of the user who uploaded the recording.
            Defaults to None.
        duration_seconds: Duration of the audio in seconds. Defaults to None
            if not yet determined.

    Returns:
        Recording: The created and persisted Recording instance with
            a generated UUID and PENDING processing status.
    """
    recording = Recording(
        title=title,
        original_filename=original_filename,
        volume_path=volume_path,
        uploaded_by=uploaded_by,
        duration_seconds=duration_seconds,
    )
    session.add(recording)
    session.commit()
    session.refresh(recording)
    return recording


def update_recording_status(
    session: Session,
    recording_id: str,
    status: ProcessingStatus,
) -> Recording:
    """Update the processing status of a recording.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording to update.
        status: New ProcessingStatus to set.

    Returns:
        Recording: The updated Recording instance.

    Raises:
        ValueError: If no recording is found with the given ID.
    """
    recording = session.query(Recording).filter_by(id=recording_id).first()
    if recording is None:
        raise ValueError(f"Recording not found: {recording_id}")

    recording.processing_status = status.value
    recording.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(recording)
    return recording


def create_transcript(
    session: Session,
    recording_id: str,
    full_text: str,
    diarized_text: str | None = None,
    language: str | None = None,
    summary: str | None = None,
) -> Transcript:
    """Create and persist a new Transcript linked to a recording.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the parent Recording.
        full_text: The complete transcript text.
        diarized_text: Speaker-diarized transcript with timestamps.
            Defaults to None.
        language: Detected language code (e.g., 'en'). Defaults to None.
        summary: Generated summary of the transcript. Defaults to None.

    Returns:
        Transcript: The created and persisted Transcript instance.

    Raises:
        ValueError: If no recording is found with the given ID.
    """
    # Verify the recording exists
    recording = session.query(Recording).filter_by(id=recording_id).first()
    if recording is None:
        raise ValueError(f"Recording not found: {recording_id}")

    transcript = Transcript(
        recording_id=recording_id,
        full_text=full_text,
        diarized_text=diarized_text,
        language=language,
        summary=summary,
    )
    session.add(transcript)
    session.commit()
    session.refresh(transcript)
    return transcript


def get_recording(session: Session, recording_id: str) -> Recording | None:
    """Retrieve a recording by its ID.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording to retrieve.

    Returns:
        Recording | None: The Recording instance if found, None otherwise.
    """
    return session.query(Recording).filter_by(id=recording_id).first()


def format_eta(eta_seconds: float | None) -> str:
    """Format ETA seconds into human-readable string.

    Args:
        eta_seconds: Seconds remaining, or None if unknown.

    Returns:
        Formatted string like "~2m 30s remaining" or "Calculating..."
    """
    if eta_seconds is None:
        return "Calculating..."

    if eta_seconds <= 0:
        return "Almost done..."

    if eta_seconds < 60:
        return f"~{int(eta_seconds)}s remaining"
    elif eta_seconds < 3600:
        minutes = int(eta_seconds // 60)
        seconds = int(eta_seconds % 60)
        return f"~{minutes}m {seconds}s remaining"
    else:
        hours = int(eta_seconds // 3600)
        minutes = int((eta_seconds % 3600) // 60)
        return f"~{hours}h {minutes}m remaining"


def calculate_processing_progress(recording: Recording) -> dict:
    """Calculate processing progress and ETA for a recording.

    Uses time-based estimation assuming diarization takes ~1:1 with audio duration.

    Phase weights (approximate time distribution):
        - PENDING: 0%
        - CONVERTING: 5% (quick, ~10 seconds)
        - DIARIZING: 90% (main bottleneck, ~1:1 with audio duration)
        - EMBEDDING: 5% (quick, ~5 seconds)

    Args:
        recording: The Recording instance to calculate progress for.

    Returns:
        dict with keys:
            - progress_percent: 0-100 percentage of estimated completion
            - eta_seconds: Estimated seconds remaining (None if unknown)
            - status_text: Human-readable status with progress
    """
    status = recording.processing_status

    # Terminal states
    if status == ProcessingStatus.COMPLETED.value:
        return {
            "progress_percent": 100,
            "eta_seconds": None,
            "status_text": "Processing complete",
        }

    if status == ProcessingStatus.FAILED.value:
        return {
            "progress_percent": 0,
            "eta_seconds": None,
            "status_text": "Processing failed",
        }

    if status == ProcessingStatus.PENDING.value:
        return {
            "progress_percent": 0,
            "eta_seconds": None,
            "status_text": "Waiting to start...",
        }

    # Phase boundaries (cumulative percentages)
    CONVERTING_END = 5
    DIARIZING_START = 5
    DIARIZING_END = 95
    EMBEDDING_START = 95

    # Calculate elapsed time since processing started
    started_at = recording.processing_started_at
    if started_at is None:
        elapsed_seconds = 0.0
    else:
        now = datetime.now(UTC)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        elapsed_seconds = (now - started_at).total_seconds()

    audio_duration = recording.duration_seconds or 0.0

    # Estimated phase durations (in seconds)
    converting_duration = 10.0
    diarizing_duration = max(audio_duration / 4, 8.0)  # ~4x faster after optimization
    embedding_duration = 5.0
    total_estimated = converting_duration + diarizing_duration + embedding_duration

    if status == ProcessingStatus.CONVERTING.value:
        phase_elapsed = min(elapsed_seconds, converting_duration)
        phase_progress = (phase_elapsed / converting_duration) * 100
        overall_progress = (phase_progress / 100) * CONVERTING_END
        remaining = total_estimated - elapsed_seconds
        return {
            "progress_percent": min(overall_progress, CONVERTING_END),
            "eta_seconds": max(remaining, 0),
            "status_text": "Converting audio...",
        }

    elif status == ProcessingStatus.DIARIZING.value:
        diarizing_elapsed = max(elapsed_seconds - converting_duration, 0)
        phase_progress = (diarizing_elapsed / diarizing_duration) * 100
        overall_progress = DIARIZING_START + (phase_progress / 100) * (
            DIARIZING_END - DIARIZING_START
        )
        remaining_diarizing = max(diarizing_duration - diarizing_elapsed, 0)
        remaining = remaining_diarizing + embedding_duration
        return {
            "progress_percent": min(overall_progress, DIARIZING_END),
            "eta_seconds": max(remaining, 0),
            "status_text": "Transcribing and diarizing...",
        }

    elif status == ProcessingStatus.EMBEDDING.value:
        embedding_elapsed = max(
            elapsed_seconds - converting_duration - diarizing_duration, 0
        )
        phase_progress = (embedding_elapsed / embedding_duration) * 100
        overall_progress = EMBEDDING_START + (phase_progress / 100) * (
            100 - EMBEDDING_START
        )
        remaining = max(embedding_duration - embedding_elapsed, 0)
        return {
            "progress_percent": min(overall_progress, 100),
            "eta_seconds": max(remaining, 0),
            "status_text": "Creating embeddings...",
        }

    # Fallback for unknown status
    return {
        "progress_percent": 0,
        "eta_seconds": None,
        "status_text": "Unknown status",
    }


def list_recordings(
    session: Session,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> list[Recording]:
    """List recordings with pagination and configurable sorting.

    Args:
        session: SQLAlchemy database session.
        limit: Maximum number of recordings to return. Defaults to 50.
        offset: Number of recordings to skip for pagination. Defaults to 0.
        sort_by: Column name to sort by. Valid values are "created_at",
            "title", or "duration_seconds". Defaults to "created_at".
        sort_order: Sort direction. Valid values are "asc" or "desc".
            Defaults to "desc".

    Returns:
        list[Recording]: List of Recording instances ordered by the specified
            column and direction.

    Raises:
        ValueError: If sort_by is not a valid column name or sort_order is
            not "asc" or "desc".
    """
    valid_sort_columns = {"created_at", "title", "duration_seconds"}
    valid_sort_orders = {"asc", "desc"}

    if sort_by not in valid_sort_columns:
        raise ValueError(
            f"Invalid sort_by value: {sort_by}. "
            f"Must be one of: {', '.join(sorted(valid_sort_columns))}"
        )

    if sort_order not in valid_sort_orders:
        raise ValueError(
            f"Invalid sort_order value: {sort_order}. "
            f"Must be one of: {', '.join(sorted(valid_sort_orders))}"
        )

    column = getattr(Recording, sort_by)
    order_func = column.asc() if sort_order == "asc" else column.desc()

    return (
        session.query(Recording)
        .order_by(order_func)
        .offset(offset)
        .limit(limit)
        .all()
    )


def _update_recording_with_error(
    session: Session,
    recording: Recording,
    error_message: str,
) -> Recording:
    """Update a recording with FAILED status and error message.

    Args:
        session: SQLAlchemy database session.
        recording: The Recording instance to update.
        error_message: The error message to store.

    Returns:
        Recording: The updated Recording instance.
    """
    recording.processing_status = ProcessingStatus.FAILED.value
    recording.error_message = error_message
    recording.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(recording)
    return recording


def process_recording(
    session: Session,
    recording_id: str,
    audio_bytes: bytes,
) -> Recording:
    """Orchestrate the full processing pipeline for a recording.

    This function manages the complete workflow from audio conversion through
    embedding storage, updating the recording status at each step.

    Processing steps:
    1. Update status to CONVERTING
    2. Convert audio to WAV format and extract duration
    3. Update recording.duration_seconds
    4. Update status to DIARIZING
    5. Perform speaker diarization to get transcription
    6. Update status to EMBEDDING
    7. Create transcript record in database
    8. Chunk the transcript text
    9. Create LangChain documents with metadata
    10. Store embeddings in pgvector
    11. Update status to COMPLETED
    12. Return the updated recording

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording to process.
        audio_bytes: Raw audio data bytes to process.

    Returns:
        Recording: The fully processed Recording instance with COMPLETED status.

    Raises:
        ValueError: If no recording is found with the given ID.
        AudioProcessingError: If audio conversion or upload fails.
        EmbeddingError: If embedding storage fails.
        Exception: Any other exception that occurs during processing.
            The recording status will be set to FAILED before re-raising.
    """
    # Fetch the recording
    recording = session.query(Recording).filter_by(id=recording_id).first()
    if recording is None:
        raise ValueError(f"Recording not found: {recording_id}")

    logger.info(f"Starting processing pipeline for recording {recording_id}")

    try:
        # Step 1: Update status to CONVERTING and set processing start time
        logger.debug(f"Recording {recording_id}: Starting audio conversion")
        recording.processing_status = ProcessingStatus.CONVERTING.value
        recording.processing_started_at = datetime.now(UTC)
        recording.updated_at = datetime.now(UTC)
        session.commit()

        # Step 2: Convert to WAV and get duration
        wav_bytes, duration_seconds = convert_to_wav(audio_bytes)
        logger.info(
            f"Recording {recording_id}: Converted to WAV, "
            f"duration: {duration_seconds:.2f}s"
        )

        # Step 3: Update duration
        recording.duration_seconds = duration_seconds
        session.commit()

        # Step 4: Update status to DIARIZING
        logger.debug(f"Recording {recording_id}: Starting diarization")
        recording.processing_status = ProcessingStatus.DIARIZING.value
        recording.updated_at = datetime.now(UTC)
        session.commit()

        # Step 7: Perform diarization
        diarize_response = diarize_audio(wav_bytes)
        if diarize_response.status != "success":
            error_msg = f"Diarization failed: {diarize_response.error}"
            logger.error(f"Recording {recording_id}: {error_msg}")
            raise RuntimeError(error_msg)

        dialog_text = diarize_response.dialog
        raw_transcription = diarize_response.transcription
        speaker_embeddings = diarize_response.speaker_embeddings
        logger.info(
            f"Recording {recording_id}: Diarization complete, "
            f"dialog length: {len(dialog_text or '')} chars"
        )

        # Step 7.5: Save speaker embeddings (if available)
        if speaker_embeddings:
            save_speaker_embeddings(session, recording_id, speaker_embeddings)
            logger.info(
                f"Recording {recording_id}: Saved {len(speaker_embeddings)} speaker embeddings"
            )

        # Step 8: Parse and roll up dialog into structured JSON
        dialog_json = process_dialog(dialog_text or "")
        logger.debug(
            f"Recording {recording_id}: Parsed {len(dialog_json)} speaker turns"
        )

        # Step 8.5: Reconstruct transcript using LLM to align clean text with speakers
        reconstructed_dialog_json = reconstruct_transcript(
            full_text=raw_transcription or "",
            dialog_json=dialog_json,
        )
        logger.info(
            f"Recording {recording_id}: Reconstructed {len(reconstructed_dialog_json)} turns"
        )

        # Step 9: Update status to EMBEDDING
        logger.debug(f"Recording {recording_id}: Starting embedding process")
        recording.processing_status = ProcessingStatus.EMBEDDING.value
        recording.updated_at = datetime.now(UTC)
        session.commit()

        # Step 10: Create transcript record with new fields
        transcript = Transcript(
            recording_id=recording_id,
            full_text=raw_transcription or "",  # Raw Whisper output
            diarized_text=dialog_text,  # Raw diarized text for debugging
            dialog_json=dialog_json,  # Rolled-up structured JSON
            reconstructed_dialog_json=reconstructed_dialog_json,  # LLM-reconstructed clean text
        )
        session.add(transcript)
        session.commit()
        logger.debug(f"Recording {recording_id}: Created transcript record")

        # Step 11: Chunk the dialog with speaker context
        # Prefer reconstructed_dialog_json for embedding (cleaner text = better search)
        embedding_source = (
            reconstructed_dialog_json if reconstructed_dialog_json else dialog_json
        )
        chunks = chunk_dialog(embedding_source)
        logger.debug(
            f"Recording {recording_id}: Created {len(chunks)} chunks from "
            f"{'reconstructed' if reconstructed_dialog_json else 'original'} dialog"
        )

        # Step 12: Store chunks with embeddings in transcript_chunks table
        stored_count = store_transcript_chunks(
            session=session,
            recording_id=recording_id,
            chunks=chunks,
            title=recording.title,
        )
        logger.info(
            f"Recording {recording_id}: Stored {stored_count} transcript chunks"
        )

        # Step 13: Update status to COMPLETED
        recording.processing_status = ProcessingStatus.COMPLETED.value
        recording.error_message = None  # Clear any previous error
        recording.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(recording)

        logger.info(f"Recording {recording_id}: Processing pipeline completed")

        # Step 14: Return the updated recording
        return recording

    except Exception as e:
        logger.error(
            f"Recording {recording_id}: Processing failed with error: {e}",
            exc_info=True,
        )
        # Update status to FAILED and store error message
        _update_recording_with_error(session, recording, str(e))
        # Re-raise the exception
        raise


def validate_title(title: str) -> str:
    """Validate and normalize a recording title.

    Args:
        title: The title to validate.

    Returns:
        The stripped/normalized title.

    Raises:
        ValueError: If title is empty, whitespace-only, or exceeds 255 chars.
    """
    stripped_title = title.strip()

    if not stripped_title:
        raise ValueError("Title cannot be empty or whitespace-only")

    if len(stripped_title) > 255:
        raise ValueError("Title cannot exceed 255 characters")

    return stripped_title


def update_recording(
    session: Session,
    recording_id: str,
    title: str | None = None,
) -> Recording:
    """Update a recording's title and timestamp.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording to update.
        title: New title for the recording. If None, title is not changed.

    Returns:
        Recording: The updated Recording instance.

    Raises:
        ValueError: If no recording is found with the given ID, or if
            the title is invalid (empty, whitespace-only, or too long).
    """
    recording = session.query(Recording).filter_by(id=recording_id).first()
    if recording is None:
        raise ValueError(f"Recording not found: {recording_id}")

    if title is not None:
        validated_title = validate_title(title)
        recording.title = validated_title

    recording.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(recording)
    return recording


def delete_recording(session: Session, recording_id: str) -> bool:
    """Delete a recording and all associated data.

    This function performs cascade deletion in the following order:
    1. Delete transcript chunks (embeddings) via delete_recording_chunks()
    2. Delete the recording (transcript cascades via FK)

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording to delete.

    Returns:
        True on successful deletion.

    Raises:
        ValueError: If no recording is found with the given ID.
    """
    recording = session.query(Recording).filter_by(id=recording_id).first()
    if recording is None:
        raise ValueError(f"Recording not found: {recording_id}")

    # Step 1: Delete transcript chunks explicitly
    deleted_chunks = delete_recording_chunks(session, recording_id)
    logger.debug(f"Deleted {deleted_chunks} chunks for recording {recording_id}")

    # Step 2: Delete the recording (transcript cascades via FK)
    session.delete(recording)
    session.commit()

    logger.info(f"Deleted recording {recording_id} from database")

    return True


def save_speaker_embeddings(
    session: Session,
    recording_id: str,
    embeddings: dict[str, list[float]],
) -> list[SpeakerEmbedding]:
    """Persist speaker embeddings for a recording.

    Replaces any existing embeddings for the recording (per spec clarification:
    re-processing replaces embeddings).

    Args:
        session: SQLAlchemy database session.
        recording_id: ID of the parent recording.
        embeddings: Dict mapping speaker labels to embedding vectors.

    Returns:
        List of created SpeakerEmbedding instances.

    Raises:
        ValueError: If no recording is found with the given ID.
    """
    # Verify recording exists
    recording = session.query(Recording).filter_by(id=recording_id).first()
    if recording is None:
        raise ValueError(f"Recording not found: {recording_id}")

    if not embeddings:
        logger.debug(f"No embeddings to save for recording {recording_id}")
        return []

    # Delete existing embeddings first (replace semantics)
    deleted_count = delete_speaker_embeddings(session, recording_id)
    if deleted_count > 0:
        logger.debug(
            f"Deleted {deleted_count} existing embeddings for recording {recording_id}"
        )

    # Create new embedding records
    created_embeddings = []
    for speaker_label, embedding_vector in embeddings.items():
        embedding = SpeakerEmbedding(
            recording_id=recording_id,
            speaker_label=speaker_label,
            embedding_vector=embedding_vector,
        )
        session.add(embedding)
        created_embeddings.append(embedding)

    session.commit()

    # Refresh to get generated IDs
    for embedding in created_embeddings:
        session.refresh(embedding)

    logger.info(
        f"Saved {len(created_embeddings)} speaker embeddings for recording {recording_id}: "
        f"{list(embeddings.keys())}"
    )

    return created_embeddings


def delete_speaker_embeddings(
    session: Session,
    recording_id: str,
) -> int:
    """Delete all speaker embeddings for a recording.

    Args:
        session: SQLAlchemy database session.
        recording_id: ID of the recording.

    Returns:
        Number of embeddings deleted.
    """
    deleted_count = (
        session.query(SpeakerEmbedding)
        .filter_by(recording_id=recording_id)
        .delete()
    )
    session.commit()

    if deleted_count > 0:
        logger.debug(
            f"Deleted {deleted_count} speaker embeddings for recording {recording_id}"
        )

    return deleted_count
