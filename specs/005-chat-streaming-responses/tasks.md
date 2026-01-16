# Tasks: Chat Streaming Responses

**Input**: Design documents from `/specs/005-chat-streaming-responses/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/sse-stream.yaml

**Tests**: Required per constitution (Test-First Development is NON-NEGOTIABLE)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dash-extensions dependency and prepare test infrastructure

- [ ] T001 Add dash-extensions>=1.0.18 to pyproject.toml dependencies
- [ ] T002 Run dependency installation and verify dash-extensions SSE component imports correctly
- [ ] T003 [P] Create test directory structure: tests/unit/, tests/integration/, tests/contract/ if not existing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create streaming service module and SSE endpoint infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create src/services/streaming.py with module docstring and imports (empty functions)
- [ ] T005 Add streaming cursor CSS styles to src/assets/ or inline in chat component
- [ ] T006 Register SSE route blueprint in src/app.py (route registration only, no implementation)

**Checkpoint**: Foundation ready - streaming module exists, CSS ready, route registered

---

## Phase 3: User Story 1 - Real-time Response Streaming (Priority: P1) MVP

**Goal**: Stream LLM responses token-by-token to the chat interface with pulsing cursor indicator

**Independent Test**: Send a chat query and observe text appearing incrementally (not all at once) with a pulsing cursor during generation

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T007 [P] [US1] Contract test for SSE event format (token, done events) in tests/contract/test_sse_contract.py
- [ ] T008 [P] [US1] Unit test for streaming generator function in tests/unit/test_streaming.py
- [ ] T009 [P] [US1] Integration test for /api/chat/stream endpoint returns SSE stream in tests/integration/test_sse_endpoint.py

### Implementation for User Story 1

- [ ] T010 [US1] Implement stream_rag_response() generator function in src/services/streaming.py that yields SSE token events
- [ ] T011 [US1] Add streaming_generate() function to src/services/rag.py using ChatDatabricks.stream() method
- [ ] T012 [US1] Implement /api/chat/stream POST endpoint in src/services/streaming.py returning Flask Response with text/event-stream
- [ ] T013 [US1] Add SSE component to chat layout in src/components/chat.py with id="chat-sse" and concat=True
- [ ] T014 [US1] Create callback to trigger SSE stream on query submit in src/components/chat.py (set url and options)
- [ ] T015 [US1] Add clientside callback to render streaming content with pulsing cursor class in src/components/chat.py
- [ ] T016 [US1] Add StreamState tracking (idle/streaming/complete) to session store in src/components/chat.py
- [ ] T017 [US1] Disable send button during active streaming (FR-008) in src/components/chat.py
- [ ] T018 [US1] Remove pulsing cursor and finalize message when done event received in src/components/chat.py

**Checkpoint**: User Story 1 complete - tokens stream incrementally with pulsing cursor, message finalizes on completion

---

## Phase 4: User Story 2 - Citation Display After Streaming (Priority: P2)

**Goal**: Display source citations after streamed response completes

**Independent Test**: Submit query, observe streaming complete, verify citations appear in expandable section matching existing format

### Tests for User Story 2

- [ ] T019 [P] [US2] Contract test for SSE citations event format in tests/contract/test_sse_contract.py
- [ ] T020 [P] [US2] Integration test verifying citations delivered after tokens in tests/integration/test_sse_endpoint.py

### Implementation for User Story 2

- [ ] T021 [US2] Modify stream_rag_response() to yield citations event after all tokens in src/services/streaming.py
- [ ] T022 [US2] Update streaming_generate() to return citations alongside token stream in src/services/rag.py
- [ ] T023 [US2] Handle citations event in clientside callback, store in state in src/components/chat.py
- [ ] T024 [US2] Render citation section (existing format) only after streaming completes in src/components/chat.py
- [ ] T025 [US2] Ensure citations=null while is_streaming=True, populated on completion in src/components/chat.py

**Checkpoint**: User Story 2 complete - citations display after streaming with existing expandable format

---

## Phase 5: User Story 3 - Graceful Error Handling (Priority: P3)

**Goal**: Handle errors during streaming gracefully, preserving partial content and allowing retry

**Independent Test**: Simulate LLM error mid-stream, verify partial content preserved, error message shown, new query submittable

### Tests for User Story 3

- [ ] T026 [P] [US3] Contract test for SSE error event format in tests/contract/test_sse_contract.py
- [ ] T027 [P] [US3] Unit test for error handling in streaming generator in tests/unit/test_streaming.py
- [ ] T028 [P] [US3] Integration test for error recovery flow in tests/integration/test_sse_endpoint.py

### Implementation for User Story 3

- [ ] T029 [US3] Add try/except around LLM streaming with error event yield in src/services/streaming.py
- [ ] T030 [US3] Implement StreamingError class with error codes (RETRIEVAL_FAILED, GENERATION_FAILED, etc.) in src/services/streaming.py
- [ ] T031 [US3] Handle error event in clientside callback, set StreamState to error in src/components/chat.py
- [ ] T032 [US3] Preserve partial_content on error, append error message to chat in src/components/chat.py
- [ ] T033 [US3] Reset StreamState to idle after error acknowledgment, re-enable send button in src/components/chat.py
- [ ] T034 [US3] Add error boundary for SSE connection failures in src/components/chat.py

**Checkpoint**: User Story 3 complete - errors handled gracefully, partial content preserved, recovery possible

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration verification, edge cases, and cleanup

- [ ] T035 [P] Add type hints to all new functions in src/services/streaming.py
- [ ] T036 [P] Add type hints to modified functions in src/services/rag.py
- [ ] T037 [P] Add docstrings to all public functions in streaming module
- [ ] T038 Run ruff check and fix any linting issues
- [ ] T039 Verify recording filter compatibility with streaming (FR-009) in src/components/chat.py
- [ ] T040 Test query queueing behavior (edge case: submit during active stream)
- [ ] T041 Run all tests and verify 80%+ coverage for new code
- [ ] T042 Run quickstart.md validation steps manually
- [ ] T043 Remove any unused blocking invocation code from src/components/chat.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can proceed sequentially in priority order (P1 -> P2 -> P3)
  - Or in parallel if team capacity allows
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational - Integrates with US1 streaming but independently testable
- **User Story 3 (P3)**: Can start after Foundational - Adds error handling to existing stream, independently testable

### Within Each User Story (TDD Workflow)

1. Tests MUST be written and FAIL before implementation (Red phase)
2. Implement minimally to make tests pass (Green phase)
3. Service functions before endpoint implementation
4. Backend streaming before frontend rendering
5. Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 Setup:**
```
T001 (deps) → T002 (verify) || T003 (dirs)
```

**Phase 2 Foundational:**
```
T004 (streaming.py) || T005 (CSS) || T006 (route)
```

**User Story 1 Tests (can run in parallel):**
```
T007 (contract) || T008 (unit) || T009 (integration)
```

**User Story 2 Tests:**
```
T019 (contract) || T020 (integration)
```

**User Story 3 Tests:**
```
T026 (contract) || T027 (unit) || T028 (integration)
```

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together (TDD - all should FAIL initially):
Task: "Contract test for SSE event format in tests/contract/test_sse_contract.py"
Task: "Unit test for streaming generator function in tests/unit/test_streaming.py"
Task: "Integration test for /api/chat/stream endpoint in tests/integration/test_sse_endpoint.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: User Story 1 (T007-T018)
4. **STOP and VALIDATE**: Send query, observe tokens streaming, cursor pulsing, message finalizing
5. Deploy/demo if ready - core value delivered

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test streaming -> Deploy (MVP!)
3. Add User Story 2 -> Test citations -> Deploy (citations work)
4. Add User Story 3 -> Test error handling -> Deploy (robust)
5. Polish phase -> Production ready

### Files Modified/Created Summary

| File | Action | User Stories |
|------|--------|--------------|
| pyproject.toml | MODIFY | Setup |
| src/services/streaming.py | CREATE | US1, US2, US3 |
| src/services/rag.py | MODIFY | US1, US2 |
| src/components/chat.py | MODIFY | US1, US2, US3 |
| src/app.py | MODIFY | Foundational |
| tests/contract/test_sse_contract.py | CREATE | US1, US2, US3 |
| tests/unit/test_streaming.py | CREATE | US1, US3 |
| tests/integration/test_sse_endpoint.py | CREATE | US1, US2, US3 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Constitution requires TDD: write failing tests FIRST
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
