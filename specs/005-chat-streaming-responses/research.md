# Research: Chat Streaming Responses

**Feature**: 005-chat-streaming-responses
**Date**: 2026-01-16
**Status**: Complete

## Research Questions Addressed

1. How to implement SSE streaming in Dash using dash-extensions?
2. Does ChatDatabricks support streaming token output?
3. Do we need DatabricksOpenAI instead of ChatDatabricks for streaming?
4. How to integrate LangGraph RAG workflow with streaming generation?

---

## Decision 1: SSE Component for Dash Streaming

**Decision**: Use `dash-extensions` SSE component for token-by-token streaming to the UI.

**Rationale**:
- The SSE component provides native support for server-sent events in Dash
- Enables ChatGPT-style streaming without custom WebSocket implementation
- Properties like `concat=True` automatically accumulate streamed tokens
- Animation options (`animate_chunk`, `animate_delay`) provide smooth rendering

**Implementation Pattern**:
```python
from dash_extensions import SSE
from dash_extensions.streaming import sse_options

# Component in layout
SSE(id="sse-stream", concat=True)

# Callback to trigger stream
@app.callback(
    [Output("sse-stream", "url"), Output("sse-stream", "options")],
    Input("submit-btn", "n_clicks"),
    State("query-input", "value")
)
def start_stream(n_clicks, query):
    return "/api/stream", sse_options(payload={"query": query})
```

**Server Endpoint Pattern** (Flask):
```python
from flask import Response
import json

@server.route("/api/stream", methods=["POST"])
def stream_response():
    def generate():
        for token in llm_stream_generator():
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"
    return Response(generate(), mimetype="text/event-stream")
```

**Alternatives Considered**:
- **DashSocketIO**: More complex setup, requires socket.io server
- **Polling**: Higher latency, not true streaming
- **Custom WebSocket**: More implementation overhead than SSE

**Sources**:
- [Plotly Community Discussion](https://community.plotly.com/t/streaming-in-dash-like-chatgpt/87364)
- [dash-extensions GitHub](https://github.com/emilhe/dash-extensions)

---

## Decision 2: ChatDatabricks Streaming Support

**Decision**: Use existing `ChatDatabricks` from `databricks_langchain` with `.stream()` method - no need for DatabricksOpenAI.

**Rationale**:
- `ChatDatabricks` natively supports streaming via `.stream()` method
- Returns an iterator of `BaseMessageChunk` objects
- Already used in the codebase (`src/services/rag.py`), minimizing changes
- Compatible with current LangChain 0.3+ dependency

**Streaming Usage**:
```python
from databricks_langchain import ChatDatabricks

llm = ChatDatabricks(endpoint="databricks-claude-sonnet-4-5")

# Streaming invocation
for chunk in llm.stream("Your prompt here"):
    yield chunk.content  # Token-by-token output
```

**Async Streaming**:
```python
async for chunk in llm.astream("Your prompt here"):
    yield chunk.content
```

**Alternatives Considered**:
- **DatabricksOpenAI**: OpenAI-compatible client, but requires different import and API pattern. Not necessary since ChatDatabricks already supports streaming.
- **databricks_genai_inference**: Lower-level SDK, more complex than LangChain wrapper.

**Sources**:
- [ChatDatabricks LangChain Docs](https://docs.langchain.com/oss/python/integrations/chat/databricks)
- [Databricks Streaming Outputs](https://notebooks.databricks.com/devrel/nbs/streaming_outputs.html)

---

## Decision 3: LangGraph Integration Strategy

**Decision**: Stream only the final generation node; keep retrieval and grading synchronous.

**Rationale**:
- Retrieval is fast (vector similarity search)
- Grading is a short classification task
- Generation is the bottleneck where streaming provides value
- Maintaining synchronous retrieve/grade simplifies the architecture
- Citations can only be displayed after retrieval completes anyway

**Implementation Approach**:
1. Execute retrieve → grade → (optionally rewrite → retrieve) synchronously
2. Once generation starts, stream tokens via SSE
3. After stream completes, send final event with citations

**Modified RAG Flow**:
```
[Sync] retrieve → grade → (rewrite loop if needed)
[Stream] generate → token1 → token2 → ... → tokenN → [citations]
```

**Alternatives Considered**:
- **Full async streaming graph**: More complex, diminishing returns since retrieval/grading are fast
- **Background task with polling**: Higher latency than SSE streaming

---

## Decision 4: Server Configuration for SSE

**Decision**: Use Flask with synchronous SSE handling; consider gevent for production scaling.

**Rationale**:
- Current Dash app uses Flask server (standard)
- Flask supports SSE via generator responses
- For single-user/development, synchronous Flask is sufficient
- For production with concurrent users, gevent workers recommended

**Development Configuration**:
```python
# Standard Flask server (current setup)
app.run_server(host="0.0.0.0", port=8000, debug=True)
```

**Production Configuration** (if needed):
```bash
gunicorn -w 4 -k gevent --bind 0.0.0.0:8000 src.app:server
```

**Alternatives Considered**:
- **FastAPI**: Better async support, but requires migrating away from Dash
- **Separate streaming microservice**: Adds deployment complexity

---

## Decision 5: Pulsing Cursor Implementation

**Decision**: Implement CSS-based pulsing cursor using a blinking caret character appended during streaming.

**Rationale**:
- Pure CSS solution, no JavaScript required
- Consistent with ChatGPT-style UX
- Easily removed when streaming completes

**Implementation**:
```css
.streaming-cursor::after {
    content: '|';
    animation: blink 1s step-end infinite;
}

@keyframes blink {
    50% { opacity: 0; }
}
```

**Component Pattern**:
```python
# During streaming
html.Span(partial_content, className="streaming-cursor")

# After completion
html.Span(full_content)  # No cursor class
```

---

## Dependencies to Add

| Package | Version | Purpose |
|---------|---------|---------|
| dash-extensions | >=1.0.18 | SSE component for streaming |

**Note**: `databricks_langchain` already present and supports streaming.

---

## Technical Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Flask blocking under concurrent SSE streams | Medium | High | Document gevent setup for production; test with concurrent users |
| SSE connection drops mid-stream | Low | Medium | Implement error boundary; preserve partial content |
| ChatDatabricks streaming inconsistency | Low | Medium | Add retry logic; fallback to invoke() if stream fails |
| Browser SSE compatibility issues | Low | Low | SSE is widely supported; add EventSource polyfill if needed |

---

## Unknowns Resolved

All NEEDS CLARIFICATION items from the Technical Context have been resolved:

1. **Update frequency**: Token-by-token via SSE (clarified in spec)
2. **Visual indicator**: Pulsing cursor/caret (clarified in spec)
3. **LLM streaming support**: Confirmed - ChatDatabricks supports `.stream()`
4. **SSE component**: Confirmed - dash-extensions SSE component suitable
5. **DatabricksOpenAI necessity**: Not needed - ChatDatabricks sufficient
