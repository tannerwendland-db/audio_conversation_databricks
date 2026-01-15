"""Audio upload component for the Audio Conversation RAG System.

This module provides a Dash component for uploading audio files with
drag-and-drop support, file validation, background processing, and
status display with progress indicators.
"""

import base64
import logging
import threading
from typing import Any

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from src.db.session import get_session
from src.models import ProcessingStatus
from src.services.audio import AudioValidationError, validate_file_format
from src.services.recording import (
    calculate_processing_progress,
    create_recording,
    format_eta,
    get_recording,
    process_recording,
)

logger = logging.getLogger(__name__)

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = ".mp3, .wav, .m4a, .flac"


def create_upload_component() -> dbc.Container:
    """Create the audio upload component layout.

    Returns:
        A Dash Bootstrap Container with the upload interface including
        drag-and-drop area, status display, and polling interval.
    """
    return dbc.Container(
        [
            html.H3("Upload Audio Recording", className="mb-4"),
            html.P(
                f"Supported formats: {ALLOWED_EXTENSIONS}",
                className="text-muted mb-3",
            ),
            # Upload area with drag-and-drop
            dcc.Upload(
                id="audio-upload",
                children=html.Div(
                    [
                        html.I(className="bi bi-cloud-upload fs-1 mb-3"),
                        html.Br(),
                        html.Span("Drag and drop an audio file here, or "),
                        html.A("click to select", className="text-primary"),
                    ],
                    className="text-center py-5",
                ),
                style={
                    "width": "100%",
                    "height": "200px",
                    "lineHeight": "60px",
                    "borderWidth": "2px",
                    "borderStyle": "dashed",
                    "borderRadius": "10px",
                    "borderColor": "#6c757d",
                    "textAlign": "center",
                    "cursor": "pointer",
                    "backgroundColor": "#f8f9fa",
                },
                multiple=False,
                accept=ALLOWED_EXTENSIONS,
            ),
            # Title input for the recording
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Recording Title (optional)", className="mt-3"),
                            dbc.Input(
                                id="recording-title-input",
                                type="text",
                                placeholder="Enter a title for this recording...",
                            ),
                        ],
                        width=12,
                    ),
                ],
                className="mb-3",
            ),
            # Upload status message
            html.Div(id="upload-status-message", className="mt-3"),
            # Processing status display
            html.Div(id="processing-status-container", className="mt-3"),
            # Store for tracking current recording ID
            dcc.Store(id="current-recording-id", storage_type="memory"),
            # Interval for polling processing status
            dcc.Interval(
                id="processing-status-interval",
                interval=2000,  # Poll every 2 seconds
                n_intervals=0,
                disabled=True,  # Disabled until processing starts
            ),
        ],
        fluid=True,
        className="p-4",
    )


def _run_processing_in_background(recording_id: str, audio_bytes: bytes) -> None:
    """Run the processing pipeline in a background thread.

    Args:
        recording_id: UUID of the recording to process.
        audio_bytes: Raw audio data bytes to process.
    """
    try:
        session = get_session()
        try:
            process_recording(session, recording_id, audio_bytes)
            logger.info(f"Background processing completed for recording {recording_id}")
        finally:
            session.close()
    except Exception as e:
        logger.error(
            f"Background processing failed for recording {recording_id}: {e}",
            exc_info=True,
        )


def _get_status_color(status: str) -> str:
    """Get Bootstrap color class for a processing status.

    Args:
        status: The processing status string.

    Returns:
        Bootstrap color class string.
    """
    status_colors = {
        ProcessingStatus.PENDING.value: "secondary",
        ProcessingStatus.CONVERTING.value: "info",
        ProcessingStatus.DIARIZING.value: "primary",
        ProcessingStatus.EMBEDDING.value: "primary",
        ProcessingStatus.COMPLETED.value: "success",
        ProcessingStatus.FAILED.value: "danger",
    }
    return status_colors.get(status, "secondary")


def _get_status_display_text(status: str) -> str:
    """Get human-readable display text for a processing status.

    Args:
        status: The processing status string.

    Returns:
        Human-readable status text.
    """
    status_text = {
        ProcessingStatus.PENDING.value: "Pending",
        ProcessingStatus.CONVERTING.value: "Converting audio...",
        ProcessingStatus.DIARIZING.value: "Transcribing and diarizing...",
        ProcessingStatus.EMBEDDING.value: "Creating embeddings...",
        ProcessingStatus.COMPLETED.value: "Processing complete!",
        ProcessingStatus.FAILED.value: "Processing failed",
    }
    return status_text.get(status, "Unknown status")


