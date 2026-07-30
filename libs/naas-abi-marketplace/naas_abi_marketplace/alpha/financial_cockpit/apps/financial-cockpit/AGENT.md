# AGENT.md — working on Financial Cockpit

Playbook for coding agents. Read this before adding or changing a page. The
most common task is **adding a page**; the checklists below list every
integration point, because a missed one fails silently (a page with no
sidebar entry, or a dataset key that resolves to `undefined`).

## Layout

| Path | What |
|---|---|
| `apps/financial-cockpit` | app root — `Makefile`, `scripts/` |
| `apps/financial-cockpit/web` | the Next.js app (all TS/React below is under here) |
| `web/data` | bundled demo datastore, mirrors the R2 layout |
| `scripts/` | standalone stdlib demo-data generators (no ABI runtime) |

Single bundled entity: `_demo` (`url_slug` = `demo`). **One dev server at a
time** — concurrent `next` processes corrupt `.next`.

## How a page renders

1. A page is a `PageId` string (e.g. `cash-flow`).
2. `web/config/config.yaml` declares it (label, `enabled`, optional banner) and
   places it in a sidebar **section**.
3. Each entity's `web/data/entities/<id>/manifest.json` maps
   `pageId → [dataset paths]`. The **dataset key** the section receives is the
   file basename without `.json` — `cash_flow/cash_flow.json` arrives as
   `datasets.cash_flow`.
4. The dynamic route `app/[entitySlug]/[pageId]` loads config + datasets,
   applies the site / company / **scenario** record filters, and resolves the
   component from `components/dashboard/sections/registry.ts`.
5. The section is a `'use client'` component taking `SectionProps`
   (`{ user, entity, site, company, datasets }`).

### Two config files, one of them generated

`config/config.yaml` is **gitignored** — `npm run kickstart` (and the
`predev`/`prebuild` hooks) generate it from `config/config.example.yaml`, which
is the committed source of truth.

> **Edit both.** A page added only to `config.yaml` works on your machine and
> vanishes on a fresh checkout.

## Checklist — new PAGE (reusing an existing section)

1. **`web/lib/types.ts`** — add the id to BOTH the `PageId` union and the
   `PAGE_IDS` array (keep them in sync; order is cosmetic).

2. **`web/config/config.yaml` AND `web/config/config.example.yaml`**
   - under `app.pages:`:
     ```yaml
     - page_id: "<page-id>"
       label: "<Sidebar / title label>"
       enabled: true
       banner:                       # OPTIONAL — this is the page's "Question"
         type: "info"                # info (blue) | warning (amber)
         text: "<the guiding question>"
         enabled: true
     ```
     Convention: the info banner is the page's headline **Question**
     (Cash Flow → "Where is cash generated and spent?").
   - under `app.sections:`, add the id to an existing section's `page_ids`.

3. **Data + manifest**
   - Write `web/data/entities/_demo/<feature>/<file>.json`:
     ```json
     { "schema_version": "1.0", "data_version": "YYYY-MM-DD HH:MM",
       "entity_id": "_demo",
       "scenarios": [ {"id":"2026","label":"2026","split":"date_year"},
                      {"id":"2026-07","label":"July 2026","split":"date_month"} ],
       "records": [ { "...": "...", "scenario": "2026-07", "scenario_year": "2026" } ] }
     ```
   - Add `"<page-id>": ["<feature>/<file>.json"]` under `datasets.pages` in
     `web/data/entities/_demo/manifest.json`.
   - Write a **generator** in `scripts/` (plain stdlib, no ABI runtime) and add
     it to the `demo-data` Makefile target. Do not hand-edit large JSON.
   - `web/data` **is committed** (except the runtime-written paths in
     `web/.gitignore`), so regenerating means committing the regenerated JSON.

   Scenario mechanics — free if you follow the shape above:
   - the `scenarios` array is auto-detected (`lib/data/scenarios.ts`); nothing
     to code for the picker;
   - a page with no `?scenario=` 307-redirects to the current calendar year's
     `date_year` scenario if present;
   - the server pre-filters records: `date_year` keeps matching
     `scenario_year`, `date_month` keeps matching `scenario`. **Your section
     receives already-filtered records — don't re-filter.**

4. **`web/lib/<feature>/model.ts`** — pure, framework-free: an
   `xRecords(dataset)` reader/validator and a `buildX(records)` returning
   everything the UI needs (KPIs, chart series, table rows).

