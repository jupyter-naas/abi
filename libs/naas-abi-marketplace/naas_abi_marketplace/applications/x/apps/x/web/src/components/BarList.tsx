"use client";

import { deltaClass, fmt } from "@/lib/format";
import type { Bar } from "@/lib/types";

type Props = {
  bars: Bar[];
};

export function BarList({ bars }: Props) {
  if (!bars.length) {
    return <div className="bar-empty">No data in range.</div>;
  }
  const max = Math.max(1, ...bars.map((b) => b.value || 0));
  return (
    <div className="bar-list">
      {bars.map((b, i) => (
        <div className="bar-row" key={`${b.label}-${i}`}>
          <div className="bl-label">
            {b.href ? (
              <a href={b.href} target="_blank" rel="noopener noreferrer">
                {b.label}
              </a>
            ) : (
              b.label
            )}
          </div>
          <div className="bl-value">
            {fmt(b.value)}
            {typeof b.delta === "number" ? (
              <span className={`bl-delta ${deltaClass(b.delta)}`}>
                {b.delta === 0
                  ? "±0"
                  : `${b.delta > 0 ? "+" : ""}${fmt(b.delta)}`}
              </span>
            ) : null}
          </div>
          <div className="bl-track">
            <div
              className="bl-fill"
              style={{ width: `${(100 * (b.value || 0)) / max}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
