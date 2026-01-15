"""Chat component for the Audio Conversation RAG System.

This module provides a Dash component for the chat interface with message
input, history display, RAG query handling, session management, and
clickable citations linking to recording details.
"""

import logging
import uuid

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from src.db.session import get_session
from src.models import ProcessingStatus
from src.services.rag import rag_query
from src.services.recording import list_recordings

logger = logging.getLogger(__name__)


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
        message history, input area, and session storage.
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
            # Message history display area
            dbc.Card(
                dbc.CardBody(
                    html.Div(
                        id="chat-message-display",
                        style={
                            "height": "400px",
                            "overflowY": "auto",
                            "padding": "10px",
                        },
                        children=[
                            _create_welcome_message(),
                        ],
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
            # Loading indicator
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
                options.append({
                    "label": f"{r.title} ({duration_str})",
                    "value": r.id,
                })
        return options
    except Exception as e:
        logger.error(f"Failed to load recordings for filter: {e}", exc_info=True)
        return []
    finally:
        session.close()


@callback(
    Output("chat-message-display", "children"),
    Output("chat-message-history", "data"),
    Output("chat-input", "value"),
    Output("chat-loading-output", "children"),
    Input("chat-send-button", "n_clicks"),
    State("chat-input", "value"),
    State("chat-message-history", "data"),
    State("chat-session-id", "data"),
    State("chat-recording-filter", "value"),
    prevent_initial_call=True,
)
def handle_chat_submit(
    n_clicks: int | None,
    user_input: str | None,
    message_history: list[dict],
    session_id: str | None,
    selected_recordings: list[str] | None,
) -> tuple[list, list[dict], str, None]:
    """Handle chat message submission and RAG query.

    Processes the user's query through the RAG service and displays
    the response with citations.

    Args:
        n_clicks: Number of times the send button was clicked.
        user_input: The user's input text.
        message_history: Current message history.
        session_id: Unique session identifier.
        selected_recordings: List of recording IDs to filter by, or None for all.

    Returns:
        Tuple of (rendered_messages, updated_history, cleared_input, loading_state).
    """
    if not n_clicks or not user_input or not user_input.strip():
        # No action needed
        return (
            _render_message_history(message_history),
            message_history,
            user_input or "",
            None,
        )

    query = user_input.strip()
    session_id = session_id or str(uuid.uuid4())

    # Initialize message history if None
    if message_history is None:
        message_history = []

    # Add user message to history
    updated_history = message_history.copy()
    updated_history.append({
        "role": "user",
        "content": query,
        "citations": [],
    })

    try:
        session = get_session()
        try:
            # Invoke RAG query
            logger.info(
                f"Processing chat query for session {session_id}: {query[:50]}..."
            )
            result = rag_query(
                session=session,
                query=query,
                session_id=session_id,
                recording_filter=selected_recordings if selected_recordings else None,
            )

            answer = result.get("answer", "")
            citations = result.get("citations", [])

            # Check for no results
            is_no_results = (
                not citations
                and "no relevant" in answer.lower()
            )

            # Add assistant response to history
            updated_history.append({
                "role": "assistant",
                "content": answer,
                "citations": citations,
                "is_no_results": is_no_results,
            })

            logger.info(
                f"Chat query completed for session {session_id} "
                f"with {len(citations)} citations"
            )

        finally:
            session.close()

    except Exception as e:
        error_msg = f"Failed to process your question: {e!s}"
        logger.error(f"Chat query failed for session {session_id}: {e}", exc_info=True)

        # Add error message to history
        updated_history.append({
            "role": "assistant",
            "content": error_msg,
            "citations": [],
            "is_error": True,
        })

    # Render and return
    return (
        _render_message_history(updated_history),
        updated_history,
        "",  # Clear input
        None,
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
)
def toggle_send_button(input_value: str | None) -> bool:
    """Enable/disable send button based on input content.

    Args:
        input_value: Current value of the input field.

    Returns:
        True to disable the button, False to enable.
    """
    return not (input_value and input_value.strip())


@callback(
    Output("chat-message-history", "data", allow_duplicate=True),
    Output("chat-message-display", "children", allow_duplicate=True),
    Output("chat-input", "value", allow_duplicate=True),
    Input("chat-clear-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_conversation(n_clicks: int | None) -> tuple[list, list, str]:
    """Clear the conversation history and reset the chat display.

    Args:
        n_clicks: Number of times the clear button was clicked.

    Returns:
        Tuple of (empty_history, welcome_message, empty_input).
    """
    if not n_clicks:
        # No action needed
        from dash.exceptions import PreventUpdate
        raise PreventUpdate

    logger.info("Clearing conversation history")
    return [], [_create_welcome_message()], ""
