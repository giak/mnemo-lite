# Memories Monitor Feature

**Status:** ✅ Implemented
**Date:** 2025-11-04
**EPIC:** EPIC-26

## Overview

Read-only monitoring dashboard at `/memories` for viewing saved conversations, code chunks, and embedding health status.

## Features

### Stats Bar
- **Total Memories**: Current count (~25,083)
- **Embedding Rate**: Success percentage with color coding (green >95%, yellow >85%, red <85%)
- **Today's Count**: Memories added in last 24 hours
- **Last Activity**: Relative time since last memory created

### Conversations Widget
- Timeline of 10 most recent conversations
- Displays: time, session ID, title, tags, embedding status
- "View" button (future: modal detail view)

### Code Chunks Widget
- Today's indexing stats (chunks + files)
- List of 10 most recent indexed chunks
- Language badges with color coding
- File path, chunk type, repository

### Embeddings Widget
- **Text Embeddings**: Total, with embeddings, success rate, model
- **Code Embeddings**: Total, model (always 100%)
- **Health Alerts**: Warnings for memories without embeddings

## Auto-Refresh

- Automatic refresh every 30 seconds
- Manual refresh button
- "Last updated" indicator

## API Endpoints

- `GET /api/v1/memories/stats` - Overall statistics
- `GET /api/v1/memories/recent?limit=10` - Recent conversations
- `GET /api/v1/memories/code-chunks/recent?limit=10` - Code indexing activity
- `GET /api/v1/memories/embeddings/health` - Embedding health alerts

## Tech Stack

- **Frontend**: Vue 3, TypeScript, Tailwind CSS
- **Backend**: FastAPI, PostgreSQL
- **Composable**: `useMemories` with auto-refresh

## Future Enhancements

- Modal for viewing full conversation content
- Search/filter within conversations
- Export conversations to markdown
- Embedding visualization (t-SNE or UMAP)
- Time-series charts for activity
