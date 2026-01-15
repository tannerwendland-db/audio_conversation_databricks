# Quickstart: Multi-Speaker Conversation Rendering

**Feature**: 003-multi-speaker-conversation
**Date**: 2026-01-14

## Overview

This guide describes how to implement multi-speaker support in the transcript viewer. The feature enables visual distinction of 10+ unique speakers with deterministic color assignment.

## Prerequisites

- Python 3.11+
- Existing codebase with `src/components/transcript.py` and `src/services/dialog_parser.py`
- pytest for running tests

## Implementation Steps

### Step 1: Extend Speaker Palette (transcript.py)

Replace the existing `SPEAKER_STYLES` dict with an extended palette:

```python
# 10-color accessible palette for multi-speaker support
SPEAKER_PALETTE = [
    {"backgroundColor": "#e3f2fd", "name": "Light Blue"},      # 0: Interviewer
    {"backgroundColor": "#f5f5f5", "name": "Light Gray"},      # 1: Respondent
    {"backgroundColor": "#e8f5e9", "name": "Light Green"},     # 2: Respondent1
    {"backgroundColor": "#fff8e1", "name": "Light Amber"},     # 3: Respondent2
    {"backgroundColor": "#f3e5f5", "name": "Light Purple"},    # 4: Respondent3
    {"backgroundColor": "#e0f2f1", "name": "Light Teal"},      # 5: Respondent4
    {"backgroundColor": "#fce4ec", "name": "Light Pink"},      # 6: Respondent5
    {"backgroundColor": "#e0f7fa", "name": "Light Cyan"},      # 7: Respondent6
    {"backgroundColor": "#f9fbe7", "name": "Light Lime"},      # 8: Respondent7
    {"backgroundColor": "#fff3e0", "name": "Light Orange"},    # 9: Respondent8
]
```

### Step 2: Add Deterministic Color Assignment (transcript.py)

```python
FIXED_SPEAKER_COLORS = {
    "interviewer": 0,
    "respondent": 1,
}

def get_speaker_color_index(speaker_label: str) -> int:
    """Get deterministic color index for a speaker label."""
    label_lower = speaker_label.lower()
    if label_lower in FIXED_SPEAKER_COLORS:
        return FIXED_SPEAKER_COLORS[label_lower]
    hash_value = sum(ord(c) for c in label_lower)
    return 2 + (hash_value % (len(SPEAKER_PALETTE) - 2))

def get_speaker_style(speaker_label: str) -> dict:
    """Get style dict for a speaker label."""
    index = get_speaker_color_index(speaker_label)
    base_style = SPEAKER_PALETTE[index].copy()
    # Position: Interviewer left-aligned, others right-aligned
    if speaker_label.lower() == "interviewer":
        base_style.update({"marginRight": "20%", "marginLeft": "0", "textAlign": "left"})
    else:
        base_style.update({"marginLeft": "20%", "marginRight": "0", "textAlign": "left"})
    return base_style
```

### Step 3: Add Label Formatting (transcript.py)

```python
def format_speaker_label(speaker_label: str) -> str:
    """Format speaker label for display (add space before numbers)."""
    import re
    return re.sub(r'(\D)(\d)', r'\1 \2', speaker_label)
```

### Step 4: Fix Dialog Parser (dialog_parser.py)

Update the speaker normalization to preserve multi-speaker labels:

```python
# BEFORE (normalizes all respondents):
if "respondent" in speaker_lower or speaker == "SPEAKER_01":
    speaker_label = "Respondent"

# AFTER (preserves distinct respondent labels):
if speaker_lower == "respondent" or speaker == "SPEAKER_01":
    speaker_label = "Respondent"
elif speaker_lower.startswith("respondent"):
    speaker_label = speaker  # Preserve Respondent1, Respondent2, etc.
```

### Step 5: Update Speaker Block Creation (transcript.py)

Update `_create_speaker_block` to use the new style system:

```python
def _create_speaker_block(turn: dict, search_query: str | None = None) -> dbc.Card:
    speaker_label = turn.get("speaker", "Unknown")
    style = get_speaker_style(speaker_label)
    display_label = format_speaker_label(speaker_label)
    # ... rest of implementation
```

## Testing

Run tests with:
```bash
pytest tests/unit/test_speaker_styles.py -v
pytest tests/integration/test_transcript_multi_speaker.py -v
```

## Verification

1. Upload a multi-speaker audio file (3+ speakers)
2. Verify each speaker displays with a distinct background color
3. Verify speaker labels show formatted (e.g., "Respondent 2" not "Respondent2")
4. Verify existing 2-speaker transcripts render with unchanged colors
