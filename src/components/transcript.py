"""Transcript viewer component for the Audio Conversation RAG System.

This module provides a Dash component for displaying transcripts with
speaker diarization, keyword search with highlighting, and metadata panel.
"""

import logging
import re
from datetime import datetime
from typing import Any

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from src.db.session import get_session
from src.models import ProcessingStatus
from src.services.recording import get_recording
from src.services.transcript import search_transcript

logger = logging.getLogger(__name__)

# Status color mapping for visual indicators
STATUS_COLORS = {
    ProcessingStatus.PENDING.value: "secondary",
    ProcessingStatus.CONVERTING.value: "info",
    ProcessingStatus.DIARIZING.value: "primary",
    ProcessingStatus.EMBEDDING.value: "primary",
    ProcessingStatus.COMPLETED.value: "success",
    ProcessingStatus.FAILED.value: "danger",
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

# 10-color accessible palette for multi-speaker support
# Material Design 100-level colors for good contrast with dark text
SPEAKER_PALETTE = [
    {"backgroundColor": "#e3f2fd", "name": "Light Blue"},      # 0: Interviewer
    {"backgroundColor": "#f5f5f5", "name": "Light Gray"},      # 1: Respondent
    {"backgroundColor": "#e8f5e9", "name": "Light Green"},     # 2: Extended palette
    {"backgroundColor": "#fff8e1", "name": "Light Amber"},     # 3: Extended palette
    {"backgroundColor": "#f3e5f5", "name": "Light Purple"},    # 4: Extended palette
    {"backgroundColor": "#e0f2f1", "name": "Light Teal"},      # 5: Extended palette
    {"backgroundColor": "#fce4ec", "name": "Light Pink"},      # 6: Extended palette
    {"backgroundColor": "#e0f7fa", "name": "Light Cyan"},      # 7: Extended palette
    {"backgroundColor": "#f9fbe7", "name": "Light Lime"},      # 8: Extended palette
    {"backgroundColor": "#fff3e0", "name": "Light Orange"},    # 9: Extended palette
]

# Fixed color assignments for backward compatibility
FIXED_SPEAKER_COLORS = {
    "interviewer": 0,  # Light Blue
    "respondent": 1,   # Light Gray
}


def get_speaker_color_index(speaker_label: str) -> int:
    """Get deterministic color index for a speaker label.

    Uses fixed assignments for Interviewer/Respondent to maintain backward
    compatibility, and a deterministic hash for other speakers.

    Args:
        speaker_label: The speaker label (e.g., "Interviewer", "Respondent2").

    Returns:
        Index into SPEAKER_PALETTE (0-9).
    """
    label_lower = speaker_label.lower()

    # Check for fixed speaker colors (backward compatibility)
    if label_lower in FIXED_SPEAKER_COLORS:
        return FIXED_SPEAKER_COLORS[label_lower]

    # Use sum of character codes for cross-session determinism
    # (Python's built-in hash() is not deterministic across sessions)
    hash_value = sum(ord(c) for c in label_lower)

    # Skip first 2 colors (reserved for Interviewer/Respondent) and use remaining
    return 2 + (hash_value % (len(SPEAKER_PALETTE) - 2))


def format_speaker_label(speaker_label: str) -> str:
    """Format speaker label for display (add space before numbers).

    Args:
        speaker_label: The raw speaker label (e.g., "Respondent2").

    Returns:
        Formatted label with space before numbers (e.g., "Respondent 2").
    """
    # Add space before digit if preceded by a non-digit, non-space character
    # Uses negative lookbehind to skip if there's already a space before the digit
    return re.sub(r"([^\s\d])(\d)", r"\1 \2", speaker_label)


def get_speaker_style(speaker_label: str) -> dict:
    """Get style dict for a speaker label.

    Args:
        speaker_label: The speaker label (e.g., "Interviewer", "Respondent2").

    Returns:
        Style dict with backgroundColor, textAlign, marginLeft, marginRight.
    """
    index = get_speaker_color_index(speaker_label)
    base_style = {"backgroundColor": SPEAKER_PALETTE[index]["backgroundColor"]}

    # Position: Interviewer left-aligned, others right-aligned
    if speaker_label.lower() == "interviewer":
        base_style.update({
            "marginRight": "20%",
            "marginLeft": "0",
            "textAlign": "left",
        })
    else:
        base_style.update({
            "marginLeft": "20%",
            "marginRight": "0",
            "textAlign": "left",
        })

    return base_style


# Legacy speaker styling configuration (deprecated, use get_speaker_style instead)
SPEAKER_STYLES = {
    "interviewer": {
        "backgroundColor": "#e3f2fd",
        "textAlign": "left",
        "marginRight": "20%",
        "marginLeft": "0",
    },
    "respondent": {
        "backgroundColor": "#f5f5f5",
        "textAlign": "left",
        "marginLeft": "20%",
        "marginRight": "0",
    },
}


def _highlight_matches_safe(text: str, query: str) -> list:
    """Return text with query matches as Dash components (XSS-safe).

    Dash automatically escapes text content when rendering, so we don't need
    to manually escape. We just wrap matches in html.Mark components.

    Args:
        text: The text to highlight.
        query: The search query to highlight.

    Returns:
        A list of Dash components (strings and html.Mark elements).
    """
    if not text or not query or not query.strip():
        return [text] if text else []

    # Escape regex special characters in query for pattern matching
    escaped_query = re.escape(query)

    parts = []
    last_end = 0
    for match in re.finditer(escaped_query, text, re.IGNORECASE):
        # Add text before the match
        if match.start() > last_end:
            parts.append(text[last_end:match.start()])
        # Add the highlighted match using Dash component
        parts.append(html.Mark(match.group()))
        last_end = match.end()

    # Add remaining text after last match
    if last_end < len(text):
        parts.append(text[last_end:])

    return parts if parts else [text]


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
    hours = int(minutes // 60)
    minutes = minutes % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
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


def _convert_dialog_json_to_turns(dialog_json: list[dict]) -> list[dict]:
    """Convert dialog_json to turns format for UI rendering.

    Args:
        dialog_json: List of dicts with 'speaker' and 'text' keys.

    Returns:
        List of dicts with 'speaker', 'speaker_type', 'timestamp', 'text' keys.
    """
    turns = []
    for item in dialog_json:
        speaker = item.get("speaker", "Unknown")
        speaker_lower = speaker.lower()
        speaker_type = "interviewer" if "interviewer" in speaker_lower else "respondent"

        turns.append({
            "speaker": speaker,
            "speaker_type": speaker_type,
            "timestamp": None,  # Not preserved in rolled-up format
            "text": item.get("text", ""),
        })

    return turns


def _parse_speaker_turns(diarized_text: str) -> list[dict]:
    """Parse diarized text into individual speaker turns.

    Handles formats like:
    - "SPEAKER_00: [00:00:01] Hello..."
    - "Interviewer: Hello..."
    - "Respondent: Hi there..."

    This is a fallback for when dialog_json is not available.

    Args:
        diarized_text: The raw diarized transcript text.

    Returns:
        List of dicts with 'speaker', 'timestamp', and 'text' keys.
    """
    if not diarized_text:
        return []

    turns = []

    # Pattern to match speaker turns with optional timestamps
    # Matches: "SPEAKER_XX: [timestamp] text" or "Speaker: text"
    # Includes numbered respondents (Respondent1, Respondent2, etc.)
    pattern = (
        r"^(SPEAKER_\d+|Interviewer|Respondent\d*|Speaker\s*\d*):"
        r"\s*(?:\[([^\]]+)\])?\s*(.*)$"
    )

    # Split by lines and process
    lines = diarized_text.strip().split("\n")
    current_turn = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            # Save previous turn if exists
            if current_turn:
                turns.append(current_turn)

            speaker = match.group(1)
            timestamp = match.group(2)
            text = match.group(3)

            # Normalize speaker names
            speaker_lower = speaker.lower()
            if "interviewer" in speaker_lower or speaker == "SPEAKER_00":
                speaker_type = "interviewer"
                speaker_label = "Interviewer"
            elif speaker_lower == "respondent" or speaker == "SPEAKER_01":
                # Plain "Respondent" without number
                speaker_type = "respondent"
                speaker_label = "Respondent"
            elif speaker_lower.startswith("respondent"):
                # Numbered respondent (Respondent1, Respondent2, etc.) - preserve label
                speaker_type = "respondent"
                speaker_label = speaker
            else:
                # For other speakers, alternate or use generic
                speaker_type = "respondent" if len(turns) % 2 == 1 else "interviewer"
                speaker_label = speaker

            current_turn = {
                "speaker": speaker_label,
                "speaker_type": speaker_type,
                "timestamp": timestamp,
                "text": text,
            }
        elif current_turn:
            # Continuation of current turn
            current_turn["text"] += " " + line

    # Don't forget the last turn
    if current_turn:
        turns.append(current_turn)

    return turns


def _create_speaker_legend(dialog_json: list[dict]) -> html.Div | None:
    """Create a legend showing all speakers with their color coding.

    Args:
        dialog_json: List of dialog turns with 'speaker' keys.

    Returns:
        A Div component with speaker legend, or None if no speakers.
    """
    if not dialog_json:
        return None

    # Extract unique speakers in order of first appearance
    seen = set()
    speakers = []
    for turn in dialog_json:
        speaker = turn.get("speaker", "")
        if speaker and speaker not in seen:
            seen.add(speaker)
            speakers.append(speaker)

    if not speakers:
        return None

    # Create legend items (color swatch + label)
    legend_items = []
    for speaker in speakers:
        style = get_speaker_style(speaker)
        display_label = format_speaker_label(speaker)

        legend_items.append(
            html.Div(
                [
                    html.Span(
                        "",
                        style={
                            "display": "inline-block",
                            "width": "16px",
                            "height": "16px",
                            "borderRadius": "3px",
                            "backgroundColor": style["backgroundColor"],
                            "marginRight": "6px",
                            "verticalAlign": "middle",
                        },
                    ),
                    html.Span(
                        display_label,
                        style={"verticalAlign": "middle", "fontSize": "0.9rem"},
                    ),
                ],
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "marginRight": "16px",
                    "marginBottom": "4px",
                },
            )
        )

    return html.Div(
        [
            html.Small(
                "Speakers:",
                className="text-muted me-2",
                style={"fontWeight": "500"},
            ),
            html.Div(
                legend_items,
                style={"display": "inline"},
            ),
        ],
        className="mb-3",
        style={
            "padding": "8px 12px",
            "backgroundColor": "#fafafa",
            "borderRadius": "6px",
            "border": "1px solid #eee",
        },
    )


def _create_speaker_block(
    turn: dict,
    search_query: str | None = None,
) -> dbc.Card:
    """Create a styled card for a speaker turn.

    Args:
        turn: Dictionary with speaker, speaker_type, timestamp, and text.
        search_query: Optional search query for highlighting matches.

    Returns:
        A styled Card component for the speaker turn.
    """
    speaker_label = turn.get("speaker", "Unknown")
    # Use new multi-speaker style system
    style = get_speaker_style(speaker_label)

    # Apply highlighting if search query provided (XSS-safe)
    text = turn.get("text", "")
    if search_query and search_query.strip():
        # Use safe highlight function that returns Dash components
        text_component = html.Span(_highlight_matches_safe(text, search_query))
    else:
        # Dash handles text escaping automatically when rendering strings
        text_component = text

    timestamp_display = ""
    if turn.get("timestamp"):
        timestamp_display = f"[{turn['timestamp']}] "

    # Format speaker label for display (add space before numbers)
    display_label = format_speaker_label(speaker_label)

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.Strong(
                            display_label,
                            className="me-2",
                        ),
                        html.Small(
                            timestamp_display,
                            className="text-muted",
                        ),
                    ],
                    className="mb-1",
                ),
                html.P(
                    text_component,
                    className="mb-0",
                    style={"whiteSpace": "pre-wrap"},
                ),
            ],
            className="py-2 px-3",
        ),
        className="mb-2",
        style={
            **style,
            "borderRadius": "10px",
            "border": "none",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.1)",
        },
    )


