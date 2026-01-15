# API Contracts: Multi-Speaker Conversation Rendering

**Feature**: 003-multi-speaker-conversation

## Overview

This feature requires **no new API endpoints**. All changes are confined to the UI rendering layer.

## Existing Contracts (Unchanged)

The following existing endpoints continue to work without modification:

- `GET /api/recordings/{id}` - Returns transcript with `dialog_json` containing speaker turns
- Search functionality - Returns chunks with speaker attribution

The speaker labels returned by these endpoints may now include extended labels (Respondent1, Respondent2, etc.) but the response structure is unchanged.
