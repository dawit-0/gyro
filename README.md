# <span style="color: #228B22;">GYRO</span>

A local webapp for orchestrating Claude Code agents.

## Architecture

- **Backend**: Python (FastAPI) + SQLite + Socket.IO for real-time updates
- **Frontend**: React 18 + TypeScript + Vite
- **Orchestrator**: Polls for queued jobs, spawns `claude` CLI subprocesses, streams output via WebSocket

## Prerequisites

- Python 3.11+
- Node.js 18+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude` must be on your PATH)

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

The backend starts on `http://localhost:3000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server starts on `http://localhost:5173` and proxies API/WebSocket requests to the backend.

### 3. Open the UI

Navigate to **http://localhost:5173** in your browser.

## Features

### Assistants

Reusable agent templates that bundle instructions, context, and default settings. Create an assistant once, then spawn jobs from it without re-entering configuration each time. Assistants support custom instructions (system prompts), attached context (files, URLs, or text), and default model/permissions/working directory.

### Permissions

Control what tools each agent can access. Choose from three presets or customize individually:

- **Read Only** — File read only (Read, Glob, Grep)
- **Standard** — File read/write + bash (default)
- **Full Access** — All tools including web search and MCP

Permissions are enforced via the Claude CLI `--allowedTools` flag.

## Usage

1. **Create a Project** (optional) — Use the sidebar to organize jobs by project.
2. **Create an Assistant** (optional) — Define a reusable template with instructions, context, and defaults.
3. **Create a Job** — Click "+ New Job", enter a title, prompt, select a model, set permissions, and optionally set a working directory. Or spawn a job directly from an assistant.
4. **Watch it run** — The orchestrator picks up queued jobs (up to 5 concurrent), spawns a Claude agent, and streams output in real-time to the agent card.
5. **Cancel / Remove** — Cancel running jobs or remove completed ones from the dashboard.

## Configuration

- `MAX_CONCURRENT_AGENTS` in `backend/orchestrator.py` controls how many agents run in parallel (default: 5).
- The orchestrator polls every 2 seconds for new queued jobs.

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI, python-socketio, aiosqlite |
| Database | SQLite (WAL mode) |
| Frontend | React 18, TypeScript, Vite |
| Real-time | Socket.IO (WebSocket) |
| Agent runtime | Claude Code CLI (`claude --print --output-format stream-json`) |
