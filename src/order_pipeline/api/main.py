"""Ingestion API. Accepts an order, persists it to DynamoDB, and emits an
``OrderPlaced`` event. Everything downstream reacts to that event."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from ..config import Settings, get_settings
from ..events.publisher import publish_order_placed
from ..models import Order, OrderCreate
from ..repository.orders import OrderRepository

app = FastAPI(title="Order Pipeline API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(dto: OrderCreate, settings: Settings = Depends(get_settings)) -> Order:
    order = Order.from_create(dto)
    OrderRepository(settings).put(order)
    publish_order_placed(order, settings)
    return order


@app.get("/orders/{order_id}")
def get_order(order_id: str, settings: Settings = Depends(get_settings)) -> dict:
    item = OrderRepository(settings).get(order_id)
    if item is None:
        raise HTTPException(status_code=404, detail="order not found")
    return item
