'use client';

import { useId, useMemo, useState } from 'react';
import { formatBucket } from './format';
import type { AnalyticsGranularity, TimeseriesPoint } from './types';

interface LineChartProps {
  data: TimeseriesPoint[];
  /** How the buckets read: `YYYY-MM-DDTHH` (hour) or `YYYY-MM-DD` (day). */
  granularity: AnalyticsGranularity;
  height?: number;
  label?: string;
}

/** The series colour: the scope's primary token (organization or workspace brand, light or dark). */
const SERIES_COLOR = 'hsl(var(--primary))';

export function LineChart({ data, granularity, height = 180, label }: LineChartProps) {
  const color = SERIES_COLOR;
  const gradientId = `lc-area-${useId().replace(/:/g, '')}`;
  const [hover, setHover] = useState<number | null>(null);

  const { points, area, line, maxValue, minValue, w, h, pad, innerH } = useMemo(() => {
    const w = 800;
    const h = height;
    const pad = { left: 36, right: 12, top: 16, bottom: 26 };
    const innerW = w - pad.left - pad.right;
    const innerH = h - pad.top - pad.bottom;

    const values = data.map((d) => d.value);
    const maxValue = Math.max(1, ...values);
    const minValue = 0;
    const span = maxValue - minValue || 1;

    const xStep = data.length > 1 ? innerW / (data.length - 1) : 0;
    const points = data.map((d, i) => ({
      x: pad.left + i * xStep,
      y: pad.top + innerH - ((d.value - minValue) / span) * innerH,
      d,
      i,
    }));

    const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    const area = points.length
      ? `${line} L ${points[points.length - 1].x} ${pad.top + innerH} L ${points[0].x} ${pad.top + innerH} Z`
      : '';

    return { points, area, line, maxValue, minValue, w, h, pad, innerH };
  }, [data, height]);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <p className="text-sm text-muted-foreground">No data</p>
      </div>
    );
  }

  // Y-axis ticks. For small integer ranges (counts of 1–4) show every integer —
  // otherwise the 3-tick scheme rounds to duplicates (e.g. maxValue=1 → 0, 1, 1).
  const tickValues =
    maxValue <= 4
      ? Array.from({ length: maxValue + 1 }, (_, v) => v)
      : [0, Math.round(maxValue / 2), maxValue];
  const yTicks = tickValues.map((v) => ({
    value: v,
    y: pad.top + innerH - ((v - minValue) / (maxValue - minValue || 1)) * innerH,
  }));

  // X-axis labels: ~5 evenly spaced
  const xLabelStep = Math.max(1, Math.floor(data.length / 5));
  const xLabels = points.filter((_, i) => i % xLabelStep === 0 || i === points.length - 1);

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="w-full h-auto"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid */}
        {yTicks.map((t, i) => (
          <line
            key={i}
            x1={pad.left}
            x2={w - pad.right}
            y1={t.y}
            y2={t.y}
            stroke="hsl(var(--border))"
            strokeWidth="1"
            strokeDasharray={i === 0 ? '0' : '2 4'}
            opacity="0.6"
          />
        ))}

        {/* Y labels */}
        {yTicks.map((t, i) => (
          <text
            key={i}
            x={pad.left - 6}
            y={t.y + 3}
            textAnchor="end"
            className="fill-muted-foreground"
            style={{ fontSize: 10 }}
          >
            {t.value}
          </text>
        ))}

        {/* Area + line */}
        <path d={area} fill={`url(#${gradientId})`} />
        <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {/* Hover capture rects */}
        {points.map((p, i) => {
          const width = points.length > 1 ? (w - pad.left - pad.right) / points.length : w - pad.left - pad.right;
          return (
            <rect
              key={i}
              x={p.x - width / 2}
              y={pad.top}
              width={width}
              height={innerH}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
            />
          );
        })}

        {/* Hover marker */}
        {hover !== null && points[hover] && (
          <>
            <line
              x1={points[hover].x}
              x2={points[hover].x}
              y1={pad.top}
              y2={pad.top + innerH}
              stroke={color}
              strokeWidth="1"
              opacity="0.35"
            />
            <circle
              cx={points[hover].x}
              cy={points[hover].y}
              r="4"
              fill={color}
              stroke="hsl(var(--card))"
              strokeWidth="2"
            />
            <circle cx={points[hover].x} cy={points[hover].y} r="7" fill={color} opacity="0.18" />
          </>
        )}

        {/* X labels */}
        {xLabels.map((p, i) => (
          <text
            key={i}
            x={p.x}
            y={h - 8}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: 10 }}
          >
            {formatBucket(p.d.date, granularity)}
          </text>
        ))}
      </svg>

      {/* Tooltip */}
      {hover !== null && points[hover] && (
        <div className="mt-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{points[hover].d.value.toLocaleString()}</span>
          {' '}
          <span>{label ?? 'events'}</span>
          <span className="mx-2">·</span>
          <span>{formatBucket(points[hover].d.date, granularity, true)}</span>
        </div>
      )}
    </div>
  );
}
