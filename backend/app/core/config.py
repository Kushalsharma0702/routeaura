"""Central, environment-based configuration. No secrets live in source control."""
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    redis_url: str | None = None

    # Auth
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    refresh_cookie_name: str = "ra_refresh"

    # HTTP
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:8080"]
    max_request_bytes: int = 1_000_000
    rate_limit_enabled: bool = True

    # Dev-only seed accounts (ignored unless environment == development)
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_traveler_email: str | None = None
    seed_traveler_password: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment == "production":
            if "*" in self.cors_origins:
                raise ValueError("CORS wildcard is not allowed in production")
            if self.jwt_secret.lower().startswith(("change", "dev", "test")):
                raise ValueError("JWT_SECRET looks like a placeholder")
        return self

    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
