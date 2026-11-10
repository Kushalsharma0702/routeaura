import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import Role

Climate = ("tropical", "temperate", "cold", "arid", "any")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    role: Role
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v and not re.fullmatch(r"[+0-9()\-\s]{6,32}", v):
            raise ValueError("Invalid phone number")
        return v or None


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class PreferencesIn(BaseModel):
    budget_per_day_minor: int | None = Field(default=None, ge=0, le=10**9)
    trip_duration_days: int | None = Field(default=None, ge=1, le=60)
    interests: list[str] = Field(default_factory=list, max_length=20)
    preferred_climate: str | None = None
    preferred_season: str | None = Field(default=None, max_length=20)
    group_size: int | None = Field(default=None, ge=1, le=50)
    travel_style: str | None = Field(default=None, max_length=20)
    accommodation_preference: str | None = Field(default=None, max_length=20)
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")

    @field_validator("interests")
    @classmethod
    def _interests(cls, v: list[str]) -> list[str]:
        cleaned = sorted({i.strip().lower() for i in v if i.strip()})
        if any(len(i) > 40 for i in cleaned):
            raise ValueError("Interest too long")
        return cleaned

    @field_validator("preferred_climate")
    @classmethod
    def _climate(cls, v: str | None) -> str | None:
        if v is not None and v not in Climate:
            raise ValueError(f"preferred_climate must be one of {Climate}")
        return v


class PreferencesOut(PreferencesIn):
    model_config = ConfigDict(from_attributes=True)
    currency: str = "INR"


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
