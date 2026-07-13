# Business logic for users/auth (used by auth routes)
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas import UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    # Hash password before saving — never store plaintext
    user = User(email=user_in.email, hashed_password=hash_password(user_in.password))
    db.add(user)
    db.commit()
    db.refresh(user)  # reload so we get id / created_at from DB
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    # Return the user if credentials match, else None
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
