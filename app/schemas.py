"""Input schemas: unknown fields are rejected, every string is bounded."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(Strict):
    username: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=128)


class CtaIn(Strict):
    cta_id: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")


class FeedbackIn(Strict):
    reaction: Literal["seen", "clicked", "not_now", "never", "intrusive"]


class ConsentIn(Strict):
    enabled: bool


class LanguageIn(Strict):
    language: Literal["en", "fr", "nl"]


class BookingIn(Strict):
    decision_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    slot_id: int = Field(ge=1)
    mode: Literal["phone", "video", "branch"]


class TaskActionIn(Strict):
    action: Literal["log_call", "book_appointment", "dismiss", "complete", "no_show", "cancel_appointment",
                    "release_transfer", "block_transfer"]
    note: str = Field(default="", max_length=500)
    outcome: Literal["reached", "no_answer"] | None = None
    slot_id: int | None = Field(default=None, ge=1)
    mode: Literal["phone", "video", "branch"] | None = None


DECISION_ID = r"^[a-f0-9]{32}$"
