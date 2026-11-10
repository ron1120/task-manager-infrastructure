# Shared FastAPI dependencies (injected into route handlers)
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models import ApiKey, User
from app.services.api_key_service import authenticate_key

# Expects header: Authorization: Bearer <jwt>
# tokenUrl tells Swagger UI where the login form posts
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    # Protect routes: decode JWT → load User from DB → or 401
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# viewer can read, analyst can also change incidents, admin can also manage keys, roles and read the audit log.
ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}


def require_role(minimum: str):
    # Use as: current_user: User = Depends(require_role("analyst"))
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(current_user.role, -1) < ROLE_RANK[minimum]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This needs the {minimum} role")
        return current_user

    return checker


def get_actor(current_user: User = Depends(get_current_user)) -> Actor:
    return Actor.user(current_user)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def api_key_for(source: str):
    """Authenticate a machine caller by API key. A key works for exactly one intake source."""

    def checker(
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> ApiKey:
        # Either `X-API-Key: ops_...` or `Authorization: Bearer ops_...` (Alertmanager can only send the latter).
        bearer = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
        key = authenticate_key(db, x_api_key or bearer)
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API key")
        if key.source != source:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This key is not for {source} events")
        return key

    return checker
