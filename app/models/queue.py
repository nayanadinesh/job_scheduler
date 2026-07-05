import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class RetryPolicy(Base):
    __tablename__ = "retry_policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="exponential")
    base_delay_s: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_delay_s: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    queues: Mapped[list["Queue"]] = relationship(back_populates="retry_policy")


class Queue(Base):
    __tablename__ = "queues"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    retry_policy_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("retry_policies.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="queues")  # type: ignore[name-defined]  # noqa: F821
    retry_policy: Mapped["RetryPolicy | None"] = relationship(back_populates="queues")
    jobs: Mapped[list] = relationship("Job", back_populates="queue", cascade="all, delete-orphan")
