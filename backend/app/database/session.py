# Database connection + per-request session helper
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Connection pool to Postgres
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
# Factory that creates a new Session when called
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    # FastAPI dependency: open a DB session for one request, then always close it
    db = SessionLocal()
    try:
        yield db  # route handlers receive this as `db: Session = Depends(get_db)`
    finally:
        db.close()
