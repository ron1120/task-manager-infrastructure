# Parent class for all ORM models (User, Task, ...)
# SQLAlchemy uses this to track table metadata.
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
