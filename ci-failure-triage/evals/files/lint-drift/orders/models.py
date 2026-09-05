"""Order models."""

from pydantic import BaseModel


class Order(BaseModel):
    order_id: str
    tier: str | None = None
    total_cents: int
