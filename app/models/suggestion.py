from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Suggestion(Base):
    """Student suggestion.

    student_key is a random UUID stored in the browser (localStorage) to identify
    "my suggestions" without requiring a full student login system.
    """

    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Client-generated anonymous identifier (UUID string)
    student_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    grade: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # SQLite 호환을 위해 String 사용 (Enum 대신)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
        nullable=False,
    )

    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
