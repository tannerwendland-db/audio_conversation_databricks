"""Dialog parser service for Audio Conversation RAG System.

This module provides functionality to parse diarized text into structured
dialog JSON format with speaker attributions.
"""

import re
from typing import Any


def _consolidate_consecutive_turns(
    turns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge consecutive turns from the same speaker into single turns.

    Args:
        turns: List of dialog turns with 'speaker' and 'text' keys.

    Returns:
        Consolidated list where consecutive same-speaker turns are merged.
    """
    if not turns:
        return []

    consolidated = []
    current: dict[str, Any] | None = None

    for turn in turns:
        if current is None:
            current = {"speaker": turn["speaker"], "text": turn["text"]}
        elif turn["speaker"] == current["speaker"]:
            # Same speaker - merge text
            current["text"] = f"{current['text']} {turn['text']}"
        else:
            # Different speaker - save current and start new
            consolidated.append(current)
            current = {"speaker": turn["speaker"], "text": turn["text"]}

    # Don't forget the last turn
    if current:
        consolidated.append(current)

    return consolidated


def process_dialog(dialog_text: str) -> list[dict[str, Any]]:
    """Parse diarized text into structured dialog JSON.

    Parses text with speaker labels and timestamps into a list of speaker turns.
    Handles formats like:
    - "SPEAKER_00: [00:00:01] Hello..."
    - "Interviewer: Hello..."
    - "Respondent: Hi there..."

    Args:
        dialog_text: Raw diarized text with speaker labels.

    Returns:
        List of dicts with 'speaker' and 'text' keys representing dialog turns.
    """
    if not dialog_text or not dialog_text.strip():
        return []

    turns: list[dict[str, Any]] = []

    # Pattern to match speaker turns with optional timestamps
    # Matches: "SPEAKER_XX: [timestamp] text" or "Speaker: text"
    # Includes numbered respondents (Respondent1, Respondent2, etc.)
    pattern = (
        r"^(SPEAKER_\d+|Interviewer|Respondent\d*|Speaker\s*\d*):"
        r"\s*(?:\[[^\]]*\])?\s*(.*)$"
    )

    # Split by lines and process
    lines = dialog_text.strip().split("\n")
    current_turn: dict[str, Any] | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            # Save previous turn if exists
            if current_turn and current_turn.get("text"):
                turns.append(current_turn)

            speaker = match.group(1)
            text = match.group(2).strip()

            # Normalize speaker names
            speaker_lower = speaker.lower()
            if "interviewer" in speaker_lower or speaker == "SPEAKER_00":
                speaker_label = "Interviewer"
            elif speaker_lower == "respondent" or speaker == "SPEAKER_01":
                # Plain "Respondent" without number
                speaker_label = "Respondent"
            elif speaker_lower.startswith("respondent"):
                # Numbered respondent (Respondent1, Respondent2, etc.) - preserve label
                speaker_label = speaker
            else:
                speaker_label = speaker

            current_turn = {
                "speaker": speaker_label,
                "text": text,
            }
        elif current_turn:
            # Continuation of current turn
            current_turn["text"] = (current_turn.get("text", "") + " " + line).strip()

    # Don't forget the last turn
    if current_turn and current_turn.get("text"):
        turns.append(current_turn)

    # Consolidate consecutive same-speaker turns
    return _consolidate_consecutive_turns(turns)
