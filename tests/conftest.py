"""Test fixtures: a live Floci container and a live Postgres container.

These integration tests need Docker available (locally or on the CI runner).
No AWS account, no credentials, no network egress to AWS.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

# Ryuk (the cleanup reaper) bind-mounts the Docker socket, which fails on some
# Docker Desktop configs. Our fixtures stop their own containers, so it's safe
# to skip. Override by setting TESTCONTAINERS_RYUK_DISABLED=false.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import boto3
import psycopg
import pytest
from botocore.config import Config
from infra.bootstrap import bootstrap
from testcontainers.core.container import DockerContainer

try:  # import path moved in newer testcontainers releases
    from testcontainers.community.postgres import PostgresContainer
except ImportError:  # pragma: no cover
    from testcontainers.postgres import PostgresContainer

from order_pipeline.config import Settings

FLOCI_IMAGE = "floci/floci:latest"
FLOCI_PORT = 4566


def _wait_until_ready(endpoint: str, timeout: float = 60.0) -> None:
    """Poll a cheap AWS call until Floci answers."""
    deadline = time.time() + timeout
    sts = boto3.client(
        "sts",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
    )
    last: Exception | None = None
    while time.time() < deadline:
        try:
            sts.get_caller_identity()
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1)
    raise RuntimeError(f"Floci not ready at {endpoint}: {last}")


@pytest.fixture(scope="session")
def floci_endpoint() -> Iterator[str]:
    container = DockerContainer(FLOCI_IMAGE).with_exposed_ports(FLOCI_PORT)
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(FLOCI_PORT)
        endpoint = f"http://{host}:{port}"
        _wait_until_ready(endpoint)
        yield endpoint
    finally:
        container.stop()


@pytest.fixture(scope="session")
def postgres() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        # testcontainers hands back a SQLAlchemy-style URL; normalise for psycopg.
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        yield url


@pytest.fixture
def settings(floci_endpoint: str, postgres: str) -> Settings:
    return Settings(aws_endpoint_url=floci_endpoint, database_url=postgres)


@pytest.fixture
def provisioned(settings: Settings) -> Settings:
    """Bootstrap all AWS resources for a test, then return the settings."""
    bootstrap(settings)
    return settings


@pytest.fixture
def pg_conn(postgres: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(postgres) as conn:
        yield conn
