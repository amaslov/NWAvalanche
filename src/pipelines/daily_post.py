"""Daily post orchestrator. Composes N products into one markdown post."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.clock import Clock, FrozenClock, SystemClock
from src.fetchers.nac_api import NACClient
from src.fetchers.nws_api import NWSClient
from src.products.avalanche_forecast import AvalancheForecastProduct
from src.products.base import ProductUnavailable
from src.products.nws_weather import NWSWeatherProduct
from src.render import render_daily_post
from src.schema import DailyContext, ValidatedProduct
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


def _date_dir(as_of: datetime) -> Path:
    d = RAW_ROOT / as_of.date().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_once(path: Path, payload: dict) -> None:
    if not path.exists():
        path.write_text(json.dumps(payload, indent=2))


def archive_avalanche(raw: dict, *, as_of: datetime, zone: AvalancheZone) -> None:
    _write_once(
        _date_dir(as_of) / f"avalanche_{zone.slug}_{raw['id']}.json",
        raw,
    )


def archive_nws(raw: dict, *, as_of: datetime, zone: AvalancheZone) -> None:
    d = _date_dir(as_of)
    _write_once(d / f"nws_{zone.slug}.json", raw["forecast"])
    _write_once(d / f"nws_hourly_{zone.slug}.json", raw["hourly"])


def _try_product(
    label: str, fetch: callable, validate: callable, archive: callable
) -> ValidatedProduct | None:
    try:
        raw = fetch()
        archive(raw)
        return validate(raw)
    except ProductUnavailable as exc:
        print(f"Skipped {label}: {exc}", file=sys.stderr)
        return None


def run(zone: AvalancheZone, as_of: datetime, *, dry_run: bool) -> Path:
    products: list[ValidatedProduct] = []
    renderers: dict[str, callable] = {}

    with NACClient() as nac, NWSClient() as nws:
        avalanche = AvalancheForecastProduct(nac)
        nws_weather = NWSWeatherProduct(nws)

        listing = nac.list_products()
        avy = _try_product(
            "avalanche_forecast",
            fetch=lambda: avalanche.fetch(zone, as_of=as_of, listing=listing),
            validate=lambda raw: avalanche.validate(raw, zone=zone, as_of=as_of),
            archive=lambda raw: archive_avalanche(raw, as_of=as_of, zone=zone),
        )
        if avy is not None:
            products.append(avy)
            renderers[avalanche.name] = avalanche.render

        wx = _try_product(
            "nws_weather",
            fetch=lambda: nws_weather.fetch(zone, as_of=as_of),
            validate=lambda raw: nws_weather.validate(raw, zone=zone, as_of=as_of),
            archive=lambda raw: archive_nws(raw, as_of=as_of, zone=zone),
        )
        if wx is not None:
            products.append(wx)
            renderers[nws_weather.name] = nws_weather.render

    if not products:
        raise ProductUnavailable("No products available for this run")

    context = DailyContext(zone=zone, as_of=as_of, products=products)
    markdown = render_daily_post(context, product_renderers=renderers)

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
