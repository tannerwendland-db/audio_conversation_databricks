"""Chat component for the Audio Conversation RAG System.

This module provides a Dash component for the chat interface with message
input, history display, RAG query handling, session management, streaming
responses, and clickable citations linking to recording details.
"""

import logging
import uuid

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, clientside_callback, dcc, html
from dash_extensions import SSE
from dash_extensions.streaming import sse_options

from src.db.session import get_session
from src.models import ProcessingStatus
from src.services.recording import list_recordings

logger = logging.getLogger(__name__)

# Stream state constants
STREAM_STATE_IDLE = "idle"
STREAM_STATE_STREAMING = "streaming"
STREAM_STATE_COMPLETE = "complete"
STREAM_STATE_ERROR = "error"


def _format_duration(seconds: float | None) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS format."""
    if seconds is None:
        return "Unknown"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def create_chat_component() -> dbc.Container:
    """Create the chat component layout.

    Returns:
        A Dash Bootstrap Container with the chat interface including
        message history, input area, streaming support, and session storage.
    """
    return dbc.Container(
        [
            html.H3("Chat with Your Recordings", className="mb-4"),
            html.P(
                "Ask questions about your transcribed audio recordings.",
                className="text-muted mb-3",
            ),
            # Session storage for unique session ID per browser tab
            dcc.Store(
                id="chat-session-id",
                storage_type="session",
                data=None,
            ),
            # Store for message history
            dcc.Store(
                id="chat-message-history",
                storage_type="session",
                data=[],
            ),
            # Store for streaming state
            dcc.Store(
                id="chat-stream-state",
                storage_type="memory",
                data={
                    "status": STREAM_STATE_IDLE,
                    "partial_content": "",
                    "citations": None,
                    "error_message": None,
                },
            ),
            # SSE component for streaming responses
            # concat=True ensures no messages are dropped - we parse the concatenated value
            SSE(
                id="chat-sse",
                concat=True,
            ),
            # Store for accumulated streaming content
            # ONLY the clientside callback outputs to this - Python callbacks read via State only
            dcc.Store(
                id="streaming-accumulated-text",
                storage_type="memory",
                data="",
            ),
            # Reset trigger - Python callbacks write to this to signal the clientside
            # callback to reset the accumulator
            dcc.Store(
                id="streaming-reset-trigger",
                storage_type="memory",
                data=0,
            ),
            # Recording filter and clear button row
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Dropdown(
                            id="chat-recording-filter",
                            multi=True,
                            placeholder="Filter by recordings (leave empty to search all)",
                        ),
                        width=10,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [
                                html.I(className="bi bi-trash me-2"),
                                "Clear",
                            ],
                            id="chat-clear-button",
                            color="secondary",
                            outline=True,
                            size="sm",
                            className="w-100",
                        ),
                        width=2,
                        className="d-flex align-items-center",
                    ),
                ],
                className="mb-3 g-2",
            ),
            # Message history display area with separate streaming container
            dbc.Card(
                dbc.CardBody(
                    html.Div(
                        [
                            # Historical messages (only re-rendered when history changes)
                            html.Div(
                                id="chat-message-display",
                                children=[
                                    _create_welcome_message(),
                                ],
                            ),
                            # Streaming message container (updated independently during streaming)
                            html.Div(
                                id="chat-streaming-container",
                                style={"display": "none"},
                            ),
                        ],
                        id="chat-scroll-container",
                        **{"data-scroll": ""},  # Dummy attribute for clientside callback output
                        style={
                            "height": "400px",
                            "overflowY": "auto",
                            "padding": "10px",
                        },
                    ),
                ),
                className="mb-3",
            ),
            # Input area
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Textarea(
                            id="chat-input",
                            placeholder="Ask a question about your recordings...",
                            style={"resize": "none"},
                            rows=2,
                        ),
                        width=10,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [
                                html.I(className="bi bi-send me-2"),
                                "Send",
                            ],
                            id="chat-send-button",
                            color="primary",
                            className="h-100 w-100",
                            disabled=False,
                        ),
                        width=2,
                    ),
                ],
                className="g-2",
            ),
            # Loading indicator (kept for non-streaming operations)
            dcc.Loading(
                id="chat-loading",
                type="circle",
                children=html.Div(id="chat-loading-output"),
            ),
        ],
        fluid=True,
        className="p-4",
    )


def _create_welcome_message() -> html.Div:
    """Create the welcome message displayed when chat is empty.

    Returns:
        A Div component with welcome message.
    """
    return html.Div(
        [
            html.I(className="bi bi-chat-dots fs-1 text-muted mb-3"),
            html.H5("Welcome to the Chat", className="text-muted"),
            html.P(
                "Ask questions about your uploaded recordings and I will "
                "search through the transcripts to find relevant answers.",
                className="text-muted",
            ),
        ],
        className="text-center py-5",
    )


def _create_user_message(content: str) -> dbc.Card:
    """Create a user message bubble.

    Args:
        content: The user's message text.

    Returns:
        A Card component styled as a user message.
    """
    return dbc.Card(
        dbc.CardBody(
            [
                html.Small("You", className="text-muted fw-bold"),
                html.P(content, className="mb-0 mt-1"),
            ],
            className="py-2 px-3",
        ),
        className="mb-2 ms-5",
        style={
            "backgroundColor": "#e3f2fd",
            "borderRadius": "15px 15px 0 15px",
        },
    )


def _create_assistant_message(content: str, citations: list[dict]) -> html.Div:
    """Create an assistant message bubble with citations.

    Args:
        content: The assistant's response text.
        citations: List of citation dictionaries.

    Returns:
        A Div component containing the message and expandable citations.
    """
    message_card = dbc.Card(
        dbc.CardBody(
            [
                html.Small("Assistant", className="text-muted fw-bold"),
                html.P(
                    content,
                    className="mb-0 mt-1",
                    style={"whiteSpace": "pre-wrap"},
                ),
            ],
            className="py-2 px-3",
        ),
        className="mb-2 me-5",
        style={
            "backgroundColor": "#f5f5f5",
            "borderRadius": "15px 15px 15px 0",
        },
    )

    # Create citations section if there are any
    citations_section = None
    if citations:
        citation_items = []
        for i, citation in enumerate(citations, start=1):
            recording_id = citation.get("recording_id", "")
            recording_title = citation.get("recording_title", "Unknown")
            excerpt = citation.get("excerpt", citation.get("content", ""))
            speaker = citation.get("speaker")

            speaker_text = f" - {speaker}" if speaker else ""

            citation_items.append(
                dbc.ListGroupItem(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Strong(f"[{i}] {recording_title}"),
                                        html.Span(speaker_text, className="text-muted"),
                                    ],
                                    width=10,
                                ),
                                dbc.Col(
                                    dcc.Link(
                                        html.I(className="bi bi-box-arrow-up-right"),
                                        href=f"/recording/{recording_id}",
                                        id={
                                            "type": "citation-link",
                                            "index": recording_id,
                                        },
                                        className="text-primary",
                                        title="View recording",
                                    ),
                                    width=2,
                                    className="text-end",
                                ),
                            ],
                        ),
                        html.Small(
                            _truncate_text(excerpt, 150),
                            className="text-muted d-block mt-1",
                        ),
                    ],
                    className="py-2",
                    action=True,
                    href=f"/recording/{recording_id}",
                )
            )

        citations_section = html.Div(
            [
                html.Details(
                    [
                        html.Summary(
                            [
                                html.I(className="bi bi-book me-2"),
                                f"Sources ({len(citations)})",
                            ],
                            className="text-primary fw-bold mb-2",
                            style={"cursor": "pointer"},
                        ),
                        dbc.ListGroup(
                            citation_items,
                            flush=True,
                        ),
                    ],
                ),
            ],
            className="mt-2 me-5",
        )

    if citations_section:
        return html.Div([message_card, citations_section])
    return html.Div([message_card])


def _create_error_message(error_text: str) -> dbc.Alert:
    """Create an error message alert.

    Args:
        error_text: The error message to display.

    Returns:
        An Alert component with the error message.
    """
    return dbc.Alert(
        [
            html.I(className="bi bi-exclamation-triangle me-2"),
            error_text,
        ],
        color="danger",
        className="mb-2 me-5",
    )


def _create_no_results_message() -> dbc.Card:
    """Create a message for when no relevant content is found.

    Returns:
        A Card component with the no results message.
    """
    return dbc.Card(
        dbc.CardBody(
            [
                html.Small("Assistant", className="text-muted fw-bold"),
                html.Div(
                    [
                        html.I(className="bi bi-search me-2"),
                        "No relevant information was found in your recordings. ",
                        "Try rephrasing your question or ensure that relevant ",
                        "recordings have been uploaded and processed.",
                    ],
                    className="mb-0 mt-1",
                ),
            ],
            className="py-2 px-3",
        ),
        className="mb-2 me-5",
        style={
            "backgroundColor": "#fff3cd",
            "borderRadius": "15px 15px 15px 0",
        },
    )


def _create_streaming_message(content: str, is_streaming: bool = True) -> dbc.Card:
    """Create a streaming message bubble with optional pulsing cursor.

    Args:
        content: The partially streamed content.
        is_streaming: Whether streaming is still active (shows cursor).

    Returns:
        A Card component styled as a streaming assistant message.
    """
    cursor_class = "streaming-cursor" if is_streaming else ""

    return dbc.Card(
        dbc.CardBody(
            [
                html.Small("Assistant", className="text-muted fw-bold"),
                html.Span(
                    content,
                    id="streaming-text-content",  # Target for DOM manipulation
                    className=f"mb-0 mt-1 streaming-content {cursor_class}",
                    style={"whiteSpace": "pre-wrap", "display": "block"},
                ),
            ],
            className="py-2 px-3",
        ),
        className="mb-2 me-5",
        style={
            "backgroundColor": "#f5f5f5",
            "borderRadius": "15px 15px 15px 0",
        },
    )


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: The text to truncate.
        max_length: Maximum allowed length.

    Returns:
        Truncated text with ellipsis if needed.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _render_message_history(messages: list[dict]) -> list:
    """Render the message history as Dash components.

    Args:
        messages: List of message dictionaries with role, content, and citations.

    Returns:
        List of Dash components representing the messages.
    """
    if not messages:
        return [_create_welcome_message()]

    rendered = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        citations = msg.get("citations", [])
        is_error = msg.get("is_error", False)
        is_no_results = msg.get("is_no_results", False)

        if role == "user":
            rendered.append(_create_user_message(content))
        elif is_error:
            rendered.append(_create_error_message(content))
        elif is_no_results:
            rendered.append(_create_no_results_message())
        else:
            rendered.append(_create_assistant_message(content, citations))

    return rendered


@callback(
    Output("chat-session-id", "data"),
    Input("chat-session-id", "data"),
)
def initialize_session(existing_session_id: str | None) -> str:
    """Initialize or retrieve the chat session ID.

    Generates a unique UUID for each browser tab on initial load.
    The session ID persists within the tab but clears on refresh.

    Args:
        existing_session_id: Existing session ID if any.

    Returns:
        Session ID string (existing or newly generated).
    """
    if existing_session_id:
        return existing_session_id

    new_session_id = str(uuid.uuid4())
    logger.debug(f"Initialized new chat session: {new_session_id}")
    return new_session_id


@callback(
    Output("chat-recording-filter", "options"),
    Input("chat-session-id", "data"),
)
def populate_recording_filter_options(session_id: str | None) -> list[dict]:
    """Populate dropdown with completed recordings.

    Fetches all recordings and filters to only include those with
    COMPLETED processing status.

    Args:
        session_id: The current session ID (used as trigger for callback).

    Returns:
        List of option dictionaries with 'label' and 'value' keys.
    """
    session = get_session()
    try:
        recordings = list_recordings(session, limit=100)
        options = []
        for r in recordings:
            if r.processing_status == ProcessingStatus.COMPLETED.value:
                duration_str = _format_duration(r.duration_seconds)
                options.append(
                    {
                        "label": f"{r.title} ({duration_str})",
                        "value": r.id,
                    }
                )
        return options
    except Exception as e:
        logger.error(f"Failed to load recordings for filter: {e}", exc_info=True)
        return []
    finally:
        session.close()


@callback(
    Output("chat-sse", "url"),
    Output("chat-sse", "options"),
    Output("chat-message-history", "data", allow_duplicate=True),
    Output("chat-message-display", "children", allow_duplicate=True),
    Output("chat-input", "value"),
    Output("chat-stream-state", "data", allow_duplicate=True),
    Output("chat-streaming-container", "children", allow_duplicate=True),
    Output("chat-streaming-container", "style", allow_duplicate=True),
    Output("streaming-reset-trigger", "data", allow_duplicate=True),
    Input("chat-send-button", "n_clicks"),
    State("chat-input", "value"),
    State("chat-message-history", "data"),
    State("chat-session-id", "data"),
    State("chat-recording-filter", "value"),
    State("chat-stream-state", "data"),
    State("streaming-reset-trigger", "data"),
    prevent_initial_call=True,
)
def handle_chat_submit(
    n_clicks: int | None,
    user_input: str | None,
    message_history: list[dict],
    session_id: str | None,
    selected_recordings: list[str] | None,
    stream_state: dict | None,
    reset_trigger: int | None,
) -> tuple[str | None, dict | None, list[dict], list, str, dict, dbc.Card, dict, int]:
    """Handle chat message submission and initiate streaming RAG query.

    Adds the user message to history and triggers the SSE stream for
    the assistant response.

    Args:
        n_clicks: Number of times the send button was clicked.
        user_input: The user's input text.
        message_history: Current message history.
        session_id: Unique session identifier.
        selected_recordings: List of recording IDs to filter by, or None for all.
        stream_state: Current streaming state.

    Returns:
        Tuple of (sse_url, sse_options, updated_history, rendered_messages,
        cleared_input, new_stream_state, streaming_msg, streaming_style,
        reset_accumulated).
    """
    from dash.exceptions import PreventUpdate

    # Check if already streaming
    if stream_state and stream_state.get("status") == STREAM_STATE_STREAMING:
        raise PreventUpdate

    if not n_clicks or not user_input or not user_input.strip():
        raise PreventUpdate

    query = user_input.strip()
    session_id = session_id or str(uuid.uuid4())

    # Initialize message history if None
    if message_history is None:
        message_history = []

    # Add user message to history
    updated_history = message_history.copy()
    updated_history.append(
        {
            "role": "user",
            "content": query,
            "citations": [],
        }
    )

    logger.info(f"Starting streaming chat query for session {session_id}: {query[:50]}...")

    # Build SSE options - payload must be JSON string for sse_options
    import json as json_module

    payload_dict = {
        "query": query,
        "session_id": session_id,
    }
    if selected_recordings:
        payload_dict["recording_filter"] = selected_recordings
    payload = json_module.dumps(payload_dict)

    # Set stream state to streaming
    new_stream_state = {
        "status": STREAM_STATE_STREAMING,
        "partial_content": "",
        "citations": None,
        "error_message": None,
    }

    # Render history WITHOUT the streaming message (streaming container handles that)
    rendered = _render_message_history(updated_history)

    # Initial streaming message (empty with cursor)
    streaming_msg = _create_streaming_message("", is_streaming=True)

    return (
        "/api/chat/stream",
        sse_options(payload=payload, headers={"Content-Type": "application/json"}),
        updated_history,
        rendered,
        "",  # Clear input
        new_stream_state,
        streaming_msg,
        {"display": "block"},  # Show streaming container
        (reset_trigger or 0) + 1,  # Increment to trigger reset in clientside callback
    )


@callback(
    Output("chat-message-display", "children", allow_duplicate=True),
    Input("chat-message-history", "data"),
    prevent_initial_call=True,
)
def sync_message_display(message_history: list[dict]) -> list:
    """Synchronize message display with stored history.

    Ensures the display is updated when history changes,
    such as on page load with existing session data.

    Args:
        message_history: Current message history from storage.

    Returns:
        List of rendered message components.
    """
    return _render_message_history(message_history or [])


@callback(
    Output("chat-send-button", "disabled"),
    Input("chat-input", "value"),
    Input("chat-stream-state", "data"),
)
def toggle_send_button(input_value: str | None, stream_state: dict | None) -> bool:
    """Enable/disable send button based on input content and streaming state.

    Disables the button when:
    - Input is empty or whitespace only
    - Streaming is in progress (FR-008)

    Args:
        input_value: Current value of the input field.
        stream_state: Current streaming state.

    Returns:
        True to disable the button, False to enable.
    """
    # Disable during streaming
    if stream_state and stream_state.get("status") == STREAM_STATE_STREAMING:
        return True

    # Disable if input is empty
    return not (input_value and input_value.strip())


@callback(
    Output("chat-message-history", "data", allow_duplicate=True),
    Output("chat-message-display", "children", allow_duplicate=True),
    Output("chat-input", "value", allow_duplicate=True),
    Output("chat-stream-state", "data", allow_duplicate=True),
    Output("chat-streaming-container", "children", allow_duplicate=True),
    Output("chat-streaming-container", "style", allow_duplicate=True),
    Output("streaming-reset-trigger", "data", allow_duplicate=True),
    Input("chat-clear-button", "n_clicks"),
    State("streaming-reset-trigger", "data"),
    prevent_initial_call=True,
)
def clear_conversation(
    n_clicks: int | None,
    reset_trigger: int | None,
) -> tuple[list, list, str, dict, None, dict, int]:
    """Clear the conversation history and reset the chat display.

    Args:
        n_clicks: Number of times the clear button was clicked.

    Returns:
        Tuple of (empty_history, welcome_message, empty_input, reset_stream_state,
        streaming_content, streaming_style, reset_accumulated).
    """
    if not n_clicks:
        # No action needed
        from dash.exceptions import PreventUpdate

        raise PreventUpdate

    logger.info("Clearing conversation history")
    return (
        [],
        [_create_welcome_message()],
        "",
        {
            "status": STREAM_STATE_IDLE,
            "partial_content": "",
            "citations": None,
            "error_message": None,
        },
        None,
        {"display": "none"},
        (reset_trigger or 0) + 1,  # Increment to trigger reset in clientside callback
    )


@callback(
    Output("chat-stream-state", "data", allow_duplicate=True),
    Output("chat-streaming-container", "children", allow_duplicate=True),
    Output("chat-streaming-container", "style", allow_duplicate=True),
    Output("chat-message-display", "children", allow_duplicate=True),
    Output("chat-message-history", "data", allow_duplicate=True),
    Output("streaming-reset-trigger", "data", allow_duplicate=True),
    Input("chat-sse", "value"),
    State("chat-stream-state", "data"),
    State("chat-message-history", "data"),
    State("streaming-accumulated-text", "data"),
    State("streaming-reset-trigger", "data"),
    prevent_initial_call=True,
)
def handle_sse_event(
    sse_value: str | None,
    stream_state: dict | None,
    message_history: list[dict],
    accumulated_content: str | None,
    reset_trigger: int | None,
) -> tuple[dict, dbc.Card | None, dict, list, list[dict], int]:
    """Handle incoming SSE events and update streaming state.

    Token events are handled by clientside callback for synchronous accumulation.
    This callback handles citations, done, and error events.

    Args:
        sse_value: Raw SSE event data.
        stream_state: Current streaming state.
        message_history: Current message history.
        accumulated_content: Content accumulated by clientside callback.

    Returns:
        Tuple of (updated_stream_state, streaming_msg, streaming_style,
        rendered_messages, updated_history, reset_accumulated).
    """
    import json

    from dash import no_update
    from dash.exceptions import PreventUpdate

    logger.debug(f"handle_sse_event called with sse_value: {str(sse_value)[:100]}")

    if not sse_value:
        raise PreventUpdate

    # Initialize state if needed
    if stream_state is None:
        stream_state = {
            "status": STREAM_STATE_IDLE,
            "partial_content": "",
            "citations": None,
            "error_message": None,
        }

    if message_history is None:
        message_history = []

    # Parse SSE events - with concat=True, the value is concatenated JSON objects
    # We need to find the LAST complete event to determine the current state
    import re

    event_data = {}
    event_type = ""

    if isinstance(sse_value, str) and sse_value.strip():
        # Split concatenated JSON objects and parse the last one
        # Pattern: split by }{ but keep the braces
        json_strings = re.split(r'}\s*{', sse_value)

        # Parse from the end to find the last valid event
        for i in range(len(json_strings) - 1, -1, -1):
            json_str = json_strings[i]
            # Add back braces that were removed by split
            if i > 0:
                json_str = '{' + json_str
            if i < len(json_strings) - 1:
                json_str = json_str + '}'

            try:
                event_data = json.loads(json_str)
                event_type = event_data.get("type", "")
                # Found a valid event, use it
                break
            except (json.JSONDecodeError, TypeError):
                continue

    if not event_type:
        raise PreventUpdate

    if event_type == "token":
        # Token events are handled by clientside callback for synchronous accumulation
        # Just update stream state status to streaming
        new_state = {
            **stream_state,
            "status": STREAM_STATE_STREAMING,
        }
        return new_state, no_update, no_update, no_update, no_update, no_update

    elif event_type == "citations":
        # Citations event - just update state, keep streaming visible
        new_state = {
            **stream_state,
            "citations": event_data.get("citations", []),
        }
        # Don't re-render anything, just store citations in state
        return new_state, no_update, no_update, no_update, no_update, no_update

    elif event_type == "error":
        # Error event - finalize to history and hide streaming container
        error_msg = event_data.get("message", "An error occurred")
        # Use accumulated content from clientside callback
        partial_content = accumulated_content or ""

        # Add error to history, preserving partial content if any
        updated_history = message_history.copy()
        if partial_content:
            updated_history.append(
                {
                    "role": "assistant",
                    "content": partial_content + f"\n\n[Error: {error_msg}]",
                    "citations": [],
                    "is_error": True,
                }
            )
        else:
            updated_history.append(
                {
                    "role": "assistant",
                    "content": f"Error: {error_msg}",
                    "citations": [],
                    "is_error": True,
                }
            )

        logger.error(f"Streaming error: {error_msg}")

        # Reset to idle
        final_state = {
            "status": STREAM_STATE_IDLE,
            "partial_content": "",
            "citations": None,
            "error_message": None,
        }

        # Hide streaming container, render final history, trigger reset
        return (
            final_state,
            None,
            {"display": "none"},
            _render_message_history(updated_history),
            updated_history,
            (reset_trigger or 0) + 1,  # Trigger reset in clientside callback
        )

    elif event_type == "done":
        # Done event - finalize to history and hide streaming container
        # Use accumulated content from clientside callback
        partial_content = accumulated_content or ""
        citations = stream_state.get("citations") or []

        if not partial_content:
            raise PreventUpdate

        # Add assistant message to history
        updated_history = message_history.copy()
        is_no_results = not citations and "no relevant" in partial_content.lower()

        updated_history.append(
            {
                "role": "assistant",
                "content": partial_content,
                "citations": citations,
                "is_no_results": is_no_results,
            }
        )

        logger.info(f"Stream done event: completed with {len(citations)} citations")

        # Reset stream state
        new_state = {
            "status": STREAM_STATE_IDLE,
            "partial_content": "",
            "citations": None,
            "error_message": None,
        }

        # Hide streaming container, render final history, trigger reset
        return (
            new_state,
            None,
            {"display": "none"},
            _render_message_history(updated_history),
            updated_history,
            (reset_trigger or 0) + 1,  # Trigger reset in clientside callback
        )

    else:
        # Unknown event - ignore
        logger.warning(f"Unknown SSE event type: {event_type}")
        raise PreventUpdate


@callback(
    Output("chat-stream-state", "data", allow_duplicate=True),
    Output("chat-streaming-container", "children", allow_duplicate=True),
    Output("chat-streaming-container", "style", allow_duplicate=True),
    Output("chat-message-display", "children", allow_duplicate=True),
    Output("chat-message-history", "data", allow_duplicate=True),
    Output("streaming-reset-trigger", "data", allow_duplicate=True),
    Input("chat-sse", "state"),
    State("chat-stream-state", "data"),
    State("chat-message-history", "data"),
    State("streaming-accumulated-text", "data"),
    State("streaming-reset-trigger", "data"),
    prevent_initial_call=True,
)
def handle_sse_completion(
    sse_state: str | None,
    stream_state: dict | None,
    message_history: list[dict],
    accumulated_content: str | None,
    reset_trigger: int | None,
) -> tuple[dict, None, dict, list, list[dict], int]:
    """Handle SSE stream completion (connection closed).

    Finalizes the streaming message, adds it to history, hides the streaming
    container, and resets stream state.

    Args:
        sse_state: SSE connection state.
        stream_state: Current streaming state.
        message_history: Current message history.
        accumulated_content: Content accumulated by clientside callback.

    Returns:
        Tuple of (reset_stream_state, streaming_content, streaming_style,
        rendered_messages, updated_history, reset_accumulated).
    """
    from dash.exceptions import PreventUpdate

    logger.debug(f"handle_sse_completion called with sse_state: {sse_state}")

    # Only act when stream closes (state becomes "closed" or None after streaming)
    if sse_state not in ["closed", None]:
        raise PreventUpdate

    if not stream_state or stream_state.get("status") != STREAM_STATE_STREAMING:
        raise PreventUpdate

    # Use accumulated content from clientside callback
    partial_content = accumulated_content or ""
    citations = stream_state.get("citations") or []

    # Skip if no content was streamed
    if not partial_content:
        raise PreventUpdate

    if message_history is None:
        message_history = []

    # Add assistant message to history
    updated_history = message_history.copy()
    is_no_results = not citations and "no relevant" in partial_content.lower()

    updated_history.append(
        {
            "role": "assistant",
            "content": partial_content,
            "citations": citations,
            "is_no_results": is_no_results,
        }
    )

    logger.info(f"Stream completed with {len(citations)} citations")

    # Reset stream state
    new_state = {
        "status": STREAM_STATE_IDLE,
        "partial_content": "",
        "citations": None,
        "error_message": None,
    }

    # Hide streaming container and render final history, trigger reset
    return (
        new_state,
        None,
        {"display": "none"},
        _render_message_history(updated_history),
        updated_history,
        (reset_trigger or 0) + 1,  # Trigger reset in clientside callback
    )


# Clientside callback for token accumulation via direct DOM manipulation
# SSE component uses concat=True, so we parse the concatenated JSON messages
# Uses window._streamingContent for the accumulated text content
# This is the ONLY callback that outputs to streaming-accumulated-text
clientside_callback(
    """
    function(sseValue, resetTrigger) {
        // Initialize window variables if needed
        if (window._streamingContent === undefined) {
            window._streamingContent = '';
        }
        if (window._lastResetTrigger === undefined) {
            window._lastResetTrigger = resetTrigger;
        }
        if (window._lastProcessedLength === undefined) {
            window._lastProcessedLength = 0;
        }

        // Check if reset was triggered (reset trigger changed)
        if (resetTrigger !== window._lastResetTrigger) {
            window._lastResetTrigger = resetTrigger;
            // Reset all accumulators
            window._streamingContent = '';
            window._lastProcessedLength = 0;
            // Also update the Store for Python callbacks
            return '';
        }

        if (!sseValue) {
            return window.dash_clientside.no_update;
        }

        // Only process the new portion of the concatenated value
        if (sseValue.length <= window._lastProcessedLength) {
            return window.dash_clientside.no_update;
        }

        const newPortion = sseValue.substring(window._lastProcessedLength);
        window._lastProcessedLength = sseValue.length;

        // Parse concatenated JSON objects (they're separated by newlines or just concatenated)
        // Split by }{ to separate individual JSON objects
        const jsonStrings = newPortion.replace(/}{/g, '}|||{').split('|||');

        let hasUpdate = false;
        let lastEventType = null;

        for (const jsonStr of jsonStrings) {
            if (!jsonStr.trim()) continue;

            try {
                const event = JSON.parse(jsonStr);

                if (event.type === 'token' && event.content !== undefined) {
                    window._streamingContent += event.content;
                    hasUpdate = true;
                }

                lastEventType = event.type;
            } catch (e) {
                // May be partial JSON at the end, ignore
                console.debug('Partial JSON:', jsonStr.substring(0, 30));
            }
        }

        if (hasUpdate) {
            // Update DOM directly for immediate visual feedback
            const textEl = document.getElementById('streaming-text-content');
            if (textEl) {
                textEl.textContent = window._streamingContent;
            }

            // Auto-scroll the chat container
            const container = document.getElementById('chat-scroll-container');
            if (container) {
                requestAnimationFrame(function() {
                    container.scrollTop = container.scrollHeight;
                });
            }

            // Return the accumulated content to update the Store for Python callbacks
            return window._streamingContent;
        }

        return window.dash_clientside.no_update;
    }
    """,
    Output("streaming-accumulated-text", "data"),
    Input("chat-sse", "value"),
    Input("streaming-reset-trigger", "data"),
    prevent_initial_call=True,
)
