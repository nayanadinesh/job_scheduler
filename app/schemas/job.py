from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator


class ScheduleImmediate(BaseModel):
    kind: Literal["immediate"] = "immediate"


class ScheduleDelay(BaseModel):
    kind: Literal["delay"] = "delay"
    delay_s: int = Field(ge=1, description="Seconds to delay before the job becomes claimable")


class ScheduleAt(BaseModel):
    kind: Literal["scheduled"] = "scheduled"
    run_at: datetime = Field(description="Absolute timestamp when the job becomes claimable")

    @field_validator("run_at")
    @classmethod
    def ensure_aware(cls, v: datetime) -> datetime:
        # Treat naive datetimes as UTC so comparisons stay consistent.
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class ScheduleBatch(BaseModel):
    kind: Literal["batch"] = "batch"
    count: int = Field(ge=2, le=1000, description="Number of identical jobs to fan out")
    delay_s: int = Field(default=0, ge=0, description="Optional delay applied to every job in the batch")


Schedule = Annotated[
    ScheduleImmediate | ScheduleDelay | ScheduleAt | ScheduleBatch,
    Field(discriminator="kind"),
]


class JobCreate(BaseModel):
    type: str
    payload: dict[str, Any] = {}
    priority: int = 5
    dedup_key: str | None = None
    schedule: Schedule = ScheduleImmediate()

    @field_validator("priority")
    @classmethod
    def priority_range(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("priority must be 1–10")
        return v


class JobOut(BaseModel):
    id: str
    queue_id: str
    type: str
    payload: dict[str, Any]
    status: str
    priority: int
    run_at: datetime
    attempts: int
    max_attempts: int
    dedup_key: str | None
    worker_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    id: str
    job_id: str
    attempt_no: int
    worker_id: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error: str | None

    model_config = {"from_attributes": True}


class LogOut(BaseModel):
    id: str
    job_id: str
    execution_id: str | None
    ts: datetime
    level: str
    message: str

    model_config = {"from_attributes": True}


class ScheduledJobCreate(BaseModel):
    name: str
    cron_expr: str
    job_type: str
    job_payload: dict[str, Any] = {}
    description: str | None = None

    @field_validator("cron_expr")
    @classmethod
    def valid_cron(cls, v: str) -> str:
        from croniter import croniter
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v!r}")
        return v


class ScheduledJobOut(BaseModel):
    id: str
    queue_id: str
    name: str
    cron_expr: str
    job_type: str
    job_payload: dict[str, Any]
    description: str | None
    is_active: bool
    last_fired_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
