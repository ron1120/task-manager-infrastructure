# Admin endpoints: users and roles, API keys, the audit log. → /api/users, /api/api-keys, /api/audit
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_actor, require_role
from app.core.actor import Actor
from app.database.session import get_db
from app.models import ApiKey, AuditLog, User
from app.schemas.ops import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyResponse,
    AuditList,
    RoleChange,
    UserSummary,
)
from app.services import api_key_service, audit

router = APIRouter(tags=["admin"])


@router.get("/users", response_model=list[UserSummary])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_role("analyst"))) -> list[User]:
    # Analysts need the list to pick an assignee. It exposes ids, emails and roles only.
    return db.query(User).order_by(User.id).all()


@router.patch("/users/{user_id}/role", response_model=UserSummary)
def change_role(
    user_id: int,
    body: RoleChange,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("admin")),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "admin" and body.role != "admin" and db.query(User).filter(User.role == "admin").count() <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There must always be at least one admin")
    if user.role != body.role:
        audit.record(db, actor, "user.role_change", "user", user.id, {"from": user.role, "to": body.role}, client_ip(request))
        user.role = body.role
        db.commit()
        db.refresh(user)
    return user


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    body: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("admin")),
) -> dict:
    key, raw = api_key_service.create_key(db, actor, body.name, body.source, client_ip(request))
    return {**ApiKeyResponse.model_validate(key).model_dump(), "key": raw}


@router.get("/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))) -> list[ApiKey]:
    return db.query(ApiKey).order_by(ApiKey.id).all()


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    current_user: User = Depends(require_role("admin")),
) -> None:
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key_service.revoke_key(db, actor, key, client_ip(request))


@router.get("/audit", response_model=AuditList)
def read_audit_log(
    action: str | None = Query(default=None, max_length=100),
    actor: str | None = Query(default=None, max_length=255),
    entity_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if actor:
        query = query.filter(AuditLog.actor == actor)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    total = query.count()
    items = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}