def _create_metadata_panel(recording: Any) -> dbc.Card:
    """Create the metadata panel for a recording.

    Args:
        recording: The Recording model instance.

    Returns:
        A Card component displaying recording metadata.
    """
    status = recording.processing_status
    status_color = STATUS_COLORS.get(status, "secondary")
    status_label = STATUS_LABELS.get(status, "Unknown")

    # Get transcript summary if available
    summary = None
    if recording.transcript and recording.transcript.summary:
        summary = recording.transcript.summary

    metadata_items = [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.I(className="bi bi-calendar me-2"),
                        html.Strong("Uploaded:"),
                    ],
                    width=4,
                ),
                dbc.Col(
                    _format_date(recording.created_at),
                    width=8,
                ),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.I(className="bi bi-clock me-2"),
                        html.Strong("Duration:"),
                    ],
                    width=4,
                ),
                dbc.Col(
                    _format_duration(recording.duration_seconds),
                    width=8,
                ),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.I(className="bi bi-gear me-2"),
                        html.Strong("Status:"),
                    ],
                    width=4,
                ),
                dbc.Col(
                    dbc.Badge(status_label, color=status_color),
                    width=8,
                ),
            ],
            className="mb-2",
        ),
    ]

    # Add summary if available
    if summary:
        metadata_items.append(html.Hr(className="my-3"))
        metadata_items.append(
            html.Div(
                [
                    html.H6(
                        [
                            html.I(className="bi bi-card-text me-2"),
                            "Summary",
                        ],
                        className="mb-2",
                    ),
                    html.P(
                        summary,
                        className="text-muted mb-0",
                        style={"fontSize": "0.9rem"},
                    ),
                ],
            )
        )

    return dbc.Card(
        dbc.CardBody(
            [
                html.H6("Recording Details", className="mb-3"),
                *metadata_items,
            ]
        ),
        className="mb-3",
    )