5. **`web/components/dashboard/sections/<Name>Section.tsx`** — `'use client'`,
   `export function <Name>Section({ company, site, datasets }: SectionProps)`,
   `useMemo(() => buildX(xRecords(datasets.<key>)), [datasets.<key>])`.
   - Compose from `PageTitle`, `KpiCard`, `DataTable`, and the existing charts
     (`TrendChart`, `CompositionDonut`, `AccountBarChart`,
     `HorizontalBarChart`, `CashProjectionChart`); new ones go under
     `components/dashboard/<feature>/`.
   - **Handle the empty-records case.**
   - Currency: `Intl.NumberFormat('fr-FR', …)` EUR. KPI cards use `valueStyle`
     (ThemeNumber — no `notation` prop).
   - Theme tokens only: `var(--text)`, `--text-muted`, `--border`, `--surface`,
     `--secondary`, `--primary`, `--accent`,
     `--recovery-{success,warning,orange,danger}`.

6. **`web/components/dashboard/sections/registry.ts`** — add
   `'<page-id>': <Name>Section`. The record is typed
   `Record<Exclude<PageId,'theme'>, …>`, so a missing entry fails typecheck.

## ADDITIONAL checklist — new SECTION

7. **Both config files** — new block under `app.sections:` (order = sidebar
   order; keep `administration` last):
   ```yaml
   - section_id: "<section-id>"
     label: "<Sidebar group label>"
     page_ids:
       - "<page-id>"
   ```
   Add `direct: true` for a section that links straight to a single page
   instead of opening the secondary panel (see `dashboard`).

8. **`web/components/layout/SidebarRail.tsx`** — a new `section_id` falls back
   to `GenericPageIcon` with no hover text unless you register:
   - `GROUP_ICONS[<section-id>]` (multi-page) or `PAGE_ICONS[<page-id>]`
     (single-page/flat section), and
   - `SECTION_DESCRIPTIONS[<section-id>]`.

9. **`web/components/layout/SidebarGroupIcons.tsx`** — reuse an existing icon
   where possible; otherwise add
   `export function <Name>Icon({ className }: IconProps)` (Heroicons-style
   stroke SVG, `strokeWidth={1.5}`, `currentColor`) and import it in
   SidebarRail.

## Demo data

The template is **source-agnostic** — it ships no upstream finance system.
Fabricated demo data is expected, but it must be **internally consistent**: a
balance sheet must balance, a cash flow must reconcile to the cash line it
claims to explain.

The generators form a chain, each reading the previous one's output:

```
generate_balance_sheet.py
  └─ generate_cash_flow.py
       ├─ generate_financial_ratios.py
       ├─ generate_cost_centers.py
       └─ generate_forecast.py
            └─ generate_scenario_analysis.py
```

Run the whole chain with `make demo-data` (order matters). All are seeded so
re-running is stable — a regeneration should change nothing but `data_version`.

- **`generate_balance_sheet.py`** — 48 monthly period-end snapshots
  (2023-01 → 2026-12). Reserves is the balancing plug, so Assets == Equity +
  Liabilities exactly.
- **`generate_cash_flow.py`** — derives an indirect-method statement from the
  balance-sheet deltas. Closing cash equals the BS "Cash & equivalents" line for
  every month, and opening + operating + investing + financing == closing
  exactly (operating is the residual; "Other operating items" is the plug).
  Also publishes a synthesized monthly P&L as `activity: "memo"` records
  (Revenue, Gross profit, EBITDA) plus the opening/closing cash anchors —
  the BS's accumulating "Net income for the year" line is far too noisy to
  difference month-over-month, which is why the P&L is synthesized here. **Every
  downstream generator reads that memo P&L**, which is what keeps the pages
  agreeing with each other.
- **`generate_financial_ratios.py`** — reads the BS for stock-based ratios and
  the cash flow's memo P&L for flow-based ones. Emits `benchmark`, `target` and
  `higher_is_better` per ratio.
- **`generate_forecast.py`** — splits the timeline at `ACTUALS_THROUGH`: closed
  months carry both an actual and the forecast that was standing at the time
  (which is what makes Forecast Accuracy real rather than invented), later
  months carry a forecast with a confidence band that widens with the horizon.
  Every month also carries the year's budget.
- **`generate_scenario_analysis.py`** — the base case **is** the forecast, read
  back and perturbed through named drivers, so Base on that page equals the
  headline on the Forecast page. Four record kinds share one dataset behind a
  `kind` discriminator (scenario / driver / sensitivity / assumption).
- **`generate_cost_centers.py`** — allocates the cash flow's cost base
  (revenue − EBITDA) across departments by fixed weights and attributes revenue
  to the revenue-generating ones. Margin contribution is attributed revenue
  minus own cost, so it reconciles to EBITDA.

### As-of vs aggregate

Two shapes recur, and picking the wrong one silently produces nonsense:

