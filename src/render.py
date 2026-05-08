"""Top-level markdown render. Composes per-product sections into a daily post."""

from __future__ import annotations

from src.schema import DailyContext, ValidatedProduct


def render_daily_post(
    context: DailyContext,
    product_renderers: dict[str, callable],
) -> str:
    """Render the full markdown post for a zone.

    `product_renderers` maps product `kind` to a render function that takes the
    validated product and returns markdown. The orchestrator wires the avalanche
    forecast product's render here. Phase 2+ adds entries without changing this code.
    """
    parts: list[str] = []
    date_str = context.as_of.date().isoformat()
    parts.append(f"# {context.zone.display_name} - {date_str}")
    parts.append("")

    if any(p.is_stale for p in context.products):
        parts.append(_stale_banner(context.products))
        parts.append("")

    parts.append("## Sources")
    parts.append("")
    for p in context.products:
        parts.append(
            f"- [{p.source.name}]({p.source.url}) - issued {p.source.issued_at.isoformat()} "
            f"({p.source.attribution})"
        )
    parts.append("")

    parts.append("## AI summary")
    parts.append("")
    parts.append("_LLM summary will appear here in Phase 3._")
    parts.append("")

    for p in context.products:
        renderer = product_renderers.get(p.kind)
        if renderer is None:
            raise KeyError(f"No renderer registered for product kind {p.kind!r}")
        parts.append(renderer(p))
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def _stale_banner(products: list[ValidatedProduct]) -> str:
    stale_kinds = ", ".join(p.kind for p in products if p.is_stale)
    return (
        "> **STALE**: One or more products are older than 24 hours "
        f"({stale_kinds}). Do not present as current conditions."
    )
