# Auth helpers: password hashing (bcrypt) + JWT create/decode
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt = one-way hash — we store hashes, never plain passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # Used on register — store the returned hash in users.hashed_password
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Used on login — compare typed password against stored hash
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    # Build a signed JWT. `subject` is usually the user id (string).
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}  # sub = who, exp = when it expires
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    # Verify signature + expiry; return user id from `sub`, or None if invalid
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject = payload.get("sub")
        return str(subject) if subject else None
    except JWTError:
        return None
