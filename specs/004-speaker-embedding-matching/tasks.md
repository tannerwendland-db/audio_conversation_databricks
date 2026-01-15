# Tasks: Speaker Embedding Matching for Cross-Chunk Alignment

**Input**: Design documents from `/specs/004-speaker-embedding-matching/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution requirement (Test-First Development)

**Organization**: Tasks are grouped by deployment target (Model vs App) and user story

**Key Constraint**: Model changes (Phase 2) MUST be deployed to Databricks before App changes (Phase 3+) can be tested end-to-end

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- **[MODEL]**: Task is for MLflow model (deploy first)
- **[APP]**: Task is for Dash application (deploy after model)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify prerequisites and environment readiness

- [X] T001 Verify pyannote embedding model access (requires HuggingFace token with pyannote/embedding permissions)
- [X] T002 [P] Verify pgvector extension is enabled in target database
- [X] T003 [P] Add pgvector to app dependencies in pyproject.toml or requirements.txt

---

## Phase 2: Model Changes (Deploy to Databricks FIRST)

**Purpose**: Add speaker embedding extraction and cross-chunk matching to MLflow model

**CRITICAL**: These changes must be deployed and tested on Databricks Model Serving before App changes in Phase 3+

### Implementation for Model

- [X] T007 [MODEL] Load pyannote/embedding model in load_context() in notebooks/audio_diarization_pyfunc.py
- [X] T008 [MODEL] Add _extract_speaker_embeddings() method to extract embeddings per speaker in notebooks/audio_diarization_pyfunc.py
- [X] T009 [MODEL] Add _compute_cosine_similarity() helper method in notebooks/audio_diarization_pyfunc.py
- [X] T010 [MODEL] Add _match_speakers() method for cross-chunk label remapping in notebooks/audio_diarization_pyfunc.py
- [X] T011 [MODEL] Update input schema to accept reference_embeddings and chunk_index in notebooks/audio_diarization_pyfunc.py
- [X] T012 [MODEL] Update output schema to include speaker_embeddings field in notebooks/audio_diarization_pyfunc.py
- [X] T013 [MODEL] Modify _transcribe_with_speakers() to call embedding extraction and matching in notebooks/audio_diarization_pyfunc.py
- [X] T014 [MODEL] Update predict() to handle new input fields and return embeddings in notebooks/audio_diarization_pyfunc.py
- [X] T015 [MODEL] Register new model version and update serving endpoint alias in notebooks/audio_diarization_pyfunc.py
- [X] T016 [MODEL] Manual verification: Test model endpoint with multi-chunk audio in Databricks

**Checkpoint**: Model deployed with embedding support. Verify via endpoint test before proceeding.

---

## Phase 3: App Foundational (Database & Models)

**Purpose**: Database schema and SQLAlchemy models required for all app user stories

**Prerequisite**: Phase 2 (Model) must be deployed

### Tests for App Foundation (TDD - Write First)

- [X] T017 [P] [APP] Write unit test for SpeakerEmbedding model in tests/unit/test_speaker_embedding_model.py
- [X] T018 [P] [APP] Write integration test for cascade delete behavior in tests/integration/test_speaker_embedding_storage.py

### Implementation for App Foundation

- [X] T019 [APP] Create alembic migration for speaker_embeddings table in alembic/versions/004_add_speaker_embeddings_table.py
- [X] T020 [APP] Create SpeakerEmbedding SQLAlchemy model in src/models/speaker_embedding.py
- [X] T021 [APP] Add SpeakerEmbedding import to src/models/__init__.py
- [X] T022 [APP] Add speaker_embeddings relationship to Recording model in src/models/recording.py
- [X] T023 [APP] Run alembic upgrade head and verify table creation

**Checkpoint**: Database schema ready. Run migration and verify speaker_embeddings table exists.

---

## Phase 4: User Story 1 - Consistent Speaker Labels Across Long Recordings (Priority: P1)

**Goal**: Maintain consistent speaker labels (Interviewer, Respondent) across all chunks of a long recording

**Independent Test**: Upload 30+ minute interview, verify same person maintains same label throughout

### Tests for User Story 1 (TDD - Write First)

- [X] T024 [P] [US1] Write unit test for DiarizeResponse with speaker_embeddings field in tests/unit/services/test_embedding_matching.py
- [X] T025 [P] [US1] Write unit test for reference embedding accumulation logic in tests/unit/services/test_embedding_matching.py
- [X] T026 [P] [US1] Write integration test for multi-chunk diarization with consistent labels in tests/integration/test_multi_chunk_diarization.py

### Implementation for User Story 1

- [X] T027 [US1] Update DiarizeResponse dataclass to include speaker_embeddings field in src/services/audio.py
- [X] T028 [US1] Modify _diarize_single_chunk() to accept reference_embeddings and chunk_index parameters in src/services/audio.py
- [X] T029 [US1] Modify _diarize_single_chunk() to pass reference_embeddings to model endpoint in src/services/audio.py
- [X] T030 [US1] Modify _diarize_single_chunk() to extract speaker_embeddings from model response in src/services/audio.py
- [X] T031 [US1] Modify diarize_audio() to track reference embeddings across chunks in src/services/audio.py
- [X] T032 [US1] Modify diarize_audio() to accumulate embeddings from first chunk as reference set in src/services/audio.py
- [X] T033 [US1] Modify diarize_audio() to pass reference embeddings to subsequent chunk calls in src/services/audio.py
- [X] T034 [US1] Add logging for embedding matching decisions (similarity scores, match/no-match) in src/services/audio.py

**Checkpoint**: US1 complete. Test with long recording - speakers should have consistent labels across chunks.

---

## Phase 5: User Story 2 - Graceful Handling of New Speakers (Priority: P2)

**Goal**: Correctly identify new speakers in later chunks while maintaining existing speaker identities

**Independent Test**: Upload recording where speaker 3 joins partway through, verify speakers 1 and 2 retain labels

### Tests for User Story 2 (TDD - Write First)

- [X] T035 [P] [US2] Write unit test for new speaker detection (below threshold) in tests/unit/services/test_embedding_matching.py
- [X] T036 [P] [US2] Write unit test for reference set accumulation with new speakers in tests/unit/services/test_embedding_matching.py

### Implementation for User Story 2

- [X] T037 [US2] Modify diarize_audio() to detect new speakers (embeddings below match threshold) in src/services/audio.py
- [X] T038 [US2] Modify diarize_audio() to add new speaker embeddings to reference set in src/services/audio.py
- [X] T039 [US2] Modify diarize_audio() to assign sequential labels to new speakers (Respondent2, Respondent3) in src/services/audio.py

**Checkpoint**: US2 complete. Test with multi-speaker recording - new speakers get new labels, existing speakers keep theirs.

---

## Phase 6: User Story 3 - Speaker Embedding Persistence (Priority: P3)

**Goal**: Store speaker embeddings for potential re-processing and future cross-recording features

**Independent Test**: Process recording, verify embeddings stored, re-process, verify embeddings replaced

### Tests for User Story 3 (TDD - Write First)

- [X] T040 [P] [US3] Write unit test for save_speaker_embeddings function in tests/unit/services/test_recording_service.py
- [X] T041 [P] [US3] Write unit test for delete_speaker_embeddings function in tests/unit/services/test_recording_service.py
- [X] T042 [P] [US3] Write integration test for embedding replacement on re-processing in tests/integration/test_speaker_embedding_storage.py

### Implementation for User Story 3

- [X] T043 [US3] Implement save_speaker_embeddings() function in src/services/recording.py
- [X] T044 [US3] Implement delete_speaker_embeddings() function in src/services/recording.py
- [X] T045 [US3] Modify recording processing flow to call save_speaker_embeddings after diarization in src/services/recording.py
- [X] T046 [US3] Modify recording re-processing to delete existing embeddings before saving new ones in src/services/recording.py

**Checkpoint**: US3 complete. Test re-processing flow - old embeddings deleted, new ones saved.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T047 [P] Run full test suite (pytest tests/) and verify all tests pass
- [X] T048 [P] Run linting (ruff check src/ tests/) and fix any issues
- [X] T049 [P] Type check all new code has proper type hints
- [ ] T050 Run quickstart.md validation steps end-to-end
- [ ] T051 Update quickstart.md with any discovered corrections

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Model) ← DEPLOY TO DATABRICKS FIRST
    ↓
Phase 3 (App Foundational) ← Database + Models
    ↓
┌───────────────────────────────────────┐
│ Phase 4 (US1) → Phase 5 (US2) → Phase 6 (US3) │
│     (Can be sequential or parallel)    │
└───────────────────────────────────────┘
    ↓
Phase 7 (Polish)
```

