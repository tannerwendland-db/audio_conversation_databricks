# Feature Specification: Diarized Transcript Viewer and Reconstruction

**Feature Branch**: `002-diarized-transcript-viewer`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "I want to add a few new features. I want the ability of the user to look at the Diarized text using our custom renderer we wrote that groups them together into a more human readable format. I also want the ability to help restore the diarized transcript from the original stored. The issue being that the Diarized input can be a little garbled because of how the audio slicing works. But we also keep a version of the original transcript. We should be able to reconstruct the diarized text from the original text to make the output higher quality. For this feature we would need a step after diarization to store the result of the reconstructed diarization. This higher quality output is what we will do the embeddings in now. I am truncating the existing database."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Diarized Transcript (Priority: P1)

As a user, I want to view the diarized transcript of my recordings using the existing custom renderer that groups speaker turns together, so I can easily read who said what in a conversation.

**Why this priority**: This is the core viewing functionality that enables users to consume diarized content in a human-readable format. Without this, users cannot effectively review transcribed conversations.

**Independent Test**: Can be fully tested by uploading a recording with diarization complete, then viewing the transcript in the UI. Delivers immediate value by showing speaker-attributed conversation flow.

**Acceptance Scenarios**:

1. **Given** a recording with completed diarization, **When** the user navigates to view the transcript, **Then** they see the diarized text displayed with clear speaker attribution and grouped turns in a readable format.
2. **Given** a diarized transcript is displayed, **When** the user views it, **Then** each speaker turn is visually distinct (different styling for interviewer vs respondent).
3. **Given** a long conversation transcript, **When** the user scrolls through it, **Then** they can easily follow the flow of conversation with clear speaker labels and turn boundaries.

---

### User Story 2 - Automatic Transcript Reconstruction (Priority: P1)

As a system user, I want the diarized transcript to be automatically reconstructed using the higher-quality original transcript after diarization completes, so that the final output has better text accuracy while preserving speaker attribution.

**Why this priority**: This is equally critical as it directly impacts the quality of all downstream functionality (display, search, embeddings). Garbled text from audio slicing degrades the entire user experience.

**Independent Test**: Can be tested by processing a recording and verifying the reconstructed diarization has cleaner text than the raw diarized output while maintaining correct speaker assignments.

**Acceptance Scenarios**:

1. **Given** a recording has completed diarization (producing potentially garbled speaker-attributed text), **When** the reconstruction step runs, **Then** the system aligns the original clean transcript text with the speaker attributions from diarization.
2. **Given** reconstruction completes, **When** the result is stored, **Then** a new "reconstructed diarized text" is persisted separately from the raw diarized text.
3. **Given** reconstruction completes, **When** embeddings are generated, **Then** they use the reconstructed (higher quality) text rather than the raw diarized text.

---

### User Story 3 - Embedding from Reconstructed Text (Priority: P2)

As a user performing semantic search, I want the search embeddings to be generated from the reconstructed high-quality transcript, so that my searches return more accurate and relevant results.

**Why this priority**: This improves search quality but depends on reconstruction being implemented first. Search can function with existing diarized text, just at lower quality.

**Independent Test**: Can be tested by searching for terms that were garbled in raw diarization but correct in the original transcript, and verifying matches are found.

**Acceptance Scenarios**:

1. **Given** a recording with reconstructed diarization, **When** embeddings are generated, **Then** they are created from the reconstructed text with speaker context preserved.
2. **Given** embeddings exist from reconstructed text, **When** a user searches for content, **Then** results match based on the higher-quality reconstructed content.

---

### Edge Cases

- What happens when reconstruction cannot align certain segments? System should preserve the original diarized segment for that portion and log a warning.
- How does the system handle recordings where only raw transcription exists (no diarization)? Reconstruction step is skipped; display falls back to existing behavior.
- What if the original transcript is significantly different in length from the diarized output (speaker overlap, audio artifacts)? Use fuzzy matching with configurable similarity threshold; unmatched segments retain original diarized text.
- What happens during reconstruction if a speaker turn in diarized text maps to multiple sentences in the original? Group the matched original sentences together under that speaker turn.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display diarized transcripts using the existing custom renderer that groups speaker turns with visual distinction between speakers.
- **FR-002**: System MUST provide a "View Transcript" button/tab within the existing recording detail view for viewing the full diarized transcript.
- **FR-003**: System MUST implement a reconstruction step that aligns the clean original transcript text with speaker attributions from diarization.
- **FR-004**: System MUST store the reconstructed diarized transcript as a separate field from the raw diarized text, preserving both versions.
- **FR-005**: System MUST execute the reconstruction step automatically after diarization completes, before embedding generation.
- **FR-006**: System MUST generate embeddings from the reconstructed transcript when available, falling back to raw diarized text if reconstruction fails.
- **FR-007**: System MUST preserve speaker context (speaker labels/prefixes) in the reconstructed output for proper chunking and embedding.
- **FR-008**: System MUST handle reconstruction failures gracefully by falling back to raw diarized text and logging the issue.
- **FR-009**: System MUST update the existing processing pipeline to include the reconstruction step in the correct order: diarize -> reconstruct -> embed.

### Key Entities

- **Transcript**: Extended to include a new field for reconstructed diarized content alongside existing `full_text`, `diarized_text`, and `dialog_json` fields.
- **Recording**: No changes needed; existing relationship to Transcript remains.
- **TranscriptChunk**: No schema changes; chunks will be generated from reconstructed content via existing embedding service.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view the complete diarized transcript for any processed recording within the application.
- **SC-002**: Reconstructed transcripts have at least 90% text accuracy compared to the original transcript (measured by character-level similarity of matched segments).
- **SC-003**: Speaker attributions are preserved correctly in 95% or more of reconstructed speaker turns (measured by manual spot-check sampling).
- **SC-004**: Search results return relevant matches for terms that exist in the original transcript but were garbled in raw diarization.
- **SC-005**: The reconstruction step adds no more than 30 seconds to the total processing time for a typical 30-minute recording.
- **SC-006**: All existing recordings can be re-processed with the new pipeline without data loss (raw and original transcripts preserved).

## Clarifications

### Session 2026-01-05

- Q: Where should the transcript viewer appear in the UI? → A: Add a "View Transcript" button/tab within the existing recording detail view
- Q: What approach for transcript reconstruction algorithm? → A: LLM-based - use an LLM to align and merge speaker turns with clean text
- Q: How to track reconstruction quality in production? → A: No metrics tracking - rely on manual spot-checks (demo project)

## Assumptions

- The existing custom renderer code is functional and can be reused for the transcript viewer without modification.
- The original transcript (`full_text`) contains higher quality text than the diarized output due to audio slicing artifacts in diarization.
- User is truncating the existing database, so migration of existing reconstructed transcripts is not required.
- Reconstruction will use an LLM-based approach to intelligently align and merge the clean original transcript text with speaker attributions from diarization.
- The `dialog_json` structure will be updated to contain the reconstructed text while maintaining the same schema format.
- This is a demo project; no production-grade observability or metrics collection is required for reconstruction quality.
