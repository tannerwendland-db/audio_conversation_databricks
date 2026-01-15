"""Transcript service for Audio Conversation RAG System.

This module provides functions for searching within transcript text,
highlighting matches, and retrieving transcripts from the database.
"""

import re

from sqlalchemy.orm import Session

from src.models.transcript import Transcript


def search_transcript(transcript_text: str, query: str) -> list[dict]:
    """Find all occurrences of query in transcript text.

    Performs case-insensitive search for the query string within the
    transcript text and returns the positions and matched text for
    each occurrence.

    Args:
        transcript_text: The full transcript text to search within.
        query: The search term to find.

    Returns:
        A list of dicts, each containing:
            - start (int): Starting index of the match in the text.
            - end (int): Ending index of the match (exclusive).
            - match (str): The matched text (preserving original case).

        Returns an empty list if query or text is empty, or if no matches found.
    """
    if not transcript_text or not query:
        return []

    # Escape special regex characters in the query
    escaped_query = re.escape(query)

    matches = []
    for match in re.finditer(escaped_query, transcript_text, re.IGNORECASE):
        matches.append(
            {
                "start": match.start(),
                "end": match.end(),
                "match": match.group(),
            }
        )

    return matches


def highlight_matches(text: str, query: str) -> str:
    """Return text with query matches wrapped in <mark> tags.

    Performs case-insensitive matching but preserves the original case
    of matched text in the output.

    Args:
        text: The text to add highlighting to.
        query: The search term to highlight.

    Returns:
        The text with all occurrences of query wrapped in <mark></mark> tags.
        Returns the original text unchanged if query or text is empty.
    """
    if not text or not query:
        return text

    # Escape special regex characters in the query
    escaped_query = re.escape(query)

    def replace_with_mark(match: re.Match) -> str:
        """Wrap the matched text in mark tags."""
        return f"<mark>{match.group()}</mark>"

    return re.sub(escaped_query, replace_with_mark, text, flags=re.IGNORECASE)


def get_transcript_by_recording_id(
    session: Session,
    recording_id: str,
) -> Transcript | None:
    """Fetch transcript for a given recording ID from the database.

    Args:
        session: SQLAlchemy database session.
        recording_id: UUID of the recording whose transcript to retrieve.

    Returns:
        The Transcript instance if found, None otherwise.
    """
    return session.query(Transcript).filter_by(recording_id=recording_id).first()
