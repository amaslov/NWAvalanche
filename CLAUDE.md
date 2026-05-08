# NWAC Daily Summary

## Purpose

Personal-use pipeline that fetches NWAC data from the National Avalanche Center public API (`api.avalanche.org/v2/public/products`, filtered for `avalanche_center_id=NWAC`), composes a daily context from one or more products, produces an LLM orientation summary, evaluates it against ground truth, and publishes to a personal subdomain hosted on Cloudflare Pages as a daily update.

Phase 1 scope: NWAC avalanche forecasts only.
Phase 2+ scope: NWAC mountain weather forecasts added as a second product, using the same plug-in pattern.
Future scope (no development yet): NWAC field observations, weather station telemetry, route guidance tied to forecast problem types.

Two equal-weight goals:

1. Useful daily orientation to conditions in PNW zones I travel in.
2. Hands-on learning project for AI agent patterns and eval design in a safety-critical domain.

Not for public redistribution. Not a substitute for the official forecast. Owner is AIARE-certified and uses LLM output as a secondary input to their own decision-making.

## Hard Constraints (life-safety, non-negotiable)

These apply to every product added in any phase.

1. **Danger ratings pass through deterministically from API fields.** LLM never generates, paraphrases, or restates "Considerable", "High", etc. Template renders from structured JSON.
2. **Avalanche problem types, elevation bands, and aspect/elevation rose data are structured fields, not prose.** Same rule.
3. **Forecaster prose (narrative fields in the avalanche forecast, and mountain weather forecasts when added) is rendered verbatim with NWAC attribution and issue time.** Not summarized. Used as context in the LLM summary prompt, but raw text appears on the page.
4. **Every rendered post has prominent source links** for each product with issue timestamps, above the LLM summary body.
5. **If any required product fails schema validation or fetch, do not publish.** Log loudly, exit non-zero. A missing post is better than a wrong one. 
6. **If any product's `issued_at` is older than 24 hours, mark STALE and do not present as current.** Any missing post needs to be logged as well.
7. **LLM summary output is validated for faithfulness before render.** Failed posts do not publish.
8. **Zone mappings are explicit in `src/zones.py`.** NWAC avalanche zones and mountain weather zones do not share the same set. Never assume 1:1. This file gets richer with each product added.

## Architectural Principles

- **Products are first-class.** Each data source implements a `Product` protocol with fetch, validate, render. The pipeline composes arbitrarily many products into a `DailyContext`.
- **Phase 1 ships with exactly one product: avalanche forecast.** The protocol and composition exist from day one so that adding mountain weather in Phase 2 is a new file, not a refactor.
- **The summarizer consumes a composite `DailyContext`.** It does not know about specific product types, only the shape of the context object.
- **Each claim in the LLM summary cites its source product.** Faithfulness evals check every factual claim traces to a product field.
- **Route guidance stub exists in Phase 1** to prove the plug-in pattern, nothing more.

## Stack

- Python 3.11+, managed with `uv`
- `anthropic` SDK for LLM calls
- `httpx` for API calls
- `pydantic` v2 for schema validation
- `pytest` for unit tests and evals
- `ruff` for lint and format
- GitHub Actions for scheduled runs (cron)
- Cloudflare Pages + Astro for the site, deployed from the site repo on `git push`
- Two repos: this automation repo, and a separate Astro site repo. Automation pushes markdown files to the site repo via the GitHub API.

## Repo Structure (automation repo)

```
.
├── CLAUDE.md
├── WORKPLAN.md
├── pyproject.toml
├── src/
│   ├── products/
│   │   ├── base.py              Product protocol, ProductSource metadata
│   │   ├── avalanche_forecast.py   Phase 1
│   │   ├── mountain_weather.py     Phase 2 stub, implemented then
│   │   ├── observations.py         (stub, future)
│   │   └── route_guidance.py       (stub, proves plug-in pattern)
│   ├── fetchers/
│   │   └── nac_api.py           api.avalanche.org client with NWAC filter
│   ├── schema.py                DailyContext, LLMOutput, shared types
│   ├── zones.py                 Zone enums and cross-product mappings
│   ├── summarize.py             LLM call, input is DailyContext
│   ├── render.py                Markdown template from DailyContext + LLMOutput
│   ├── publish.py               Push to site repo via GitHub API
│   ├── prompts/
│   │   └── summarize_v1.md      Versioned prompt
│   └── pipelines/
│       └── daily_post.py        Orchestrator
├── evals/
│   ├── fixtures/                Real forecasts + my ground-truth summaries
│   ├── deterministic.py
│   ├── llm_judge.py
│   └── report.py
├── data/
│   └── raw/YYYY-MM-DD/          Archived API responses
├── docs/
│   └── api_exploration.md       Phase 0 recon output
├── tests/
└── .github/workflows/
    └── daily.yml                Cron at 08:30 PT
```

