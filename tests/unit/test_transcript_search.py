"""Unit tests for the transcript search service module.

This module tests the transcript search functions for finding and highlighting
text matches within transcript content. Following TDD approach - these tests
are written BEFORE the implementation.

Task: T065 - Phase 5 (User Story 3 - Browse and Review Individual Recordings)
"""


class TestSearchTranscript:
    """Test cases for search_transcript() function."""

    def test_basic_search_returns_match(self):
        """Basic search should return match with start, end, and matched text."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting."
        result = search_transcript(text, "welcome")

        assert len(result) == 1
        assert result[0]["start"] == 7
        assert result[0]["end"] == 14
        assert result[0]["match"] == "welcome"

    def test_case_insensitive_search(self):
        """Search should be case-insensitive."""
        from src.services.transcript import search_transcript

        text = "Hello, WELCOME to the Meeting."
        result = search_transcript(text, "welcome")

        assert len(result) == 1
        assert result[0]["match"] == "WELCOME"

    def test_case_insensitive_query_uppercase(self):
        """Uppercase query should match lowercase text."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting."
        result = search_transcript(text, "WELCOME")

        assert len(result) == 1
        assert result[0]["match"] == "welcome"

    def test_multiple_matches_returned(self):
        """Search should return all matches when query appears multiple times."""
        from src.services.transcript import search_transcript

        text = "The meeting was great. Another meeting is scheduled."
        result = search_transcript(text, "meeting")

        assert len(result) == 2
        assert result[0]["match"] == "meeting"
        assert result[1]["match"] == "meeting"
        # Verify positions are different
        assert result[0]["start"] != result[1]["start"]

    def test_no_matches_returns_empty_list(self):
        """Search with no matches should return empty list."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting."
        result = search_transcript(text, "goodbye")

        assert result == []

    def test_empty_query_returns_empty_list(self):
        """Empty query should return empty list."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting."
        result = search_transcript(text, "")

        assert result == []

    def test_empty_text_returns_empty_list(self):
        """Empty text should return empty list."""
        from src.services.transcript import search_transcript

        result = search_transcript("", "hello")

        assert result == []

    def test_special_characters_in_query(self):
        """Search should handle special regex characters in query."""
        from src.services.transcript import search_transcript

        text = "What is the price? It costs $100.00 each."
        result = search_transcript(text, "$100.00")

        assert len(result) == 1
        assert result[0]["match"] == "$100.00"

    def test_special_characters_brackets(self):
        """Search should handle bracket characters in query."""
        from src.services.transcript import search_transcript

        text = "[SPEAKER_00 0:00:00] Hello everyone."
        result = search_transcript(text, "[SPEAKER_00")

        assert len(result) == 1
        assert result[0]["match"] == "[SPEAKER_00"

    def test_whitespace_query_returns_empty_list(self):
        """Whitespace-only query should return empty list."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting."
        result = search_transcript(text, "   ")

        assert result == []

    def test_match_positions_are_correct(self):
        """Returned positions should correctly index into original text."""
        from src.services.transcript import search_transcript

        text = "The quick brown fox jumps."
        result = search_transcript(text, "brown")

        assert len(result) == 1
        start = result[0]["start"]
        end = result[0]["end"]
        # Verify slicing with positions gives back the match
        assert text[start:end] == "brown"

    def test_match_at_beginning_of_text(self):
        """Search should find match at the beginning of text."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting."
        result = search_transcript(text, "Hello")

        assert len(result) == 1
        assert result[0]["start"] == 0
        assert result[0]["end"] == 5

    def test_match_at_end_of_text(self):
        """Search should find match at the end of text."""
        from src.services.transcript import search_transcript

        text = "Hello, welcome to the meeting"
        result = search_transcript(text, "meeting")

        assert len(result) == 1
        assert result[0]["end"] == len(text)

    def test_overlapping_matches(self):
        """Search should find overlapping pattern occurrences."""
        from src.services.transcript import search_transcript

        text = "aaaa"
        result = search_transcript(text, "aa")

        # Standard regex finditer does not return overlapping matches
        # "aa" in "aaaa" finds matches at positions 0 and 2
        assert len(result) == 2
        assert result[0]["start"] == 0
        assert result[1]["start"] == 2

    def test_multiline_text_search(self):
        """Search should work across multiline text."""
        from src.services.transcript import search_transcript

        text = """[SPEAKER_00 0:00:00]
Hello everyone, welcome to the meeting.

[SPEAKER_01 0:00:05]
Thanks for having us. Let's discuss the project updates."""

        result = search_transcript(text, "project")

        assert len(result) == 1
        assert result[0]["match"] == "project"

    def test_returns_list_of_dicts(self):
        """Return type should be list[dict] with correct keys."""
        from src.services.transcript import search_transcript

        text = "Hello world"
        result = search_transcript(text, "world")

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert "start" in result[0]
        assert "end" in result[0]
        assert "match" in result[0]

    def test_unicode_characters_in_text(self):
        """Search should handle unicode characters in text."""
        from src.services.transcript import search_transcript

        text = "The cafe has great coffee."
        result = search_transcript(text, "cafe")

        assert len(result) == 1
        assert result[0]["match"] == "cafe"

    def test_unicode_characters_in_query(self):
        """Search should handle unicode characters in query."""
        from src.services.transcript import search_transcript

        text = "The cafe has great coffee."
        result = search_transcript(text, "cafe")

        assert len(result) == 1


