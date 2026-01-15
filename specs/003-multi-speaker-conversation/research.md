# Research: Multi-Speaker Conversation Rendering

**Feature**: 003-multi-speaker-conversation
**Date**: 2026-01-14

## Research Areas

### 1. Accessible Color Palette for Multiple Speakers

**Decision**: Use a curated 10-color palette with sufficient contrast differentiation

**Rationale**:
- WCAG 2.1 AA requires 4.5:1 contrast ratio for normal text on background colors
- Light background colors with dark text are most accessible
- Distinct hues help users with color vision deficiencies distinguish speakers
- Pastel/light variants of hues work well for card backgrounds

**Palette Selection**:

| Index | Speaker Type | Background Color | Hex Code | Notes |
|-------|--------------|------------------|----------|-------|
| 0 | Interviewer | Light Blue | #e3f2fd | Existing - keep for backward compat |
| 1 | Respondent | Light Gray | #f5f5f5 | Existing - keep for backward compat |
| 2 | Respondent1 | Light Green | #e8f5e9 | Distinct from gray |
| 3 | Respondent2 | Light Amber | #fff8e1 | Warm tone |
| 4 | Respondent3 | Light Purple | #f3e5f5 | Cool tone |
| 5 | Respondent4 | Light Teal | #e0f2f1 | Blue-green |
| 6 | Respondent5 | Light Pink | #fce4ec | Red family |
| 7 | Respondent6 | Light Cyan | #e0f7fa | Light blue variant |
| 8 | Respondent7 | Light Lime | #f9fbe7 | Yellow-green |
| 9 | Respondent8 | Light Orange | #fff3e0 | Orange family |

**Alternatives Considered**:
- Material Design 100-level colors (selected - good accessibility, consistent design language)
- Bootstrap theme colors (rejected - too saturated for card backgrounds)
- Auto-generated HSL palette (rejected - unpredictable contrast ratios)

### 2. Deterministic Color Assignment

**Decision**: Use simple string hash modulo palette length

**Rationale**:
- Python's `hash()` is deterministic within a session but not across sessions
- For UI consistency, use a custom hash function (sum of character codes) that is deterministic across all Python invocations
- Simple implementation, no external dependencies
- Same speaker label always gets same color within and across transcripts

**Implementation Approach**:
```python
def get_speaker_color_index(speaker_label: str) -> int:
    """Get deterministic color index for a speaker label."""
    # Use sum of character codes for cross-session determinism
    hash_value = sum(ord(c) for c in speaker_label.lower())
    return hash_value % len(SPEAKER_PALETTE)
```

**Alternatives Considered**:
- Python built-in `hash()` (rejected - not deterministic across Python invocations)
- MD5/SHA hash (rejected - overkill for simple color assignment)
- Sequential assignment by order of appearance (rejected - same speaker could get different colors in different transcripts)

### 3. Speaker Label Normalization

**Decision**: Preserve original labels from pyfunc; only format for display

**Rationale**:
- The pyfunc already outputs well-structured labels (Interviewer, Respondent, Respondent1, etc.)
- dialog_parser.py currently normalizes Respondent1/Respondent2 to just "Respondent" - this needs to be fixed
- Display formatting adds space before numbers: "Respondent2" -> "Respondent 2"

**Changes Required**:
1. `dialog_parser.py`: Remove normalization that collapses Respondent1/Respondent2 to "Respondent"
2. `transcript.py`: Add display formatter for speaker labels
3. `transcript.py`: Update `_parse_speaker_turns` to preserve original labels

**Alternatives Considered**:
- Store normalized labels in database (rejected - loses information, requires migration)
- Normalize all speakers to generic "Speaker 1", "Speaker 2" (rejected - loses semantic meaning of Interviewer role)

### 4. Backward Compatibility

**Decision**: Interviewer and Respondent retain existing colors; new speakers use extended palette

**Rationale**:
- Existing users expect Interviewer=blue, Respondent=gray
- Hash-based assignment must special-case these two labels
- Existing transcripts with only Interviewer/Respondent render identically

**Implementation**:
```python
FIXED_SPEAKER_COLORS = {
    "interviewer": 0,  # Light Blue
    "respondent": 1,   # Light Gray
}

def get_speaker_color_index(speaker_label: str) -> int:
    label_lower = speaker_label.lower()
    if label_lower in FIXED_SPEAKER_COLORS:
        return FIXED_SPEAKER_COLORS[label_lower]
    # Hash-based for other speakers
    hash_value = sum(ord(c) for c in label_lower)
    # Skip first 2 colors (reserved) and use remaining palette
    return 2 + (hash_value % (len(SPEAKER_PALETTE) - 2))
```

## Summary

All research areas resolved. No NEEDS CLARIFICATION items remain. Ready for Phase 1 design.
