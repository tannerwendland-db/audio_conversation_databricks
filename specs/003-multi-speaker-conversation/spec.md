# Feature Specification: Multi-Speaker Conversation Rendering

**Feature Branch**: `003-multi-speaker-conversation`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "I want to add a new feature to our app to roll up the conversation for multiple speakers. The audio endpoint actually responds with multiple respondents from our pyfunc. We need the ability to render the conversation with all the speakers intact."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Multi-Participant Conversations Distinctly (Priority: P1)

As a user reviewing transcribed audio with multiple speakers (e.g., a panel interview, focus group, or meeting with multiple participants), I want each unique speaker to be visually distinguished so that I can easily follow who said what throughout the conversation.

**Why this priority**: This is the core value proposition. Without distinct speaker rendering, multi-participant audio loses critical attribution context, making transcripts difficult to follow and analyze.

**Independent Test**: Can be fully tested by uploading a multi-speaker audio file and verifying each speaker appears with unique visual styling. Delivers immediate value by making transcripts readable.

**Acceptance Scenarios**:

1. **Given** a transcript with 3+ speakers (e.g., Interviewer, Respondent, Respondent1, Respondent2), **When** I view the transcript, **Then** each speaker type displays with a distinct visual style (background color and/or positioning)
2. **Given** a transcript with multiple respondents, **When** I view the transcript, **Then** "Respondent" and "Respondent1" and "Respondent2" are visually distinguishable from each other
3. **Given** a speaker labeled "Respondent2", **When** I view their turn in the transcript, **Then** the speaker label clearly shows "Respondent 2" (with space for readability)

---

### User Story 2 - Search Results Show Correct Speaker Attribution (Priority: P2)

As a user searching through a multi-speaker transcript, I want search results to correctly attribute quotes to the specific speaker (not just "Respondent" for all non-interviewers) so that I can understand the context of each match.

**Why this priority**: Search is a key feature for analyzing transcripts. Without correct speaker attribution in results, users cannot determine which participant made a specific statement.

**Independent Test**: Can be tested by searching a multi-speaker transcript and verifying search result highlights show correct speaker labels.

**Acceptance Scenarios**:

1. **Given** a multi-speaker transcript, **When** I search for a term spoken by "Respondent2", **Then** the search result shows "Respondent 2" as the speaker
2. **Given** search results spanning multiple speakers, **When** I view the highlighted results, **Then** each result correctly shows the specific speaker who said the matched text

---

### User Story 3 - Speaker Legend/Key (Priority: P3)

As a user viewing a conversation with many speakers, I want to see a summary of all participants at a glance so that I can understand the conversation dynamics before diving into the transcript.

**Why this priority**: Enhances usability for complex conversations but not required for basic multi-speaker support.

**Independent Test**: Can be tested by viewing a multi-speaker transcript and verifying a speaker summary/legend appears showing all unique speakers with their visual styling.

**Acceptance Scenarios**:

1. **Given** a transcript with 4 speakers, **When** I view the transcript, **Then** I can see a legend/summary showing all 4 speakers with their respective colors
2. **Given** the speaker legend, **When** I look at it, **Then** I can quickly understand the visual encoding (which color = which speaker)

---

### Edge Cases

- What happens when there are more than 10 speakers? System should continue assigning distinct colors from a predefined palette, cycling if necessary.
- How does the system handle speaker labels like "SPEAKER_00" vs "Interviewer"? Both should be normalized to readable labels.
- What happens when a speaker label cannot be determined? Display as "Unknown Speaker" with neutral styling.
- How does the system handle very long speaker labels? Truncate with ellipsis in the UI while preserving full label in data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display each unique speaker with a visually distinct style (background color and/or positioning)
- **FR-002**: System MUST support at least 10 distinct speaker styles before cycling through the color palette
- **FR-002a**: System MUST assign colors deterministically based on speaker label (same label always maps to same color within a transcript)
- **FR-003**: System MUST normalize speaker labels to human-readable format ("Respondent 2" instead of "Respondent2", "SPEAKER_02" normalized to appropriate label)
- **FR-004**: System MUST preserve speaker attribution when displaying search results within transcripts
- **FR-005**: System MUST handle edge cases of unknown/unlabeled speakers gracefully with a default "Unknown Speaker" style
- **FR-006**: System MUST maintain backward compatibility with existing two-speaker transcripts (Interviewer/Respondent)
- **FR-007**: System MUST apply consistent speaker styling across all transcript views (modal, search results, main view)
- **FR-008**: System MUST preserve existing speaker color conventions (Interviewer = blue tones, Respondents = gray/neutral tones with variation)

### Key Entities

- **Speaker**: A participant in a conversation, identified by label (Interviewer, Respondent, Respondent1, etc.) with associated visual styling
- **SpeakerStyle**: Visual presentation attributes for a speaker (background color, text color, margin/positioning)
- **DialogTurn**: A segment of conversation attributed to a single speaker, containing the speaker label and text content

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can distinguish all speakers in a 5+ participant conversation without confusion
- **SC-002**: 100% of transcribed multi-speaker audio files display with correct speaker attribution (no rollup of distinct speakers)
- **SC-003**: Search results in multi-speaker transcripts show correct speaker attribution in 100% of cases
- **SC-004**: Existing two-speaker transcripts continue to render identically to current behavior (zero regression)
- **SC-005**: Users can identify speaker changes in the transcript at a glance within 1 second

## Clarifications

### Session 2026-01-14

- Q: Should existing transcripts be reprocessed to restore multi-speaker attribution? → A: No reprocessing - apply only to new transcripts; existing data displays as-is
- Q: How should speaker colors be assigned for multiple respondents? → A: Deterministic by label - hash speaker label to palette index for consistent color per speaker

## Assumptions

- The pyfunc/audio endpoint already returns distinct speaker labels (Interviewer, Respondent, Respondent1, Respondent2, etc.) - this is confirmed in the codebase
- Existing transcripts will NOT be reprocessed; multi-speaker rendering applies only to newly processed audio
- The dialog parsing service already preserves multiple speaker labels - this needs to be verified and potentially updated
- Speaker colors will follow a predefined palette that maintains accessibility (sufficient contrast for readability)
- Speaker count in typical use cases will be under 10 participants
