"""Unit tests for multi-speaker styling utilities.

Tests for the speaker color palette, deterministic color assignment,
label formatting, and backward compatibility with existing 2-speaker transcripts.
"""

import pytest


class TestSpeakerPalette:
    """Tests for SPEAKER_PALETTE constant."""

    def test_palette_contains_10_colors(self):
        """SPEAKER_PALETTE must contain exactly 10 colors."""
        from src.components.transcript import SPEAKER_PALETTE

        assert len(SPEAKER_PALETTE) == 10

    def test_each_palette_entry_has_background_color(self):
        """Each palette entry must have a backgroundColor key."""
        from src.components.transcript import SPEAKER_PALETTE

        for i, entry in enumerate(SPEAKER_PALETTE):
            assert "backgroundColor" in entry, f"Entry {i} missing backgroundColor"
            assert entry["backgroundColor"].startswith("#"), f"Entry {i} not a hex color"

    def test_interviewer_color_is_light_blue(self):
        """Index 0 (Interviewer) must be light blue #e3f2fd."""
        from src.components.transcript import SPEAKER_PALETTE

        assert SPEAKER_PALETTE[0]["backgroundColor"] == "#e3f2fd"

    def test_respondent_color_is_light_gray(self):
        """Index 1 (Respondent) must be light gray #f5f5f5."""
        from src.components.transcript import SPEAKER_PALETTE

        assert SPEAKER_PALETTE[1]["backgroundColor"] == "#f5f5f5"


class TestGetSpeakerColorIndex:
    """Tests for get_speaker_color_index() determinism."""

    def test_same_label_returns_same_index(self):
        """Same speaker label must always return the same color index."""
        from src.components.transcript import get_speaker_color_index

        # Call multiple times with same input
        label = "Respondent3"
        results = [get_speaker_color_index(label) for _ in range(10)]

        assert all(r == results[0] for r in results), "Color index not deterministic"

    def test_different_labels_can_get_different_indices(self):
        """Different speaker labels should generally get different indices."""
        from src.components.transcript import get_speaker_color_index

        labels = ["Respondent1", "Respondent2", "Respondent3", "Respondent4"]
        indices = [get_speaker_color_index(label) for label in labels]

        # At least some should be different (not all same color)
        assert len(set(indices)) > 1, "All speakers got same color"

    def test_index_within_palette_bounds(self):
        """Returned index must be within palette bounds (0-9)."""
        from src.components.transcript import SPEAKER_PALETTE, get_speaker_color_index

        test_labels = [
            "Respondent1",
            "Respondent2",
            "Respondent10",
            "Unknown Speaker",
            "Panel Member A",
            "Focus Group Participant",
        ]

        for label in test_labels:
            index = get_speaker_color_index(label)
            assert 0 <= index < len(SPEAKER_PALETTE), f"Index {index} out of bounds for {label}"


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing 2-speaker transcripts."""

    def test_interviewer_always_gets_index_0(self):
        """Interviewer must always get index 0 (light blue)."""
        from src.components.transcript import get_speaker_color_index

        assert get_speaker_color_index("Interviewer") == 0
        assert get_speaker_color_index("interviewer") == 0
        assert get_speaker_color_index("INTERVIEWER") == 0

    def test_respondent_always_gets_index_1(self):
        """Respondent (without number) must always get index 1 (light gray)."""
        from src.components.transcript import get_speaker_color_index

        assert get_speaker_color_index("Respondent") == 1
        assert get_speaker_color_index("respondent") == 1
        assert get_speaker_color_index("RESPONDENT") == 1

    def test_numbered_respondents_get_different_indices(self):
        """Respondent1, Respondent2, etc. must NOT get index 1."""
        from src.components.transcript import get_speaker_color_index

        # Numbered respondents should use the extended palette (indices 2-9)
        assert get_speaker_color_index("Respondent1") >= 2
        assert get_speaker_color_index("Respondent2") >= 2
        assert get_speaker_color_index("Respondent3") >= 2


class TestFormatSpeakerLabel:
    """Tests for format_speaker_label() function."""

    def test_adds_space_before_number(self):
        """format_speaker_label adds space before number: 'Respondent2' -> 'Respondent 2'."""
        from src.components.transcript import format_speaker_label

        assert format_speaker_label("Respondent2") == "Respondent 2"
        assert format_speaker_label("Respondent10") == "Respondent 10"

    def test_preserves_labels_without_numbers(self):
        """Labels without numbers are unchanged."""
        from src.components.transcript import format_speaker_label

        assert format_speaker_label("Interviewer") == "Interviewer"
        assert format_speaker_label("Respondent") == "Respondent"

    def test_handles_already_spaced_labels(self):
        """Labels with existing spaces should not double-space."""
        from src.components.transcript import format_speaker_label

        # "Respondent 2" should stay as "Respondent 2"
        assert format_speaker_label("Respondent 2") == "Respondent 2"

    def test_handles_speaker_with_multiple_numbers(self):
        """Handle labels like 'Speaker12' correctly."""
        from src.components.transcript import format_speaker_label

        assert format_speaker_label("Speaker12") == "Speaker 12"


class TestGetSpeakerStyle:
    """Tests for get_speaker_style() function."""

    def test_returns_dict_with_background_color(self):
        """get_speaker_style returns dict with backgroundColor."""
        from src.components.transcript import get_speaker_style

        style = get_speaker_style("Respondent1")
        assert "backgroundColor" in style
        assert isinstance(style["backgroundColor"], str)

    def test_interviewer_has_correct_margins(self):
        """Interviewer should be left-aligned with marginRight=20%."""
        from src.components.transcript import get_speaker_style

        style = get_speaker_style("Interviewer")
        assert style["marginRight"] == "20%"
        assert style["marginLeft"] == "0"

    def test_respondent_has_correct_margins(self):
        """Respondent should be right-aligned with marginLeft=20%."""
        from src.components.transcript import get_speaker_style

        style = get_speaker_style("Respondent")
        assert style["marginLeft"] == "20%"
        assert style["marginRight"] == "0"

    def test_numbered_respondent_has_correct_margins(self):
        """Numbered respondents should also have marginLeft=20%."""
        from src.components.transcript import get_speaker_style

        style = get_speaker_style("Respondent2")
        assert style["marginLeft"] == "20%"
        assert style["marginRight"] == "0"


class TestParseSpeakerTurnsMultiSpeaker:
    """Tests for _parse_speaker_turns preserving multi-speaker labels."""

    def test_preserves_respondent1_label(self):
        """_parse_speaker_turns should preserve Respondent1 label."""
        from src.components.transcript import _parse_speaker_turns

        text = "Respondent1: Hello, I'm the first respondent."
        result = _parse_speaker_turns(text)
        assert len(result) == 1
        assert result[0]["speaker"] == "Respondent1"

    def test_preserves_respondent2_label(self):
        """_parse_speaker_turns should preserve Respondent2 label."""
        from src.components.transcript import _parse_speaker_turns

        text = "Respondent2: I'm the second respondent."
        result = _parse_speaker_turns(text)
        assert len(result) == 1
        assert result[0]["speaker"] == "Respondent2"

    def test_multi_speaker_diarized_text(self):
        """Parse diarized text with multiple distinct respondents."""
        from src.components.transcript import _parse_speaker_turns

        text = """Interviewer: Welcome everyone.
