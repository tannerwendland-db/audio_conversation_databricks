# Feature Specification: Speaker Embedding Matching for Cross-Chunk Alignment

**Feature Branch**: `004-speaker-embedding-matching`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "Speaker embedding matching for cross-chunk speaker alignment - use voice fingerprints to maintain consistent speaker identity when audio is processed in chunks due to 16MB payload limits"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent Speaker Labels Across Long Recordings (Priority: P1)

As a user uploading a long interview recording that exceeds the 16MB payload limit, I want the system to maintain consistent speaker labels (Interviewer, Respondent) throughout the entire transcript, even when the audio is processed in multiple chunks.

**Why this priority**: This is the core problem being solved. Without consistent speaker alignment, transcripts from long recordings become unusable because speakers may swap labels mid-conversation.

**Independent Test**: Can be fully tested by uploading a 30+ minute interview recording and verifying that the same person maintains the same label (Interviewer or Respondent) throughout the entire transcript.

**Acceptance Scenarios**:

1. **Given** a 45-minute interview recording that requires chunking, **When** the system processes and transcribes it, **Then** the first speaker in chunk 1 retains their label (e.g., "Interviewer") in all subsequent chunks.
2. **Given** an audio file processed in 3 chunks, **When** the same voice speaks in chunks 1, 2, and 3, **Then** that voice is assigned the same speaker label in all chunks.
3. **Given** a recording with 2 speakers, **When** processing completes, **Then** the transcript shows exactly 2 distinct speaker labels consistently applied throughout.

---

### User Story 2 - Graceful Handling of New Speakers in Later Chunks (Priority: P2)

As a user uploading a recording where a third participant joins mid-conversation, I want the system to correctly identify them as a new speaker while maintaining the original two speakers' identities.

**Why this priority**: Multi-party conversations are common in real-world recordings. The system must handle speakers appearing/disappearing across chunks.

**Independent Test**: Can be tested by uploading a recording where speaker 3 joins partway through, verifying they get a new label while speakers 1 and 2 retain original labels.

**Acceptance Scenarios**:

1. **Given** a recording where a third speaker appears only in chunk 3, **When** processing completes, **Then** speakers 1 and 2 retain their original labels and speaker 3 receives a new label (e.g., "Respondent2").
2. **Given** a speaker who was silent in chunk 2 but spoke in chunks 1 and 3, **When** processing completes, **Then** that speaker maintains their original label across all chunks.

---

### User Story 3 - Speaker Embedding Persistence for Re-processing (Priority: P3)

As a system administrator, I want speaker embeddings to be stored so that the system can track which speakers were identified in a recording and support future capabilities like cross-recording speaker identification.

**Why this priority**: Enables future features like speaker identification across multiple recordings, audit trails of processing results, and potential manual correction workflows.

**Independent Test**: Can be tested by processing a recording, verifying embeddings are stored, then re-processing and confirming old embeddings are replaced with fresh extractions.

**Acceptance Scenarios**:

1. **Given** a previously processed recording with stored speaker embeddings, **When** the same recording is re-processed, **Then** all existing embeddings are replaced with newly extracted ones (fresh start).
2. **Given** a recording that has been processed, **When** viewing the recording's data, **Then** the associated speaker embeddings are accessible for potential cross-recording comparison.

---

### Edge Cases

- What happens when a chunk contains only one speaker? The system should still extract and store that speaker's embedding for matching.
- How does the system handle very short utterances (< 1 second)? Embeddings should only be extracted from segments with sufficient audio for reliable voice fingerprinting.
- What happens when the embedding model cannot confidently match a speaker? The system treats low-confidence matches (below threshold) as new speakers, assigns a new label, and adds the embedding to the reference set for matching in subsequent chunks.
- How does the system handle audio quality degradation between chunks? The embedding matching should account for reasonable quality variations.
- What happens when all speakers in a chunk are silent? The system should gracefully handle empty chunks without affecting other chunk alignments.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract speaker voice embeddings from diarized audio segments using a dedicated embedding model.
- **FR-002**: System MUST store reference speaker embeddings from the first chunk of a recording for use in subsequent chunk processing.
- **FR-003**: System MUST compare speaker embeddings from subsequent chunks against reference embeddings using cosine similarity.
- **FR-004**: System MUST remap speaker labels in subsequent chunks to match reference speakers when similarity exceeds the matching threshold.
- **FR-005**: System MUST assign new speaker labels for voices that do not match any reference embedding above the threshold, and MUST add these new speakers' embeddings to the reference set for subsequent chunk matching.
- **FR-006**: System MUST persist speaker embeddings associated with each recording for potential re-processing.
- **FR-007**: System MUST only extract embeddings from audio segments longer than 1 second to ensure reliable voice fingerprinting.
- **FR-008**: System MUST maintain speaker label consistency even when a speaker is absent from intermediate chunks.
- **FR-009**: System MUST handle recordings with 2-5 distinct speakers.
- **FR-010**: System MUST process chunked audio in sequential order to maintain embedding reference chain.

### Key Entities

- **Speaker Embedding**: A numerical vector representation of a speaker's voice characteristics, stored in a dedicated `speaker_embeddings` table with foreign key to Recording. Contains the embedding vector, speaker label, and creation timestamp.
- **Reference Embedding Set**: The collection of speaker embeddings from the first chunk of a recording, used as the baseline for matching speakers in subsequent chunks.
- **Similarity Score**: A measure (0.0 to 1.0) of how closely a new speaker embedding matches a reference embedding.
- **Recording**: Related to speaker embeddings via one-to-many relationship (one recording has multiple speaker embeddings).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Speaker labels remain consistent across chunks for 95% of recordings with 2-3 speakers.
- **SC-002**: Users reviewing transcripts report correct speaker attribution in 90% of spot-checked utterances.
- **SC-003**: Processing time for chunked recordings increases by no more than 20% compared to current non-aligned processing.
- **SC-004**: Speaker matching correctly identifies returning speakers (who were silent for 1+ chunks) in 85% of cases.
- **SC-005**: New speakers appearing mid-recording are correctly identified as distinct from existing speakers 90% of the time.

## Clarifications

### Session 2026-01-14

- Q: Where should speaker embeddings be stored? → A: In a new dedicated speaker_embeddings table with foreign key to recording.
- Q: What should happen when a speaker cannot be confidently matched (below threshold)? → A: Treat as new speaker, assign new label, and add to reference set for future chunks.
- Q: When re-processing a recording with existing embeddings, what should happen? → A: Replace all embeddings with newly extracted ones (fresh start).

## Assumptions

- The pyannote embedding model (or equivalent like wespeaker) provides sufficiently discriminative voice embeddings for speaker matching.
- A cosine similarity threshold of approximately 0.7-0.8 will provide good balance between false positives and false negatives (to be tuned during implementation).
- Audio quality is consistent enough within a recording that embeddings remain comparable across chunks.
- Chunk boundaries will be determined by the 16MB payload limit, resulting in chunks of approximately 10-15 minutes of audio depending on format and quality.
- The existing diarization pipeline output provides sufficient segment information to extract per-speaker audio for embedding generation.
