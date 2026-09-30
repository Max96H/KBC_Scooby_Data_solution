"""Schémas d'entrée : tout champ inconnu est refusé, toutes les chaînes sont bornées."""
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


DECISION_ID = r"^[a-f0-9]{32}$"
