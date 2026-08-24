"""End-to-end integration tests against Floci + Postgres."""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from order_pipeline.api.main import app, get_settings
from order_pipeline.aws import client
from order_pipeline.config import Settings
from order_pipeline.repository.orders import OrderRepository
from order_pipeline.repository.reporting import ensure_schema
from order_pipeline.workers import invoice_worker, reporting_worker
from order_pipeline.workers._sqs import queue_url

SAMPLE = {
    "customer_email": "buyer@distributor.com",
    "items": [
        {"sku": "HELM-01", "name": "Hard Hat", "quantity": 2, "unit_price_cents": 3500},
        {
            "sku": "VEST-04",
            "name": "Hi-Vis Vest",
            "quantity": 1,
            "unit_price_cents": 2400,
        },
    ],
}


def _api_client(settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _poll_queue(settings: Settings, name: str, timeout: float = 20.0) -> list[dict]:
    sqs = client("sqs", settings)
    url = queue_url(settings, name)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = sqs.receive_message(
            QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=2
        )
        if resp.get("Messages"):
            return resp["Messages"]
    return []


def test_post_order_persists_to_dynamodb(provisioned: Settings) -> None:
    resp = _api_client(provisioned).post("/orders", json=SAMPLE)
    assert resp.status_code == 201
    order_id = resp.json()["id"]

    stored = OrderRepository(provisioned).get(order_id)
    assert stored is not None
    assert stored["customer_email"] == SAMPLE["customer_email"]
    assert stored["total_cents"] == 2 * 3500 + 2400


def test_order_event_fans_out_to_both_queues(provisioned: Settings) -> None:
    _api_client(provisioned).post("/orders", json=SAMPLE)

    for queue in (provisioned.invoice_queue, provisioned.reporting_queue):
        messages = _poll_queue(provisioned, queue)
        assert messages, f"no message delivered to {queue}"


def test_invoice_worker_writes_to_s3(provisioned: Settings) -> None:
    order_id = _api_client(provisioned).post("/orders", json=SAMPLE).json()["id"]

    # Drain until this order's invoice appears (other tests may share the queue).
    for _ in range(10):
        if invoice_worker.process_once(provisioned) == 0:
            break

    s3 = client("s3", provisioned)
    obj = s3.get_object(
        Bucket=provisioned.invoice_bucket, Key=f"invoices/{order_id}.json"
    )
    invoice = json.loads(obj["Body"].read())
    assert invoice["order_id"] == order_id
    assert invoice["total_cents"] == 2 * 3500 + 2400


def test_reporting_worker_upserts_fact_row(provisioned: Settings, pg_conn) -> None:
    ensure_schema(pg_conn)
    order_id = _api_client(provisioned).post("/orders", json=SAMPLE).json()["id"]

    for _ in range(10):
        if reporting_worker.process_once(pg_conn, provisioned) == 0:
            break

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT customer_email, item_count, total_cents "
            "FROM order_facts WHERE order_id = %s",
            (order_id,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == SAMPLE["customer_email"]
    assert row[2] == 2 * 3500 + 2400
