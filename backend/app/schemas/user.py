# Pydantic schemas = JSON shapes for HTTP request/response (not DB tables)
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    # Body for POST /api/auth/register
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    # What we return about a user (never includes the password)
    model_config = ConfigDict(from_attributes=True)  # allow building from ORM User objects

    id: int
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    # Body returned by POST /api/auth/login
    access_token: str
    token_type: str = "bearer"
