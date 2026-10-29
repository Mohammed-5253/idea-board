"""Pydantic models = the API contract in code.

SPEC: POST /api/ideas "Accepts a JSON object like {"content": "My new idea"}".
      GET /api/ideas  "Returns a JSON array of all ideas".
These models validate input and shape output. FastAPI also turns them into the OpenAPI
schema served at /docs, so documentation can never drift from the code.

Validation rules (Phase 0, Q12, approved):
  * `content` must be a JSON string (a number/object/null → 422, no silent coercion).
  * Leading/trailing whitespace is trimmed BEFORE the length check.
  * After trimming: 1..500 characters (Unicode characters, matching PostgreSQL char_length).
  * Unknown extra fields are ignored (the spec says "a JSON object LIKE …"; being lenient
    on input and strict on output is Postel's law). IF you want to reject extras THEN set
    `extra="forbid"` - BUT clients sending metadata would start failing.
LEARN: docs/learning/10-backend-python-fastapi.md §3, §6
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from idea_board.db.tables import CONTENT_MAX_LENGTH

# `strict=True` → only real JSON strings are accepted; `strip_whitespace` trims first,
# then min/max length apply to the trimmed value.
IdeaContent = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=CONTENT_MAX_LENGTH
    ),
]


class IdeaCreate(BaseModel):
    """Request body for POST /api/ideas."""

    model_config = ConfigDict(extra="ignore")
    content: IdeaContent = Field(
        description="The idea text (trimmed, 1-500 characters).",
        examples=["My new idea"],
    )


class IdeaOut(BaseModel):
    """One idea in responses - exactly the table's three columns, nothing more."""

    id: int = Field(examples=[1])
    content: str = Field(examples=["My new idea"])
    # Serialised as RFC 3339 / ISO 8601 with timezone, e.g. "2026-10-28T10:15:30.123456Z".
    created_at: datetime


class ErrorDetail(BaseModel):
    """One field-level problem (used for 422 validation errors)."""

    field: str
    message: str


class ErrorBody(BaseModel):
    """Inner error object."""

    code: str = Field(examples=["validation_error"])
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """The ONE error shape used by every non-2xx response (consistent error responses)."""

    error: ErrorBody
