# App entrypoint — uvicorn loads this as: app.main:app
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, tasks
from app.core.config import settings

app = FastAPI(title="Task Manager API", version="0.1.0")

# Allow the React frontend (different origin/port) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules under /api  →  /api/auth/..., /api/tasks/...
app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")


@app.get("/health")
def health_check() -> dict[str, str]:
    # Simple liveness check (no auth). Used by Docker/health probes.
    return {"status": "ok!"}
