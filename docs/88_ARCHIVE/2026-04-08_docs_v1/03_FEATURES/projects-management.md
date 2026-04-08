# Projects Management

Manage indexed code repositories from the web UI.

## Features

- View all indexed projects with detailed statistics
- Switch active project for search and navigation
- Reindex projects to refresh code chunks
- Delete projects and all associated data
- Quick project switcher in navbar

## Pages

### Projects Page (`/projects`)

Table view of all indexed projects showing:
- Repository name
- File and chunk counts
- Lines of code
- Languages detected
- Graph coverage percentage
- Last indexed timestamp
- Status (healthy, needs reindex, poor coverage, error)

Actions:
- Set Active: Switch to this project
- Reindex: Trigger full reindexing
- Delete: Remove all project data

### Navbar Project Switcher

Dropdown menu in navbar for quick project switching:
- Shows all projects with chunk counts
- Current active project highlighted
- Link to full Projects page

## API Endpoints

- `GET /api/v1/projects` - List all projects
- `GET /api/v1/projects/active` - Get active project
- `POST /api/v1/projects/active` - Set active project
- `POST /api/v1/projects/{repo}/reindex` - Trigger reindex
- `DELETE /api/v1/projects/{repo}` - Delete project

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Frontend: Vue 3, TypeScript, Tailwind CSS
- State: Composables with localStorage persistence

## Future Enhancements

- Add project from UI (file picker)
- Real-time indexing progress
- Project-level settings (ignore patterns, etc.)
- Export/import project configuration
