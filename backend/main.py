import asyncio
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from database import init_db
from orchestrator import Orchestrator
from routes.tasks import router as tasks_router
from routes.task_runs import router as task_runs_router
from routes.flows import router as flows_router
from routes.assistants import router as assistants_router

# Socket.IO
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

orchestrator = Orchestrator(sio)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await orchestrator.start()
    yield
    await orchestrator.stop()


# FastAPI
app = FastAPI(title="Gyro", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(task_runs_router)
app.include_router(flows_router)
app.include_router(assistants_router)


# Cancel task run endpoint that needs orchestrator
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    await orchestrator.cancel_task_run(task_id)
    return {"ok": True}


# Socket.IO events
@sio.event
async def connect(sid, environ):
    print(f"[ws] client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[ws] client disconnected: {sid}")


# Mount Socket.IO
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Serve frontend static files in production
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=3000)
