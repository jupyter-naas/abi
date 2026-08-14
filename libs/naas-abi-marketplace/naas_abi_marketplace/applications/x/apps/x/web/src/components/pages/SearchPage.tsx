"use client";

import { BarList } from "@/components/BarList";
import { DataTable } from "@/components/DataTable";
import { KpiGrid } from "@/components/KpiGrid";
import { LineChart } from "@/components/LineChart";
import { pickByQueryScenario } from "@/lib/format";
import {
  FACET_COLUMNS,
  facetValues,
  type ColumnValue,
} from "@/lib/tweetSearch";
import type { Scenario, Snapshots } from "@/lib/types";

type Props = {
  data: Snapshots["search"];
  querySlug: string;
  scenarioId: string;
  timezone: string;
  scenarios: Scenario[];
};

function formatWindowInstant(iso: string, timezone: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      timeZone: timezone,
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function SearchPage({
  data,
  querySlug,
  scenarioId,
  timezone,
  scenarios,
}: Props) {
  const kpis = pickByQueryScenario(data.kpis, querySlug, scenarioId);
  const bars = pickByQueryScenario(data.barcharts, querySlug, scenarioId);
  const line = pickByQueryScenario(data.linecharts, querySlug, scenarioId);
  const authors = (bars?.items || []).find((i) => i.id === "top_authors");
  const locs = (bars?.items || []).find((i) => i.id === "top_locations");
  const current =
    line?.series?.find((s) => s.id === "current")?.points || [];
  const previous =
    line?.series?.find((s) => s.id === "previous")?.points || [];
  const tweets =
    data.tables.find(
      (t) =>
        t.id === "tweets" &&
        t.query_slug === querySlug &&
        t.scenario_id === scenarioId,
    ) || null;
  const authorsTable =
    data.tables.find(
      (t) =>
        t.id === "authors" &&
        t.query_slug === querySlug &&
        t.scenario_id === scenarioId,
    ) || null;
  const scenario = scenarios.find((s) => s.id === scenarioId);
  const kpiItems = (kpis?.items || []).map((it) => {
    if (it.id !== "tweets_ingested" || !scenario) return it;
    return {
      ...it,
      hint: `${formatWindowInstant(scenario.start_time, timezone)} to ${formatWindowInstant(scenario.end_time, timezone)}`,
    };
  });
  // The checkbox lists come from the published facets, which are aggregated
  // over the whole query + window — not just the rows in the table above.
  const facets: Record<string, ColumnValue[]> = {};
  const facetsTruncated: Record<string, boolean> = {};
  for (const column of FACET_COLUMNS) {
    facets[column] = facetValues(data.facets, querySlug, scenarioId, column);
    facetsTruncated[column] = Boolean(
      (data.facets || []).find(
        (f) =>
          f.query_slug === querySlug &&
          f.scenario_id === scenarioId &&
          f.column === column,
      )?.truncated,
    );
  }

  return (
    <div>
      <KpiGrid items={kpiItems} accentFirst />
      <div className="kpi-charts">
        <div className="kpi-chart">
          <div className="kpi-label">Top authors</div>
          <BarList bars={authors?.bars || []} />
        </div>
        <div className="kpi-chart">
          <div className="kpi-label">Top author locations</div>
          <BarList bars={locs?.bars || []} />
        </div>
      </div>
      <div className="section">
        <div className="section-head">
          <h2>Ingested tweets over time</h2>
          <p className="sub">
            {line?.granularity === "day" ? "Per day" : "Per hour"} · ingested
            tweets (sample ≤ 1 000)
          </p>
        </div>
        <div className="card">
          <LineChart current={current} previous={previous} />
        </div>
      </div>
      <div className="section">
        <div className="section-head">
          <h2>Tweets fetched</h2>
          <p className="sub">
            {tweets && scenario
              ? `${(tweets.rows || []).length} tweet(s) from ${formatWindowInstant(scenario.start_time, timezone)} to ${formatWindowInstant(scenario.end_time, timezone)}`
              : ""}
          </p>
        </div>
        <div className="card">
          <DataTable
            table={tweets}
            timezone={timezone}
            nestUrlUnderText
            facets={facets}
            facetsTruncated={facetsTruncated}
          />
        </div>
      </div>
      <div className="section">
        <div className="section-head">
          <h2>Top authors</h2>
          <p className="sub">
            {authorsTable
              ? `${(authorsTable.rows || []).length} author(s) in range`
              : ""}
          </p>
        </div>
        <div className="card">
          <DataTable table={authorsTable} timezone={timezone} />
        </div>
      </div>
    </div>
  );
}
