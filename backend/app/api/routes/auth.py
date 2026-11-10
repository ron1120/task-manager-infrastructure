# Auth HTTP endpoints → mounted at /api/auth/...
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.core.actor import Actor
from app.core.security import create_access_token
from app.database.session import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserResponse
from app.services import audit
from app.services.auth_service import authenticate_user, create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    # Create account (email + password). No JWT yet — client should login after.
    if get_user_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = create_user(db, user_in)
    audit.record(db, Actor.user(user), "user.register", "user", user.id, {"role": user.role}, client_ip(request))
    db.commit()
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),  # expects form: username + password
    db: Session = Depends(get_db),
) -> Token:
    # OAuth2 form uses "username" field — we put the email there
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # Failed logins are security events: record who was tried and from where (never the password).
        audit.record(
            db, Actor.anonymous(form_data.username[:100]), "auth.login_failed", "user", None, None, client_ip(request)
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    audit.record(db, Actor.user(user), "auth.login", "user", user.id, None, client_ip(request))
    db.commit()
    # JWT subject = user id; frontend stores this token in localStorage
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    # Requires Bearer token — returns the logged-in user
    return current_user
