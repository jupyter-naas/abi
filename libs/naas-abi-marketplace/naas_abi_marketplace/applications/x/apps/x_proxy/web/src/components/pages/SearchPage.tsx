"use client";

import { BarList } from "@/components/BarList";
import { KpiGrid } from "@/components/KpiGrid";
import { LineChart } from "@/components/LineChart";
import { pickByQueryScenario } from "@/lib/format";
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
  const current =
    line?.series?.find((s) => s.id === "current")?.points || [];
  const previous =
    line?.series?.find((s) => s.id === "previous")?.points || [];
  const scenario = scenarios.find((s) => s.id === scenarioId);
  const kpiItems = (kpis?.items || []).map((it) => {
    if (it.id !== "tweets_ingested" || !scenario) return it;
    return {
      ...it,
      hint: `${formatWindowInstant(scenario.start_time, timezone)} to ${formatWindowInstant(scenario.end_time, timezone)}`,
    };
  });
  return (
    <div>
      <KpiGrid items={kpiItems} accentFirst />
      <div className="section">
        <div className="section-head">
          <h2>Posts ingested over time</h2>
          <p className="sub">
            {line?.granularity === "day" ? "Per day" : "Per hour"} · current vs
            previous period
          </p>
        </div>
        <div className="card">
          <LineChart current={current} previous={previous} />
        </div>
      </div>
      <div className="section">
        <div className="section-head">
          <h2>Top authors</h2>
          <p className="sub">
            {authors?.bars?.length
              ? `${authors.bars.length} author(s) in range · by posts ingested`
              : ""}
          </p>
        </div>
        <div className="card">
          <BarList bars={authors?.bars || []} authors />
        </div>
      </div>
    </div>
  );
}
