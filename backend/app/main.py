# App entrypoint — uvicorn loads this as: app.main:app
import time

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy.orm import Session

from app.api.routes import admin, auth, incidents, intake, tasks
from app.core import metrics
from app.core.config import settings
from app.database.session import get_db

app = FastAPI(title="Task Manager API", version="0.2.0")

# Allow the React frontend (different origin/port) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def record_metrics(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    # Use the route template (/api/incidents/{incident_id}), not the URL, so the label set stays small.
    route = request.scope.get("route")
    metrics.observe(request.method, route.path if route else "unmatched", response.status_code, started)
    return response


# Mount route modules under /api  →  /api/auth/..., /api/tasks/...
app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(intake.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/health")
def health_check() -> dict[str, str]:
    # Simple liveness check (no auth). Used by Docker/health probes.
    return {"status": "ok!"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(db: Session = Depends(get_db)) -> Response:
    # Scraped by Prometheus. No login, like most exporters: keep it on the internal network (do not publish it).
    return Response(metrics.render(db), media_type=CONTENT_TYPE_LATEST)