## Site Repo (separate, Astro on Cloudflare Pages)

Minimal responsibilities. Publishing is a git commit to this repo.

```
site/
├── src/
│   ├── content/
│   │   └── posts/               Markdown files, one per zone per day
│   ├── pages/
│   └── layouts/
├── astro.config.mjs
└── package.json
```

Cloudflare Pages auto-deploys on push to `main`. The automation repo's publish step uses the GitHub API with a fine-grained PAT scoped to the site repo's `src/content/posts/` directory.

## Commands

- `uv run python -m src.pipelines.daily_post --zone SNOQUALMIE --dry-run` : run without publishing
- `uv run python -m src.pipelines.daily_post --zone SNOQUALMIE` : full run
- `uv run pytest tests/` : unit tests
- `uv run pytest evals/ -m eval` : eval suite
- `uv run python -m evals.report --date YYYY-MM-DD` : side-by-side for manual review
- `uv run ruff check . && uv run ruff format .` : lint and format

## Working Conventions

- No em-dashes anywhere. Titles, body, code comments, git messages, prompts, generated content.
- Avoid AI-speak in generated content. Banned: "delve", "tapestry", "navigate" (as metaphor), "crucial", "it's worth noting", "in conclusion", "leverage" (as verb).
- Prompts live in `src/prompts/` as `.md` files. Versioned. Never inline in Python.
- Every LLM call specifies a JSON output schema.
- No `datetime.now()` or `time.time()` in business logic. Inject a clock.
- Log every raw API response to `data/raw/YYYY-MM-DD/`. Never overwrite.
- Type hints required on public functions. Internal helpers exempt.
- Product fetchers include a proper User-Agent with contact email per NAC API guidance.
- Secrets live in GitHub Actions secrets. Never committed, never in the hosting provider.

## Testing and Eval Philosophy

- Unit tests cover deterministic code: parsing, schema validation, freshness, zone mapping, rendering, publish idempotency.
- The eval suite is separate and can be slow. Runs against a fixture set of real forecasts and my own ground-truth summaries.
- Three layers:
  1. **Faithfulness (deterministic):** danger rating verbatim, all problem types present, forecaster prose unmodified, no numbers in LLM output absent from source, every LLM claim has a product citation.
  2. **Hallucination (LLM judge):** "list every claim in this summary not supported by any product in this DailyContext." Judge is Haiku 4.5 for cost.
  3. **Alignment (LLM judge + my review):** rate emphasis, specificity, tone against my reference summary on a 1-5 scale.
- Before changing a prompt, run evals. After, run evals. Commit the delta.

## Things Claude Code Should Not Do

- Do not paraphrase, reword, or generate danger ratings, problem types, elevation bands, or forecaster prose in the LLM layer.
- Do not summarize narrative fields (bottom line, detailed discussion, mountain weather when added). Render verbatim.
- Do not silently catch exceptions in fetch or validation code. Surface them.
- Do not publish without running the eval suite against the current prompt at least once.
- Do not add dependencies without asking. No LangChain, Pydantic AI, or framework that hides primitives.
- Do not implement mountain weather, observations, or route guidance in Phase 1. Stubs only.
- Do not assume 1:1 zone mapping between products.
- Do not write prose-heavy docstrings. One line usually suffices.
- Do not use em-dashes.

## Open Questions

- Exact NWAC avalanche forecast `product_type` string and response shape. Confirm in Phase 0.
- Exact NWAC mountain weather product availability on the public API. Confirm in Phase 0 even though implementation waits until Phase 2.
- NWAC zone list for Phase 1. Default: Snoqualmie Pass, Stevens Pass, Crystal/Mt Rainier, Mt Baker, Mt Hood. Confirm before Phase 1.
- Subdomain name for the site, e.g., `snow.yourdomain.com`.
