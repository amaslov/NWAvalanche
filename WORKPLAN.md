# Workplan

Each phase has a goal and acceptance criteria. Do not start phase N+1 until phase N's criteria pass.

Phase 1 ships a working end-to-end pipeline with a single product (NWAC avalanche forecast). Every subsequent product is a new file, not a refactor. Route guidance is an architectural forward-compatibility requirement, not a phase.

## Phase 0: Setup and API reconnaissance (2-3 hrs)

**Goal:** Repo skeleton, tooling, confirm which NWAC products the public API exposes and their exact shapes.

Tasks:

- `uv init`, Python 3.11, dependencies: httpx, anthropic, pydantic, pytest, ruff
- `.env` with `ANTHROPIC_API_KEY`
- Hit `GET https://api.avalanche.org/v2/public/products?avalanche_center_id=NWAC` with a proper User-Agent (contact email, product identifier)
- Enumerate every `product_type` value returned for NWAC
- Document in `docs/api_exploration.md`:
  - All product types NWAC publishes
  - Example payloads for each, saved as JSON
  - Which zones each covers, issue cadence observed
  - Exact field names for danger rating, problem types, elevation bands, narrative prose
- Confirm mountain weather availability: is it on the public API? Under what `product_type`? Is it prose or structured? Document the answer even though implementation waits until Phase 2. If not exposed, document the fallback options.

**Acceptance:** `docs/api_exploration.md` lists all NWAC product types with example payloads. Avalanche forecast shape is fully understood. Mountain weather availability is documented. Raw response dumps saved for use as Phase 1 fixtures.

## Phase 1: Deterministic backbone, avalanche forecast only (6-10 hrs)

**Goal:** Full pipeline end-to-end with zero LLM involvement, one product. Plug-in pattern proven via stubs.

Tasks:

- `src/products/base.py`: `Product` protocol with `fetch`, `validate`, `render` methods and a `ProductSource` metadata type (name, url, issued_at, attribution)
- `src/products/avalanche_forecast.py`: full implementation. Pydantic models preserve all structured fields including aspect/elevation rose and per-problem aspect/elevation data. Narrative prose rendered verbatim with attribution.
- `src/products/mountain_weather.py`: **stub only.** Raises `NotImplementedError` or returns `ProductUnavailable`. Present to prove the protocol.
- `src/products/route_guidance.py`: **stub only.** Same reason.
- `src/zones.py`: `AvalancheZone` enum populated with Phase 1 zones. `MountainWeatherZone` enum declared but empty. Mapping function declared with a stub implementation.
- `src/schema.py`: `DailyContext` composite type. Designed to carry N products, but Phase 1 only ever populates one.
- `src/fetchers/nac_api.py`: httpx client with correct User-Agent, NWAC filter, error handling
- `src/pipelines/daily_post.py`: orchestrator. For Phase 1, fetches only avalanche forecast for a given zone.
- `src/render.py`: markdown template. Sections for each product (Phase 1 renders one), placeholder for LLM summary, source links above the fold.
- Freshness check per product, STALE marker if `issued_at` > 24h
- Archive each raw response to `data/raw/YYYY-MM-DD/avalanche_{zone}.json`
- Unit tests for: schema validation, freshness logic, zone enum lookup, render output snapshot

**Acceptance:** `uv run python -m src.pipelines.daily_post --zone SNOQUALMIE --dry-run` produces a markdown file containing: current danger rating, problem types with aspect/elevation, narrative forecast prose rendered verbatim with attribution, source link, placeholder for AI summary. Zero LLM calls. Unit tests pass. Adding `mountain_weather.py` as a real implementation in Phase 2 requires no edits to existing product files or to the `DailyContext` schema.

## Phase 2: Add mountain weather as a second product (3-5 hrs)

**Goal:** Prove the plug-in pattern by adding NWAC mountain weather. Validate that nothing in Phase 1's code had to change.

Tasks:

- Implement `src/products/mountain_weather.py` against the `Product` protocol. Pydantic models for whatever shape Phase 0 found.
- Populate `MountainWeatherZone` enum. Fill in the real `AvalancheZone -> MountainWeatherZone` mapping function.
- Register mountain weather in the pipeline alongside avalanche forecast.
- Template renders both sections. Each with its own attribution and issue time.
- Archive `data/raw/YYYY-MM-DD/weather_{weather_zone}.json`.
- Unit tests for the new product and the zone mapping.

**Acceptance:** Dry-run output contains both avalanche forecast and mountain weather sections, each with its own attribution and source link. Zero edits to `avalanche_forecast.py`, `base.py`, or `schema.py` during this phase. If any of those changed, stop and fix the Phase 1 design.

## Phase 3: LLM summarization (4-6 hrs)

**Goal:** Add the AI orientation section. Synthesizes across whatever products are present in `DailyContext`.

Tasks:

- `src/prompts/summarize_v1.md`: prompt takes a DailyContext, outputs JSON with `headline` (one sentence), `orientation` (2-3 sentences framing the day), and `citations[]` (each claim maps to a product source)
- Explicit prompt rules: do not restate danger ratings, problem types, elevation bands, or forecaster prose verbatim. Those render deterministically. Job is to synthesize *why* and *so what*.
- Pydantic validates LLM output. Retry once on schema failure, then fail loud.
- Citation validation: every citation references a product present in the DailyContext. Any citation to an absent product is a hard failure.