def _create_not_found_view() -> html.Div:
    """Create the view displayed when a recording is not found.

    Returns:
        A Div component with not found message.
    """
    return html.Div(
        [
            html.I(className="bi bi-question-circle fs-1 text-muted mb-3"),
            html.H4("Recording Not Found", className="text-muted"),
            html.P(
                "The requested recording could not be found.",
                className="text-muted mb-4",
            ),
            dcc.Link(
                dbc.Button(
                    [
                        html.I(className="bi bi-arrow-left me-2"),
                        "Back to Library",
                    ],
                    color="primary",
                    outline=True,
                ),
                href="/library",
            ),
        ],
        className="text-center py-5",
    )


def _create_no_transcript_view() -> html.Div:
    """Create the view displayed when transcript is not yet available.

    Returns:
        A Div component indicating transcript is processing.
    """
    return html.Div(
        [
            html.I(className="bi bi-hourglass-split fs-1 text-muted mb-3"),
            html.H5("Transcript Not Available", className="text-muted"),
            html.P(
                "The transcript for this recording is still being processed. "
                "Please check back later.",
                className="text-muted",
            ),
        ],
        className="text-center py-5",
    )


def create_transcript_view(recording_id: str | None = None) -> html.Div:
    """Create the transcript view layout.

    This function creates the static layout structure. The actual content
    is populated by callbacks based on the recording_id.

    Args:
        recording_id: Optional recording ID to display. If None, the layout
            will be populated by URL-based callbacks.

    Returns:
        A Div component with the transcript viewer structure.
    """
    return html.Div(
        [
            # Store for the current recording ID
            dcc.Store(id="transcript-recording-id", data=recording_id),
            # Store for parsed transcript data
            dcc.Store(id="transcript-data", data=None),
            dbc.Container(
                [
                    # Header row with back button and title
                    dbc.Row(
                        [
                            dbc.Col(
                                dcc.Link(
                                    dbc.Button(
                                        [
                                            html.I(className="bi bi-arrow-left me-2"),
                                            "Back to Library",
                                        ],
                                        color="outline-secondary",
                                        size="sm",
                                    ),
                                    href="/library",
                                ),
                                width="auto",
                            ),
                            dbc.Col(
                                html.H3(
                                    id="transcript-title",
                                    className="mb-0",
                                    children="Loading...",
                                ),
                                width=True,
                                className="ps-3",
                            ),
                        ],
                        className="mb-4 align-items-center",
                    ),
                    # Main content row
                    dbc.Row(
                        [
                            # Left column: Metadata panel
                            dbc.Col(
                                html.Div(id="transcript-metadata-panel"),
                                width=12,
                                lg=4,
                                className="mb-3",
                            ),
                            # Right column: Search and transcript
                            dbc.Col(
                                [
                                    # Search input
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText(
                                                html.I(className="bi bi-search"),
                                            ),
                                            dbc.Input(
                                                id="transcript-search-input",
                                                type="text",
                                                placeholder="Search transcript...",
                                                debounce=True,
                                            ),
                                            dbc.Button(
                                                html.I(className="bi bi-x-lg"),
                                                id="transcript-search-clear",
                                                color="outline-secondary",
                                                n_clicks=0,
                                            ),
                                        ],
                                        className="mb-3",
                                    ),
                                    # Match count display
                                    html.Div(
                                        id="transcript-match-count",
                                        className="mb-2 text-muted",
                                        style={"fontSize": "0.9rem"},
                                    ),
                                    # Transcript content area
                                    dbc.Card(
                                        dbc.CardBody(
                                            html.Div(
                                                id="transcript-content",
                                                style={
                                                    "maxHeight": "600px",
                                                    "overflowY": "auto",
                                                    "padding": "10px",
                                                },
                                                children=[
                                                    html.Div(
                                                        [
                                                            dbc.Spinner(
                                                                color="primary",
                                                                size="lg",
                                                            ),
                                                            html.P(
                                                                "Loading transcript...",
                                                                className=(
                                                                    "mt-3 text-muted"
                                                                ),
                                                            ),
                                                        ],
                                                        className="text-center py-5",
                                                    )
                                                ],
                                            ),
                                        ),
                                    ),
                                ],
                                width=12,
                                lg=8,
                            ),
                        ],
                    ),
                ],
                fluid=True,
                className="p-4",
            ),
        ]
    )