class TestHighlightMatches:
    """Test cases for highlight_matches() function."""

    def test_single_match_highlighting(self):
        """Single match should be wrapped in mark tags."""
        from src.services.transcript import highlight_matches

        text = "Hello, welcome to the meeting."
        result = highlight_matches(text, "welcome")

        assert result == "Hello, <mark>welcome</mark> to the meeting."

    def test_multiple_match_highlighting(self):
        """Multiple matches should all be wrapped in mark tags."""
        from src.services.transcript import highlight_matches

        text = "The meeting was great. Another meeting is scheduled."
        result = highlight_matches(text, "meeting")

        assert (
            result
            == "The <mark>meeting</mark> was great. Another <mark>meeting</mark> is scheduled."
        )

    def test_case_insensitive_highlighting_preserves_case(self):
        """Highlighting should preserve original case of matched text."""
        from src.services.transcript import highlight_matches

        text = "Hello, WELCOME to the Meeting."
        result = highlight_matches(text, "welcome")

        # Should highlight WELCOME, preserving its original case
        assert "<mark>WELCOME</mark>" in result

    def test_case_insensitive_mixed_case_query(self):
        """Mixed case query should match and preserve original text case."""
        from src.services.transcript import highlight_matches

        text = "The MEETING was about meeting prep."
        result = highlight_matches(text, "MeEtInG")

        assert result == "The <mark>MEETING</mark> was about <mark>meeting</mark> prep."

    def test_no_matches_returns_original_text(self):
        """Text with no matches should be returned unchanged."""
        from src.services.transcript import highlight_matches

        text = "Hello, welcome to the meeting."
        result = highlight_matches(text, "goodbye")

        assert result == text

    def test_empty_query_returns_original_text(self):
        """Empty query should return original text unchanged."""
        from src.services.transcript import highlight_matches

        text = "Hello, welcome to the meeting."
        result = highlight_matches(text, "")

        assert result == text

    def test_empty_text_returns_empty_string(self):
        """Empty text should return empty string."""
        from src.services.transcript import highlight_matches

        result = highlight_matches("", "hello")

        assert result == ""

    def test_whitespace_query_returns_original_text(self):
        """Whitespace-only query should return original text unchanged."""
        from src.services.transcript import highlight_matches

        text = "Hello, welcome to the meeting."
        result = highlight_matches(text, "   ")

        assert result == text

    def test_special_characters_in_query(self):
        """Highlighting should handle special regex characters in query."""
        from src.services.transcript import highlight_matches

        text = "What is the price? It costs $100.00 each."
        result = highlight_matches(text, "$100.00")

        assert result == "What is the price? It costs <mark>$100.00</mark> each."

    def test_special_characters_parentheses(self):
        """Highlighting should handle parentheses in query."""
        from src.services.transcript import highlight_matches

        text = "The function foo() was called."
        result = highlight_matches(text, "foo()")

        assert result == "The function <mark>foo()</mark> was called."

    def test_match_at_beginning(self):
        """Match at beginning of text should be highlighted."""
        from src.services.transcript import highlight_matches

        text = "Hello, welcome to the meeting."
        result = highlight_matches(text, "Hello")

        assert result == "<mark>Hello</mark>, welcome to the meeting."

    def test_match_at_end(self):
        """Match at end of text should be highlighted."""
        from src.services.transcript import highlight_matches

        text = "Hello, welcome to the meeting"
        result = highlight_matches(text, "meeting")

        assert result == "Hello, welcome to the <mark>meeting</mark>"

    def test_multiline_text_highlighting(self):
        """Highlighting should work across multiline text."""
        from src.services.transcript import highlight_matches

        text = """[SPEAKER_00 0:00:00]
Hello everyone, welcome to the meeting.

[SPEAKER_01 0:00:05]
Thanks for the welcome. Let's discuss."""

        result = highlight_matches(text, "welcome")

        assert result.count("<mark>welcome</mark>") == 2

    def test_adjacent_matches(self):
        """Adjacent matches should both be highlighted."""
        from src.services.transcript import highlight_matches

        text = "testtest"
        result = highlight_matches(text, "test")

        assert result == "<mark>test</mark><mark>test</mark>"

    def test_returns_string(self):
        """Return type should be str."""
        from src.services.transcript import highlight_matches

        result = highlight_matches("Hello world", "world")

        assert isinstance(result, str)

    def test_speaker_label_highlighting(self):
        """Highlighting should work with speaker labels in transcript."""
        from src.services.transcript import highlight_matches

        text = """[SPEAKER_00 0:00:00]
Hello everyone, welcome to the meeting.

[SPEAKER_01 0:00:05]
Thanks for having us."""

        result = highlight_matches(text, "SPEAKER_00")

        assert "<mark>SPEAKER_00</mark>" in result

    def test_does_not_double_escape_html(self):
        """Existing HTML entities in text should not be affected."""
        from src.services.transcript import highlight_matches

        text = "The result is &gt; 100."
        result = highlight_matches(text, "result")

        assert result == "The <mark>result</mark> is &gt; 100."

    def test_preserves_newlines_and_whitespace(self):
        """Highlighting should preserve newlines and whitespace."""
        from src.services.transcript import highlight_matches

        text = "Line one\n\nLine two  with  spaces"
        result = highlight_matches(text, "Line")

        assert result == "<mark>Line</mark> one\n\n<mark>Line</mark> two  with  spaces"


