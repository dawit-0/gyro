# <span style="color: #228B22; text-transform: uppercase;">gyro</span>

A local webapp for orchestrating Claude Code agents in parallel.

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

## Usage

1. **Create a Project** (optional) — Use the sidebar to organize jobs by project.
2. **Create a Job** — Click "+ New Job", enter a title, prompt, select a model, and optionally set a working directory.
3. **Watch it run** — The orchestrator picks up queued jobs (up to 5 concurrent), spawns a Claude agent, and streams output in real-time to the agent card.
4. **Cancel / Remove** — Cancel running jobs or remove completed ones from the dashboard.

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