### Critical Deployment Order

1. **Model changes (Phase 2)** must be deployed to Databricks Model Serving FIRST
2. **App changes (Phase 3-6)** depend on the updated model endpoint being available
3. Integration tests in Phase 4+ will fail if model doesn't return speaker_embeddings

### User Story Dependencies

- **US1 (P1)**: Depends on App Foundational (Phase 3)
- **US2 (P2)**: Depends on US1 (uses reference accumulation logic)
- **US3 (P3)**: Can run in parallel with US1/US2 (database storage is independent)

### Parallel Opportunities

**Within Phase 2 (Model):**
```
T004, T005, T006 in parallel (test files)
```

**Within Phase 3 (App Foundation):**
```
T017, T018 in parallel (test files)
```

**Within Phase 4 (US1):**
```
T024, T025, T026 in parallel (test files)
```

**Within Phase 5 (US2):**
```
T035, T036 in parallel (test files)
```

**Within Phase 6 (US3):**
```
T040, T041, T042 in parallel (test files)
```

---

## Implementation Strategy

### MVP First (Model + US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Model Changes → **DEPLOY TO DATABRICKS**
3. Complete Phase 3: App Foundational
4. Complete Phase 4: User Story 1
5. **STOP and VALIDATE**: Test with long recording, verify consistent labels
6. Deploy/demo if ready

### Full Feature Delivery

1. MVP (above) → Delivers core value
2. Add US2 → Handles new speakers mid-recording
3. Add US3 → Enables embedding persistence for future features
4. Polish → Full test coverage, docs

### Task Counts

| Phase | Task Count | Notes |
|-------|------------|-------|
| Setup | 3 | Prerequisites |
| Model | 13 | Deploy first |
| App Foundational | 7 | Database setup |
| US1 | 11 | Core feature |
| US2 | 5 | New speaker handling |
| US3 | 7 | Persistence |
| Polish | 5 | Validation |
| **Total** | **51** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [MODEL] = MLflow model changes (deploy to Databricks)
- [APP] = Dash application changes
- [US#] = User story assignment for traceability
- TDD: Write tests first, verify they fail, then implement
- Model must be deployed BEFORE app integration tests will work
- Commit after each logical group of tasks
