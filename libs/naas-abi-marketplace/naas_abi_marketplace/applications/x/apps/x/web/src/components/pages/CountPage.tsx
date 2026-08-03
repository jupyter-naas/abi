"use client";

import { KpiGrid } from "@/components/KpiGrid";
import { LineChart } from "@/components/LineChart";
import { pickByQueryScenario } from "@/lib/format";
import type { Snapshots } from "@/lib/types";

type Props = {
  data: Snapshots["count"];
  querySlug: string;
  scenarioId: string;
};

export function CountPage({ data, querySlug, scenarioId }: Props) {
  const kpis = pickByQueryScenario(data.kpis, querySlug, scenarioId);
  const line = pickByQueryScenario(data.linecharts, querySlug, scenarioId);
  const current =
    line?.series?.find((s) => s.id === "current")?.points || [];
  const previous =
    line?.series?.find((s) => s.id === "previous")?.points || [];

  return (
    <div>
      <KpiGrid items={kpis?.items || []} accentFirst />
      <div className="section">
        <div className="section-head">
          <h2>Posts over time</h2>
          <p className="sub">
            {line?.granularity === "day" ? "Per day" : "Per hour"} · current vs
            previous period
          </p>
        </div>
        <div className="card">
          <LineChart current={current} previous={previous} />
        </div>
      </div>
    </div>
  );
}
