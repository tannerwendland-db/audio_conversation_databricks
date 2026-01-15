"""Recording library component for the Audio Conversation RAG System.

This module provides a Dash component for displaying the library of
audio recordings with status indicators, filtering, and navigation.
"""

import logging
from datetime import datetime
from typing import Any

import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from src.db.session import get_session
from src.models import ProcessingStatus
from src.services.recording import (
    calculate_processing_progress,
    delete_recording,
    format_eta,
    list_recordings,
    update_recording,
)

logger = logging.getLogger(__name__)

# Status color mapping for visual indicators
STATUS_COLORS = {
    ProcessingStatus.PENDING.value: "secondary",  # Gray
    ProcessingStatus.CONVERTING.value: "info",  # Blue
    ProcessingStatus.DIARIZING.value: "primary",  # Blue
    ProcessingStatus.EMBEDDING.value: "primary",  # Blue
    ProcessingStatus.COMPLETED.value: "success",  # Green
    ProcessingStatus.FAILED.value: "danger",  # Red
}

# Human-readable status labels
STATUS_LABELS = {
    ProcessingStatus.PENDING.value: "Pending",
    ProcessingStatus.CONVERTING.value: "Converting",
    ProcessingStatus.DIARIZING.value: "Diarizing",
    ProcessingStatus.EMBEDDING.value: "Embedding",
    ProcessingStatus.COMPLETED.value: "Completed",
    ProcessingStatus.FAILED.value: "Failed",
}

# Sort option mapping (dropdown value -> (sort_by, sort_order))
SORT_OPTIONS = {
    "date-newest": ("created_at", "desc"),
    "date-oldest": ("created_at", "asc"),
    "title-az": ("title", "asc"),
    "title-za": ("title", "desc"),
    "duration-longest": ("duration_seconds", "desc"),
    "duration-shortest": ("duration_seconds", "asc"),
}


def create_library_component() -> dbc.Container:
    """Create the recording library component layout.

    Returns:
        A Dash Bootstrap Container with the library interface including
        recording list, status indicators, and refresh functionality.
    """
    return dbc.Container(
        [
            html.H3("Recording Library", className="mb-4"),
            html.P(
                "View and manage your uploaded audio recordings.",
                className="text-muted mb-3",
            ),
            # Controls row: refresh button and sort dropdown
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            [
                                html.I(className="bi bi-arrow-clockwise me-2"),
                                "Refresh",
                            ],
                            id="refresh-library-button",
                            color="outline-primary",
                            className="mb-3",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dcc.Dropdown(
                            id="library-sort-dropdown",
                            options=[
                                {"label": "Date (Newest)", "value": "date-newest"},
                                {"label": "Date (Oldest)", "value": "date-oldest"},
                                {"label": "Title (A-Z)", "value": "title-az"},
                                {"label": "Title (Z-A)", "value": "title-za"},
                                {"label": "Duration (Longest)", "value": "duration-longest"},
                                {"label": "Duration (Shortest)", "value": "duration-shortest"},
                            ],
                            value="date-newest",
                            clearable=False,
                            className="mb-3",
                            style={"minWidth": "180px"},
                        ),
                        width="auto",
                    ),
                ],
                className="mb-3",
                align="center",
            ),
            # Recording list container
            html.Div(id="recording-list-container"),
            # Auto-refresh interval for library
            dcc.Interval(
                id="library-refresh-interval",
                interval=10000,  # Refresh every 10 seconds
                n_intervals=0,
            ),
            # Store for sort option persistence
            dcc.Store(id="library-sort-store", storage_type="memory"),
            # Store for tracking which recording is being edited
            dcc.Store(id="editing-recording-store", storage_type="memory", data=None),
            # Store for tracking which recording is being deleted
            dcc.Store(id="deleting-recording-store", storage_type="memory", data=None),
            # Delete confirmation modal
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Confirm Delete")),
                    dbc.ModalBody(id="delete-modal-body"),
                    dbc.ModalFooter(
                        [
                            dbc.Button(
                                "Cancel",
                                id="cancel-delete-button",
                                color="secondary",
                                className="me-2",
                            ),
                            dbc.Button(
                                "Delete",
                                id="confirm-delete-button",
                                color="danger",
                            ),
                        ]
                    ),
                ],
                id="delete-confirmation-modal",
                is_open=False,
                centered=True,
            ),
            # Alert for delete success/error
            html.Div(id="library-alert-container"),
            # Location component for programmatic navigation
            dcc.Location(id="library-url", refresh=True),
        ],
        fluid=True,
        className="p-4",
    )


