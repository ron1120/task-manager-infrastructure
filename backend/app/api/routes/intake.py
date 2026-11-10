# Machine intake → mounted at /api/intake/...
# Callers authenticate with an X-API-Key header (create keys at POST /api/api-keys). A key works for one source.
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import api_key_for, client_ip
from app.database.session import get_db
from app.models import ApiKey
from app.schemas.ops import AlertmanagerWebhook, CiTriageReport, GenericIntake, GitHubWorkflowRun, IntakeResult
from app.services import intake_service

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
