"""Transcript reconstruction service for Audio Conversation RAG System.

This module provides LLM-based reconstruction of diarized transcripts by aligning
clean text from the original Whisper transcription with speaker attributions from
the diarization output.
"""

import json
import logging
from typing import Any

from databricks_langchain import ChatDatabricks
from langchain_core.messages import HumanMessage

from src.config import get_settings

logger = logging.getLogger(__name__)


def _get_llm() -> ChatDatabricks:
    """Get configured ChatDatabricks LLM instance.

    Returns:
        ChatDatabricks instance configured with the LLM endpoint.
    """
    settings = get_settings()
    return ChatDatabricks(endpoint=settings.LLM_ENDPOINT)


def _validate_dialog_structure(data: Any) -> bool:
    """Validate that data has the expected dialog JSON structure.

    Args:
        data: Data to validate.

    Returns:
        True if data is a list of dicts with 'speaker' and 'text' keys.
    """
    if not isinstance(data, list):
        return False

    for item in data:
        if not isinstance(item, dict):
            return False
        if "speaker" not in item or "text" not in item:
            return False

    return True


def _create_reconstruction_prompt(
    full_text: str, dialog_json: list[dict[str, Any]]
) -> str:
    """Create the LLM prompt for transcript reconstruction.

    Args:
        full_text: Clean transcript text from Whisper (no speaker labels).
        dialog_json: Diarized dialog with speaker attributions (potentially garbled text).

    Returns:
        Formatted prompt string for the LLM.
    """
    dialog_str = json.dumps(dialog_json, indent=2)

    # Long prompt lines are intentional for LLM clarity
    return f"""You are a transcript reconstruction assistant. \
Your task is to align clean text with speaker attributions.

INPUTS:
1. Original clean transcript (no speaker labels):
{full_text}

2. Diarized transcript with speaker labels (may have garbled/imperfect text):
{dialog_str}

TASK:
Create a reconstructed dialog by:
1. Keeping the same speaker attributions from the diarized transcript
2. Replacing the garbled text with the corresponding clean text from the original
3. Preserve the turn structure (same number of turns, same speakers)
4. Match text segments semantically - the garbled text should be close to the clean version

OUTPUT FORMAT:
Return ONLY a valid JSON array with the reconstructed dialog.
Each element must have "speaker" and "text" keys.
Example: [{{"speaker": "Interviewer", "text": "Clean text"}}]

IMPORTANT:
- Return ONLY the JSON array, no explanations or markdown
- Keep the exact same number of turns as the input
- Preserve all speaker attributions exactly
- If you cannot confidently match text, use the original diarized text"""


def reconstruct_transcript(
    full_text: str, dialog_json: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reconstruct diarized transcript using LLM to align clean text with speakers.

    Takes the clean original transcript and the diarized dialog JSON, and uses an LLM
    to align the clean text with the speaker attributions from the diarization.

    Args:
        full_text: Clean transcript text from Whisper (no speaker labels).
        dialog_json: Diarized dialog with speaker attributions and potentially garbled text.

    Returns:
        List of dicts with 'speaker' and 'text' keys containing reconstructed dialog.
        Falls back to original dialog_json if reconstruction fails.
    """
    # Handle edge cases
    if not dialog_json:
        return []

    if not full_text or not full_text.strip():
        logger.warning("Empty full_text provided, returning original dialog_json")
        return dialog_json

    try:
        llm = _get_llm()
        prompt = _create_reconstruction_prompt(full_text, dialog_json)

        # Invoke LLM
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content

        # Parse JSON response
        # Handle case where LLM wraps in markdown code block
        if response_text.startswith("```"):
            # Extract content between code blocks
            lines = response_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        reconstructed = json.loads(response_text.strip())

        # Validate structure
        if not _validate_dialog_structure(reconstructed):
            logger.warning(
                "LLM returned invalid dialog structure, falling back to original"
            )
            return dialog_json

        logger.info(
            f"Successfully reconstructed transcript with {len(reconstructed)} turns"
        )
        return reconstructed

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        return dialog_json

    except Exception as e:
        logger.error(f"Reconstruction failed: {e}", exc_info=True)
        return dialog_json
