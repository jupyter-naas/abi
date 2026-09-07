"use client";

import { useMemo } from "react";
import { fmt } from "@/lib/format";
import type { ChartPoint } from "@/lib/types";

type Props = {
  current: ChartPoint[];
  previous?: ChartPoint[];
};

export function LineChart({ current, previous }: Props) {
  const n = current.length;
  const W = Math.max(720, n * 12);
  const H = 300;
  const pad = { l: 48, r: 20, t: 16, b: 54 };

  const geometry = useMemo(() => {
    if (!n) return null;
    const innerW = W - pad.l - pad.r;
    const innerH = H - pad.t - pad.b;
    const maxV = Math.max(
      1,
      ...current.map((p) => p.value),
      ...(previous || []).map((p) => p.value),
    );
    const xAt = (i: number) =>
      pad.l + (n > 1 ? (i * innerW) / (n - 1) : innerW / 2);
    const yAt = (v: number) => pad.t + innerH - (v / maxV) * innerH;
    const curPath = current
      .map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`)
      .join(" ");
    const prevPath =
      previous && previous.length
        ? previous
            .slice(0, n)
            .map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`)
            .join(" ")
        : null;
    const area = `${curPath} L ${xAt(n - 1)} ${pad.t + innerH} L ${xAt(0)} ${pad.t + innerH} Z`;
    const every = Math.max(1, Math.ceil(n / 12));
    return { maxV, xAt, yAt, curPath, prevPath, area, every, innerH };
  }, [current, previous, n, W]);

  if (!n || !geometry) {
    return (
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img">
        <text x={W / 2} y={H / 2} textAnchor="middle">
          No data in this range.
        </text>
      </svg>
    );
  }

  const { maxV, xAt, yAt, curPath, prevPath, area, every } = geometry;

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img">
      {[0, 0.5, 1].map((f) => {
        const v = Math.round(maxV * f);
        const y = yAt(v);
        return (
          <g key={f}>
            <line
              x1={pad.l}
              x2={W - pad.r}
              y1={y}
              y2={y}
              stroke="#2f3336"
            />
            <text x={pad.l - 8} y={y + 4} textAnchor="end">
              {fmt(v)}
            </text>
          </g>
        );
      })}
      {prevPath ? (
        <path
          d={prevPath}
          fill="none"
          stroke="#71767b"
          strokeWidth={1.5}
          strokeDasharray="4 4"
        />
      ) : null}
      <path d={area} fill="#1d9bf0" fillOpacity={0.12} />
      <path d={curPath} fill="none" stroke="#1d9bf0" strokeWidth={2} />
      {current.map((p, i) => {
        const lx = xAt(i);
        const ly = H - pad.b + 15;
        return (
          <g key={`${p.t}-${i}`}>
            <circle cx={lx} cy={yAt(p.value)} r={2.2} fill="#1d9bf0" />
            {i === n - 1 || i % every === 0 ? (
              <text
                x={lx}
                y={ly}
                textAnchor="end"
                transform={`rotate(-32 ${lx} ${ly})`}
              >
                {p.label}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