**Acceptance:** Dry-run output includes AI headline and orientation with every factual claim citing which product supports it. Manual spot-check across 3 different forecast days shows no restated danger ratings, no unsupported claims, weather context (if present) correctly attributed.

## Phase 4: Eval harness (6-10 hrs, core learning phase)

**Goal:** Automated faithfulness and alignment checks. The AIARE background earns its keep here.

Tasks:

- Fixture collection: over two weeks of use, archive each day's API responses and write your own summary for each zone. Target 15-20 fixture days before using evals to gate prompt changes.
- `evals/deterministic.py`:
  - Danger rating string appears verbatim in rendered post
  - All problem types from API appear
  - Forecaster prose byte-equal to source (no rendering drift)
  - No numbers or percentages in LLM output that aren't in source products
  - Every LLM claim has a citation to a DailyContext product
  - Word count bounds on LLM output
- `evals/llm_judge.py`:
  - Faithfulness judge prompt: "list every claim in this summary not supported by the DailyContext JSON below"
  - Alignment judge prompt: "rate emphasis, tone, specificity against the reference summary on a 1-5 scale"
  - Judge model: Haiku 4.5
- `evals/report.py`: side-by-side of source products, your summary, LLM summary, deterministic pass/fail, judge scores. Markdown output.

**Acceptance:** `uv run pytest evals/ -m eval` runs cleanly on the fixture set. Report generates. Baseline scores documented in `docs/eval_baseline.md`. Calibration explicit: "a prompt change is a regression if faithfulness drops below X or alignment median drops below Y."

## Phase 5: Publishing to Cloudflare Pages via Astro site repo (3-5 hrs)

**Goal:** Posts land on the live subdomain automatically.

Prereqs done by you, not Claude Code:

- Subdomain chosen, DNS CNAME created (can route through Squarespace DNS for now)
- Separate site repo created (`snow-site` or similar), Astro initialized with a content collection at `src/content/posts/`
- Cloudflare Pages project connected to site repo, build command `npm run build`, publish directory `dist`
- Fine-grained GitHub PAT created, scoped to the site repo, write access to contents
- Hello-world Astro post deployed and live before writing any Python publish code

Tasks (in automation repo):

- `src/publish.py`: uses GitHub API (via `httpx` or `PyGithub`) to PUT a new file into site repo's `src/content/posts/YYYY-MM-DD-{zone}.md`
- Idempotent: if today's file already exists for this zone, update it (PUT with sha), do not create duplicate
- Frontmatter includes: date, zone, source links with issue times, danger rating, stale flag if set
- Dry-run flag preserved: writes the file locally in `out/` but does not push
- Post-publish validation: fetch the expected public URL, assert 200 and today's date in body. Retry with exponential backoff (Cloudflare Pages build takes 30-90s).

**Acceptance:** A real post lands at `https://snow.yourdomain.com/posts/YYYY-MM-DD-snoqualmie/` within 2 minutes of a full-run command, correctly formatted, source links above the summary. Running twice on the same day does not create duplicate commits.

## Phase 6: Scheduled production (1-2 hrs)

Tasks:

- GitHub Actions cron at 08:30 PT daily (NWAC issues by ~06:30 PT typically). Use `0 16 * * *` UTC with a timezone note, or the `cron` spec with explicit PT handling.
- Secrets configured: `ANTHROPIC_API_KEY`, `SITE_REPO_PAT`
- Dead-man's-switch: no post in 48h during season triggers an email alert (GitHub Actions can send mail via a simple script or a free service like Resend)
- Offseason detection: if all target zones return no active forecast, skip publishing and log "dormant" rather than failing
- Manual trigger via `workflow_dispatch` for testing

**Acceptance:** Runs unattended for one week without intervention. Alerts fire correctly when tested by simulating a stale state.

## Phase 7: Agentic extension (optional, 8-12 hrs, for learning)

**Goal:** Build a V2 using the Anthropic tool-use API directly. Compare against baseline.

Tasks:

- Tools exposed:
  - `get_current_forecast(zone)`, `get_previous_forecast(zone, days_ago)`
  - `get_current_weather(zone)`, `get_weather_history(zone, days_back)`
  - `get_observations(zone, lookback_days)` if Phase 0 confirmed availability
- Agent task: produce a richer summary that reasons across time, e.g., "the persistent slab layer from 2/18 is the same problem as yesterday but two observations this weekend showed propagation on NE aspects"
- Baseline V1 pipeline stays unchanged. V2 competes.
- Both run through the same eval suite.

**Acceptance:** Eval report compares V1 vs V2 across faithfulness, alignment, cost, latency. Reasoned call on whether V2 earns its complexity.

## Not a Phase: Route Guidance

Forward-compatible by construction. What keeps it unblocked:

- The `Product` protocol admits new products without surgery on existing ones
- Aspect, elevation, and slope data from avalanche forecasts are preserved, not flattened
- Phase 7's agent tool pattern generalizes to route lookup
- `DailyContext` composes arbitrarily many products

Do not design route-matching logic now. Do not scope it. Do not let it drift into earlier phases. Just do not block it.
