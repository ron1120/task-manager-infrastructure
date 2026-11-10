# API keys for machine callers (CI, Alertmanager). The plain key is shown once; only its SHA-256 is stored.
import hashlib
import secrets

from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.models import ApiKey
from app.services import audit
from app.services.incident_service import now


def hash_key(raw: str) -> str:
    # Keys are long random strings, so a fast hash is enough: there is nothing to brute-force.
    return hashlib.sha256(raw.encode()).hexdigest()


def create_key(db: Session, actor: Actor, name: str, source: str, ip: str | None = None) -> tuple[ApiKey, str]:
    raw = "ops_" + secrets.token_urlsafe(32)
    key = ApiKey(name=name, source=source, prefix=raw[:8], key_hash=hash_key(raw), created_by_id=actor.user_id)
    db.add(key)
    db.flush()
    audit.record(db, actor, "apikey.create", "api_key", key.id, {"name": name, "source": source}, ip)
    db.commit()
    db.refresh(key)
    return key, raw


def revoke_key(db: Session, actor: Actor, key: ApiKey, ip: str | None = None) -> None:
    if key.revoked_at is None:
        key.revoked_at = now()
        audit.record(db, actor, "apikey.revoke", "api_key", key.id, {"name": key.name}, ip)
        db.commit()


def authenticate_key(db: Session, raw: str | None) -> ApiKey | None:
    if not raw:
        return None
    key = db.query(ApiKey).filter(ApiKey.key_hash == hash_key(raw)).first()
    if key is None or key.revoked_at is not None:
        return None
    key.last_used_at = now()
    db.commit()
    return key