- **Aggregate** over the window — flows (revenue, spend, cash movements). Sum
  them.
- **As-of** the latest period in the window — stocks (cash balance, headcount,
  balance-sheet lines) and forward-looking analyses that are re-stated every
  month (scenario analysis). Read the last period; never sum.

A dataset can mix both: the cash flow sums its movements but reads opening and
closing cash from the first and last month's memo records.

## Verify — do all four, report results

From `apps/financial-cockpit/web`:

1. `npx tsc --noEmit` → clean.
2. `npx next lint` → no new warnings **for your files** (four pre-existing
   unused-var warnings are expected).
3. Kill stray dev servers first, then a clean build:
   ```bash
   ps aux | grep -E "[n]ext dev|[n]ext-server" | awk '{print $2}' | xargs -r kill -9
   rm -rf .next && npx next build
   ```
   → succeeds. One pre-existing warning (`jose` / `CompressionStream` not
   supported in the Edge Runtime, via `lib/auth/jwt.ts`) is expected.
4. Smoke test on **one** dev server:
   ```bash
   npx next dev -p 3412 &            # wait for "Ready"
   curl -s -c /tmp/c.txt -X POST localhost:3412/api/auth/password \
     -H 'Content-Type: application/json' -d '{"password":"demo"}'   # ROOT_PASSWORD=demo
   curl -s -b /tmp/c.txt "localhost:3412/demo/<page-id>?scenario=2026" \
     -o /tmp/p.html -w '%{http_code}\n'
   grep -c NaN /tmp/p.html          # expect 0
   curl -s -b /tmp/c.txt -o /dev/null "localhost:3412/demo/<page-id>" \
     -w '%{http_code} %{redirect_url}\n'   # expect 307 → ?scenario=<year>
   ```
   Confirm HTTP 200, title/KPIs/table render, no `NaN`, the redirect, and that
   the sidebar links to the new page. **Kill the dev server when done.**

## Reference implementation

Six worked examples. `balance-sheet` is the simplest end-to-end page; copy its
shape when in doubt.

| Page | Generator | Model | Charts | Section |
|---|---|---|---|---|
| `balance-sheet` | `generate_balance_sheet.py` | `lib/balanceSheet/model.ts` | `dashboard/balance-sheet/` | `BalanceSheetSection.tsx` |
| `cash-flow` | `generate_cash_flow.py` | `lib/cashFlow/model.ts` | shared `WaterfallChart` | `CashFlowSection.tsx` |
| `financial-ratios` | `generate_financial_ratios.py` | `lib/financialRatios/model.ts` | `dashboard/financial-ratios/` | `FinancialRatiosSection.tsx` |
| `forecast` | `generate_forecast.py` | `lib/forecast/model.ts` | `dashboard/forecast/` | `ForecastSection.tsx` |
| `scenario-analysis` | `generate_scenario_analysis.py` | `lib/scenarioAnalysis/model.ts` | `dashboard/scenario-analysis/` | `ScenarioAnalysisSection.tsx` |
| `cost-centers` | `generate_cost_centers.py` | `lib/costCenters/model.ts` | `dashboard/cost-centers/` | `CostCentersSection.tsx` |

Shared wiring: `web/lib/types.ts`, `web/config/config{,.example}.yaml`,
`web/components/dashboard/sections/registry.ts`.

### Shared charts — extend, don't clone

Generic components live directly in `components/dashboard/`; page-specific ones
in `components/dashboard/<feature>/`. Before writing a chart, check whether one
of these already does the job with a prop:

- **`WaterfallChart`** — floating-bar bridge. Models supply `start`/`end` per
  step, so the component stays presentational. Used by three pages.
- **`HeatmapGrid`** — two-axis grid with a `diverging` or `sequential` scale and
  a `goodDirection`, so overspend can read red while extra EBITDA reads green.
  Used by the sensitivity matrix and the variance heatmap.
- **`TrendChart`** — optional `formatValue` (defaults to compact EUR; pass a
  percent formatter for non-currency series).
- **`CompositionDonut`** — optional `totalLabel` for the donut hole.

A third page needing a chart that already exists twice is the signal to
generalize it into `components/dashboard/` rather than clone it again.

## Guardrails

- Work **only** inside `apps/financial-cockpit` — never `asgard-group/src`.
- One dev server at a time.
- Don't invent an upstream data source; fabricate consistent demo data instead.
- Signed figures shown against a benchmark or target should be oriented so
  positive always reads as *good*, but the accompanying wording must state the
  **literal** numeric direction — for a lower-is-better ratio like Debt Ratio,
  a good value is numerically *below* its benchmark.
