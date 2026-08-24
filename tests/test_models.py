"""Pure unit tests — no containers, run in milliseconds."""

from order_pipeline.models import Order, OrderCreate, OrderItem, OrderStatus
from order_pipeline.workers.invoice_worker import render_invoice


def _sample_items() -> list[OrderItem]:
    return [
        OrderItem(sku="HELM-01", name="Hard Hat", quantity=2, unit_price_cents=3500),
        OrderItem(sku="GLOVE-09", name="Cut Gloves", quantity=3, unit_price_cents=1200),
    ]


def test_line_and_order_totals() -> None:
    order = Order(customer_email="a@b.com", items=_sample_items())
    assert order.items[0].line_total_cents == 7000
    assert order.total_cents == 7000 + 3600
    assert order.item_count == 5
    assert order.status is OrderStatus.PLACED


def test_from_create_generates_id() -> None:
    dto = OrderCreate(customer_email="a@b.com", items=_sample_items())
    order = Order.from_create(dto)
    assert order.id
    assert order.customer_email == "a@b.com"


def test_render_invoice_is_pure() -> None:
    order = Order(customer_email="a@b.com", items=_sample_items())
    invoice = render_invoice(order.model_dump(mode="json"))
    assert invoice["order_id"] == order.id
    assert invoice["total_cents"] == order.total_cents
    assert invoice["invoice_id"].startswith("INV-")
    assert invoice["currency"] == "USD"
