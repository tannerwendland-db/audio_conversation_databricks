# Quickstart: Chat Streaming Responses

**Feature**: 005-chat-streaming-responses
**Date**: 2026-01-16

## Prerequisites

- Python 3.11+
- Existing project setup (virtualenv, dependencies installed)
- Access to Databricks model serving endpoint

## Setup

### 1. Install New Dependency

Add `dash-extensions` to your dependencies:

```bash
# Using pip
pip install "dash-extensions>=1.0.18"

# Or add to pyproject.toml
# dash-extensions = ">=1.0.18"
```

### 2. Verify Databricks Streaming Support

Test that ChatDatabricks streaming works:

```python
from databricks_langchain import ChatDatabricks

llm = ChatDatabricks(endpoint="databricks-claude-sonnet-4-5")

# Test streaming
for chunk in llm.stream("Say hello"):
    print(chunk.content, end="", flush=True)
print()  # Newline after stream
```

Expected: Tokens appear incrementally, not all at once.

## Key Components

### SSE Component (Frontend)

```python
from dash_extensions import SSE

# In your layout
SSE(
    id="chat-sse",
    concat=True,  # Accumulate tokens
)
```

### SSE Endpoint (Backend)

```python
from flask import Response
import json

@server.route("/api/chat/stream", methods=["POST"])
def stream_chat():
    def generate():
        # ... retrieval and grading ...
        for chunk in llm.stream(prompt):
            event = {"content": chunk.content}
            yield f"event: token\ndata: {json.dumps(event)}\n\n"
        yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"
        yield "event: done\ndata: {}\n\n"
    return Response(generate(), mimetype="text/event-stream")
```

### Trigger Callback

```python
from dash_extensions.streaming import sse_options

@app.callback(
    [Output("chat-sse", "url"), Output("chat-sse", "options")],
    Input("send-btn", "n_clicks"),
    State("query-input", "value"),
    State("session-id", "data"),
)
def start_stream(n_clicks, query, session_id):
    if not n_clicks or not query:
        raise PreventUpdate
    return "/api/chat/stream", sse_options(
        payload={"query": query, "session_id": session_id}
    )
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run streaming-specific tests
pytest tests/unit/test_streaming.py
pytest tests/integration/test_sse_endpoint.py
pytest tests/contract/test_sse_contract.py
```

## Development Server

```bash
# Standard development (single user)
python src/app.py

# With gevent for concurrent SSE support
pip install gevent gunicorn
gunicorn -w 1 -k gevent --bind 0.0.0.0:8000 src.app:server
```

## Troubleshooting

### Tokens not streaming (all-at-once response)

1. Verify ChatDatabricks streaming works in isolation (see test above)
2. Check browser Network tab - SSE events should appear incrementally
3. Ensure `Response` has `mimetype="text/event-stream"`

### SSE connection drops

1. Check for proxy/load balancer timeout settings
2. Verify Flask server is running with SSE-compatible worker
3. Review browser console for connection errors

### Cursor not appearing

1. Verify CSS is loaded (check for `.streaming-cursor` class)
2. Ensure `is_streaming` state is correctly set during streaming
3. Check that clientside callback is updating the UI

## File Structure Reference

```
src/
├── components/
│   └── chat.py              # SSE component integration
├── services/
│   ├── rag.py               # Streaming generation function
│   └── streaming.py         # SSE endpoint logic
└── app.py                   # SSE route registration

tests/
├── unit/test_streaming.py
├── integration/test_sse_endpoint.py
└── contract/test_sse_contract.py
```

## Next Steps

After implementing this feature:

1. Run `/speckit.tasks` to generate implementation tasks
2. Follow TDD workflow: write failing tests first
3. Implement streaming service
4. Update chat component
5. Verify all acceptance scenarios pass
