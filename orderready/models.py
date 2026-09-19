"""Shared data contract. Business rules live in validation.py."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class OrderDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str | None = None
    deadline_raw: str | None = None
    deadline_iso: str | None = None
    requested_total: StrictInt | None = None
    size_s: StrictInt | None = None
    size_m: StrictInt | None = None
    size_l: StrictInt | None = None
    unresolved_issues: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "unavailable", "error"]
    draft: OrderDraft | None = None
    message: str


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str
