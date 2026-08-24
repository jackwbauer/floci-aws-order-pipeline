"""Publishes order lifecycle events to the EventBridge bus."""

from __future__ import annotations

from ..aws import client
from ..config import Settings, get_settings
from ..models import Order


def publish_order_placed(order: Order, settings: Settings | None = None) -> None:
    s = settings or get_settings()
    client("events", s).put_events(
        Entries=[
            {
                "Source": s.event_source,
                "DetailType": s.event_detail_type,
                "Detail": order.model_dump_json(),
                "EventBusName": s.event_bus_name,
            }
        ]
    )
