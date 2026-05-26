'use client';

import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  trend?: { value: number; label?: string };
  className?: string;
}

export function KpiCard({ label, value, hint, icon: Icon, trend, className }: KpiCardProps) {
  const trendPositive = trend && trend.value >= 0;
  return (
    <div
      className={cn(
        'rounded-2xl border border-border/60 bg-card p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]',
        'transition-all hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] hover:border-border',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
          {hint && <p className="mt-1.5 text-xs text-muted-foreground truncate">{hint}</p>}
          {trend && (
            <p
              className={cn(
                'mt-2 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium',
                trendPositive
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
              )}
            >
              {trendPositive ? '▲' : '▼'} {Math.abs(trend.value).toFixed(1)}%
              {trend.label && <span className="text-muted-foreground ml-1">{trend.label}</span>}
            </p>
          )}
        </div>
        {Icon && (
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Icon size={18} />
          </div>
        )}
      </div>
    </div>
  );
}
