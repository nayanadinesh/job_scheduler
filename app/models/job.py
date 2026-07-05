import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base

# Job status state machine
JobStatus = SAEnum(
    "queued", "scheduled", "claimed", "running", "completed", "failed", "dead", "cancelled",
    name="job_status",
)


def _now() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # Hot-path partial index: only claimable rows
        Index(
            "idx_jobs_ready",
            "queue_id", "priority", "run_at",
            postgresql_where="status IN ('queued', 'scheduled')",
        ),
        # Idempotent submission
        Index(
            "idx_jobs_dedup",
            "queue_id", "dedup_key",
            unique=True,
            postgresql_where="dedup_key IS NOT NULL",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    queue_id: Mapped[str] = mapped_column(String, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Use JSONB on Postgres, JSON on SQLite (for tests)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # FK to workers added in increment 6 when the workers table exists
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=func.now()
    )

    queue: Mapped["Queue"] = relationship("Queue")  # type: ignore[name-defined]  # noqa: F821
    executions: Mapped[list["JobExecution"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    logs: Mapped[list["JobLog"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobExecution(Base):
    __tablename__ = "job_executions"
    __table_args__ = (
        Index("idx_executions_job", "job_id", "attempt_no"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="executions")


class JobLog(Base):
    __tablename__ = "job_logs"
    __table_args__ = (
        Index("idx_logs_job", "job_id", "ts"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String, ForeignKey("job_executions.id", ondelete="CASCADE"), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="logs")
