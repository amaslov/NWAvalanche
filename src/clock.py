"""Clock injection. CLAUDE.md forbids datetime.now() in business logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Returns a fixed datetime. For tests and `--as-of` overrides."""

    def __init__(self, frozen_at: datetime) -> None:
        if frozen_at.tzinfo is None:
            frozen_at = frozen_at.replace(tzinfo=UTC)
        self._frozen_at = frozen_at

    def now(self) -> datetime:
        return self._frozen_at
