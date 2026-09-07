"use client";

import { deltaClass, formatDelta, fmt } from "@/lib/format";
import type { KpiItem } from "@/lib/types";

type Props = {
  items: KpiItem[];
  columns?: 3 | 4;
  accentFirst?: boolean;
};

export function KpiGrid({ items, columns = 4, accentFirst = false }: Props) {
  return (
    <div className={`kpis${columns === 3 ? " three" : ""}`}>
      {items.map((it, i) => (
        <div className="kpi" key={it.id || `${it.label}-${i}`}>
          <div className="kpi-label">{it.label}</div>
          <div className={`kpi-value${accentFirst && i === 0 ? " up" : ""}`}>
            <span>
              {it.text != null
                ? it.text
                : it.value == null
                  ? "-"
                  : fmt(it.value)}
              {it.text == null && it.unit === "%" ? "%" : ""}
            </span>
            <span className={`kpi-delta ${deltaClass(it.delta)}`}>
              {formatDelta(it.delta, it.unit === "%" ? " pts" : "")}
            </span>
          </div>
          {it.hint ? <div className="kpi-hint">{it.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}
