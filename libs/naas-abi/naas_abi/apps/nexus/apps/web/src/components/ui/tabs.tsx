'use client';

import { useRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type TabItem<T extends string = string> = {
  id: T;
  label: ReactNode;
  icon?: ReactNode;
  /** A count or a short badge after the label. */
  count?: ReactNode;
  disabled?: boolean;
};

/**
 * Tabs over one pane. `underline` sits on a pane's top edge; `segmented` is a compact
 * switch inside a toolbar. Arrow keys, Home and End move between tabs (roving focus).
 */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  variant = 'underline',
  label,
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  variant?: 'underline' | 'segmented';
  /** Accessible name of the tab list. */
  label: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const enabled = items.map((item, index) => (item.disabled ? -1 : index)).filter((index) => index >= 0);
  // The tab Tab lands on: the selected one, else the first enabled one (nothing selected must
  // not take the whole strip out of the keyboard order).
  const selectedIndex = items.findIndex((item) => item.id === value);
  const tabStop = selectedIndex >= 0 ? selectedIndex : enabled[0];
  const move = (from: number, step: number | 'first' | 'last') => {
    const at = enabled.indexOf(from);
    const nextIndex =
      step === 'first' ? enabled[0] : step === 'last' ? enabled[enabled.length - 1] : enabled[(at + step + enabled.length) % enabled.length];
    const next = items[nextIndex];
    if (!next) return;
    onChange(next.id);
    refs.current[nextIndex]?.focus();
  };
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        'flex min-w-0 items-center',
        variant === 'underline' ? 'gap-4 border-b border-border' : 'gap-0.5 border border-border bg-muted/40 p-0.5',
        className
      )}
    >
      {items.map((item, index) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={index === tabStop ? 0 : -1}
            disabled={item.disabled}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => {
              const step =
                event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : event.key === 'Home' ? 'first' : event.key === 'End' ? 'last' : null;
              if (step === null) return;
              event.preventDefault();
              move(index, step);
            }}
            className={cn(
              'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-sm transition-colors disabled:pointer-events-none disabled:opacity-50',
              variant === 'underline'
                ? cn('-mb-px border-b-2 px-0.5 py-2', selected ? 'border-primary font-medium text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')
                : cn('h-7 px-2.5 text-xs', selected ? 'bg-background font-medium text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')
            )}
          >
            {item.icon}
            {item.label}
            {item.count !== undefined && item.count !== null ? (
              <span className="bg-muted px-1.5 text-micro text-muted-foreground">{item.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
