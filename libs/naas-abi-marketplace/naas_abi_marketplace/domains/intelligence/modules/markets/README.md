# markets — S2 intelligence

What is true about a market: how it divides into segments, which organizations compete in each,
how big it is and how fast it grows, and its SWOT. A loadable module next to
[`organizations/`](../organizations/) and [`people/`](../people/); competitors are the same
`abi:Organization` individuals those modules mint (`abi:Organization/<slug of the label>`).

```
markets/
├── __init__.py                      ABIModule: graph .../graph/markets, datastore intelligence/markets
├── agents/MarketsAgent.py           7 SPARQL tools + 7 registration tools
├── data/demo/CloudComputing.yaml    the curated Cloud Computing seed
├── ontologies/
│   ├── modules/MarketsOntology.ttl (+ .py)    shared vocabulary + consolidated slices
│   ├── processes/                             one slice per act, BFO 7 buckets (+ .py each)
│   │   ├── ActOfMarketSegmentationProcess.ttl
│   │   ├── ActOfCompetingProcess.ttl
│   │   ├── ActOfMarketSizingProcess.ttl
│   │   └── ActOfMarketAnalysisProcess.ttl     (SWOT)
│   └── queries/MarketSparqlQueries.ttl        7 queries
├── pipelines/                       one per act + Yahoo Finance + the seed (each with _test.py)
└── utils/
    ├── company_directory.py         CompanyDirectoryPort + YahooFinanceCompanyDirectory
    └── market_storage.py            datastore layout
```

`abi:Market` and `abi:MarketSegment` are core classes, in
`naas_abi/ontologies/modules/MarketOntology.ttl` (moved out of the domain-level
`OfferingOntology.ttl`, which now imports it). This module adds everything else.

## The model

| Act | WHO | WHEN | WHERE | WHY | HOW WE KNOW |
|---|---|---|---|---|---|
| `ActOfMarketSegmentation` | analyst | period | — | `MarketAnalystRole` | market divided, `MarketSegment`s yielded, `SegmentationCriterion`, source |
| `ActOfCompeting` | competitor (`hasCompetitor`) | period | region | `CompetitorRole` | market (`isInMarket`), `MarketShareMeasurement` (share %, rank), source |
| `ActOfMarketSizing` | analyst | reference year | region | `MarketAnalystRole` | `MarketSizeMeasurement` (value, currency, year, CAGR), source |
| `ActOfMarketAnalysis` | analyst | period | region | `MarketAnalystRole` | `MarketOpportunity` / `MarketThreat` about the market, `CompetitiveStrength` / `CompetitiveWeakness` about one competitor in it, source |

HOW IT IS is not stated on any act: shares and sizes are measured, so they are information content
entities (HOW WE KNOW), not qualities.

**Every act cites a `MarketSource`** (`abi:hasMarketSource`: title, url, publisher, date). Nothing
is asserted about a market without saying where it comes from. Curated statements cite the seed
itself ("Cloud Computing market map (curated seed)", publisher "bob markets module"), so they are
told apart from published ones in every answer.

**Segments carry the criterion they were cut along.** IaaS is a *service model*, Public Cloud a
*deployment model*, GPU cloud a *workload*, Cloud Data Centers a *value chain layer*. Segments cut
along different criteria overlap — GPU cloud is a segment of both IaaS and Public Cloud — so sizes
are never summed across them, and the queries return each size with its own market, year, region
and source.

**Competition is never an organization-to-organization edge.** Two organizations compete when they
have acts of competing in the same market over overlapping periods. That keeps every claim dated,
scoped to a geography and sourced, and lets a company lead GPU cloud while being absent from
Private Cloud. `abi:hasMarket` (organization → market) is written alongside as a one-hop shortcut.

**SWOT is split by what it is about.** Opportunities and threats are external and belong to the
market; strengths and weaknesses are internal and belong to one competitor's position in it, so
they name both. Every finding is also typed `abi:SWOTFinding`: the store runs no reasoner.

