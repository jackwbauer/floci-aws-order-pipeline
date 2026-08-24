"""Shared SQS helpers for the workers."""

from __future__ import annotations

import json

from ..aws import client
from ..config import Settings


def queue_url(settings: Settings, name: str) -> str:
    return client("sqs", settings).get_queue_url(QueueName=name)["QueueUrl"]


def extract_order(body: str) -> dict:
    """Return the order dict regardless of whether the SQS body is a raw order
    or a full EventBridge envelope (``{"detail": {...}}``)."""
    payload = json.loads(body)
    detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
    if isinstance(detail, str):
        detail = json.loads(detail)
    return detail
