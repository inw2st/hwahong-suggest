from __future__ import annotations

from pydantic import BaseModel, Field


class PushSubscriptionIn(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushSubscriptionOut(BaseModel):
    id: int
    student_key: str
    endpoint: str

    class Config:
        from_attributes = True