Respondent1: Thanks for having us.
Respondent2: Happy to be here."""
        result = _parse_speaker_turns(text)
        assert len(result) == 3
        assert result[0]["speaker"] == "Interviewer"
        assert result[1]["speaker"] == "Respondent1"
        assert result[2]["speaker"] == "Respondent2"


class TestCreateSpeakerBlockMultiSpeaker:
    """Tests for _create_speaker_block using new multi-speaker style system."""

    def test_speaker_block_uses_get_speaker_style(self):
        """Speaker block should get style from get_speaker_style function."""
        from src.components.transcript import (
            _create_speaker_block,
            get_speaker_style,
        )

        turn = {"speaker": "Respondent2", "speaker_type": "respondent", "text": "Hello"}
        block = _create_speaker_block(turn)

        # The block's style should match what get_speaker_style returns
        expected_style = get_speaker_style("Respondent2")
        # Check the block has a style with backgroundColor from Respondent2's palette
        assert block.style is not None
        assert "backgroundColor" in block.style
        assert block.style["backgroundColor"] == expected_style["backgroundColor"]

    def test_different_respondents_get_different_colors(self):
        """Different numbered respondents should get different background colors."""
        from src.components.transcript import _create_speaker_block

        turn1 = {"speaker": "Respondent1", "speaker_type": "respondent", "text": "Hi"}
        turn2 = {"speaker": "Respondent2", "speaker_type": "respondent", "text": "Hey"}

        block1 = _create_speaker_block(turn1)
        block2 = _create_speaker_block(turn2)

        # They should have different background colors (from extended palette)
        color1 = block1.style["backgroundColor"]
        color2 = block2.style["backgroundColor"]
        assert color1 != color2, "Different respondents should have different colors"

    def test_speaker_label_is_formatted(self):
        """Speaker label in block should be formatted (Respondent2 -> Respondent 2)."""
        from src.components.transcript import _create_speaker_block

        turn = {"speaker": "Respondent2", "speaker_type": "respondent", "text": "Test"}
        block = _create_speaker_block(turn)

        # Find the speaker label in the card body
        # The card body should contain a Strong element with formatted label
        card_body = block.children
        # Navigate the structure to find the speaker label
        # CardBody -> [Div with Strong, P with text]
        header_div = card_body.children[0]  # First child is the header div
        strong_element = header_div.children[0]  # Strong element with speaker name
        assert "Respondent 2" in str(strong_element.children), (
            "Speaker label should be formatted with space"
        )


class TestSearchAttributionMultiSpeaker:
    """Tests for search results showing correct speaker attribution (US2)."""

    def test_search_results_preserve_multi_speaker_labels(self):
        """Search results should show correct speaker labels (e.g., Respondent 2)."""
        from src.components.transcript import _create_speaker_block

        # Simulate a search match in a multi-speaker turn
        turn = {
            "speaker": "Respondent2",
            "speaker_type": "respondent",
            "text": "I found the keyword here",
        }
        block = _create_speaker_block(turn, search_query="keyword")

        # The block should still have proper styling and formatted label
        card_body = block.children
        header_div = card_body.children[0]
        strong_element = header_div.children[0]

        # Label should be formatted
        assert "Respondent 2" in str(strong_element.children)

        # Color should match Respondent2's palette (not generic respondent)
        from src.components.transcript import get_speaker_style

        expected_style = get_speaker_style("Respondent2")
        assert block.style["backgroundColor"] == expected_style["backgroundColor"]

    def test_search_highlighting_works_with_multi_speaker(self):
        """Search highlighting should work with multi-speaker blocks."""
        from src.components.transcript import _create_speaker_block

        turn = {
            "speaker": "Respondent1",
            "speaker_type": "respondent",
            "text": "This contains the search term here",
        }
        block = _create_speaker_block(turn, search_query="search")

        # Block should be created successfully
        assert block is not None
        # Should have proper color from extended palette
        from src.components.transcript import get_speaker_style

        expected_style = get_speaker_style("Respondent1")
        assert block.style["backgroundColor"] == expected_style["backgroundColor"]


class TestSpeakerLegend:
    """Tests for speaker legend component (US3)."""

    def test_create_speaker_legend_returns_component(self):
        """_create_speaker_legend should return a Dash component."""
        from src.components.transcript import _create_speaker_legend

        dialog_json = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Respondent1", "text": "Hi"},
            {"speaker": "Respondent2", "text": "Hey"},
        ]
        legend = _create_speaker_legend(dialog_json)
        assert legend is not None

    def test_legend_shows_all_unique_speakers(self):
        """Legend should show all unique speakers from the dialog."""
        from src.components.transcript import _create_speaker_legend

        dialog_json = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Respondent1", "text": "Hi"},
            {"speaker": "Respondent2", "text": "Hey"},
            {"speaker": "Respondent1", "text": "Me again"},  # Duplicate
        ]
        legend = _create_speaker_legend(dialog_json)

        # Convert to string to check content
        legend_str = str(legend)
        assert "Interviewer" in legend_str
        assert "Respondent 1" in legend_str  # Should be formatted
        assert "Respondent 2" in legend_str  # Should be formatted

    def test_legend_includes_color_swatches(self):
        """Legend should include colored swatches for each speaker."""
        from src.components.transcript import _create_speaker_legend, SPEAKER_PALETTE

        dialog_json = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Respondent", "text": "Hi"},
        ]
        legend = _create_speaker_legend(dialog_json)

        # The legend should contain background colors from palette
        legend_str = str(legend)
        # Interviewer should have light blue
        assert SPEAKER_PALETTE[0]["backgroundColor"] in legend_str
        # Respondent should have light gray
        assert SPEAKER_PALETTE[1]["backgroundColor"] in legend_str

    def test_legend_empty_for_no_speakers(self):
        """Legend should handle empty dialog gracefully."""
        from src.components.transcript import _create_speaker_legend

        legend = _create_speaker_legend([])
        # Should return None or empty component for empty dialog
        assert legend is None or str(legend) == ""
