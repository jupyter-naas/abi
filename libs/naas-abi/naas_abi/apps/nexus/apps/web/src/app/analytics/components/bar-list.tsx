'use client';

import { cn } from '@/lib/utils';

export interface BarItem {
  key: string;
  label: string;
  value: number;
  sublabel?: string;
}

interface BarListProps {
  items: BarItem[];
  valueLabel?: (v: number) => string;
  className?: string;
  onItemClick?: (item: BarItem) => void;
  emptyText?: string;
}

export function BarList({
  items,
  valueLabel = (v) => v.toLocaleString(),
  className,
  onItemClick,
  emptyText = 'No data',
}: BarListProps) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{emptyText}</p>;
  }
  const max = Math.max(1, ...items.map((i) => i.value));

  return (
    <ul className={cn('space-y-1', className)}>
      {items.map((item) => {
        const pct = Math.max(2, (item.value / max) * 100);
        const interactive = !!onItemClick;
        return (
          <li
            key={item.key}
            className={cn(
              'group relative isolate flex items-center justify-between gap-3 rounded-md px-3 py-2 text-sm',
              interactive && 'cursor-pointer transition-colors hover:bg-muted/50',
            )}
            onClick={interactive ? () => onItemClick(item) : undefined}
          >
            <div
              aria-hidden
              className="absolute inset-y-1 left-1 -z-10 rounded bg-primary/10 transition-all"
              style={{ width: `calc(${pct}% - 0.5rem)` }}
            />
            <div className="flex-1 min-w-0">
              <p className="truncate font-medium text-foreground">{item.label}</p>
              {item.sublabel && (
                <p className="truncate text-xs text-muted-foreground">{item.sublabel}</p>
              )}
            </div>
            <span className="text-sm tabular-nums text-muted-foreground">{valueLabel(item.value)}</span>
          </li>
        );
      })}
    </ul>
  );
}
