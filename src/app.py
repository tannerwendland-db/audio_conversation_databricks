"""Main Dash application for Audio Conversation RAG System.

This module provides the entry point for the web application,
including the main layout with navigation tabs and health check endpoint.
"""

import json
import re

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, callback, dcc, html
from flask import Response

from src.config import get_settings

# UUID pattern for validating recording IDs in URLs
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Application version
__version__ = "0.1.0"

# Create Dash app with Bootstrap styling and icons
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.BOOTSTRAP,  # Bootstrap icons for UI elements
    ],
    suppress_callback_exceptions=True,
)

# Expose the underlying Flask server for additional routes
server = app.server

# Import components and callbacks AFTER app creation
# This ensures callbacks are registered with the app
from src.components import chat as chat_callbacks  # noqa: E402, F401
from src.components import (  # noqa: E402
    create_chat_component,
    create_library_component,
    create_transcript_view,
    create_upload_component,
)
from src.components import library as library_callbacks  # noqa: E402, F401
from src.components import upload as upload_callbacks  # noqa: E402, F401


# Health check endpoint
@server.route("/health")
def health_check() -> Response:
    """Return health status of the application.

    Returns:
        JSON response with status "healthy".
    """
    return Response(
        json.dumps({"status": "healthy"}),
        mimetype="application/json",
    )


# Navigation bar
navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand("Audio Conversation RAG", className="ms-2"),
        ],
        fluid=True,
    ),
    color="dark",
    dark=True,
    className="mb-4",
)

# Main tab contents - using the new components
upload_tab_content = dbc.Container(
    [
        html.Div(
            id="upload-tab-content",
            children=[create_upload_component()],
        )
    ],
    className="mt-3",
)

library_tab_content = dbc.Container(
    [
        html.Div(
            id="library-tab-content",
            children=[create_library_component()],
        )
    ],
    className="mt-3",
)

chat_tab_content = dbc.Container(
    [
        html.Div(
            id="chat-tab-content",
            children=[create_chat_component()],
        )
    ],
    className="mt-3",
)

# Main tabs
tabs = dbc.Tabs(
    [
        dbc.Tab(upload_tab_content, label="Upload", tab_id="tab-upload"),
        dbc.Tab(library_tab_content, label="Library", tab_id="tab-library"),
        dbc.Tab(chat_tab_content, label="Chat", tab_id="tab-chat"),
    ],
    id="main-tabs",
    active_tab="tab-upload",
)

# Main tabs layout (used for non-transcript views)
main_tabs_layout = dbc.Container(
    [tabs],
    fluid=True,
)

# Footer with version info
footer = dbc.Container(
    [
        html.Hr(),
        html.Footer(
            html.P(
                f"Audio Conversation RAG System v{__version__}",
                className="text-muted text-center",
            ),
            className="py-3",
        ),
    ],
    fluid=True,
)

# Main application layout
app.layout = dbc.Container(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        html.Div(id="page-content"),
        footer,
    ],
    fluid=True,
)


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname: str | None) -> dbc.Container:
    """Route to appropriate content based on URL pathname.

    Args:
        pathname: The current URL pathname.

    Returns:
        The appropriate page content component.
    """
    # Handle /recording/{id} and /transcript/{id} routes (both show transcript view)
    if pathname and (
        pathname.startswith("/recording/") or pathname.startswith("/transcript/")
    ):
        recording_id = pathname.split("/")[-1]
        # Validate UUID format before proceeding
        if UUID_PATTERN.match(recording_id):
            return create_transcript_view(recording_id)
        # Invalid UUID format, show error
        return dbc.Container(
            dbc.Alert(
                "Invalid recording ID format. Please check the URL.",
                color="warning",
            ),
            className="mt-4",
        )
    return main_tabs_layout


if __name__ == "__main__":
    settings = get_settings()
    app.run(debug=settings.DEBUG, host="0.0.0.0", port=8000)
