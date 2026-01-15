# Tasks: Diarized Transcript Viewer and Reconstruction

**Input**: Design documents from `/specs/002-diarized-transcript-viewer/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Required per constitution (Test-First Development - NON-NEGOTIABLE)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root

---

## Phase 1: Setup

**Purpose**: Project structure verification and database preparation

- [X] T001 Verify feature branch `002-diarized-transcript-viewer` is active
- [X] T002 Truncate existing database tables (recordings, transcripts, transcript_chunks) per user request

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: The new model field is shared across all user stories and must be added first

- [X] T003 Add `reconstructed_dialog_json` JSONB field to Transcript model in src/models/transcript.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View Diarized Transcript (Priority: P1)

**Goal**: Users can view diarized transcripts using the existing custom renderer with a dedicated button in the library

**Independent Test**: Upload a recording with completed diarization, click "View Transcript" button, verify transcript displays with speaker grouping and styling

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (TDD - Constitution Requirement)**

- [X] T004 [P] [US1] Unit test for "View Transcript" button rendering in tests/unit/components/test_library_transcript_button.py
- [X] T005 [P] [US1] Integration test for transcript view navigation in tests/integration/test_transcript_navigation.py

### Implementation for User Story 1

- [X] T006 [US1] Add "View Transcript" button to recording cards in src/components/library.py
- [X] T007 [US1] Verify/update route configuration for `/transcript/{recording_id}` in src/app.py (if needed)
- [X] T008 [US1] Update transcript component fallback chain to prefer `reconstructed_dialog_json` in src/components/transcript.py

**Checkpoint**: User Story 1 complete - users can view diarized transcripts via dedicated button

---

## Phase 4: User Story 2 - Automatic Transcript Reconstruction (Priority: P1)

**Goal**: System automatically reconstructs diarized transcript using LLM to align clean original text with speaker attributions

**Independent Test**: Process a recording, verify `reconstructed_dialog_json` is populated with cleaner text than raw `dialog_json` while preserving speaker assignments

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (TDD - Constitution Requirement)**

- [X] T009 [P] [US2] Unit test for reconstruction service with mocked LLM in tests/unit/services/test_reconstruction.py
- [X] T010 [P] [US2] Unit test for reconstruction error handling and fallback in tests/unit/services/test_reconstruction.py
- [X] T011 [P] [US2] Integration test for reconstruction in recording pipeline in tests/integration/test_recording_pipeline_reconstruction.py

### Implementation for User Story 2

- [X] T012 [US2] Create reconstruction service with LLM prompt in src/services/reconstruction.py
- [X] T013 [US2] Implement `reconstruct_transcript()` function that takes `full_text` and `dialog_json`, returns `reconstructed_dialog_json` in src/services/reconstruction.py
- [X] T014 [US2] Add error handling for LLM failures with fallback to `dialog_json` in src/services/reconstruction.py
- [X] T015 [US2] Update processing pipeline to call reconstruction after diarization in src/services/recording.py
- [X] T016 [US2] Store `reconstructed_dialog_json` in transcript record in src/services/recording.py

**Checkpoint**: User Story 2 complete - reconstruction automatically runs after diarization

---

## Phase 5: User Story 3 - Embedding from Reconstructed Text (Priority: P2)

**Goal**: Embeddings are generated from reconstructed high-quality transcript for better search results

**Independent Test**: Search for terms that were garbled in raw diarization but correct in original transcript, verify matches are found

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (TDD - Constitution Requirement)**

- [X] T017 [P] [US3] Unit test for embedding service preferring reconstructed content in tests/unit/services/test_embedding_reconstructed.py
- [X] T018 [P] [US3] Integration test for search using reconstructed embeddings in tests/integration/test_search_reconstructed.py

### Implementation for User Story 3

- [X] T019 [US3] Update `chunk_dialog()` in src/services/embedding.py to accept source parameter (reconstructed vs original)
- [X] T020 [US3] Update pipeline to prefer `reconstructed_dialog_json` when calling embedding service in src/services/recording.py
- [X] T021 [US3] Implement fallback: use `dialog_json` if `reconstructed_dialog_json` is None in src/services/recording.py

**Checkpoint**: User Story 3 complete - embeddings use reconstructed content for better search quality

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T022 [P] Run ruff linter and fix any issues
- [X] T023 [P] Verify type hints on all new functions
- [X] T024 Run full test suite and ensure all tests pass
- [X] T025 Validate quickstart.md scenarios work as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (different files)
  - US3 depends on US2 completion (needs reconstruction to exist)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P2)**: Depends on User Story 2 completion (embedding needs reconstructed content to exist)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD - Constitution)
- Services before pipeline integration
- Story complete before moving to next priority

### Parallel Opportunities

- T004, T005 can run in parallel (different test files)
- T009, T010, T011 can run in parallel (different test focuses)
- T017, T018 can run in parallel (different test files)
- US1 and US2 can be worked on in parallel after Phase 2

---

## Parallel Example: User Story 2 Tests

```bash
# Launch all tests for User Story 2 together:
Task: "Unit test for reconstruction service with mocked LLM in tests/unit/services/test_reconstruction.py"
Task: "Unit test for reconstruction error handling and fallback in tests/unit/services/test_reconstruction.py"
Task: "Integration test for reconstruction in recording pipeline in tests/integration/test_recording_pipeline_reconstruction.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (add model field)
3. Complete Phase 3: User Story 1 (View Transcript button)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Can demo transcript viewing immediately

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test independently -> Demo (can view transcripts!)
3. Add User Story 2 -> Test independently -> Demo (reconstructed transcripts!)
4. Add User Story 3 -> Test independently -> Demo (better search!)
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (View Transcript)
   - Developer B: User Story 2 (Reconstruction)
3. After US2 complete: Developer C starts User Story 3

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests MUST fail before implementing (TDD - Constitution requirement)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
