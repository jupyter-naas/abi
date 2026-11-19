'use client';

import { Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ANALYTICS_PERIODS } from './scope';
import type { AnalyticsPeriod } from './types';

/** Today / Yesterday / This week / This month, as one segmented control, and the timezone they follow. */
export function PeriodControl({
  value,
  onChange,
  timeZone,
}: {
  value: AnalyticsPeriod;
  onChange: (period: AnalyticsPeriod) => void;
  timeZone: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div role="radiogroup" aria-label="Period" className="flex items-center border border-border bg-card">
        {ANALYTICS_PERIODS.map((p) => {
          const active = p.id === value;
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(p.id)}
              className={cn(
                'h-9 border-r border-border px-3 text-sm font-medium transition-colors last:border-r-0',
                active
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              {p.label}
            </button>
          );
        })}
      </div>
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Clock size={12} aria-hidden />
        Times in {timeZone}
      </span>
    </div>
  );
}
