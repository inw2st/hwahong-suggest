from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SuggestionCreateIn(BaseModel):
    grade: int = Field(ge=1, le=3)
    title: str = Field(min_length=2, max_length=140)
    content: str = Field(min_length=5, max_length=10_000)


class SuggestionUpdateIn(BaseModel):
    grade: int | None = Field(default=None, ge=1, le=3)
    title: str | None = Field(default=None, min_length=2, max_length=140)
    content: str | None = Field(default=None, min_length=5, max_length=10_000)


class SuggestionAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)


class SuggestionOut(BaseModel):
    id: int
    grade: int
    title: str
    content: str
    status: str
    answer: str | None
    answered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