def _format_duration(seconds: float | None) -> str:
    """Format duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds, or None.

    Returns:
        Formatted duration string (e.g., "5:32" or "--:--").
    """
    if seconds is None:
        return "--:--"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def _format_date(dt: datetime | None) -> str:
    """Format a datetime to a human-readable string.

    Args:
        dt: Datetime object or None.

    Returns:
        Formatted date string (e.g., "Dec 18, 2025 10:30 AM").
    """
    if dt is None:
        return "N/A"

    return dt.strftime("%b %d, %Y %I:%M %p")


def _create_recording_card(recording: Any, is_editing: bool = False) -> dbc.Card:
    """Create a card component for a single recording.

    Args:
        recording: Recording model instance.
        is_editing: Whether this recording is currently being edited.

    Returns:
        A Dash Bootstrap Card representing the recording.
    """
    status = recording.processing_status
    status_color = STATUS_COLORS.get(status, "secondary")
    status_label = STATUS_LABELS.get(status, "Unknown")

    # Determine if processing is in progress
    is_processing = status in (
        ProcessingStatus.CONVERTING.value,
        ProcessingStatus.DIARIZING.value,
        ProcessingStatus.EMBEDDING.value,
    )

    # Determine if the recording is clickable (only completed recordings)
    is_clickable = status == ProcessingStatus.COMPLETED.value

    # Build title section based on editing state
    if is_editing:
        title_section = dbc.Col(
            [
                dbc.InputGroup(
                    [
                        dbc.Input(
                            id={"type": "edit-title-input", "index": recording.id},
                            value=recording.title,
                            placeholder="Enter title",
                            className="me-2",
                        ),
                        dbc.Button(
                            html.I(className="bi bi-check"),
                            id={"type": "save-title-btn", "index": recording.id},
                            color="success",
                            size="sm",
                            className="me-1",
                        ),
                        dbc.Button(
                            html.I(className="bi bi-x"),
                            id={"type": "cancel-edit-btn", "index": recording.id},
                            color="secondary",
                            size="sm",
                        ),
                    ],
                    size="sm",
                ),
                html.Small(
                    recording.original_filename,
                    className="text-muted",
                ),
            ],
            width=8,
        )
    else:
        # Both completed and non-completed recordings have buttons inline with title
        title_section = dbc.Col(
            [
                html.Div(
                    [
                        html.H5(
                            recording.title,
                            className="card-title mb-1 d-inline",
                        ),
                        html.Button(
                            html.I(className="bi bi-pencil"),
                            id={"type": "edit-title-btn", "index": recording.id},
                            className="btn btn-link btn-sm p-0 ms-2",
                            style={"border": "none", "fontSize": "0.9rem"},
                            n_clicks=0,
                        ),
                        html.Button(
                            html.I(className="bi bi-trash"),
                            id={"type": "delete-btn", "index": recording.id},
                            className="btn btn-link btn-sm p-0 ms-2 text-danger",
                            style={"border": "none", "fontSize": "0.9rem"},
                            n_clicks=0,
                        ),
                    ],
                ),
                html.Small(
                    recording.original_filename,
                    className="text-muted",
                ),
            ],
            width=8,
        )

    # Build card body content
    card_content = [
        dbc.Row(
            [
                title_section,
                dbc.Col(
                    [
                        dbc.Badge(
                            status_label,
                            color=status_color,
                            className="float-end",
                        ),
                    ],
                    width=4,
                    className="text-end",
                ),
            ],
            className="mb-2",
        ),
        html.Hr(className="my-2"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Small(
                            [
                                html.I(className="bi bi-clock me-1"),
                                _format_duration(recording.duration_seconds),
                            ],
                            className="text-muted me-3",
                        ),
                        html.Small(
                            [
                                html.I(className="bi bi-calendar me-1"),
                                _format_date(recording.created_at),
                            ],
                            className="text-muted",
                        ),
                    ],
                    width=12,
                ),
            ],
        ),
    ]

    # Add "View Transcript" button for completed recordings with transcripts
    if is_clickable and recording.transcript:
        card_content.append(
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Link(
                            dbc.Button(
                                [
                                    html.I(className="bi bi-file-text me-2"),
                                    "View Transcript",
                                ],
                                id={"type": "view-transcript-btn", "index": recording.id},
                                color="outline-primary",
                                size="sm",
                                className="w-100",
                            ),
                            href=f"/transcript/{recording.id}",
                        ),
                        width=12,
                    ),
                ],
                className="mt-2",
            )
        )

    # Add progress bar for processing recordings
    if is_processing:
        progress_info = calculate_processing_progress(recording)
        progress_percent = progress_info["progress_percent"]
        eta_text = format_eta(progress_info["eta_seconds"])
        card_content.append(
            html.Div(
                [
                    dbc.Progress(
                        value=progress_percent,
                        color=status_color,
                        striped=True,
                        animated=True,
                        className="mt-2",
                        style={"height": "8px"},
                    ),
                    html.Small(
                        f"{progress_percent:.0f}% - {eta_text}",
                        className="text-muted d-block mt-1",
                    ),
                ]
            )
        )

    # Add error message for failed recordings
    if status == ProcessingStatus.FAILED.value and recording.error_message:
        card_content.append(
            dbc.Alert(
                [
                    html.Small(
                        [
                            html.Strong("Error: "),
                            recording.error_message[:100],
                            "..." if len(recording.error_message) > 100 else "",
                        ]
                    ),
                ],
                color="danger",
                className="mt-2 mb-0 py-1 px-2",
            )
        )

    # Build card style - add hover effect for clickable cards
    card_style = {"borderLeft": f"4px solid var(--bs-{status_color})"}
    if is_clickable and not is_editing:
        card_style["cursor"] = "pointer"

    # For clickable cards wrapped in a Link, mb-3 is on the outer wrapper
    card_class = "recording-card-clickable" if is_clickable and not is_editing else "mb-3"

    card = dbc.Card(
        dbc.CardBody(card_content),
        id={"type": "recording-card", "index": recording.id},
        className=card_class,
        style=card_style,
    )

    # For completed recordings, card is clickable (handled via callback)
    # No dcc.Link wrapper needed - this prevents button click bubbling
    return card


