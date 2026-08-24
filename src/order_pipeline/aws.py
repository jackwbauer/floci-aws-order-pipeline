"""boto3 client/resource factory, pre-pointed at the configured endpoint.

Centralising construction here means the endpoint override lives in exactly one
place: swap ``AWS_ENDPOINT_URL`` and the whole app moves between Floci and real
AWS with no code changes.
"""

from __future__ import annotations

import boto3
from botocore.config import Config

from .config import Settings, get_settings


def _kwargs(settings: Settings) -> dict:
    kw: dict = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.aws_endpoint_url:
        kw["endpoint_url"] = settings.aws_endpoint_url
    return kw


def client(service: str, settings: Settings | None = None):
    s = settings or get_settings()
    extra: dict = {}
    if service == "s3":
        # Path-style addressing keeps S3 happy against a localhost endpoint.
        extra["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client(service, **_kwargs(s), **extra)


def resource(service: str, settings: Settings | None = None):
    s = settings or get_settings()
    return boto3.resource(service, **_kwargs(s))
