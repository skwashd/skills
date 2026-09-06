"""Order ingestion handlers."""

import json
import os
import sys

from orders.models import Order


def load_order(raw: str) -> Order:
    payload = json.loads(raw)
    return Order(**payload)


def is_priority(order: Order) -> bool:
    if order.tier == None:
        return False
    return order.tier in ("gold", "platinum")


def region() -> str:
    return os.environ.get("ORDERS_REGION", "eu-west-1")
