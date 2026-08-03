# Financial Cockpit

A finance and steering dashboard template — a Next.js 15 app that reads
pre-built JSON datasets and renders them as a navigable set of finance pages:
income statement, balance sheet, cash flow, financial ratios, cash forecast,
receivables and payables.

It is **source-agnostic**. The app ships no connector to an accounting system:
it reads a small, well-defined datastore layout, and whatever fills that
datastore (an ABI workflow, an export, a script) is up to you. The bundled
`_demo` entity is fabricated demo data so the app runs the moment you clone it.

## Quick start

```bash
cd web
npm install
npm run kickstart     # creates config/config.yaml + .env (random SESSION_SECRET)
npm run dev           # http://localhost:3000
```

Sign in with the root password — `demo` by default, printed by `kickstart` and
stored as `ROOT_PASSWORD` in `web/.env`.

From the app root, `make dev` does the install + dev-server step for you.

## Make targets

| Target | What |
|---|---|
| `make kickstart` | generate `config.yaml` + `.env`, print next steps |
| `make dev` | install deps (first run) + dev server on :3000 |
| `make build` | production build |
| `make lint` / `make typecheck` | ESLint / `tsc --noEmit` |
| `make demo-data` | regenerate the fabricated demo datasets in `web/data` |
| `make preview` | Cloudflare Workers preview (OpenNext) |
| `make push-r2-dry` / `make push-r2` | seed an R2 bucket from `web/data` |

## Layout

```
apps/financial-cockpit
├── Makefile
├── AGENT.md                  # playbook for coding agents — read before adding a page
├── scripts/                  # demo-data generators, mirrored on sidebar sections
│   ├── performance/          # balance_sheet, cash_flow, financial_ratios
│   ├── pilotage/             # forecast, scenario_analysis, cost_centers
│   ├── treasury/             # cash_position, cash_forecast, financing
│   ├── operations/           # customer_invoices, supplier_invoices, …
│   ├── comptabilite/         # general_ledger, journal_entries, …
│   ├── administration/       # settings
│   └── push_to_r2.py
└── web/                      # the Next.js app
    ├── app/                  # routes (App Router)
    ├── components/
    │   ├── dashboard/        # kpi/, viz/, table/ + pages nested by section
    │   └── layout/           # sidebar rail, page nav, page title
    ├── config/               # config.example.yaml (committed) → config.yaml (generated)
    ├── data/                 # bundled demo datastore, mirrors the R2 layout
    └── lib/                  # models nested by section + shared auth/data/theme
```

## Concepts

### Entities, sites, companies

An **entity** is a perimeter — an organization or a consolidation of several.
A perimeter may break down further into **sites** or **companies**, which the
routes expose as `/[entitySlug]`, `/[entitySlug]/sites/[siteSlug]/[pageId]` and
`/[entitySlug]/companies/[companySlug]/[pageId]`. Records are filtered to the
selected perimeter server-side.

The template bundles a single entity, `_demo`, served at `/demo`.

### Pages and sections

A page is a `PageId` string declared in `config.yaml` and rendered by a section
component resolved from `components/dashboard/registry.ts`. Pages are
grouped into sidebar **sections** (Dashboard, Performance, Planning, Cash,
Operations, Accounting) — plus Administration, which follows its own rules (see
below).

Each page carries an optional **banner** — by convention an info banner holding
the page's headline *Question*:

| Section | Page | Question |
|---|---|---|
| Dashboard | Dashboard | Is the company healthy today? |
| Performance | Income Statement | Where does profit come from? |
| Performance | Balance Sheet | How strong is our financial position? |
| Performance | Cash Flow | Where is cash generated and spent? |
| Performance | Financial Ratios | Is the company financially healthy? |
| Planning | Forecast | Where will we finish the year? |
| Planning | Scenario Analysis | What happens if assumptions change? |
| Planning | Cost Centers | Which departments drive performance? |
| Cash | Cash Position | How much cash is available today? |
| Cash | Cash Forecast | Will we have enough cash? |
| Cash | Financing | How is the company financed? |
| Operations | Customers | Are customers paying on time? |
| Operations | Suppliers | What do we owe suppliers? |
| Operations | Expenses | Where is money being spent? |
| Operations | Procurement | Are purchases under control? |
| Accounting | General Ledger | What happened in the accounting records? |
| Accounting | Journal Entries | Which accounting adjustments were made? |
| Accounting | Fixed Assets | How are our assets evolving? |
| Accounting | Financial Close | Are we ready to close the period? |

### Administration

