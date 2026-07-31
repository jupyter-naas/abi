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
| `scripts/` | demo-data generators, mirrored on the frontend sidebar sections |

`scripts/` mirrors `app.sections` in `config.yaml` — one folder per section,
one file per page (snake_case). Infra scripts (`push_to_r2.py`) stay at the
scripts root:

```
scripts/
├── performance/          # Income Statement, Balance Sheet, Cash Flow, Ratios
│   ├── balance_sheet.py
│   ├── cash_flow.py
│   └── financial_ratios.py
├── pilotage/             # Budget, Forecast, Scenario Analysis, Cost Centers
│   ├── forecast.py
│   ├── scenario_analysis.py
│   └── cost_centers.py
├── treasury/             # Cash Position, Cash Forecast, Financing
│   ├── cash_position.py
│   ├── cash_forecast.py
│   └── financing.py
├── operations/           # Customers, Suppliers, Expenses, Procurement
│   ├── customer_invoices.py
│   ├── supplier_invoices.py
│   ├── expenses.py
│   └── procurement.py
├── comptabilite/         # GL, Journals, Fixed Assets, Financial Close
│   ├── general_ledger.py
│   ├── journal_entries.py
│   ├── fixed_assets.py
│   └── financial_close.py
├── administration/
│   └── settings.py
└── push_to_r2.py
```

Pages without a generator yet (`pnl` / Income Statement, `pnl-budget`,
`pnl-adjustments`, `dashboard`) still use committed JSON under `web/data`.

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
   - Write a **generator** under `scripts/<section_id>/<page>.py` (plain
     stdlib, no ABI runtime — mirrors the sidebar section) and add it to the
     `demo-data` Makefile target. Do not hand-edit large JSON.
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

## Checklist — new ADMINISTRATION screen

Administration is a **different animal** from the finance pages: no `PageId`, no
config.yaml entry, no manifest, no scenario picker. Its screens are
configuration, live at absolute `/admin/*` routes, and are admin-only.

1. **`web/components/layout/AdminNav.tsx`** — the single source of truth. Add
   the id to the `AdminSection` union and an item to the right group in
   `ADMIN_NAV_GROUPS`. Title, sidebar entry and analytics key all follow; a new
   group also needs an icon in `SidebarGroupIcons.tsx`.

2. **Data** — `web/data/globals/admin/<name>.json`, shape
   `{schema_version, data_version, records:[…]}`. **Global, not per-entity**: it
   describes the instance, not a perimeter. Generated by
   `scripts/administration/settings.py`; add the name to `AdminSettingsName` in
   `web/lib/admin/settings.ts`.

3. **`web/app/admin/<route>/page.tsx`** — a server component:
   `requireAdmin()` → `readAdminSettings('<name>')` → `<AdminLayout active="…">`
   wrapping `<AdminSettingsPage …>`. `countBy` / `sumBy` / `distinctBy` from
   `lib/admin/settings.ts` cover the KPI arithmetic.

   `AdminSettingsPage` props cross the server/client boundary, so **columns must
   stay plain objects** — no `renderCell` / `renderValue` functions. Ask for
   badges with `statusColumns={['status']}` instead.

4. Screens needing real interaction (Entities, Users, Theme) are hand-written
   components under `components/admin/` instead — `AdminSettingsPage` is for
   read-only configuration views.

Verify with the same four steps below, hitting `/admin/<route>` instead of
`/demo/<page-id>` (no `?scenario=`, no redirect to check).

## Demo data

The template is **source-agnostic** — it ships no upstream finance system.
Fabricated demo data is expected, but it must be **internally consistent**: a
balance sheet must balance, a cash flow must reconcile to the cash line it
claims to explain.

The generators form a chain, each reading the previous one's output:

```
performance/balance_sheet.py
  ├─ treasury/cash_position.py
  ├─ treasury/financing.py
  ├─ comptabilite/fixed_assets.py
  └─ performance/cash_flow.py
       ├─ performance/financial_ratios.py
       ├─ pilotage/cost_centers.py
       ├─ operations/expenses.py
       ├─ operations/procurement.py
       ├─ comptabilite/general_ledger.py
       │    ├─ comptabilite/journal_entries.py
       │    └─ comptabilite/financial_close.py
       ├─ operations/customer_invoices.py     (also reads the balance sheet)
       ├─ operations/supplier_invoices.py        (also reads the balance sheet)
       └─ pilotage/forecast.py
            ├─ pilotage/scenario_analysis.py
            └─ treasury/cash_forecast.py
```

`administration/settings.py` runs last, off the ledger, the cost centers and the
bank accounts. Run the whole chain with `make demo-data` (order matters). All are seeded so
re-running is stable — a regeneration should change nothing but `data_version`.

