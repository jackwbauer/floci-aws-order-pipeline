"""Idempotently provision every AWS resource the pipeline needs, inside Floci.

Run it directly (``python -m infra.bootstrap``) or via ``make bootstrap``.
Safe to run repeatedly — existing resources are left untouched.

Wiring: an EventBridge rule matches ``OrderPlaced`` events and fans them out to
two SQS queues (invoice + reporting). That single rule is the fan-out.
"""

from __future__ import annotations

import contextlib
import json
import sys

from botocore.exceptions import ClientError

from order_pipeline.aws import client
from order_pipeline.config import Settings, get_settings


def _ignore(err: ClientError, *codes: str) -> None:
    code = err.response.get("Error", {}).get("Code", "")
    if code not in codes:
        raise


def create_orders_table(s: Settings) -> None:
    ddb = client("dynamodb", s)
    try:
        ddb.create_table(
            TableName=s.orders_table,
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.get_waiter("table_exists").wait(TableName=s.orders_table)
        print(f"  dynamodb table  '{s.orders_table}' created")
    except ClientError as err:
        _ignore(err, "ResourceInUseException")
        print(f"  dynamodb table  '{s.orders_table}' already exists")


def create_bucket(s: Settings) -> None:
    s3 = client("s3", s)
    try:
        s3.create_bucket(Bucket=s.invoice_bucket)
        print(f"  s3 bucket       '{s.invoice_bucket}' created")
    except ClientError as err:
        _ignore(err, "BucketAlreadyOwnedByYou", "BucketAlreadyExists")
        print(f"  s3 bucket       '{s.invoice_bucket}' already exists")


def create_queue(s: Settings, name: str) -> tuple[str, str]:
    sqs = client("sqs", s)
    url = sqs.create_queue(QueueName=name)["QueueUrl"]
    arn = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    # Allow EventBridge to deliver to this queue (best-effort; Floci is lenient).
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": arn,
            }
        ],
    }
    with contextlib.suppress(ClientError):
        sqs.set_queue_attributes(
            QueueUrl=url, Attributes={"Policy": json.dumps(policy)}
        )
    print(f"  sqs queue       '{name}' ready")
    return url, arn


def create_bus_and_rule(s: Settings, targets: list[str]) -> None:
    eb = client("events", s)
    try:
        eb.create_event_bus(Name=s.event_bus_name)
        print(f"  eventbridge bus '{s.event_bus_name}' created")
    except ClientError as err:
        _ignore(err, "ResourceAlreadyExistsException")
        print(f"  eventbridge bus '{s.event_bus_name}' already exists")

    rule_name = "order-placed"
    eb.put_rule(
        Name=rule_name,
        EventBusName=s.event_bus_name,
        EventPattern=json.dumps(
            {"source": [s.event_source], "detail-type": [s.event_detail_type]}
        ),
        State="ENABLED",
    )
    eb.put_targets(
        Rule=rule_name,
        EventBusName=s.event_bus_name,
        Targets=[{"Id": f"target-{i}", "Arn": arn} for i, arn in enumerate(targets)],
    )
    print(f"  eventbridge rule '{rule_name}' -> {len(targets)} target(s)")

def bootstrap(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    print(f"Bootstrapping Floci at {s.aws_endpoint_url} ...")
    create_orders_table(s)
    create_bucket(s)
    _, invoice_arn = create_queue(s, s.invoice_queue)
    _, reporting_arn = create_queue(s, s.reporting_queue)
    create_bus_and_rule(s, [invoice_arn, reporting_arn])
    print("Done.")


if __name__ == "__main__":
    try:
        bootstrap()
    except Exception as exc:  # pragma: no cover
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