def _create_empty_state() -> html.Div:
    """Create the empty state display when no recordings exist.

    Returns:
        A Div component with empty state message.
    """
    return html.Div(
        [
            html.I(className="bi bi-music-note-list fs-1 text-muted mb-3"),
            html.H5("No recordings yet", className="text-muted"),
            html.P(
                "Upload an audio file from the Upload tab to get started.",
                className="text-muted",
            ),
        ],
        className="text-center py-5",
    )


@callback(
    Output("recording-list-container", "children"),
    Input("refresh-library-button", "n_clicks"),
    Input("library-refresh-interval", "n_intervals"),
    Input("library-sort-dropdown", "value"),
    State("editing-recording-store", "data"),
)
def refresh_library(
    n_clicks: int | None,
    n_intervals: int,
    sort_value: str | None,
    editing_recording_id: str | None,
) -> Any:
    """Refresh the recording library list.

    Args:
        n_clicks: Number of times the refresh button was clicked.
        n_intervals: Number of interval ticks.
        sort_value: Selected sort option value.
        editing_recording_id: ID of the recording being edited, or None.

    Returns:
        List of recording cards or empty state component.
    """
    # Skip auto-refresh while editing to preserve unsaved input
    if editing_recording_id is not None and ctx.triggered_id == "library-refresh-interval":
        return no_update

    try:
        session = get_session()
        try:
            # Get sort parameters from dropdown value
            sort_by, sort_order = SORT_OPTIONS.get(
                sort_value or "date-newest", ("created_at", "desc")
            )

            recordings = list_recordings(
                session, limit=50, offset=0, sort_by=sort_by, sort_order=sort_order
            )

            if not recordings:
                return _create_empty_state()

            # Create a card for each recording
            recording_cards = [
                _create_recording_card(recording, is_editing=(recording.id == editing_recording_id))
                for recording in recordings
            ]

            return html.Div(recording_cards)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to load recordings: {e}", exc_info=True)
        return dbc.Alert(
            f"Failed to load recordings: {e}",
            color="danger",
        )


