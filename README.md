# <span style="color: #228B22;">GYRO</span>

A local webapp for orchestration of Claude agents.

## Architecture

- **Backend**: Python (FastAPI) + SQLite + Socket.IO for real-time updates
- **Frontend**: React 18 + TypeScript + Vite + React Flow
- **Orchestrator**: Manages task scheduling, dependency resolution, and spawns `claude` CLI subprocesses with real-time output streaming via WebSocket

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

### Tasks

Tasks are individual units of work that run Claude agents with specific prompts. Each task can be configured with a model (Sonnet, Opus, Haiku), working directory, permissions, and an optional cron schedule. Tasks track their execution history through task runs, which record status, duration, cost, and full output.

### Flows

Flows group related tasks into a dependency graph (DAG). Tasks within a flow can declare dependencies on other tasks, enabling complex multi-step workflows. The UI renders flows as an interactive DAG visualization with color-coded status indicators and automatic hierarchical layout.

Key flow capabilities:
- **Dependency management** — Tasks can depend on other tasks; circular dependencies are detected and rejected
- **Cascading execution** — When a task succeeds, downstream tasks are automatically queued (if all their dependencies are met)
- **Cascading failure** — When a task fails, all queued downstream runs are cancelled
- **Flow-level scheduling** — Set a cron schedule on a flow to automatically trigger all root tasks (those with no upstream dependencies)
- **Manual trigger** — Trigger all root tasks in a flow on demand

### Agents

Reusable agent templates that bundle instructions, context, and default settings. Create an agent once, then spawn tasks from it without re-entering configuration each time. Agents support custom instructions (system prompts), attached context (files, URLs, or text), and default model/permissions/working directory.

### Scheduling

Tasks and flows support cron-based scheduling with common presets:
- Hourly
- Daily at 9 AM
- Weekdays at 9 AM
- Weekly on Monday
- Monthly on the 1st

The orchestrator continuously checks schedules and automatically triggers tasks or flows when they are due.

### Permissions

Control what tools each agent can access. Choose from three presets or customize individually:

- **Read Only** — File read only (Read, Glob, Grep)
- **Standard** — File read/write + bash (default)
- **Full Access** — All tools including web search and MCP

Permissions are enforced via the Claude CLI `--allowedTools` flag.

## Usage

1. **Create a Flow** (optional) — Organize related tasks into a dependency graph.
2. **Create an Agent** (optional) — Define a reusable template with instructions, context, and defaults.
3. **Create a Task** — Click "+ New Task", enter a title, prompt, select a model, set permissions, configure dependencies, and optionally set a schedule or working directory. Or spawn a task directly from an agent.
4. **Watch it run** — The orchestrator picks up queued tasks (up to 5 concurrent), spawns a Claude agent, and streams output in real-time. View the DAG visualization to monitor flow progress.
5. **Cancel / Delete** — Cancel running tasks or delete completed ones from the dashboard.

## Configuration

- `MAX_CONCURRENT_RUNS` in `backend/orchestrator.py` controls how many tasks run in parallel (default: 5).
- The orchestrator continuously polls for scheduled tasks and queued runs.

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI, python-socketio, aiosqlite |
| Database | SQLite (WAL mode) |
| Frontend | React 18, TypeScript, Vite, React Flow |
| Real-time | Socket.IO (WebSocket) |
| Agent runtime | Claude Code CLI (`claude --print --output-format stream-json`) |