class TestSearchTranscriptEdgeCases:
    """Edge case tests for search_transcript() function."""

    def test_very_long_text(self):
        """Search should handle very long transcripts efficiently."""
        from src.services.transcript import search_transcript

        long_text = "This is a sample sentence for testing. " * 1000
        result = search_transcript(long_text, "sample")

        assert len(result) == 1000

    def test_very_long_query(self):
        """Search should handle long query strings."""
        from src.services.transcript import search_transcript

        long_query = "This is a very long search query that spans many words"
        text = f"Start. {long_query} End."
        result = search_transcript(text, long_query)

        assert len(result) == 1
        assert result[0]["match"] == long_query

    def test_none_text_returns_empty_list(self):
        """None as text should return empty list."""
        from src.services.transcript import search_transcript

        result = search_transcript(None, "hello")
        assert result == []

    def test_none_query_returns_empty_list(self):
        """None as query should return empty list."""
        from src.services.transcript import search_transcript

        result = search_transcript("Hello world", None)
        assert result == []

    def test_numeric_content_search(self):
        """Search should work with numeric content."""
        from src.services.transcript import search_transcript

        text = "The meeting is at 10:30 AM on 2024-01-15."
        result = search_transcript(text, "10:30")

        assert len(result) == 1
        assert result[0]["match"] == "10:30"


class TestHighlightMatchesEdgeCases:
    """Edge case tests for highlight_matches() function."""

    def test_very_long_text(self):
        """Highlighting should handle very long transcripts."""
        from src.services.transcript import highlight_matches

        long_text = "This is a sample sentence for testing. " * 1000
        result = highlight_matches(long_text, "sample")

        assert result.count("<mark>sample</mark>") == 1000

    def test_none_text_returns_none(self):
        """None as text should return None."""
        from src.services.transcript import highlight_matches

        result = highlight_matches(None, "hello")
        assert result is None

    def test_none_query_returns_original_text(self):
        """None as query should return original text."""
        from src.services.transcript import highlight_matches

        result = highlight_matches("Hello world", None)
        assert result == "Hello world"

    def test_text_with_existing_mark_tags(self):
        """Text with existing mark tags should not interfere with highlighting."""
        from src.services.transcript import highlight_matches

        text = "This has <mark>existing</mark> marks and hello."
        result = highlight_matches(text, "hello")

        # Should still highlight 'hello' without breaking existing marks
        assert "<mark>hello</mark>" in result
        assert "<mark>existing</mark>" in result

    def test_query_containing_mark_tag(self):
        """Query containing mark tag text should be handled safely."""
        from src.services.transcript import highlight_matches

        text = "The word <mark> appears in text."
        result = highlight_matches(text, "<mark>")

        assert "<mark><mark></mark>" in result


class TestSearchTranscriptWithSampleFixture:
    """Test search_transcript with sample transcript fixture data."""

    def test_search_in_diarized_content(self, sample_transcript):
        """Search should work with diarized transcript content."""
        from src.services.transcript import search_transcript

        result = search_transcript(sample_transcript.diarized_text, "project")

        assert len(result) >= 1
        assert any(m["match"].lower() == "project" for m in result)

    def test_search_speaker_label(self, sample_transcript):
        """Search should find speaker labels in diarized content."""
        from src.services.transcript import search_transcript

        result = search_transcript(sample_transcript.diarized_text, "SPEAKER_00")

        assert len(result) >= 1

    def test_search_in_full_text(self, sample_transcript):
        """Search should work with full_text transcript content."""
        from src.services.transcript import search_transcript

        result = search_transcript(sample_transcript.full_text, "meeting")

        assert len(result) >= 1


class TestHighlightMatchesWithSampleFixture:
    """Test highlight_matches with sample transcript fixture data."""

    def test_highlight_in_diarized_content(self, sample_transcript):
        """Highlighting should work with diarized transcript content."""
        from src.services.transcript import highlight_matches

        result = highlight_matches(sample_transcript.diarized_text, "project")

        assert "<mark>" in result
        assert "</mark>" in result

    def test_highlight_speaker_label(self, sample_transcript):
        """Highlighting should work with speaker labels."""
        from src.services.transcript import highlight_matches

        result = highlight_matches(sample_transcript.diarized_text, "SPEAKER_00")

        assert "<mark>SPEAKER_00</mark>" in result
