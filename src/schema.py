"""Composite types shared across products."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.zones import AvalancheZone


class ProductSource(BaseModel):
    """Provenance metadata that every rendered product surfaces above the fold."""

    model_config = ConfigDict(frozen=True)

    name: str
    url: str
    issued_at: datetime
    attribution: str


class ValidatedProduct(BaseModel):
    """Base type for any product that has been fetched, parsed, and freshness-checked."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    source: ProductSource
    is_stale: bool


class DailyContext(BaseModel):
    """The composite view a renderer or summarizer consumes."""

    zone: AvalancheZone
    as_of: datetime
    products: list[ValidatedProduct]

    def get(self, kind: str) -> ValidatedProduct | None:
        return next((p for p in self.products if p.kind == kind), None)
