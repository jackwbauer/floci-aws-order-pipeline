"""Relational read-model (the "analytics" side of the pipeline).

A denormalised fact row per order, upserted idempotently so re-delivered SQS
messages don't create duplicates.
"""

from __future__ import annotations

import psycopg

DDL = """
CREATE TABLE IF NOT EXISTS order_facts (
    order_id       TEXT PRIMARY KEY,
    customer_email TEXT        NOT NULL,
    status         TEXT        NOT NULL,
    item_count     INTEGER     NOT NULL,
    total_cents    BIGINT      NOT NULL,
    placed_at      TIMESTAMPTZ NOT NULL,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

UPSERT = """
INSERT INTO order_facts
    (order_id, customer_email, status, item_count, total_cents, placed_at)
VALUES
    (%(order_id)s, %(customer_email)s, %(status)s, %(item_count)s,
     %(total_cents)s, %(placed_at)s)
ON CONFLICT (order_id) DO UPDATE SET
    status      = EXCLUDED.status,
    item_count  = EXCLUDED.item_count,
    total_cents = EXCLUDED.total_cents,
    placed_at   = EXCLUDED.placed_at,
    recorded_at = now();
"""


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def upsert_order_fact(conn: psycopg.Connection, order: dict) -> None:
    params = {
        "order_id": order["id"],
        "customer_email": order["customer_email"],
        "status": order["status"],
        "item_count": order.get("item_count")
        or sum(i["quantity"] for i in order["items"]),
        "total_cents": order["total_cents"],
        "placed_at": order["created_at"],
    }
    with conn.cursor() as cur:
        cur.execute(UPSERT, params)
    conn.commit()
