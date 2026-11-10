# Incident endpoints → mounted at /api/incidents/...
# Reading needs any signed-in user (viewer and up). Changing needs the analyst role.
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_actor, get_current_user, require_role
from app.core.actor import Actor
from app.database.session import get_db
from app.models import User
from app.schemas.ops import (
    CommentCreate,
    IncidentCreate,
    IncidentDetail,
    IncidentList,
    IncidentResponse,
    IncidentUpdate,
    Severity,
    StatusChange,
    Stats,
    Status,
)
from app.services import incident_service as svc

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _out(incident) -> dict:
    # Adds the computed `breached` flag (past its SLA deadline and not resolved) to what the ORM holds.
    data = IncidentResponse.model_validate(incident).model_dump()
    data["breached"] = svc.is_breached(incident)
    return data


def _detail(incident) -> dict:
    data = IncidentDetail.model_validate(incident).model_dump()
    data["breached"] = svc.is_breached(incident)
    return data


def _get_or_404(db: Session, incident_id: int):
    incident = svc.get_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.get("", response_model=IncidentList)
def list_incidents(
    status_: Status | None = Query(default=None, alias="status"),
    severity: Severity | None = None,
    service: str | None = None,
    environment: str | None = None,
    source: str | None = None,
    assignee: str | None = Query(default=None, description='A user id, or "me"'),
    unassigned: bool = False,
    q: str | None = Query(default=None, min_length=1, max_length=100),
    breached: bool | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    assignee_id = None
    if assignee:
        if assignee == "me":
            assignee_id = current_user.id
        elif assignee.isdigit():
            assignee_id = int(assignee)
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='assignee must be a user id or "me"')
    items, total = svc.list_incidents(
        db, status=status_, severity=severity, service=service, environment=environment, source=source,
        assignee_id=assignee_id, unassigned=unassigned, q=q, breached=breached, limit=limit, offset=offset,
    )
    return {"items": [_out(i) for i in items], "total": total, "limit": limit, "offset": offset}


@router.get("/stats", response_model=Stats)
def incident_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return svc.stats(db)


@router.post("", response_model=IncidentDetail, status_code=status.HTTP_201_CREATED)
def create_incident(
    body: IncidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("analyst")),
) -> dict:
    try:
        incident = svc.create_incident(db, Actor.user(current_user), ip=client_ip(request), **body.model_dump())
    except svc.UnknownUser as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _detail(incident)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    return _detail(_get_or_404(db, incident_id))


@router.patch("/{incident_id}", response_model=IncidentDetail)
def update_incident(
    incident_id: int,
    body: IncidentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("analyst")),
) -> dict:
    incident = _get_or_404(db, incident_id)
    changes = body.model_dump(exclude_unset=True)  # only what the caller sent; assignee_id: null unassigns
    try:
        incident = svc.update_incident(db, incident, actor, changes, client_ip(request))
    except svc.UnknownUser as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _detail(incident)


@router.post("/{incident_id}/status", response_model=IncidentDetail)
def change_status(
    incident_id: int,
    body: StatusChange,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("analyst")),
) -> dict:
    incident = _get_or_404(db, incident_id)
    try:
        incident = svc.change_status(db, incident, actor, body.status, body.note, client_ip(request))
    except svc.InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _detail(incident)


@router.post("/{incident_id}/comments", response_model=IncidentDetail, status_code=status.HTTP_201_CREATED)
def add_comment(
    incident_id: int,
    body: CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("analyst")),
) -> dict:
    incident = _get_or_404(db, incident_id)
    return _detail(svc.add_comment(db, incident, actor, body.body, client_ip(request)))
