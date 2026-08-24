"""DynamoDB persistence for orders."""

from __future__ import annotations

from ..aws import resource
from ..config import Settings, get_settings
from ..models import Order


class OrderRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._table = resource("dynamodb", self._settings).Table(
            self._settings.orders_table
        )

    def put(self, order: Order) -> None:
        self._table.put_item(Item=self._to_item(order))

    def get(self, order_id: str) -> dict | None:
        return self._table.get_item(Key={"id": order_id}).get("Item")

    @staticmethod
    def _to_item(order: Order) -> dict:
        return {
            "id": order.id,
            "customer_email": order.customer_email,
            "status": order.status.value,
            "created_at": order.created_at.isoformat(),
            "total_cents": order.total_cents,
            "item_count": order.item_count,
            "items": [
                {
                    "sku": i.sku,
                    "name": i.name,
                    "quantity": i.quantity,
                    "unit_price_cents": i.unit_price_cents,
                    "line_total_cents": i.line_total_cents,
                }
                for i in order.items
            ],
        }
