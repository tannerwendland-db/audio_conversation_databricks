<!--
SYNC IMPACT REPORT
==================
Version change: N/A -> 1.0.0 (Initial ratification)

Modified principles: N/A (initial creation)

Added sections:
- Core Principles: Test-First Development, Simplicity & YAGNI
- Technology Standards
- Development Workflow
- Governance

Removed sections: N/A

Templates requiring updates:
- .specify/templates/plan-template.md: N/A (compatible)
- .specify/templates/spec-template.md: N/A (compatible)
- .specify/templates/tasks-template.md: N/A (compatible)

Follow-up TODOs: None
==================
-->

# Audio Conversational RAG Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)

All production code MUST follow Test-Driven Development (TDD):

1. **Write tests first**: Before implementing any feature or fix, tests MUST be written that define the expected behavior
2. **Tests MUST fail**: New tests MUST fail before implementation begins (Red phase)
3. **Implement minimally**: Write only enough code to make tests pass (Green phase)
4. **Refactor safely**: Improve code quality while maintaining passing tests (Refactor phase)

**Rationale**: TDD ensures code correctness, provides living documentation, enables safe refactoring, and catches regressions early. For an audio conversational RAG system, correctness is critical - users depend on accurate retrieval and generation.

**Enforcement**:
- PRs without corresponding tests for new functionality MUST be rejected
- Test coverage for new code MUST meet or exceed 80%
- Integration tests MUST cover all external service interactions (LangChain, vector stores, audio processing)

### II. Simplicity & YAGNI

All design decisions MUST favor simplicity over speculation:

1. **Build only what's needed**: Do NOT implement features "for the future" - build for current, validated requirements
2. **Minimize abstractions**: Every abstraction MUST justify its existence with a concrete, present-day use case
3. **Prefer standard solutions**: Use LangChain's built-in patterns before creating custom implementations
4. **Delete aggressively**: Remove unused code, dead imports, and speculative features immediately

**Rationale**: RAG systems can become complex quickly. Premature abstraction obscures behavior, complicates debugging, and slows iteration. Simple code is easier to test, review, and maintain.

**Enforcement**:
- New abstractions require documented justification in PR descriptions
- Code reviews MUST challenge complexity: "Is there a simpler way?"
- Unused code detected during review MUST be removed before merge

## Technology Standards

**Language**: Python 3.11+
**LLM Orchestration**: LangChain
**Testing Framework**: pytest

**Required Testing Layers**:
- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test interactions with LangChain, vector stores, and external services
- **Contract Tests**: Verify API request/response schemas match specifications

**Code Quality**:
- Type hints MUST be used for all function signatures
- Linting via ruff or flake8 MUST pass before merge
- Formatting via black or ruff format MUST be consistent

## Development Workflow

**Branch Strategy**:
- Feature branches MUST be created from `main`
- Branch names MUST follow pattern: `[issue-number]-brief-description`

**Commit Standards**:
- Commits MUST be atomic (one logical change per commit)
- Commit messages MUST follow conventional commits format

**Code Review Requirements**:
- All changes MUST be reviewed before merge
- Reviews MUST verify:
  1. Tests exist and pass
  2. Code follows simplicity principle
  3. No security vulnerabilities introduced
  4. Type hints present on new code

## Governance

This constitution supersedes all other development practices and guidelines. When conflicts arise, this document takes precedence.

**Amendment Process**:
1. Propose changes via PR to this constitution file
2. Changes require review and approval
3. Breaking changes (principle removal/redefinition) require explicit team acknowledgment
4. All amendments MUST update the version and date below

**Versioning Policy**:
- MAJOR: Backward-incompatible principle changes or removals
- MINOR: New principles added or existing principles expanded
- PATCH: Clarifications, typo fixes, non-semantic refinements

**Compliance Review**:
- All PRs MUST be checked against constitution principles
- Violations MUST be documented and justified if exceptions are granted
- Unjustified violations MUST block merge

**Version**: 1.0.0 | **Ratified**: 2025-12-12 | **Last Amended**: 2025-12-12
