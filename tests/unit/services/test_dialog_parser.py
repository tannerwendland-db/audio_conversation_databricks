"""Unit tests for dialog_parser service."""

from src.services.dialog_parser import (
    _consolidate_consecutive_turns,
    process_dialog,
)


class TestConsolidateConsecutiveTurns:
    """Tests for _consolidate_consecutive_turns function."""

    def test_empty_input(self):
        """Empty list returns empty list."""
        result = _consolidate_consecutive_turns([])
        assert result == []

    def test_single_turn(self):
        """Single turn is returned unchanged."""
        turns = [{"speaker": "Interviewer", "text": "Hello"}]
        result = _consolidate_consecutive_turns(turns)
        assert result == [{"speaker": "Interviewer", "text": "Hello"}]

    def test_alternating_speakers(self):
        """Alternating speakers are preserved as separate turns."""
        turns = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Respondent", "text": "Hi there"},
            {"speaker": "Interviewer", "text": "How are you?"},
        ]
        result = _consolidate_consecutive_turns(turns)
        assert len(result) == 3
        assert result[0] == {"speaker": "Interviewer", "text": "Hello"}
        assert result[1] == {"speaker": "Respondent", "text": "Hi there"}
        assert result[2] == {"speaker": "Interviewer", "text": "How are you?"}

    def test_consecutive_same_speaker_merged(self):
        """Consecutive turns from same speaker are merged."""
        turns = [
            {"speaker": "Interviewer", "text": "Hello"},
            {"speaker": "Interviewer", "text": "How are you?"},
            {"speaker": "Interviewer", "text": "Nice to meet you."},
        ]
        result = _consolidate_consecutive_turns(turns)
        assert len(result) == 1
        assert result[0]["speaker"] == "Interviewer"
        assert result[0]["text"] == "Hello How are you? Nice to meet you."

    def test_mixed_consolidation(self):
        """Mix of consecutive same-speaker and alternating turns."""
        turns = [
            {"speaker": "Interviewer", "text": "Awesome. Yeah,"},
            {"speaker": "Interviewer", "text": "thank you for meeting."},
            {"speaker": "Respondent", "text": "No problem."},
            {"speaker": "Respondent", "text": "Happy to be here."},
            {"speaker": "Interviewer", "text": "Great!"},
        ]
        result = _consolidate_consecutive_turns(turns)
        assert len(result) == 3
        assert result[0] == {
            "speaker": "Interviewer",
            "text": "Awesome. Yeah, thank you for meeting.",
        }
        assert result[1] == {
            "speaker": "Respondent",
            "text": "No problem. Happy to be here.",
        }
        assert result[2] == {"speaker": "Interviewer", "text": "Great!"}


class TestProcessDialog:
    """Tests for process_dialog function with consolidation."""

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert process_dialog("") == []
        assert process_dialog("   ") == []

    def test_single_speaker_turn(self):
        """Single speaker turn is parsed correctly."""
        dialog = "SPEAKER_00: [00:00:01] Hello there."
        result = process_dialog(dialog)
        assert len(result) == 1
        assert result[0]["speaker"] == "Interviewer"
        assert result[0]["text"] == "Hello there."

    def test_consecutive_same_speaker_consolidated(self):
        """Consecutive same-speaker lines are consolidated."""
        dialog = """SPEAKER_00: [00:00:01] Hello
SPEAKER_00: [00:00:02] How are you
SPEAKER_00: [00:00:03] Nice to meet you"""
        result = process_dialog(dialog)
        assert len(result) == 1
        assert result[0]["speaker"] == "Interviewer"
        assert result[0]["text"] == "Hello How are you Nice to meet you"

    def test_alternating_speakers_preserved(self):
        """Alternating speakers remain as separate turns."""
        dialog = """SPEAKER_00: [00:00:01] Hello
SPEAKER_01: [00:00:02] Hi there
SPEAKER_00: [00:00:03] How are you?"""
        result = process_dialog(dialog)
        assert len(result) == 3
        assert result[0]["speaker"] == "Interviewer"
        assert result[1]["speaker"] == "Respondent"
        assert result[2]["speaker"] == "Interviewer"

    def test_realistic_fragmented_input(self):
        """Realistic fragmented diarization output is properly consolidated."""
        dialog = """SPEAKER_00: [00:00:01] Awesome. Yeah,
SPEAKER_00: [00:00:02] thank you for meeting. I
SPEAKER_00: [00:00:03] know it's a little
SPEAKER_00: [00:00:04] bit later in the day for some
SPEAKER_00: [00:00:05] of us. But I
SPEAKER_00: [00:00:06] wanted to
SPEAKER_00: [00:00:07] kind of get you guys together
SPEAKER_00: [00:00:08] to"""
        result = process_dialog(dialog)
        assert len(result) == 1
        assert result[0]["speaker"] == "Interviewer"
        expected_text = (
            "Awesome. Yeah, thank you for meeting. I know it's a little "
            "bit later in the day for some of us. But I wanted to "
            "kind of get you guys together to"
        )
        assert result[0]["text"] == expected_text


class TestMultiSpeakerPreservation:
    """Tests for preserving multi-speaker labels (Respondent1, Respondent2, etc.)."""

    def test_preserves_respondent1_label(self):
        """Respondent1 label should be preserved, not normalized to Respondent."""
        dialog = "Respondent1: Hello, I'm the first respondent."
        result = process_dialog(dialog)
        assert len(result) == 1
        assert result[0]["speaker"] == "Respondent1"
        assert result[0]["text"] == "Hello, I'm the first respondent."

    def test_preserves_respondent2_label(self):
        """Respondent2 label should be preserved, not normalized to Respondent."""
        dialog = "Respondent2: I'm the second respondent."
        result = process_dialog(dialog)
        assert len(result) == 1
        assert result[0]["speaker"] == "Respondent2"
        assert result[0]["text"] == "I'm the second respondent."

    def test_multi_speaker_conversation(self):
        """Multi-speaker conversation preserves distinct speaker labels."""
        dialog = """Interviewer: Welcome everyone.
Respondent1: Thanks for having us.
Respondent2: Happy to be here.
Respondent1: Should I go first?
Interviewer: Yes please."""
        result = process_dialog(dialog)
        assert len(result) == 5
        assert result[0]["speaker"] == "Interviewer"
        assert result[1]["speaker"] == "Respondent1"
        assert result[2]["speaker"] == "Respondent2"
        assert result[3]["speaker"] == "Respondent1"
        assert result[4]["speaker"] == "Interviewer"

    def test_plain_respondent_still_normalized(self):
        """Plain 'Respondent' (without number) should still work as before."""
        dialog = "Respondent: Just a single respondent."
        result = process_dialog(dialog)
        assert len(result) == 1
        assert result[0]["speaker"] == "Respondent"

    def test_consecutive_respondent1_consolidated(self):
        """Consecutive turns from same numbered respondent are consolidated."""
        dialog = """Respondent1: First part.
Respondent1: Second part.
Respondent2: Different speaker."""
        result = process_dialog(dialog)
        assert len(result) == 2
        assert result[0]["speaker"] == "Respondent1"
        assert result[0]["text"] == "First part. Second part."
        assert result[1]["speaker"] == "Respondent2"
