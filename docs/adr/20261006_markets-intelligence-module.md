# Markets intelligence module; Market as a core class family

Status: Accepted

Date: 2026-10-06

## Context

The intelligence bucket could say who people and organizations are, but not which markets they
compete in, how those markets divide, how big they are, or their SWOT. `abi:Market` and
`abi:MarketSegment` existed only in the domain-level `OfferingOntology.ttl`, with `hasMarket` and
`hasMarketSegment` and nothing that could carry a competitor, a size or a source.

Market facts are contested: sources size the same market differently because they draw its
boundary differently, shares are quarter- and region-specific, and segments cut along different
criteria (service model, deployment model, workload) overlap. Yahoo Finance, the market-data
integration at hand, files companies by broad industry, not by market.

## Decision

**Market is a core class family.** `abi:Market`, `abi:MarketSegment`, `hasMarket` / `isMarketOf`
and `hasMarketSegment` / `isMarketSegmentOf` move to `naas_abi/ontologies/modules/MarketOntology.ttl`.
`OfferingOntology.ttl` imports it and keeps the offering terms. A segment may belong to several
broader markets.

**`intelligence/modules/markets`** owns the rest, as one slice per act on the BFO 7 buckets:
`ActOfMarketSegmentation`, `ActOfCompeting`, `ActOfMarketSizing`, `ActOfMarketAnalysis`. Its named
graph is `http://ontology.naas.ai/graph/markets` and its datastore path `intelligence/markets`, one
folder per market holding the curated YAML, the built TTL and the Yahoo Finance profiles read.

- **Every act cites a `MarketSource`.** Curated statements cite the curated file.
- **Competition is an act, never an organization-to-organization edge.** Competitors are those
  with acts of competing in the same market; each act is dated, regional and sourced.
- **Shares and sizes are measurement ICEs**, kept per source and never summed or averaged.
- **Segments name their segmentation criterion**, so overlaps are explicit.
- **SWOT is split**: opportunities and threats are about the market, strengths and weaknesses
  about one competitor in it.
- **Yahoo Finance sits behind a `CompanyDirectoryPort`.** It enriches named listed competitors and
  suggests industry peers as candidates; it never decides who competes.

## Consequences

- Competitors join the organizations and people graphs on the same `abi:Organization/<slug>` IRIs.
- Queries walk `isMarketSegmentOf*` and state subclass types explicitly; the store runs no reasoner.
- Unlisted competitors (Scaleway, Hetzner, Lambda…) are registered by hand or by the agent with a
  source; Yahoo cannot read them.
- Anything still importing `OfferingOntology` gets the Market classes through its new import;
  anything reading the old definitions' `abi:is_curated_in_foundry` annotations on them loses them.
