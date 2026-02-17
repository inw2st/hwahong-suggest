from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class AdminOut(BaseModel):
    id: int
    username: str
    created_at: datetime
    last_login_at: datetime | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