@callback(
    Output("upload-status-message", "children"),
    Output("current-recording-id", "data"),
    Output("processing-status-interval", "disabled"),
    Input("audio-upload", "contents"),
    State("audio-upload", "filename"),
    State("recording-title-input", "value"),
    prevent_initial_call=True,
)
def handle_upload(
    contents: str | None,
    filename: str | None,
    title: str | None,
) -> tuple[Any, str | None, bool]:
    """Handle file upload, validate, and trigger background processing.

    Args:
        contents: Base64 encoded file contents from dcc.Upload.
        filename: Original filename of the uploaded file.
        title: Optional title provided by the user.

    Returns:
        Tuple of (status_message, recording_id, interval_disabled).
    """
    if contents is None or filename is None:
        return None, None, True

    # Decode the file contents
    try:
        content_type, content_string = contents.split(",")
        audio_bytes = base64.b64decode(content_string)
    except Exception as e:
        logger.error(f"Failed to decode uploaded file: {e}", exc_info=True)
        return (
            dbc.Alert(
                "Failed to process the uploaded file. Please try again.",
                color="danger",
            ),
            None,
            True,
        )

    # Validate file format and size
    file_size = len(audio_bytes)
    try:
        validate_file_format(filename, file_size)
    except AudioValidationError as e:
        logger.warning(f"File validation failed for {filename}: {e}")
        return (
            dbc.Alert(str(e), color="danger"),
            None,
            True,
        )

    # Use filename as title if no title provided
    recording_title = title.strip() if title and title.strip() else filename

    # Create the recording in the database
    try:
        session = get_session()
        try:
            recording = create_recording(
                session=session,
                title=recording_title,
                original_filename=filename,
                volume_path="pending",  # Will be updated during processing
            )
            recording_id = recording.id
            logger.info(f"Created recording {recording_id} for file {filename}")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to create recording: {e}", exc_info=True)
        return (
            dbc.Alert(
                "Failed to save the recording. Please try again.",
                color="danger",
            ),
            None,
            True,
        )

    # Start background processing
    thread = threading.Thread(
        target=_run_processing_in_background,
        args=(recording_id, audio_bytes),
        daemon=True,
    )
    thread.start()

    return (
        dbc.Alert(
            f"Upload successful! Processing '{recording_title}'...",
            color="success",
        ),
        recording_id,
        False,  # Enable polling interval
    )


@callback(
    Output("processing-status-container", "children"),
    Output("processing-status-interval", "disabled", allow_duplicate=True),
    Input("processing-status-interval", "n_intervals"),
    State("current-recording-id", "data"),
    prevent_initial_call=True,
)
def update_processing_status(
    n_intervals: int,
    recording_id: str | None,
) -> tuple[Any, bool]:
    """Poll and display the current processing status.

    Args:
        n_intervals: Number of interval ticks (used to trigger update).
        recording_id: UUID of the recording being processed.

    Returns:
        Tuple of (status_display, interval_disabled).
    """
    if not recording_id:
        return None, True

    try:
        session = get_session()
        try:
            recording = get_recording(session, recording_id)
            if recording is None:
                return (
                    dbc.Alert("Recording not found.", color="warning"),
                    True,
                )

            status = recording.processing_status
            color = _get_status_color(status)

            # Get progress information
            progress_info = calculate_processing_progress(recording)
            progress_percent = progress_info["progress_percent"]
            eta_seconds = progress_info["eta_seconds"]
            status_text = progress_info["status_text"]

            # Build status display
            status_components = [
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Processing Status", className="card-title"),
                            dbc.Badge(
                                status_text,
                                color=color,
                                className="mb-2 fs-6",
                            ),
                        ]
                    ),
                    className="mb-3",
                )
            ]

            # Add progress indicator for in-progress statuses
            if status not in (
                ProcessingStatus.COMPLETED.value,
                ProcessingStatus.FAILED.value,
            ):
                eta_text = format_eta(eta_seconds)
                status_components.append(
                    html.Div(
                        [
                            dbc.Progress(
                                value=progress_percent,
                                color=color,
                                striped=True,
                                animated=True,
                                className="mb-2",
                                style={"height": "20px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        f"{progress_percent:.0f}%",
                                        className="text-muted me-3",
                                    ),
                                    html.Span(
                                        eta_text,
                                        className="text-muted",
                                    ),
                                ],
                                className="d-flex justify-content-between",
                            ),
                        ],
                        className="mb-3",
                    )
                )

            # Add error message for failed status
            if status == ProcessingStatus.FAILED.value and recording.error_message:
                status_components.append(
                    dbc.Alert(
                        [
                            html.Strong("Error: "),
                            recording.error_message,
                        ],
                        color="danger",
                        className="mb-3",
                    )
                )

            # Stop polling if processing is complete or failed
            interval_disabled = status in (
                ProcessingStatus.COMPLETED.value,
                ProcessingStatus.FAILED.value,
            )

            return html.Div(status_components), interval_disabled

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to fetch processing status: {e}", exc_info=True)
        return (
            dbc.Alert("Failed to fetch processing status.", color="warning"),
            True,
        )
