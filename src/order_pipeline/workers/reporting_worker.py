"""Consumes OrderPlaced events and upserts a fact row into Postgres."""

from __future__ import annotations

import time

import psycopg

from ..aws import client
from ..config import Settings, get_settings
from ..repository.reporting import ensure_schema, upsert_order_fact
from ._sqs import extract_order, queue_url


def process_once(conn: psycopg.Connection, settings: Settings | None = None) -> int:
    s = settings or get_settings()
    sqs = client("sqs", s)
    url = queue_url(s, s.reporting_queue)

    resp = sqs.receive_message(
        QueueUrl=url,
        MaxNumberOfMessages=s.poll_batch_size,
        WaitTimeSeconds=s.poll_wait_seconds,
    )
    messages = resp.get("Messages", [])
    for msg in messages:
        order = extract_order(msg["Body"])
        upsert_order_fact(conn, order)
        sqs.delete_message(QueueUrl=url, ReceiptHandle=msg["ReceiptHandle"])
    return len(messages)


def run() -> None:  # pragma: no cover - long-running loop
    s = get_settings()
    print("[reporting-worker] connecting to postgres...", flush=True)
    with psycopg.connect(s.database_url) as conn:
        ensure_schema(conn)
        print("[reporting-worker] polling...", flush=True)
        while True:
            try:
                n = process_once(conn, s)
                if n:
                    print(f"[reporting-worker] processed {n}", flush=True)
            except Exception as exc:
                print(f"[reporting-worker] error: {exc}", flush=True)
                time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    run()