- **`performance/balance_sheet.py`** — 48 monthly period-end snapshots
  (2023-01 → 2026-12). Reserves is the balancing plug, so Assets == Equity +
  Liabilities exactly.
- **`performance/cash_flow.py`** — derives an indirect-method statement from the
  balance-sheet deltas. Closing cash equals the BS "Cash & equivalents" line for
  every month, and opening + operating + investing + financing == closing
  exactly (operating is the residual; "Other operating items" is the plug).
  Also publishes a synthesized monthly P&L as `activity: "memo"` records
  (Revenue, Gross profit, EBITDA) plus the opening/closing cash anchors —
  the BS's accumulating "Net income for the year" line is far too noisy to
  difference month-over-month, which is why the P&L is synthesized here. **Every
  downstream generator reads that memo P&L**, which is what keeps the pages
  agreeing with each other.
- **`performance/financial_ratios.py`** — reads the BS for stock-based ratios and
  the cash flow's memo P&L for flow-based ones. Emits `benchmark`, `target` and
  `higher_is_better` per ratio.
- **`pilotage/forecast.py`** — splits the timeline at `ACTUALS_THROUGH`: closed
  months carry both an actual and the forecast that was standing at the time
  (which is what makes Forecast Accuracy real rather than invented), later
  months carry a forecast with a confidence band that widens with the horizon.
  Every month also carries the year's budget.
- **`pilotage/scenario_analysis.py`** — the base case **is** the forecast, read
  back and perturbed through named drivers, so Base on that page equals the
  headline on the Forecast page. Four record kinds share one dataset behind a
  `kind` discriminator (scenario / driver / sensitivity / assumption).
- **`pilotage/cost_centers.py`** — allocates the cash flow's cost base
  (revenue − EBITDA) across departments by fixed weights and attributes revenue
  to the revenue-generating ones. Margin contribution is attributed revenue
  minus own cost, so it reconciles to EBITDA.
- **`treasury/cash_position.py`** — decides only *where* the balance sheet's
  cash line sits, splitting it across bank accounts by bank, country and
  currency, so the accounts always sum back to it. Emits a `memo` account
  carrying short-term debt for the Net Cash KPI.
- **`treasury/cash_forecast.py`** — cuts each month of the forecast into four
  weeks whose movements sum to that month's change in cash, and re-anchors the
  base case on the monthly figure so the weekly walk never drifts from the
  Forecast page. A month can close comfortably while the balance dips inside
  it, which is the whole reason the page is weekly.
- **`treasury/financing.py`** — decides only *who lent* the balance sheet's
  borrowings and on what terms, so the facilities sum back to it. Emits a
  `memo` facility carrying total assets for the Debt Ratio KPI.
- **`operations/customer_invoices.py`** — decides only *who owes* the balance sheet's
  Trade receivables line and how late they are, so the open invoices sum back
  to it. Invoiced comes from the memo P&L revenue and collections fall out of
  `closing AR = opening AR + invoiced − collected`, so the Collection Rate is
  derived rather than drawn. `memo` records carry DSO on a trailing three-month
  revenue window.
- **`operations/supplier_invoices.py`** — the mirror image against Trade payables, with
  purchases taken from the cost base (revenue − EBITDA) and payments falling
  out of the same identity. Bills carry a `due_week` so the payment calendar
  needs no date arithmetic in the UI.
- **`operations/expenses.py`** — carves the **controllable overhead** slice
  (`OVERHEAD_SHARE`) out of the cost base and attributes every euro to a
  category, a department and a vendor. Departments are the Cost Centers roster,
  so the two pages name the same organization. A `memo` record carries the
  prior month's total, which is what makes Expense Growth defined on a
  single-month window.
- **`comptabilite/fixed_assets.py`** — decides only *what* the balance sheet's
  Intangible assets and Property, plant & equipment lines are made of. The
  register is built in relative units, then each class is scaled by
  `balance-sheet net ÷ register net` for that month; gross, accumulated
  depreciation and net are scaled by the same factor, so `net = gross − accum`
  survives and the class total lands on the balance sheet to the cent.
- **`comptabilite/general_ledger.py`** — turns the memo P&L into the double-entry
  record that would have produced it: sales, purchase, payroll, bank and
  miscellaneous journals, posted line by line. Every entry balances, the sales
  journal's income accounts sum back to memo revenue and the purchase plus
  payroll journals sum back to the cost base. `CLOSED_THROUGH` is the last
  locked month — anything after it is an open period. Manual entries
  (`source: "manual"`) are what the two pages downstream read.
- **`comptabilite/journal_entries.py`** — invents nothing: it reads the ledger back,
  keeps the manual lines, and folds each entry into one row carrying the review
  workflow (type, preparer, validator, late against the close deadline). Manual
  Entries therefore matches the General Ledger page by construction.