@callback(
    Output("transcript-title", "children"),
    Output("transcript-metadata-panel", "children"),
    Output("transcript-content", "children"),
    Output("transcript-data", "data"),
    Input("transcript-recording-id", "data"),
)
def load_transcript(
    recording_id: str | None,
) -> tuple[str, Any, Any, list[dict] | None]:
    """Load and display the transcript for a recording.

    Args:
        recording_id: UUID of the recording to display.

    Returns:
        Tuple of (title, metadata_panel, transcript_content, parsed_turns).
    """
    if not recording_id:
        return (
            "Recording Not Found",
            None,
            _create_not_found_view(),
            None,
        )

    try:
        session = get_session()
        try:
            recording = get_recording(session, recording_id)

            if not recording:
                return (
                    "Recording Not Found",
                    None,
                    _create_not_found_view(),
                    None,
                )

            title = recording.title

            # Create metadata panel
            metadata_panel = _create_metadata_panel(recording)

            # Check if transcript exists
            if not recording.transcript:
                return (
                    title,
                    metadata_panel,
                    _create_no_transcript_view(),
                    None,
                )

            # Fallback chain: reconstructed_dialog_json > dialog_json > diarized_text > full_text
            if recording.transcript.reconstructed_dialog_json:
                # Prefer reconstructed (LLM-cleaned) dialog if available
                turns = _convert_dialog_json_to_turns(
                    recording.transcript.reconstructed_dialog_json
                )
            elif recording.transcript.dialog_json:
                # Fall back to raw dialog_json from diarization
                turns = _convert_dialog_json_to_turns(recording.transcript.dialog_json)
            else:
                # Fallback to parsing diarized_text
                diarized_text = recording.transcript.diarized_text
                if not diarized_text:
                    diarized_text = recording.transcript.full_text
                turns = _parse_speaker_turns(diarized_text)

            if not turns:
                # If parsing fails, display raw text
                raw_text = (
                    recording.transcript.diarized_text
                    or recording.transcript.full_text
                    or "No transcript content available."
                )
                transcript_content = html.Div(
                    [
                        html.P(
                            raw_text,
                            style={"whiteSpace": "pre-wrap"},
                        )
                    ]
                )
                return (title, metadata_panel, transcript_content, None)

            # Create speaker legend (for multi-speaker transcripts)
            legend = _create_speaker_legend(turns)

            # Create speaker blocks
            speaker_blocks = [_create_speaker_block(turn) for turn in turns]

            # Combine legend and speaker blocks
            transcript_children = []
            if legend:
                transcript_children.append(legend)
            transcript_children.extend(speaker_blocks)
            transcript_content = html.Div(transcript_children)

            return (title, metadata_panel, transcript_content, turns)

        finally:
            session.close()

    except Exception as e:
        logger.error(
            f"Failed to load transcript for {recording_id}: {e}",
            exc_info=True,
        )
        return (
            "Error Loading Recording",
            dbc.Alert(
                "An error occurred while loading the recording. Please try again.",
                color="danger",
            ),
            None,
            None,
        )


