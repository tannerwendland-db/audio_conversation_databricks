# Tasks: Audio Conversation RAG System

**Input**: Design documents from `/specs/001-audio-conversation-rag/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: TDD is required per constitution. Tests MUST be written first and fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- `alembic/` for database migrations
- Paths based on plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure per plan.md (src/models/, src/services/, src/components/, src/db/, tests/unit/, tests/integration/, tests/contract/, alembic/)
- [X] T002 Create pyproject.toml with Python 3.11+ and all dependencies (dash, sqlalchemy, langgraph, langchain, psycopg, databricks-sdk, databricks-langchain, alembic, pgvector, librosa, soundfile, pydantic, python-dotenv, pytest, ruff)
- [X] T003 [P] Create requirements.txt from pyproject.toml dependencies
- [X] T004 [P] Create Makefile with targets: install, run, test, test-unit, test-integration, lint, format, migrate, migrate-new
- [X] T005 [P] Configure ruff.toml for linting and formatting rules
- [X] T006 [P] Create .env.example with all required environment variables (POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, VOLUME_PATH)
- [X] T007 [P] Create app.yaml for Databricks App deployment with secrets, volumes, and serving endpoints configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Create src/config.py with environment configuration using pydantic Settings class
- [X] T009 Initialize Alembic with alembic.ini and alembic/env.py for PostgreSQL connection
- [X] T010 Create alembic/versions/001_initial_schema.py with recordings and transcripts tables per data-model.md
- [X] T011 Create src/models/__init__.py with Base class export
- [X] T012 [P] Create src/models/recording.py with Recording model and ProcessingStatus enum per data-model.md
- [X] T013 [P] Create src/models/transcript.py with Transcript model per data-model.md
- [X] T014 Create src/db/__init__.py exporting session utilities
- [X] T015 Create src/db/session.py with get_engine() and get_session() functions using environment variables
- [X] T016 Create tests/conftest.py with pytest fixtures for database session, test client, and mock Databricks client
- [X] T017 Create src/services/__init__.py exporting all services
- [X] T018 Create src/components/__init__.py exporting all Dash components
- [X] T019 Create base src/app.py with Dash app initialization, layout skeleton, and health check

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Upload Customer Call Recording (Priority: P1) MVP

**Goal**: Enable users to upload audio files, process them through diarization, and store vectorized transcripts

**Independent Test**: Upload a sample audio file and verify the system confirms successful processing with the recording appearing in the library

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US1] Create tests/unit/test_audio.py with tests for: validate_file_format(), convert_to_wav(), get_audio_duration()
- [X] T021 [P] [US1] Create tests/unit/test_embedding.py with tests for: chunk_transcript(), create_documents_with_metadata()
- [X] T022 [P] [US1] Create tests/integration/test_diarization.py with tests for: diarize_audio() calling mock endpoint, handling success/error responses
- [X] T023 [P] [US1] Create tests/integration/test_db.py with tests for: create_recording(), update_recording_status(), create_transcript()
- [X] T024 [P] [US1] Create tests/integration/test_vector_store.py with tests for: get_vector_store(), store_embeddings()

### Implementation for User Story 1

- [X] T025 [US1] Create src/services/audio.py with validate_file_format() accepting MP3, WAV, M4A, FLAC up to 500MB
- [X] T026 [US1] Add convert_to_wav() to src/services/audio.py using librosa to convert audio to 16kHz WAV
- [X] T027 [US1] Add get_audio_duration() to src/services/audio.py returning duration in seconds
- [X] T028 [US1] Add upload_to_volume() to src/services/audio.py using databricks.sdk WorkspaceClient to upload to UC Volume
- [X] T029 [US1] Add diarize_audio() to src/services/audio.py calling audio-transcription-diarization-endpoint with base64 WAV
- [ ] T030 [US1] Add chunk_audio_for_diarization() to src/services/audio.py to split large files into 5-minute chunks
- [X] T031 [US1] Create src/services/embedding.py with chunk_transcript() using RecursiveCharacterTextSplitter (chunk_size=500, overlap=50)
- [X] T032 [US1] Add create_documents_with_metadata() to src/services/embedding.py creating LangChain Documents with recording_id, recording_title, chunk_index, speaker metadata
- [X] T033 [US1] Add get_vector_store() to src/services/embedding.py returning configured PGVector with DatabricksEmbeddings
- [X] T034 [US1] Add store_embeddings() to src/services/embedding.py storing documents in pgvector
- [ ] T035 [US1] Add delete_embeddings_for_recording() to src/services/embedding.py to remove embeddings by recording_id filter
- [X] T036 [US1] Create src/services/recording.py with create_recording() creating Recording with pending status
- [X] T037 [US1] Add update_recording_status() to src/services/recording.py updating status through processing states
- [X] T038 [US1] Add create_transcript() to src/services/recording.py creating Transcript linked to Recording
- [ ] T039 [US1] Add generate_summary() to src/services/recording.py using Claude to summarize diarized text
- [X] T040 [US1] Add process_recording() to src/services/recording.py orchestrating: convert -> upload -> diarize (with chunked progress for files >30min) -> chunk -> embed -> summarize, updating processing_status at each stage and emitting progress percentage for long recordings
- [X] T041 [US1] Create src/components/upload.py with Dash dcc.Upload component accepting audio files
- [X] T042 [US1] Add upload callback in src/components/upload.py handling file validation, creating recording, triggering background processing
- [X] T043 [US1] Add processing status display in src/components/upload.py showing progress indicator and completion/error messages
- [X] T043a [US1] Add retry functionality in src/components/upload.py with retry button for failed recordings that re-triggers process_recording() using existing volume file
- [X] T044 [US1] Create src/components/library.py with basic recording list display (id, title, status, date) for upload verification
- [X] T045 [US1] Integrate upload and library components into src/app.py layout with tab navigation

**Checkpoint**: User Story 1 complete - users can upload audio, see processing status, and verify recordings appear in library

---

## Phase 4: User Story 2 - Conversational Search Over Recordings (Priority: P2)

**Goal**: Enable users to ask natural language questions and receive answers with citations from recordings

**Independent Test**: Ask questions about uploaded recordings and verify accurate, sourced responses

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T046 [P] [US2] Create tests/unit/test_rag.py with tests for: RAGAgentState schema, format_context_with_citations(), build_rag_graph()
- [X] T047 [P] [US2] Create tests/integration/test_rag_agent.py with tests for: retrieve_documents(), generate_response_with_citations(), handle_no_results()

### Implementation for User Story 2

- [X] T048 [US2] Create src/services/rag.py with RAGAgentState TypedDict (messages, retrieved_docs, source_citations)
- [X] T049 [US2] Add get_llm() to src/services/rag.py returning ChatDatabricks configured for databricks-claude-sonnet-4-5
- [X] T050 [US2] Add get_retriever() to src/services/rag.py returning pgvector retriever with MMR search (k=5, fetch_k=20)
- [X] T051 [US2] Add retrieve_node() to src/services/rag.py as LangGraph node querying vector store
- [X] T052 [US2] Add grade_relevance_node() to src/services/rag.py using LLM to assess document relevance
- [X] T053 [US2] Add rewrite_query_node() to src/services/rag.py reformulating unclear queries
- [X] T054 [US2] Add format_context_with_citations() to src/services/rag.py formatting retrieved docs with source citations
- [X] T055 [US2] Add generate_node() to src/services/rag.py producing response with inline citations [Recording: title]
- [X] T056 [US2] Add build_rag_graph() to src/services/rag.py constructing LangGraph StateGraph with retrieve -> grade -> [generate|rewrite] flow
- [X] T057 [US2] Add get_rag_agent() to src/services/rag.py returning compiled graph with InMemorySaver checkpointer
- [X] T058 [US2] Add query() to src/services/rag.py invoking agent with session_id config and returning answer + citations
- [X] T059 [US2] Create src/components/chat.py with Dash chat interface (message input, send button, message history display)
- [X] T060 [US2] Add chat callback in src/components/chat.py handling query submission, invoking RAG agent, displaying response with citations
- [X] T061 [US2] Add session management in src/components/chat.py generating session_id per browser tab, clearing on refresh
- [X] T062 [US2] Add citation click handling in src/components/chat.py linking to recording detail view
- [X] T063 [US2] Add "no results found" message handling in src/components/chat.py for queries with no matching content
- [X] T064 [US2] Integrate chat component into src/app.py layout as Chat tab
- [X] T064a [P] [US2] Create tests/unit/test_chat_recording_filter.py with tests for: recording selector rendering, multi-select state management, filtered query submission with multiple recording_ids
- [X] T064b [US2] Update similarity_search() in src/services/embedding.py to accept optional recording_ids list parameter, filtering with SQL IN clause when provided
- [X] T064c [US2] Update rag_query() and build_rag_graph() in src/services/rag.py to pass recording_ids list to similarity_search()
- [X] T064d [US2] Add optional multi-select recording filter dropdown to src/components/chat.py above chat input, passing selected recording_ids to rag_query()

**Checkpoint**: User Story 2 complete - users can ask questions and receive cited answers from recordings

---

## Phase 5: User Story 3 - Browse and Review Individual Recordings (Priority: P3)

**Goal**: Enable users to view full transcripts, search within them, and see recording metadata/summary

**Independent Test**: Select a processed recording and view its full transcript with search and metadata

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T065 [P] [US3] Create tests/unit/test_transcript_search.py with tests for: search_transcript(), highlight_matches()
- [X] T066 [P] [US3] Create tests/integration/test_recording_detail.py with tests for: get_recording_with_transcript()

### Implementation for User Story 3

- [X] T067 [US3] Add get_recording() to src/services/recording.py fetching recording by ID with eager-loaded transcript
- [X] T068 [US3] Add list_recordings() to src/services/recording.py with sort_by and sort_order parameters
- [X] T069 [US3] Create src/services/transcript.py with search_transcript() finding keyword matches in diarized_text
- [X] T070 [US3] Add highlight_matches() to src/services/transcript.py wrapping matches in highlight spans
- [X] T071 [US3] Add get_transcript_by_recording_id() to src/services/transcript.py
- [X] T072 [US3] Create src/components/transcript.py with transcript viewer showing full diarized text with visually distinct speaker labels (Interviewer/Respondent styling, alternating background colors)
- [X] T073 [US3] Add keyword search input and callback in src/components/transcript.py highlighting and navigating matches
- [X] T074 [US3] Add metadata panel in src/components/transcript.py showing upload date, duration, summary
- [X] T075 [US3] Update src/components/library.py with clickable recording rows opening transcript view
- [X] T076 [US3] Integrate transcript component into src/app.py with URL routing for /recording/{id}

**Checkpoint**: User Story 3 complete - users can browse recordings and view full transcripts with search

---

## Phase 6: User Story 4 - Manage Recording Library (Priority: P4)

**Goal**: Enable users to rename recordings, delete recordings, and sort the library

**Independent Test**: Rename and delete recordings, verify changes persist and deleted recordings are removed from search

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T077 [P] [US4] Create tests/unit/test_recording_management.py with tests for: validate_title(), rename_recording(), delete_recording_cascade()
- [X] T078 [P] [US4] Create tests/integration/test_recording_delete.py with tests for: delete removes recording, transcript, embeddings, and volume file

### Implementation for User Story 4

- [X] T079 [US4] Add validate_title() to src/services/recording.py enforcing max 255 chars, non-empty
- [X] T080 [US4] Add update_recording() to src/services/recording.py updating title with validation
- [X] T081 [US4] Add delete_recording() to src/services/recording.py with cascade: delete embeddings -> delete transcript -> delete volume file -> delete recording
- [X] T082 [US4] Add delete_volume_file() to src/services/audio.py removing file from UC Volume
- [X] T083 [US4] Update src/components/library.py adding sort dropdown (date, title, duration) and sort callbacks
- [X] T084 [US4] Add rename inline edit in src/components/library.py with edit icon, input field, save/cancel
- [X] T085 [US4] Add delete button in src/components/library.py with confirmation modal
- [X] T086 [US4] Add delete callback in src/components/library.py invoking delete_recording() and refreshing list

**Checkpoint**: User Story 4 complete - users can fully manage their recording library

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T087 [P] Create tests/contract/test_api_contracts.py validating service function signatures match contracts/api.yaml schemas
- [ ] T088 [P] Add comprehensive error handling in all services with custom exception classes in src/exceptions.py
- [ ] T089 [P] Add logging configuration in src/config.py and logging calls throughout services
- [ ] T090 Run ruff check and ruff format on entire codebase, fix any issues
- [ ] T091 Verify test coverage meets 80% target, add additional tests if needed
- [ ] T092 Update src/app.py with production-ready configuration (debug=False, proper error pages)
- [ ] T093 Validate end-to-end flow following quickstart.md steps
- [ ] T094 Create .gitignore with Python, env, and Databricks-specific patterns

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (Phase 3) must complete first (provides upload/processing)
  - US2 (Phase 4) depends on US1 (needs recordings to query)
  - US3 (Phase 5) depends on US1 (needs recordings to view)
  - US4 (Phase 6) depends on US1 (needs recordings to manage)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Foundation for all stories
- **User Story 2 (P2)**: Can start after US1 complete - Needs recordings to query
- **User Story 3 (P3)**: Can start after US1 complete - Needs recordings to view
- **User Story 4 (P4)**: Can start after US1 complete - Needs recordings to manage

**Note**: US2, US3, US4 can be developed in parallel once US1 is complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD per constitution)
- Models before services
- Services before components
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks T012, T013 can run in parallel (different model files)
- Within US1: T020-T024 tests can run in parallel; T025-T035 service implementations follow sequentially
- Within US2: T046-T047 tests can run in parallel
- Within US3: T065-T066 tests can run in parallel
- Within US4: T077-T078 tests can run in parallel
- After US1: US2, US3, US4 can be worked on in parallel by different team members

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together:
Task: "Create tests/unit/test_audio.py with tests for: validate_file_format(), convert_to_wav(), get_audio_duration()"
Task: "Create tests/unit/test_embedding.py with tests for: chunk_transcript(), create_documents_with_metadata()"
Task: "Create tests/integration/test_diarization.py with tests for: diarize_audio()"
Task: "Create tests/integration/test_db.py with tests for: create_recording(), update_recording_status()"
Task: "Create tests/integration/test_vector_store.py with tests for: get_vector_store(), store_embeddings()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test upload flow end-to-end
5. Deploy/demo if ready - users can upload and see recordings

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test independently -> Deploy/Demo (MVP!)
3. Add User Story 2 -> Test independently -> Deploy/Demo (core value)
4. Add User Story 3 -> Test independently -> Deploy/Demo
5. Add User Story 4 -> Test independently -> Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after US1 is complete:

1. Team completes Setup + Foundational + US1 together
2. Once US1 is done:
   - Developer A: User Story 2 (RAG chat)
   - Developer B: User Story 3 (transcript viewer)
   - Developer C: User Story 4 (library management)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD required: Verify tests fail before implementing (constitution mandate)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The diarization endpoint `audio-transcription-diarization-endpoint` is already deployed
- LLM endpoint is `databricks-claude-sonnet-4-5`
- Embeddings use DatabricksEmbeddings with pgvector