Administration is the one section that is **not** config-driven. Its screens are
configuration rather than finance, so they live at absolute `/admin/*` routes,
are visible to admins only, and are declared in
`components/layout/AdminNav.tsx` — the single source the sidebar panel, the page
titles and the analytics keys all read.

| Group | Screens |
|---|---|
| Organizations | Entities · Business Units · Cost Centers |
| Users & Roles | Users · Roles · Permissions |
| Accounting Settings | Chart of Accounts · Fiscal Years · Accounting Periods · Journals |
| Workflows | Approval Flows · Notifications · Validation Rules |
| Integrations | ERP · Banking · API · Imports / Exports |
| Audit Logs | User Activity · System Logs · Synchronization History |
| Appearance | Theme |

Entities, Users, User Activity and Theme are interactive (perimeter and user
management, the usage log, the theme editor). The remaining screens are
read-only views over `globals/admin/*.json`, rendered through the shared
`components/admin/AdminSettingsPage.tsx` shell. Those datasets are written by
`scripts/administration/settings.py`, which derives the accounting ones from the
general ledger and the organization ones from the cost-center roster — so the
settings pages and the finance pages describe the same instance.

### Scenarios

Datasets declare a `scenarios` array of year (`date_year`) and month
(`date_month`) options, which populates the period picker automatically. A page
opened without `?scenario=` redirects to the current calendar year. The server
filters records to the selection before the section sees them.

### The datastore

`web/data` mirrors the production R2 layout:

```
data/entities/<entity_id>/
  manifest.json          # pageId → [dataset paths], plus the entity dataset
  <feature>/<file>.json  # { schema_version, data_version, entity_id, scenarios, records }
```

The dataset key a section receives is the file basename without `.json`, so
`cash_flow/cash_flow.json` arrives as `datasets.cash_flow`.

Locally the app reads `DATA_LOCAL_ROOT` (`./data`). With `ENV=prod` on Workers
it reads the R2 bucket bound as `DATASETS`, under the `R2_DATA_PREFIX` prefix.

### Demo data

The bundled datasets are fabricated but internally consistent — the balance
sheet balances, the cash flow reconciles to the balance sheet's cash line
exactly, the bank accounts and the loan book sum back to that same balance
sheet, the scenario page's base case equals the forecast, the cost centers
reconcile to EBITDA, and the customer and supplier ledgers sum back to the
balance sheet's trade receivables and payables lines. Thirteen seeded
generators form a chain, each reading the previous one's output:

```bash
make demo-data   # order matters — see AGENT.md for the dependency graph
```

See [AGENT.md](AGENT.md#demo-data) for what each one derives and why.

## Configuration

`web/config/config.example.yaml` is the committed source of truth; `kickstart`
copies it to `config/config.yaml`, which is gitignored. **Edit both** when
adding pages or sections, or your change will not survive a fresh checkout.

It declares:

- `brand` — product name, tagline, logo and favicon paths (the image bytes are
  synced from `web/assets` by `npm run sync:brand`);
- `app.default_page` / `app.default_entity` — where users land after sign-in;
- `app.pages` — page ids, labels, `enabled`, banners;
- `app.sections` — sidebar grouping and order;
- `users` — the single protected `owner` identity.

## Authentication and roles

The template uses a **shared root password**, not e-mail or magic links:
entering `ROOT_PASSWORD` on `/login` grants a full-access `owner` session
carried in a JWT cookie signed with `SESSION_SECRET` (both in `web/.env`;
the app returns 500 if `SESSION_SECRET` is unset, and sign-in is disabled
entirely if `ROOT_PASSWORD` is unset).

The `owner` is the protected top role — defined in `config.yaml`, never
editable from the app. Everyone else is managed at `/admin/users` and stored in
the datastore: additional `admin`s (also full access), and viewers scoped to
specific entities and pages.

Other admin routes: `/admin/theme` (theme tokens and typography) and
`/admin/analytics` (page views).

## Deployment

The app deploys to Cloudflare Workers via OpenNext.

```bash
npm run preview                       # local Workers preview
wrangler r2 bucket create app-financial-cockpit
python scripts/push_to_r2.py          # seed the bucket from ./web/data
wrangler secret put SESSION_SECRET
wrangler secret put ROOT_PASSWORD
wrangler secret put ENV               # "prod" — selects the R2 data path
```

Bindings and vars live in `web/wrangler.toml`.

## Adding a page

See **[AGENT.md](AGENT.md)** — it lists every integration point (types, both
config files, dataset + manifest, model, section, registry, and the sidebar
wiring a new section needs), plus the four verification steps to run before
calling it done.
