# Machine intake → mounted at /api/intake/...
# Callers authenticate with an X-API-Key header (create keys at POST /api/api-keys). A key works for one source.
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import api_key_for, client_ip
from app.database.session import get_db
from app.models import ApiKey
from app.core.actor import Actor
from app.schemas.ops import (
    AlertmanagerWebhook,
    CiTriageReport,
    GenericIntake,
    GitHubWorkflowRun,
    IntakeResult,
    ScanResult,
)
from app.services import finding_service, intake_service
from app.services.scan_parsers import ScanFormatError

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/github-actions", response_model=IntakeResult)
def github_actions(
    body: GitHubWorkflowRun,
    request: Request,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(api_key_for("github_actions")),
) -> dict:
    """A failed workflow run becomes an incident. Post GitHub's own `workflow_run` event payload as-is."""
    return intake_service.github_actions(db, key, body, client_ip(request))


@router.post("/alertmanager", response_model=IntakeResult)
def alertmanager(
    body: AlertmanagerWebhook,
    request: Request,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(api_key_for("alertmanager")),
) -> dict:
    """Prometheus Alertmanager webhook. Firing alerts open incidents; resolved ones mark them mitigated."""
    return intake_service.alertmanager(db, key, body, client_ip(request))


@router.post("/ci-triage", response_model=IntakeResult)
def ci_triage(
    body: CiTriageReport,
    request: Request,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(api_key_for("ci_triage")),
) -> dict:
    """The ci-triage-agent's diagnosis: attached to the incident for that run, or a new incident."""
    return intake_service.ci_triage(db, key, body, client_ip(request))


@router.post("/generic", response_model=IntakeResult)
def generic(
    body: GenericIntake,
    request: Request,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(api_key_for("generic")),
) -> dict:
    """Anything else that can send JSON. The same external_id again counts as a repeat of the same incident."""
    return intake_service.generic(db, key, body, client_ip(request))


@router.post("/scan/{scanner}", response_model=ScanResult)
def scan(
    scanner: Literal["trivy", "gitleaks", "hadolint"],
    request: Request,
    report: dict | list = Body(..., description="The scanner's own JSON output, unchanged"),
    target: str | None = Query(default=None, max_length=255, description="What was scanned; defaults to the report's own"),
    ref: str | None = Query(default=None, max_length=100, description="Commit SHA"),
    run_url: str | None = Query(default=None, max_length=500),
    complete: bool = Query(default=True, description="False for a partial scan, so missing findings are not closed"),
    db: Session = Depends(get_db),
    key: ApiKey = Depends(api_key_for("scanner")),
) -> dict:
    """Upload Trivy, gitleaks or Hadolint JSON. New findings are recorded, ones that vanished are marked fixed, and a
    leaked secret or a new critical finding opens an incident. Secret values are never stored."""
    try:
        return finding_service.ingest_scan(
            db, Actor.api_key(key), scanner, report, target=target, ref=ref, run_url=run_url, complete=complete,
            ip=client_ip(request),
        )
    except ScanFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
