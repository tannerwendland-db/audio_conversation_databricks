# Data Model: Multi-Speaker Conversation Rendering

**Feature**: 003-multi-speaker-conversation
**Date**: 2026-01-14

## Overview

This feature requires **no database schema changes**. The existing data model already supports multiple speakers; the issue is purely in the UI rendering layer.

## Existing Entities (Unchanged)

### Transcript

The `Transcript` model already stores multi-speaker data correctly:

| Field | Type | Description |
|-------|------|-------------|
| `dialog_json` | `list[dict]` | Parsed speaker turns: `[{"speaker": "Respondent1", "text": "..."}]` |
| `diarized_text` | `str` | Raw diarized text with speaker labels |
| `reconstructed_dialog_json` | `list[dict]` | LLM-cleaned dialog with speakers |

**Key Insight**: The pyfunc outputs distinct speaker labels (Interviewer, Respondent, Respondent1, Respondent2), and these are stored correctly in the database. The rollup issue occurs in two places:
1. `dialog_parser.py` normalizes Respondent1/Respondent2 to "Respondent"
2. `transcript.py` only has styles for "interviewer" and "respondent"

### DialogTurn (Logical Entity - Not Persisted Separately)

A single turn in a conversation, stored within `dialog_json`:

| Field | Type | Description |
|-------|------|-------------|
| `speaker` | `str` | Speaker label (e.g., "Interviewer", "Respondent", "Respondent1") |
| `text` | `str` | The spoken text content |

## New Logical Entities (UI Layer Only)

### SpeakerStyle

Configuration for rendering a speaker's turns. This is a UI-only concept, not persisted:

| Field | Type | Description |
|-------|------|-------------|
| `backgroundColor` | `str` | CSS hex color for card background |
| `textAlign` | `str` | Text alignment ("left") |
| `marginLeft` | `str` | Left margin for visual offset |
| `marginRight` | `str` | Right margin for visual offset |

### SpeakerPalette

Collection of colors for multi-speaker support:

| Index | Label Pattern | Color |
|-------|---------------|-------|
| 0 | Interviewer | #e3f2fd (Light Blue) |
| 1 | Respondent | #f5f5f5 (Light Gray) |
| 2-9 | RespondentN, Other | Extended palette (see research.md) |

## Validation Rules

1. **Speaker labels** must be non-empty strings
2. **Color indices** must be within palette bounds (0-9, with cycling for >10)
3. **Backward compatibility**: "Interviewer" and "Respondent" always map to indices 0 and 1

## State Transitions

N/A - This feature does not involve any state machines or workflow changes.

## Data Volume Assumptions

- Typical transcripts: 2-5 speakers
- Maximum expected: ~10 speakers (panel discussions, focus groups)
- Palette cycles after 10 distinct speakers

## Migration Requirements

**None required**. Existing data is already correctly structured. Changes are purely in the rendering code.
