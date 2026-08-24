"""Domain models. Money is stored in integer cents everywhere to avoid float
and Decimal foot-guns across JSON, DynamoDB, and Postgres."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


class OrderStatus(StrEnum):
    PLACED = "PLACED"
    INVOICED = "INVOICED"
    FULFILLED = "FULFILLED"


class OrderItem(BaseModel):
    sku: str
    name: str
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)

    # pydantic's mypy plugin normally recognizes this pattern; it's incompatible
    # with the installed mypy version, so silence the false positive directly.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class OrderCreate(BaseModel):
    """Inbound payload for POST /orders."""

    customer_email: str
    items: list[OrderItem] = Field(min_length=1)


class Order(BaseModel):
    id: str = Field(default_factory=_new_id)
    customer_email: str
    items: list[OrderItem]
    status: OrderStatus = OrderStatus.PLACED
    created_at: datetime = Field(default_factory=_utcnow)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_cents(self) -> int:
        return sum(item.line_total_cents for item in self.items)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    @classmethod
    def from_create(cls, dto: OrderCreate) -> Order:
        return cls(customer_email=dto.customer_email, items=dto.items)
