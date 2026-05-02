from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_SQL_INJECTION_PATTERNS = [
    re.compile(r"PG_SLEEP\s*\(", re.IGNORECASE),
    re.compile(r"DBMS_PIPE\s*\.\s*RECEIVE_MESSAGE", re.IGNORECASE),
    re.compile(r"waitfor\s+delay\s+", re.IGNORECASE),
    re.compile(r"sleep\s*\(\s*\d+\s*\)", re.IGNORECASE),
    re.compile(r"XOR\s*\(?\s*if\s*\(\s*now\s*\(\s*\)\s*=\s*sysdate\s*\(\s*\)", re.IGNORECASE),
    re.compile(r"\(select\s*\(\s*0\s*\)\s*from\s*\(\s*select\s*\(\s*sleep", re.IGNORECASE),
    re.compile(r"-1\s+OR\s+\d+\+\d+-\d+-1=0\+0\+0\+1", re.IGNORECASE),
    re.compile(r"-1'\s+OR\s+\d+\+\d+-\d+-1=0\+0\+0\+1", re.IGNORECASE),
    re.compile(r"-1\"\s+OR\s+\d+\+\d+-\d+-1=0\+0\+0\+1", re.IGNORECASE),
]


def _contains_sql_injection(value: str) -> bool:
    for pattern in _SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return True
    return False


def _validate_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("유효한 이메일 주소를 입력해 주세요.")
    local, domain = email.rsplit("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("유효한 이메일 주소를 입력해 주세요.")
    if len(email) > 320:
        raise ValueError("이메일 주소가 너무 깁니다.")
    return email


class SuggestionCreateIn(BaseModel):
    grade: int = Field(ge=1, le=3)
    title: str = Field(min_length=2, max_length=140)
    content: str = Field(min_length=5, max_length=10_000)

    @field_validator("content")
    @classmethod
    def validate_no_sqli(cls, value: str) -> str:
        if _contains_sql_injection(value):
            raise ValueError("부적절한 내용이 포함되어 있습니다.")
        return value


class SuggestionUpdateIn(BaseModel):
    grade: int | None = Field(default=None, ge=1, le=3)
    title: str | None = Field(default=None, min_length=2, max_length=140)
    content: str | None = Field(default=None, min_length=5, max_length=10_000)

    @field_validator("content")
    @classmethod
    def validate_no_sqli(cls, value: str | None) -> str | None:
        if value is not None and _contains_sql_injection(value):
            raise ValueError("부적절한 내용이 포함되어 있습니다.")
        return value


class SuggestionAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)


class SuggestionNotificationEmailIn(BaseModel):
    email: str = Field(min_length=5, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


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
