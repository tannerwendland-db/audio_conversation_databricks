# Data Model: Chat Streaming Responses

**Feature**: 005-chat-streaming-responses
**Date**: 2026-01-16

## Overview

This feature primarily modifies the **runtime state** of the chat component rather than persisted data. The key entities describe the streaming state and message structure during token delivery.

## Entities

### StreamState (Runtime)

Tracks the current state of streaming for the chat interface.

| Field | Type | Description |
|-------|------|-------------|
| status | Enum | Current streaming status: `idle`, `streaming`, `complete`, `error` |
| session_id | str | Unique session identifier (existing, from chat component) |
| partial_content | str | Accumulated tokens during streaming |
| error_message | str | null | Error details if status is `error` |

**State Transitions**:
```
idle → streaming (on query submit)
streaming → complete (on final token)
streaming → error (on failure)
complete → idle (ready for next query)
error → idle (after acknowledgment)
```

### StreamingMessage (Runtime)

Represents a message actively being streamed.

| Field | Type | Description |
|-------|------|-------------|
| role | str | Always "assistant" for streaming messages |
| content | str | Partial content accumulated so far |
| is_streaming | bool | True while tokens are still arriving |
| citations | list | null | Citations (null until streaming completes) |

### SSEEvent (Wire Format)

Structure of events sent over the SSE connection.

| Field | Type | Description |
|-------|------|-------------|
| type | str | Event type: `token`, `citations`, `error`, `done` |
| data | varies | Event payload (see below) |

**Event Payloads**:

- `token`: `{"content": "<token_string>"}`
- `citations`: `{"citations": [<citation_objects>]}`
- `error`: `{"message": "<error_message>"}`
- `done`: `{}`

### Citation (Existing - Unchanged)

Source citation structure, already defined in the system.

| Field | Type | Description |
|-------|------|-------------|
| recording_id | str | ID of the source recording |
| recording_title | str | Title of the source recording |
| excerpt | str | Relevant text excerpt |
| speaker | str | null | Speaker attribution if available |

## Relationships

```
ChatSession (existing)
    │
    └── StreamState (1:1, runtime)
            │
            └── StreamingMessage (0..1, active during streaming)

SSEEndpoint
    │
    └── SSEEvent (1:many, sent over connection)
            │
            ├── token events (many)
            ├── citations event (0..1)
            └── done/error event (1)
```

## Validation Rules

### StreamState
- `status` must be one of: `idle`, `streaming`, `complete`, `error`
- `partial_content` can only be non-empty when `status` is `streaming` or `complete`
- `error_message` can only be non-null when `status` is `error`

### SSEEvent
- `type` must be one of: `token`, `citations`, `error`, `done`
- `token` events must have non-empty `content` string
- `citations` event can only be sent after all `token` events
- `done` or `error` must be the final event in a stream

### StreamingMessage
- `is_streaming` must be `True` while `status` is `streaming`
- `citations` must remain `null` until `is_streaming` becomes `False`

## No Database Changes

This feature does not modify the PostgreSQL schema. All entities are runtime/transient:
- `StreamState`: Stored in Dash `dcc.Store` (session storage)
- `StreamingMessage`: Rendered in UI, not persisted
- `SSEEvent`: Transmitted over HTTP, not persisted

Existing entities (`ChatMessage`, `Citation`) are unchanged in structure.
