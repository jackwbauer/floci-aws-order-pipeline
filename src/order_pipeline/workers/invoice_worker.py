"""Consumes OrderPlaced events and writes a rendered invoice to S3."""

from __future__ import annotations

import json
import time

from ..aws import client
from ..config import Settings, get_settings
from ._sqs import extract_order, queue_url


def render_invoice(order: dict) -> dict:
    """Pure function: order dict -> invoice dict. Trivially unit-testable."""
    return {
        "invoice_id": f"INV-{order['id'][:8].upper()}",
        "order_id": order["id"],
        "customer_email": order["customer_email"],
        "currency": "USD",
        "line_items": order["items"],
        "total_cents": order["total_cents"],
    }


def process_once(settings: Settings | None = None) -> int:
    s = settings or get_settings()
    sqs = client("sqs", s)
    s3 = client("s3", s)
    url = queue_url(s, s.invoice_queue)

    resp = sqs.receive_message(
        QueueUrl=url,
        MaxNumberOfMessages=s.poll_batch_size,
        WaitTimeSeconds=s.poll_wait_seconds,
    )
    messages = resp.get("Messages", [])
    for msg in messages:
        order = extract_order(msg["Body"])
        invoice = render_invoice(order)
        s3.put_object(
            Bucket=s.invoice_bucket,
            Key=f"invoices/{order['id']}.json",
            Body=json.dumps(invoice).encode(),
            ContentType="application/json",
        )
        sqs.delete_message(QueueUrl=url, ReceiptHandle=msg["ReceiptHandle"])
    return len(messages)


def run() -> None:  # pragma: no cover - long-running loop
    print("[invoice-worker] polling...", flush=True)
    while True:
        try:
            n = process_once()
            if n:
                print(f"[invoice-worker] processed {n} message(s)", flush=True)
        except Exception as exc:  # keep the loop alive
            print(f"[invoice-worker] error: {exc}", flush=True)
            time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    run()