@callback(
    Output("editing-recording-store", "data", allow_duplicate=True),
    Input({"type": "edit-title-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_edit_click(n_clicks_list: list[int | None]) -> str | None:
    """Handle click on edit title button.

    Args:
        n_clicks_list: List of n_clicks for all edit buttons.

    Returns:
        The recording ID to edit, or None.
    """
    if not ctx.triggered_id:
        return no_update

    # Check if any button was actually clicked
    if not any(n for n in n_clicks_list if n and n > 0):
        return no_update

    # Get the recording ID from the triggered button
    triggered_id = ctx.triggered_id
    if isinstance(triggered_id, dict) and triggered_id.get("type") == "edit-title-btn":
        return triggered_id.get("index")

    return no_update


@callback(
    Output("editing-recording-store", "data", allow_duplicate=True),
    Input({"type": "cancel-edit-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_cancel_edit(n_clicks_list: list[int | None]) -> None:
    """Handle click on cancel edit button.

    Args:
        n_clicks_list: List of n_clicks for all cancel buttons.

    Returns:
        None to clear the editing state.
    """
    if not ctx.triggered_id:
        return no_update

    # Check if any button was actually clicked
    if not any(n for n in n_clicks_list if n and n > 0):
        return no_update

    return None


@callback(
    Output("editing-recording-store", "data", allow_duplicate=True),
    Output("library-alert-container", "children", allow_duplicate=True),
    Input({"type": "save-title-btn", "index": ALL}, "n_clicks"),
    State({"type": "edit-title-input", "index": ALL}, "value"),
    State("editing-recording-store", "data"),
    prevent_initial_call=True,
)
def handle_save_title(
    n_clicks_list: list[int | None],
    title_values: list[str | None],
    editing_recording_id: str | None,
) -> tuple[None, Any]:
    """Handle click on save title button.

    Args:
        n_clicks_list: List of n_clicks for all save buttons.
        title_values: List of title input values.
        editing_recording_id: ID of the recording being edited.

    Returns:
        Tuple of (None to clear editing state, alert component).
    """
    if not ctx.triggered_id:
        return no_update, no_update

    # Check if any button was actually clicked
    if not any(n for n in n_clicks_list if n and n > 0):
        return no_update, no_update

    if not editing_recording_id:
        return no_update, no_update

    # Get the triggered button's recording ID
    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, dict):
        return no_update, no_update

    recording_id = triggered_id.get("index")
    if recording_id != editing_recording_id:
        return no_update, no_update

    # Find the new title value
    new_title = None
    for val in title_values:
        if val is not None:
            new_title = val
            break

    if not new_title or not new_title.strip():
        return no_update, dbc.Alert(
            "Title cannot be empty.",
            color="warning",
            dismissable=True,
            duration=4000,
        )

    try:
        session = get_session()
        try:
            update_recording(session, recording_id, title=new_title.strip())
            return None, dbc.Alert(
                "Recording title updated successfully.",
                color="success",
                dismissable=True,
                duration=4000,
            )
        finally:
            session.close()
    except ValueError as e:
        logger.error(f"Failed to update recording title: {e}")
        return no_update, dbc.Alert(
            f"Failed to update title: {e}",
            color="danger",
            dismissable=True,
            duration=4000,
        )
    except Exception as e:
        logger.error(f"Failed to update recording title: {e}", exc_info=True)
        return no_update, dbc.Alert(
            f"Failed to update title: {e}",
            color="danger",
            dismissable=True,
            duration=4000,
        )


@callback(
    Output("delete-confirmation-modal", "is_open", allow_duplicate=True),
    Output("deleting-recording-store", "data"),
    Output("delete-modal-body", "children"),
    Input({"type": "delete-btn", "index": ALL}, "n_clicks"),
    State({"type": "delete-btn", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def handle_delete_click(
    n_clicks_list: list[int | None],
    button_ids: list[dict],
) -> tuple[bool, str | None, str]:
    """Handle click on delete button to open confirmation modal.

    Args:
        n_clicks_list: List of n_clicks for all delete buttons.
        button_ids: List of button ID dictionaries.

    Returns:
        Tuple of (modal is_open, recording_id to delete, modal body text).
    """
    if not ctx.triggered_id:
        return no_update, no_update, no_update

    # Check if any button was actually clicked
    if not any(n for n in n_clicks_list if n and n > 0):
        return no_update, no_update, no_update

    # Get the recording ID from the triggered button
    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, dict) or triggered_id.get("type") != "delete-btn":
        return no_update, no_update, no_update

    recording_id = triggered_id.get("index")

    # Get the recording title for the confirmation message
    try:
        session = get_session()
        try:
            from src.services.recording import get_recording

            recording = get_recording(session, recording_id)
            title = recording.title if recording else "this recording"
        finally:
            session.close()
    except Exception:
        title = "this recording"

    modal_body = f"Are you sure you want to delete '{title}'? This action cannot be undone."

    return True, recording_id, modal_body


@callback(
    Output("delete-confirmation-modal", "is_open", allow_duplicate=True),
    Input("cancel-delete-button", "n_clicks"),
    prevent_initial_call=True,
)
def handle_cancel_delete(n_clicks: int | None) -> bool:
    """Handle click on cancel delete button.

    Args:
        n_clicks: Number of times the cancel button was clicked.

    Returns:
        False to close the modal.
    """
    if n_clicks:
        return False
    return no_update


@callback(
    Output("delete-confirmation-modal", "is_open"),
    Output("library-alert-container", "children"),
    Output("refresh-library-button", "n_clicks"),
    Input("confirm-delete-button", "n_clicks"),
    State("deleting-recording-store", "data"),
    State("refresh-library-button", "n_clicks"),
    prevent_initial_call=True,
)
def handle_confirm_delete(
    n_clicks: int | None,
    recording_id: str | None,
    current_refresh_clicks: int | None,
) -> tuple[bool, Any, int]:
    """Handle click on confirm delete button.

    Args:
        n_clicks: Number of times the confirm button was clicked.
        recording_id: ID of the recording to delete.
        current_refresh_clicks: Current n_clicks value of the refresh button.

    Returns:
        Tuple of (modal is_open, alert component, new refresh n_clicks).
    """
    if not n_clicks or not recording_id:
        return no_update, no_update, no_update

    try:
        session = get_session()
        try:
            delete_recording(session, recording_id)
            # Trigger a refresh by incrementing n_clicks
            new_clicks = (current_refresh_clicks or 0) + 1
            return (
                False,
                dbc.Alert(
                    "Recording deleted successfully.",
                    color="success",
                    dismissable=True,
                    duration=4000,
                ),
                new_clicks,
            )
        finally:
            session.close()
    except ValueError as e:
        logger.error(f"Failed to delete recording: {e}")
        return (
            False,
            dbc.Alert(
                f"Failed to delete recording: {e}",
                color="danger",
                dismissable=True,
                duration=4000,
            ),
            no_update,
        )
    except Exception as e:
        logger.error(f"Failed to delete recording: {e}", exc_info=True)
        return (
            False,
            dbc.Alert(
                f"Failed to delete recording: {e}",
                color="danger",
                dismissable=True,
                duration=4000,
            ),
            no_update,
        )


# Callback to refresh list after editing state changes
@callback(
    Output("refresh-library-button", "n_clicks", allow_duplicate=True),
    Input("editing-recording-store", "data"),
    State("refresh-library-button", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_after_edit_state_change(
    editing_id: str | None,
    current_clicks: int | None,
) -> int:
    """Trigger a refresh when editing state changes.

    Args:
        editing_id: ID of the recording being edited, or None.
        current_clicks: Current n_clicks value of the refresh button.

    Returns:
        Incremented n_clicks to trigger refresh.
    """
    return (current_clicks or 0) + 1


@callback(
    Output("library-url", "href"),
    Input({"type": "recording-card", "index": ALL}, "n_clicks"),
    Input({"type": "edit-title-btn", "index": ALL}, "n_clicks"),
    Input({"type": "delete-btn", "index": ALL}, "n_clicks"),
    State("editing-recording-store", "data"),
    State("deleting-recording-store", "data"),
    State("delete-confirmation-modal", "is_open"),
    prevent_initial_call=True,
)
def handle_card_click(
    card_n_clicks_list: list[int | None],
    edit_n_clicks_list: list[int | None],
    delete_n_clicks_list: list[int | None],
    editing_recording_id: str | None,
    deleting_recording_id: str | None,
    delete_modal_open: bool,
) -> str:
    """Handle click on recording card to navigate to recording detail.

    Only navigates if a card was clicked directly, not if a button was clicked.

    Args:
        card_n_clicks_list: List of n_clicks for all recording cards.
        edit_n_clicks_list: List of n_clicks for all edit buttons.
        delete_n_clicks_list: List of n_clicks for all delete buttons.
        editing_recording_id: ID of the recording being edited, or None.
        deleting_recording_id: ID of the recording being deleted, or None.
        delete_modal_open: Whether the delete confirmation modal is open.

    Returns:
        URL to navigate to, or no_update.
    """
    if not ctx.triggered_id:
        return no_update

    # Check if any card was actually clicked (n_clicks > 0)
    # This prevents navigation when components are first rendered
    if not any(n for n in card_n_clicks_list if n and n > 0):
        return no_update

    # Check what was triggered - only navigate if it was a card click
    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, dict):
        return no_update

    # If a button was clicked, don't navigate
    if triggered_id.get("type") in ("edit-title-btn", "delete-btn"):
        return no_update

    # Don't navigate if we're in editing mode or delete modal is open
    if editing_recording_id or deleting_recording_id or delete_modal_open:
        return no_update

    # Check if a card was clicked
    if triggered_id.get("type") == "recording-card":
        recording_id = triggered_id.get("index")
        if recording_id:
            # Only navigate if recording is completed
            try:
                session = get_session()
                try:
                    from src.services.recording import get_recording

                    recording = get_recording(session, recording_id)
                    is_completed = (
                        recording
                        and recording.processing_status == ProcessingStatus.COMPLETED.value
                    )
                    if is_completed:
                        return f"/recording/{recording_id}"
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Failed to check recording status: {e}")

    return no_update
