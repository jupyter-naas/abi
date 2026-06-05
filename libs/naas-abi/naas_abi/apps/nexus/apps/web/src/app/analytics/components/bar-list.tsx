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
  activeKey?: string | null;
  emptyText?: string;
}

export function BarList({
  items,
  valueLabel = (v) => v.toLocaleString(),
  className,
  onItemClick,
  activeKey,
  emptyText = 'No data',
}: BarListProps) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{emptyText}</p>;
  }
  const max = Math.max(1, ...items.map((i) => i.value));

  return (
    <ul className={cn('space-y-0.5', className)}>
      {items.map((item) => {
        const pct = Math.max(2, (item.value / max) * 100);
        const interactive = !!onItemClick;
        const isActive = activeKey === item.key;
        return (
          <li
            key={item.key}
            className={cn(
              'group relative isolate flex items-center justify-between gap-3 px-3 py-2 text-sm',
              interactive && 'cursor-pointer transition-colors hover:bg-muted/50',
              isActive && 'ring-1 ring-inset ring-workspace-accent rounded',
            )}
            onClick={interactive ? () => onItemClick(item) : undefined}
          >
            <div
              aria-hidden
              className={cn(
                'absolute inset-y-1 left-1 -z-10 transition-all',
                isActive ? 'bg-workspace-accent/20' : 'bg-workspace-accent-10',
              )}
              style={{ width: `calc(${pct}% - 0.5rem)` }}
            />
            <div className="flex-1 min-w-0">
              <p className={cn('truncate font-medium', isActive ? 'text-workspace-accent' : 'text-foreground')}>
                {item.label}
              </p>
              {item.sublabel && (
                <p className="truncate text-xs text-muted-foreground">{item.sublabel}</p>
              )}
            </div>
            <span className={cn('text-sm tabular-nums', isActive ? 'text-workspace-accent font-semibold' : 'text-muted-foreground')}>
              {valueLabel(item.value)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
