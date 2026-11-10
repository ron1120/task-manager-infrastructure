# Prometheus metrics for GET /metrics: request counts and latency, plus incident gauges read from the database
import time

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from sqlalchemy.orm import Session

from app.models import Incident
from app.services import incident_service

# Request metrics live for the life of the process and are updated by the middleware in app/main.py.
REGISTRY = CollectorRegistry()
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"], registry=REGISTRY)
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"], registry=REGISTRY)


def observe(method: str, path: str, status: int, started: float) -> None:
    REQUESTS.labels(method, path, str(status)).inc()
    LATENCY.labels(method, path).observe(time.perf_counter() - started)


def render(db: Session) -> bytes:
    """Request metrics from memory, plus incident gauges computed fresh from the database on every scrape."""
    gauges = CollectorRegistry()
    open_by_severity = Gauge("incidents_open", "Open incidents by severity", ["severity"], registry=gauges)
    breached = Gauge("incidents_breached", "Open incidents past their SLA deadline", registry=gauges)
    summary = incident_service.stats(db) if db.query(Incident.id).first() else None
    for severity in ("P1", "P2", "P3", "P4"):
        open_by_severity.labels(severity).set(summary["open_by_severity"][severity] if summary else 0)
    breached.set(summary["breached"] if summary else 0)
    return generate_latest(REGISTRY) + generate_latest(gauges)
