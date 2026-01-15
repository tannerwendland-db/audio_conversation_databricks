# Implementation Plan: Multi-Speaker Conversation Rendering

**Branch**: `003-multi-speaker-conversation` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-multi-speaker-conversation/spec.md`

## Summary

Enable visual distinction of multiple speakers (beyond just Interviewer/Respondent) in the transcript viewer. The pyfunc already outputs distinct speaker labels (Respondent, Respondent1, Respondent2, etc.), but the UI currently normalizes all non-Interviewer speakers to "Respondent" with identical styling. This feature extends the color palette and speaker type detection to support 10+ unique speakers with deterministic color assignment.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Dash 3.3+, dash-bootstrap-components 2.0+, SQLAlchemy 2.0+, LangChain 0.3+
**Storage**: PostgreSQL (Databricks Lakebase) with pgvector; existing `dialog_json` field stores speaker turns
**Testing**: pytest 8.0+ with pytest-cov
**Target Platform**: Databricks Apps (web application)
**Project Type**: Single project (Dash web application with services layer)
**Performance Goals**: N/A (UI rendering only; no backend performance requirements)
**Constraints**: Must maintain backward compatibility with existing 2-speaker transcripts
**Scale/Scope**: Typical conversations have 2-10 speakers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Test-First Development** | PASS | Will write tests for speaker style utilities, label normalization, and color assignment before implementation |
| **II. Simplicity & YAGNI** | PASS | Extends existing SPEAKER_STYLES dict; no new abstractions required. Uses hash-based color assignment instead of complex state management |

**Gate Status**: PASSED - No violations detected

## Project Structure

### Documentation (this feature)

```text
specs/003-multi-speaker-conversation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no new APIs)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── components/
│   └── transcript.py    # MODIFY: Extend SPEAKER_STYLES, update speaker_type detection
├── services/
│   └── dialog_parser.py # MODIFY: Preserve multi-speaker labels (Respondent1, Respondent2)
├── models/              # NO CHANGES (dialog_json structure unchanged)
└── config.py            # NO CHANGES

tests/
├── unit/
│   └── test_speaker_styles.py  # NEW: Test color palette, label normalization
└── integration/
    └── test_transcript_multi_speaker.py  # NEW: Test multi-speaker rendering
```

**Structure Decision**: Single project structure. Changes are confined to UI components and dialog parsing service. No new API endpoints or data model changes required.

## Complexity Tracking

No violations - no complexity justifications required.
