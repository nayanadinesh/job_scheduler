from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

RetryStrategy = Literal["fixed", "linear", "exponential"]


class RetryPolicyCreate(BaseModel):
    strategy: RetryStrategy = "exponential"
    base_delay_s: int = 5
    max_attempts: int = 3
    max_delay_s: int = 3600

    @field_validator("base_delay_s", "max_attempts", "max_delay_s")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Must be at least 1")
        return v


class RetryPolicyOut(BaseModel):
    id: str
    strategy: str
    base_delay_s: int
    max_attempts: int
    max_delay_s: int
    created_at: datetime

    model_config = {"from_attributes": True}


class QueueCreate(BaseModel):
    name: str
    priority: int = 5
    concurrency_limit: int = 10
    retry_policy: RetryPolicyCreate | None = None

    @field_validator("concurrency_limit")
    @classmethod
    def concurrency_min_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("concurrency_limit must be >= 1")
        return v

    @field_validator("priority")
    @classmethod
    def priority_range(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("priority must be 1–10")
        return v


class QueueUpdate(BaseModel):
    name: str | None = None
    priority: int | None = None
    concurrency_limit: int | None = None

    @field_validator("concurrency_limit")
    @classmethod
    def concurrency_min_one(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("concurrency_limit must be >= 1")
        return v


class QueueOut(BaseModel):
    id: str
    project_id: str
    name: str
    priority: int
    concurrency_limit: int
    is_paused: bool
    retry_policy: RetryPolicyOut | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
