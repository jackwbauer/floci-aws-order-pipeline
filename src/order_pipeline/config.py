"""Runtime configuration.

Every setting is overridable via environment variables so the same code runs
against Floci locally (``http://localhost:4566``), against Floci inside Docker
Compose (``http://floci:4566``), or against real AWS (drop ``AWS_ENDPOINT_URL``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- AWS / Floci connection -------------------------------------------------
    # Leave endpoint empty to talk to real AWS.
    aws_endpoint_url: str | None = "http://localhost:4566"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    # --- Resource names ---------------------------------------------------------
    orders_table: str = "orders"
    event_bus_name: str = "orders-bus"
    event_source: str = "order.api"
    event_detail_type: str = "OrderPlaced"
    invoice_queue: str = "invoice-queue"
    reporting_queue: str = "reporting-queue"
    invoice_bucket: str = "invoices"

    # --- Reporting read-model (relational) --------------------------------------
    database_url: str = "postgresql://floci:floci@localhost:5432/reporting"

    # --- Worker tuning ----------------------------------------------------------
    poll_wait_seconds: int = 5
    poll_batch_size: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
