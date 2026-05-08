"""Tests for the 24-hour staleness rule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.products.base import STALE_THRESHOLD, is_stale


def _at(hour: int) -> datetime:
    return datetime(2026, 3, 1, hour, tzinfo=UTC)


def test_fresh_just_now() -> None:
    issued = _at(10)
    assert is_stale(issued, _at(10)) is False


def test_fresh_just_under_24h() -> None:
    issued = datetime(2026, 3, 1, 10, tzinfo=UTC)
    as_of = issued + timedelta(hours=23, minutes=59)
    assert is_stale(issued, as_of) is False


def test_stale_just_over_24h() -> None:
    issued = datetime(2026, 3, 1, 10, tzinfo=UTC)
    as_of = issued + timedelta(hours=24, minutes=1)
    assert is_stale(issued, as_of) is True


def test_threshold_constant() -> None:
    assert STALE_THRESHOLD == timedelta(hours=24)
