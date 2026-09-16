"""
LeadCore Zero v2 — Application Settings

Reads all configuration from environment variables (or .env file).
Startup fails fast with a human-readable error if required vars are missing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database (Neon Postgres) ──────────────────────────────────────────
    # Pooled URL for the API: use -pooler hostname; PgBouncer transaction mode.
    # prepare_threshold=None is set in the pool to disable server-side prepared
    # statements (required for PgBouncer).
    database_url: str = Field(
        ...,
        description=(
            "Pooled Neon URL (use the -pooler hostname). "
            "Example: postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?sslmode=require"
        ),
    )

    # Direct URL for Alembic migrations and LangGraph PostgresSaver.
    database_url_direct: str = Field(
        ...,
        description=(
            "Direct (non-pooled) Neon URL. "
            "Example: postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require"
        ),
    )

    # ── Identity (required for fair-use User-Agents) ─────────────────────
    contact_email: str = Field(
        ...,
        description=(
            "Contact email embedded in the crawler User-Agent and Nominatim "
            "requests. Required by Nominatim usage policy."
        ),
    )

    # ── LLM (optional — system works without it) ─────────────────────────
    llm_enabled: bool = Field(default=False, description="Enable Ollama LLM nodes")
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )
    ollama_model: str = Field(
        default="qwen2.5:7b",
        description="Ollama model to use for keyword planning and grounded extraction",
    )

    # ── External data sources ─────────────────────────────────────────────
    overpass_endpoints: list[str] = Field(
        default=[
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        ],
        description="Ordered list of Overpass API endpoints; failover in order",
    )
    nominatim_url: str = Field(
        default="https://nominatim.openstreetmap.org",
        description="Nominatim base URL (max 1 req/s, cache all responses)",
    )
    photon_url: str = Field(
        default="https://photon.komoot.io",
        description="Photon geocoder base URL (fallback after Nominatim)",
    )

    # ── Worker concurrency ────────────────────────────────────────────────
    run_concurrency: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Maximum number of simultaneous run graphs in the worker pool",
    )
    crawl_concurrency: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Maximum concurrent website requests across all domains",
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins (include your frontend URL here)",
    )

    # ── Storage ───────────────────────────────────────────────────────────
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for local DuckDB / Overture Parquet cache",
    )

    # ── Derived properties ────────────────────────────────────────────────
    @property
    def overture_cache_dir(self) -> Path:
        return self.data_dir / "overture"

    @property
    def crawler_user_agent(self) -> str:
        return f"LeadCoreZero/2.0 (+contact: {self.contact_email})"

    # ── Validators ────────────────────────────────────────────────────────
    @field_validator("database_url", "database_url_direct", mode="before")
    @classmethod
    def _validate_db_url(cls, v: str) -> str:
        if not v or v.startswith("postgresql://") is False and v.startswith("postgres://") is False:
            raise ValueError(
                "Database URL must start with 'postgresql://' or 'postgres://'. "
                "Get your Neon connection string from the Neon console → Connection Details."
            )
        return v

    @field_validator("contact_email", mode="before")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if not v or "@" not in v:
            raise ValueError(
                "CONTACT_EMAIL must be a valid email address. "
                "It is embedded in the crawler User-Agent as required by Nominatim's "
                "usage policy. Example: scraper@yourdomain.com"
            )
        return v

    @model_validator(mode="after")
    def _validate_pooled_vs_direct(self) -> "Settings":
        """
        Warn if the pooled and direct URLs are the same — they should differ
        (pooled has the -pooler hostname).
        """
        if self.database_url == self.database_url_direct:
            print(
                "\n⚠️  WARNING: DATABASE_URL and DATABASE_URL_DIRECT are identical.\n"
                "   The pooled URL (DATABASE_URL) should use the '-pooler' Neon hostname.\n"
                "   Example: ep-cool-name-pooler.us-east-2.aws.neon.tech\n"
                "   The direct URL (DATABASE_URL_DIRECT) uses the regular hostname.\n",
                file=sys.stderr,
            )
        return self

    def ensure_data_dirs(self) -> None:
        """Create local storage directories if they don't exist."""
        self.overture_cache_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "imports").mkdir(parents=True, exist_ok=True)


# Singleton — import this from anywhere in the app
settings = Settings()  # type: ignore[call-arg]
settings.ensure_data_dirs()
