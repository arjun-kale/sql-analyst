from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException

from app.environment import SQLAnalystEnv
from app.models import ResetRequest, SQLAction, SQLObservation, StateResponse, StepResult
from app.tasks.registry import TASKS

env: SQLAnalystEnv | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global env
    env = SQLAnalystEnv()
    env.reset()
    yield


app = FastAPI(
    title="SQLAnalyst-Env",
    description="Business Intelligence SQL Agent Environment (OpenEnv)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/reset", response_model=SQLObservation)
async def reset(request: ResetRequest = ResetRequest()):
    """Reset environment to initial state. Returns initial observation."""
    if env is None:
        raise HTTPException(status_code=500, detail="Environment not initialized")
    return env.reset(task_id=request.task_id or "easy_sales_report")


@app.post("/step", response_model=StepResult)
async def step(action: SQLAction):
    """Execute one SQL query. Returns observation, reward, done, info."""
    if env is None:
        raise HTTPException(status_code=500, detail="Environment not initialized")
    try:
        return env.step(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/state", response_model=StateResponse)
async def state():
    """Return current environment state snapshot."""
    if env is None:
        raise HTTPException(status_code=500, detail="Environment not initialized")
    return env.state()


@app.get("/tasks")
async def tasks() -> List[Dict]:
    """Return list of all available tasks."""
    return [
        {
            "id": t.id,
            "name": t.name,
            "difficulty": t.difficulty,
            "description": t.description,
            "max_steps": t.max_steps,
        }
        for t in TASKS.values()
    ]


@app.get("/health")
async def health():
    """Service health check."""
    return {"status": "ok", "env": "SQLAnalyst-Env", "version": "1.0.0"}


def serve(host: str = "0.0.0.0", port: int = 7860) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
