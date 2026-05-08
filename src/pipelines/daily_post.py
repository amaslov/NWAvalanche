"""Phase 1 orchestrator. Fetches one zone's avalanche forecast and renders markdown."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.clock import Clock, FrozenClock, SystemClock
from src.fetchers.nac_api import NACClient
from src.products.avalanche_forecast import AvalancheForecastProduct
from src.products.base import ProductUnavailable
from src.render import render_daily_post
from src.schema import DailyContext
from src.zones import AvalancheZone

ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "raw"
OUT_DIR = ROOT / "out"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="daily_post")
    parser.add_argument(
        "--zone",
        required=True,
        help="NWAC zone short name (e.g. STEVENS, SNOQUALMIE, MT_HOOD)",
    )
    parser.add_argument(
        "--as-of",
        help="Override 'today' for offseason testing. Format: YYYY-MM-DD",
        default=None,
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Render to out/ instead of publishing"
    )
    return parser.parse_args(argv)


def build_clock(as_of: str | None) -> Clock:
    if as_of is None:
        return SystemClock()
    return FrozenClock(datetime.fromisoformat(as_of).replace(tzinfo=UTC))


def archive_raw(raw: dict, *, as_of: datetime, zone: AvalancheZone) -> Path:
    date_dir = RAW_ROOT / as_of.date().isoformat()
    date_dir.mkdir(parents=True, exist_ok=True)
    path = date_dir / f"avalanche_{zone.slug}_{raw['id']}.json"
    if not path.exists():
        path.write_text(json.dumps(raw, indent=2))
    return path


def run(zone: AvalancheZone, as_of: datetime, *, dry_run: bool) -> Path:
    with NACClient() as client:
        listing = client.list_products()
        product = AvalancheForecastProduct(client)
        raw = product.fetch(zone, as_of=as_of, listing=listing)
        archive_raw(raw, as_of=as_of, zone=zone)
        validated = product.validate(raw, zone=zone, as_of=as_of)

    context = DailyContext(zone=zone, as_of=as_of, products=[validated])
    markdown = render_daily_post(
        context,
        product_renderers={"avalanche_forecast": product.render},
    )

    if not dry_run:
        raise NotImplementedError("Live publish lands in Phase 5")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{as_of.date().isoformat()}-{zone.slug}.md"
    out_path.write_text(markdown)
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    zone = AvalancheZone.from_cli(args.zone)
    clock = build_clock(args.as_of)
    as_of = clock.now()

    try:
        out_path = run(zone, as_of, dry_run=args.dry_run)
    except ProductUnavailable as exc:
        print(f"ProductUnavailable: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
