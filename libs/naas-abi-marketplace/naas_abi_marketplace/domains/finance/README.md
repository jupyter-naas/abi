# S8 — finance

## The question this bucket answers

> *Where does the money go, and what is it worth?*

In the staff system, S8 owns finance policy, resource management and contracts. In a civilian
organization it covers accounting, treasury, controlling, FP&A and contract administration.

Finance is defined by the **ledger**: if the module's subject is a recorded financial fact — a
transaction, a balance, a budget line, a contractual obligation — it belongs here.

## What's here

```
finance/
├── __init__.py                         # ABIModule, datastore_path = "finance"
├── agents/
│   ├── AccountantAgent.py
│   ├── FinancialControllerAgent.py
│   └── TreasurerAgent.py
└── apps/
    └── financial_cockpit/              # nested loadable module
```

| Module | Component | What it delivers |
|---|---|---|
| `AccountantAgent` | `agents/` | Financial accounting, bookkeeping, tax preparation, audit support |
| `FinancialControllerAgent` | `agents/` | Planning, budgeting, cost analysis, controls, reporting |
| `TreasurerAgent` | `agents/` | Cash management, financial risk, investment strategy |
| [`financial_cockpit/`](apps/financial_cockpit/) | `apps/` | P&L, treasury and performance dashboard — app-only, no agent |

`financial_cockpit` is the reference example of a single-component module: it contains only a web
app, so it files under `apps/` without argument.

## What belongs here

- Bookkeeping, journals, period close, statutory accounting
- Treasury: cash, liquidity, FX, investment
- Controlling, budgeting, variance analysis, FP&A
- Invoicing, revenue recognition, collections
- Contract administration and financial compliance
- Financial reporting and dashboards

## Boundary tests

**vs [`operations/`](../operations/) (S3) — the deal or the ledger.**
Closing the contract is operations. Invoicing it, recognizing the revenue and chasing payment is
finance. The handover point is the moment the commercial commitment becomes a recorded financial
obligation.

**vs [`logistics/`](../logistics/) (S4) — the goods or the money.**
Choosing a supplier, raising the purchase order and tracking the asset is logistics. Paying the
invoice, capitalizing the asset and depreciating it is finance. Procurement modules usually
straddle both — file by output: a purchase decision → logistics, a ledger entry → finance.

**vs [`plans/`](../plans/) (S5) — the money or the plan.**
Deciding *what* to do next year is plans; costing and budgeting it is finance. A forecast built to
choose a course of action is plans; a forecast built to manage cash is finance.

**vs [`personnel/`](../personnel/) (S1) — payroll.**
Who someone is, their employment status and their records is personnel. What they are paid, and how
that lands in the ledger, is finance.

## Filing a module here

`finance/<component>/<module>/`, where `<component>` is the module's dominant deliverable.
Single-agent modules may sit flat as `agents/<Name>Agent.py`. See [`../AGENT.md`](../AGENT.md) for
the full filing rules and [`../README.md`](../README.md) for the framework.
