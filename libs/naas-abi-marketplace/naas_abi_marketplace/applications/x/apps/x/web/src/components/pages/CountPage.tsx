"use client";

import { BarList } from "@/components/BarList";
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
  const bars = pickByQueryScenario(data.barcharts, querySlug, scenarioId);
  const line = pickByQueryScenario(data.linecharts, querySlug, scenarioId);
  const topBars = bars?.items?.[0]?.bars || [];
  const current =
    line?.series?.find((s) => s.id === "current")?.points || [];
  const previous =
    line?.series?.find((s) => s.id === "previous")?.points || [];

  return (
    <div>
      <KpiGrid items={kpis?.items || []} accentFirst />
      <div className="kpi-charts" style={{ marginTop: 12 }}>
        <div className="kpi-chart">
          <div className="kpi-label">Top periods</div>
          <BarList bars={topBars} />
        </div>
      </div>
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
