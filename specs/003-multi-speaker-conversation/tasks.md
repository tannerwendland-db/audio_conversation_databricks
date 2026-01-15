# Tasks: Multi-Speaker Conversation Rendering

**Input**: Design documents from `/specs/003-multi-speaker-conversation/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Required per Constitution (Test-First Development principle)

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup

**Purpose**: No new project setup required - this feature modifies existing files only

- [X] T001 Verify existing test infrastructure works by running `pytest tests/ -v --collect-only`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Components

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T002 [P] Create test file tests/unit/test_speaker_styles.py with test class structure
- [X] T003 [P] Write failing test for SPEAKER_PALETTE containing 10 colors in tests/unit/test_speaker_styles.py
- [X] T004 [P] Write failing test for get_speaker_color_index() determinism in tests/unit/test_speaker_styles.py
- [X] T005 [P] Write failing test for backward compat (Interviewer=0, Respondent=1) in tests/unit/test_speaker_styles.py
- [X] T006 [P] Write failing test for format_speaker_label() in tests/unit/test_speaker_styles.py

### Implementation for Foundational Components

- [X] T007 Add SPEAKER_PALETTE list with 10 colors to src/components/transcript.py
- [X] T008 Add FIXED_SPEAKER_COLORS dict to src/components/transcript.py
- [X] T009 Implement get_speaker_color_index() function in src/components/transcript.py
- [X] T010 Implement format_speaker_label() function in src/components/transcript.py
- [X] T011 Implement get_speaker_style() function in src/components/transcript.py
- [X] T012 Run tests to verify foundational components pass: `pytest tests/unit/test_speaker_styles.py -v`

**Checkpoint**: Foundation ready - SPEAKER_PALETTE, color assignment, and label formatting utilities complete

---

## Phase 3: User Story 1 - View Multi-Participant Conversations Distinctly (Priority: P1)

**Goal**: Each unique speaker displays with distinct visual style in transcript viewer

**Independent Test**: Upload multi-speaker audio, verify each speaker has unique background color and formatted label

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [P] [US1] Write failing test for dialog_parser preserving Respondent1/Respondent2 labels in tests/unit/test_dialog_parser.py
- [X] T014 [P] [US1] Write failing test for _parse_speaker_turns preserving multi-speaker labels in tests/unit/test_speaker_styles.py
- [X] T015 [P] [US1] Write failing test for _create_speaker_block using new style system in tests/unit/test_speaker_styles.py

### Implementation for User Story 1

- [X] T016 [US1] Fix process_dialog() in src/services/dialog_parser.py to preserve Respondent1/Respondent2 labels
- [X] T017 [US1] Update _parse_speaker_turns() in src/components/transcript.py to preserve multi-speaker labels
- [X] T018 [US1] Update _create_speaker_block() in src/components/transcript.py to use get_speaker_style()
- [X] T019 [US1] Update _create_speaker_block() to use format_speaker_label() for display
- [X] T020 [US1] Remove or deprecate old SPEAKER_STYLES dict in src/components/transcript.py
- [X] T021 [US1] Run all US1 tests: `pytest tests/unit/test_speaker_styles.py tests/unit/test_dialog_parser.py -v`

**Checkpoint**: User Story 1 complete - Multi-speaker transcripts display with distinct colors

---

## Phase 4: User Story 2 - Search Results Show Correct Speaker Attribution (Priority: P2)

**Goal**: Search results correctly attribute quotes to specific speakers (not just "Respondent")

**Independent Test**: Search multi-speaker transcript, verify results show correct speaker labels (e.g., "Respondent 2")

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T022 [P] [US2] Write failing test for search results with multi-speaker attribution in tests/unit/test_speaker_styles.py

### Implementation for User Story 2

- [X] T023 [US2] Verify search_transcript() in src/services/transcript.py preserves speaker labels (likely already works)
- [X] T024 [US2] Update any search result rendering in src/components/transcript.py to use format_speaker_label()
- [X] T025 [US2] Run US2 tests: `pytest tests/unit/test_speaker_styles.py -k search -v`

**Checkpoint**: User Story 2 complete - Search results show correct speaker attribution

---

## Phase 5: User Story 3 - Speaker Legend/Key (Priority: P3)

**Goal**: Display summary of all participants with their color coding at top of transcript

**Independent Test**: View multi-speaker transcript, verify legend shows all speakers with matching colors

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T026 [P] [US3] Write failing test for _create_speaker_legend() function in tests/unit/test_speaker_styles.py

### Implementation for User Story 3

- [X] T027 [US3] Create _create_speaker_legend() function in src/components/transcript.py
- [X] T028 [US3] Extract unique speakers from dialog_json in _create_speaker_legend()
- [X] T029 [US3] Render legend with speaker labels and color swatches
- [X] T030 [US3] Integrate legend into create_transcript_view() in src/components/transcript.py
- [X] T031 [US3] Run US3 tests: `pytest tests/unit/test_speaker_styles.py -k legend -v`

**Checkpoint**: User Story 3 complete - Speaker legend displays at top of transcript

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T032 [P] Run full test suite: `pytest tests/ -v`
- [X] T033 [P] Run linting: `ruff check src/components/transcript.py src/services/dialog_parser.py`
- [X] T034 Verify backward compatibility: Test existing 2-speaker transcript renders unchanged
- [X] T035 Run quickstart.md verification steps manually
- [X] T036 Update any inline documentation/comments in modified files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verify test infrastructure
- **Foundational (Phase 2)**: BLOCKS all user stories - must complete first
- **User Story 1 (Phase 3)**: Depends on Foundational - core multi-speaker rendering
- **User Story 2 (Phase 4)**: Depends on Foundational - can run parallel to US1
- **User Story 3 (Phase 5)**: Depends on Foundational - can run parallel to US1/US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent after Foundational
- **User Story 2 (P2)**: Independent after Foundational (uses same utilities as US1)
- **User Story 3 (P3)**: Independent after Foundational (uses same utilities as US1)

### Within Each Phase

- Tests MUST be written and FAIL before implementation
- Implementation follows test completion
- All tests must pass before phase is complete

### Parallel Opportunities

**Foundational Phase**:
```
T002, T003, T004, T005, T006 can run in parallel (different test cases)
```

**User Stories** (after Foundational):
```
US1, US2, US3 can be developed in parallel by different developers
```

**Within Each User Story**:
```
Test tasks marked [P] can run in parallel
```

---

## Parallel Example: Foundational Tests

```bash
# Launch all foundational tests together:
Task: "T002 Create test file tests/unit/test_speaker_styles.py"
Task: "T003 Write failing test for SPEAKER_PALETTE"
Task: "T004 Write failing test for get_speaker_color_index()"
Task: "T005 Write failing test for backward compat"
Task: "T006 Write failing test for format_speaker_label()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002-T012)
3. Complete Phase 3: User Story 1 (T013-T021)
4. **STOP and VALIDATE**: Multi-speaker transcripts render with distinct colors
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Foundational -> Core utilities ready
2. Add User Story 1 -> Multi-speaker rendering (MVP!)
3. Add User Story 2 -> Search attribution (enhancement)
4. Add User Story 3 -> Speaker legend (nice-to-have)
5. Each story adds value without breaking previous stories

---

## Notes

- Constitution requires TDD - all tests written before implementation
- [P] tasks = different files or independent test cases
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Files modified: `src/components/transcript.py`, `src/services/dialog_parser.py`
- Files created: `tests/unit/test_speaker_styles.py`