@callback(
    Output("transcript-content", "children", allow_duplicate=True),
    Output("transcript-match-count", "children"),
    Input("transcript-search-input", "value"),
    State("transcript-data", "data"),
    prevent_initial_call=True,
)
def filter_transcript(
    search_query: str | None,
    turns: list[dict] | None,
) -> tuple[Any, str]:
    """Filter and highlight transcript based on search query.

    Args:
        search_query: The search string to filter/highlight.
        turns: Parsed speaker turns from the transcript.

    Returns:
        Tuple of (filtered_content, match_count_text).
    """
    if not turns:
        return (
            html.Div(
                "No transcript data available.",
                className="text-muted text-center py-3",
            ),
            "",
        )

    # If no search query, show all turns without highlighting
    if not search_query or not search_query.strip():
        speaker_blocks = [_create_speaker_block(turn) for turn in turns]
        return (html.Div(speaker_blocks), "")

    # Count matches across all turns
    total_matches = 0
    matching_turns = []

    for turn in turns:
        text = turn.get("text", "")
        matches = search_transcript(text, search_query)
        if matches:
            total_matches += len(matches)
            matching_turns.append(turn)

    # Create speaker blocks with highlighting
    if matching_turns:
        speaker_blocks = [
            _create_speaker_block(turn, search_query=search_query)
            for turn in matching_turns
        ]
        match_suffix = "es" if total_matches != 1 else ""
        turn_suffix = "s" if len(matching_turns) != 1 else ""
        match_text = (
            f"Found {total_matches} match{match_suffix} "
            f"in {len(matching_turns)} speaker turn{turn_suffix}"
        )
    else:
        # No matches found - show all turns but indicate no results
        speaker_blocks = [_create_speaker_block(turn) for turn in turns]
        match_text = "No matches found"

    return (html.Div(speaker_blocks), match_text)


@callback(
    Output("transcript-search-input", "value"),
    Input("transcript-search-clear", "n_clicks"),
    prevent_initial_call=True,
)
def clear_search(n_clicks: int) -> str:
    """Clear the search input when clear button is clicked.

    Args:
        n_clicks: Number of times the clear button was clicked.

    Returns:
        Empty string to clear the input.
    """
    return ""
