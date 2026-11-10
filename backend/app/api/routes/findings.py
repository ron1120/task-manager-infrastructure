# Security findings → mounted at /api/findings and /api/scans
# Reading needs any signed-in user. Accepting a risk or opening an incident needs the analyst role.
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_actor, get_current_user, require_role
from app.core.actor import Actor
from app.database.session import get_db
from app.models import User
from app.schemas.ops import (
    FindingKind,
    FindingList,
    FindingResponse,
    FindingSeverity,
    FindingStats,
    FindingStatusChange,
    IncidentDetail,
    ScanResponse,
)
from app.services import finding_service as svc
from app.services import incident_service

router = APIRouter(tags=["findings"])


def _get_or_404(db: Session, finding_id: int):
    finding = svc.get_finding(db, finding_id)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    return finding


@router.get("/findings", response_model=FindingList)
def list_findings(
    status_: str | None = Query(default=None, alias="status", pattern="^(open|accepted|fixed)$"),
    severity: FindingSeverity | None = None,
    scanner: str | None = Query(default=None, max_length=30),
    kind: FindingKind | None = None,
    target: str | None = Query(default=None, max_length=255),
    fixable: bool | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    items, total = svc.list_findings(
        db, status=status_, severity=severity, scanner=scanner, kind=kind, target=target, fixable=fixable, q=q,
        limit=limit, offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/findings/stats", response_model=FindingStats)
def finding_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return svc.stats(db)


@router.get("/findings/{finding_id}", response_model=FindingResponse)
def get_finding(finding_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_or_404(db, finding_id)


@router.post("/findings/{finding_id}/status", response_model=FindingResponse)
def change_status(
    finding_id: int,
    body: FindingStatusChange,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("analyst")),
):
    finding = _get_or_404(db, finding_id)
    try:
        return svc.set_status(db, finding, actor, body.status, body.reason, client_ip(request))
    except svc.RiskReasonRequired as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/findings/{finding_id}/incident", response_model=IncidentDetail, status_code=status.HTTP_201_CREATED)
def open_incident(
    finding_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("analyst")),
) -> dict:
    """Open an incident for this finding (or return the one already linked to it)."""
    incident = svc.open_incident_for(db, _get_or_404(db, finding_id), actor, client_ip(request))
    data = IncidentDetail.model_validate(incident).model_dump()
    data["breached"] = incident_service.is_breached(incident)
    return data


@router.get("/scans", response_model=list[ScanResponse])
def list_scans(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return svc.recent_scans(db, limit)