- **`comptabilite/financial_close.py`** — lays the monthly close checklist over the
  ledger's periods. Locked months ran in full, the first open month is cut at
  `PROGRESS_DAY`, later months carry the plan only. Tasks are planned in
  **business days after the period end**, which is how a close is actually run
  and what makes months comparable however the weekends fall.
- **`operations/procurement.py`** — carves the PO-covered slice (`PO_SHARE`) out
  of the cost base into an order book. Each order stores the **date every
  pipeline milestone is reached**, never a stage: the stage is derived in the
  model against the window's closing month, because an order is in flight on
  its own month and invoiced on a full year. Baking a stage in would zero out
  Open Orders and Commitments on every past month.

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
| `balance-sheet` | `performance/balance_sheet.py` | `lib/balanceSheet/model.ts` | `dashboard/balance-sheet/` | `BalanceSheetSection.tsx` |
| `cash-flow` | `performance/cash_flow.py` | `lib/cashFlow/model.ts` | shared `WaterfallChart` | `CashFlowSection.tsx` |
| `financial-ratios` | `performance/financial_ratios.py` | `lib/financialRatios/model.ts` | `dashboard/financial-ratios/` | `FinancialRatiosSection.tsx` |
| `forecast` | `pilotage/forecast.py` | `lib/forecast/model.ts` | `dashboard/forecast/` | `ForecastSection.tsx` |
| `scenario-analysis` | `pilotage/scenario_analysis.py` | `lib/scenarioAnalysis/model.ts` | `dashboard/scenario-analysis/` | `ScenarioAnalysisSection.tsx` |
| `cost-centers` | `pilotage/cost_centers.py` | `lib/costCenters/model.ts` | `dashboard/cost-centers/` | `CostCentersSection.tsx` |
| `cash-position` | `treasury/cash_position.py` | `lib/cashPosition/model.ts` | `dashboard/cash-position/` | `CashPositionSection.tsx` |
| `treasury` | `treasury/cash_forecast.py` | `lib/cashForecast/model.ts` | `dashboard/cash-forecast/` | `TreasurySection.tsx` |
| `financing` | `treasury/financing.py` | `lib/financing/model.ts` | `dashboard/financing/` | `FinancingSection.tsx` |
| `customer-invoices` | `operations/customer_invoices.py` | `lib/receivables/model.ts` | shared `AgingBarChart` | `CustomersSection.tsx` |
| `supplier-invoices` | `operations/supplier_invoices.py` | `lib/payables/model.ts` | `dashboard/payables/` | `SuppliersSection.tsx` |
| `expenses` | `operations/expenses.py` | `lib/expenses/model.ts` | shared `Treemap` | `ExpensesSection.tsx` |
| `procurement` | `operations/procurement.py` | `lib/procurement/model.ts` | `dashboard/procurement/` | `ProcurementSection.tsx` |
| `general-ledger` | `comptabilite/general_ledger.py` | `lib/generalLedger/model.ts` | `dashboard/accounting/` | `GeneralLedgerSection.tsx` |
| `journal-entries` | `comptabilite/journal_entries.py` | `lib/journalEntries/model.ts` | shared donut / bars | `JournalEntriesSection.tsx` |
| `fixed-assets` | `comptabilite/fixed_assets.py` | `lib/fixedAssets/model.ts` | shared `Treemap` | `FixedAssetsSection.tsx` |
| `financial-close` | `comptabilite/financial_close.py` | `lib/financialClose/model.ts` | `dashboard/financial-close/` | `FinancialCloseSection.tsx` |
| `/admin/*` | `administration/settings.py` | `lib/admin/settings.ts` | — | `admin/AdminSettingsPage.tsx` |

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
- **`HorizontalBarChart`** — ranked bars from `{label, amount, count}`; any
  model producing that shape can use it (see Bank Allocation).
- **`AgingBarChart`** — open balance by days past due, from
  `{key, label, amount, count, share}`. Shared by receivables and payables, so
  the two ledgers read identically.
- **`Treemap`** — nested squarified treemap over
  `{key, label, value, leaves[]}`. `cost-centers/Treemap` is a thin adapter
  mapping the cost-center shape onto it; do the same rather than cloning the
  layout.
- **`CompositionDonut`** / **`AccountBarChart`** — both default to EUR but take
  `formatValue` / `valueStyle` respectively, so a donut can slice counts
  (Approval Status, Task Status) and a ranked bar can plot them (Issue
  Distribution) without a second component.
- **`KpiCard`** — optional `displayValue` renders text instead of the number,
  for metrics that are genuinely *undefined* rather than zero. A runway with no
  burn shows `∞`; showing `0` would read as the worst possible value.

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