## Pipelines

| Pipeline | Tool | Writes |
|---|---|---|
| `MarketSegmentationPipeline` | `register_market_segmentation` | market, segments, one act per (parent, criterion) |
| `MarketCompetitorPipeline` | `register_market_competitors` | acts of competing, share/rank, website, ticker |
| `YahooFinanceCompetitorPipeline` | `register_market_competitors_from_yahoo_finance`, `find_yahoo_finance_industry_candidates` | acts of competing for listed companies, cited to their quote page |
| `MarketSizingPipeline` | `register_market_size` | act of sizing + size measurement |
| `MarketAnalysisPipeline` | `register_market_swot` | act of analysis + SWOT findings |
| `MarketSeedPipeline` | `load_market_from_datastore` | all of the above from `<Market>/<Market>.yaml` |

IRIs are deterministic (`abi:Market/<key>`, `abi:ActOfCompeting/<org>-<market>-<region>`…), so a
pipeline run twice writes the same triples.

### Yahoo Finance

Yahoo does not file companies by market, only by broad industry: `software-infrastructure` holds
OVHcloud and Microsoft, but also Palo Alto Networks and CrowdStrike. So Yahoo **enriches** the
listed competitors a curator or the agent names (legal name, website, ticker, and the quote page as
source), and **suggests** industry peers as candidates — `find_yahoo_finance_industry_candidates`
never registers anything. The adapter goes through the `yahoofinance` integration when that module
is loaded and calls `yfinance` directly otherwise. What it read is kept under
`<Market>/yahoofinance/<SYMBOL>.json`.

## Datastore

```
intelligence/markets/<Market>/
├── <Market>.yaml               the market as curated (input)
├── <Market>.ttl                the graph built from it (output)
└── yahoofinance/<SYMBOL>.json  the Yahoo Finance profiles its listed competitors were read from
```

The folder is the label in PascalCase, as organizations are filed. To (re)build a market:

```python
from naas_abi_core.services.object_storage.ObjectStorageFactory import ObjectStorageFactory
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSeedPipeline import (
    MarketSeedPipeline, MarketSeedPipelineConfiguration, MarketSeedPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.company_directory import (
    YahooFinanceCompanyDirectory,
)

storage = ObjectStorageFactory.ObjectStorageServiceFS("storage/datastore")
MarketSeedPipeline(
    MarketSeedPipelineConfiguration(
        object_storage=storage, directory=YahooFinanceCompanyDirectory(), persist=False
    )
).run(MarketSeedPipelineParameters(folder="CloudComputing"))
```

Pass `triple_store=` and `persist=True` (or use the agent's `load_market_from_datastore`) to also
insert it into `GRAPH <http://ontology.naas.ai/graph/markets>`.

## Queries

| Query | Answers | Arguments |
|---|---|---|
| `find_markets` | Which markets do we track? (with parents, criterion, competitor count) | `market_name`, `limit` |
| `find_market_segments` | How is this market segmented? (every depth) | `market_name`, `limit` |
| `find_market_competitors` | Who competes in it, with share, rank, source? | `market_name`, `limit` |
| `find_markets_of_organization` | Which markets is this company in? | `organization_name`, `limit` |
| `find_competitors_of_organization` | Who are its competitors? (shared markets) | `organization_name`, `limit` |
| `find_market_sizes` | How big is it? (every source, never summed) | `market_name`, `limit` |
| `find_market_swot` | Its strengths, weaknesses, opportunities, threats | `market_name`, `limit` |

A market argument matches a substring of the label and includes every segment below it
(`abi:isMarketSegmentOf*`).

## Regenerating

```bash
uv run python -m naas_abi_core.utils.onto2py --module \
  libs/naas-abi-marketplace/naas_abi_marketplace/domains/intelligence/modules/markets
```

This regenerates the slices' Python, consolidates them into `MarketsOntology.ttl` between the
`onto2py:consolidated-processes` markers, and regenerates the module's Python.
