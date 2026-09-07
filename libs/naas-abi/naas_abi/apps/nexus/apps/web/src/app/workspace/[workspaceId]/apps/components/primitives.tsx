'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Bot, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PROPERTY_BY_KEY, propertyValues, type AppRecord, type PropertyKey } from './types';

// ---------------------------------------------------------------------------
// App icon
// ---------------------------------------------------------------------------

const ICON_DIMS = {
  sm: 'h-6 w-6 text-sm',
  md: 'h-9 w-9 text-lg',
  lg: 'h-12 w-12 text-2xl',
} as const;

const ICON_GLYPH = { sm: 13, md: 18, lg: 24 } as const;

export function AppIcon({
  record,
  size = 'md',
}: {
  record: Pick<AppRecord, 'avatarUrl' | 'iconEmoji' | 'name'>;
  size?: keyof typeof ICON_DIMS;
}) {
  const [failed, setFailed] = useState(false);

  if (record.avatarUrl && !failed) {
    return (
      <span
        className={cn(
          ICON_DIMS[size],
          'relative flex-shrink-0 overflow-hidden p-0',
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={record.avatarUrl}
          alt={record.name}
          className="absolute inset-0 h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      </span>
    );
  }
  return (
    <div
      className={cn(
        ICON_DIMS[size],
        'flex flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10 leading-none',
      )}
    >
      {record.iconEmoji ?? <Bot size={ICON_GLYPH[size]} className="text-workspace-accent" />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Property rendering
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  alpha: 'bg-amber-500/10 text-amber-600',
  ai: 'bg-blue-500/10 text-blue-500',
  domain: 'bg-amber-500/10 text-amber-600',
  core: 'bg-workspace-accent/10 text-workspace-accent',
  external: 'bg-muted text-muted-foreground',
};

function tagClass(key: PropertyKey, value: string): string {
  if (key === 'category') return CATEGORY_COLORS[value] ?? 'bg-muted text-muted-foreground';
  return 'bg-muted text-muted-foreground';
}

/** A property value as Notion renders it: tags for selects, plain text otherwise. */
export function PropertyValue({
  record,
  propertyKey,
  className,
}: {
  record: AppRecord;
  propertyKey: PropertyKey;
  className?: string;
}) {
  const def = PROPERTY_BY_KEY[propertyKey];
  const values = propertyValues(record, propertyKey);

  if (values.length === 0) {
    return <span className={cn('text-xs text-muted-foreground/50', className)}>—</span>;
  }

  if (def.type === 'select' || def.type === 'multi') {
    return (
      <span className={cn('flex flex-wrap items-center gap-1', className)}>
        {values.map((value) => (
          <span
            key={value}
            className={cn('inline-block px-1.5 py-0.5 text-[11px] font-medium', tagClass(propertyKey, value))}
          >
            {value}
          </span>
        ))}
      </span>
    );
  }

  return (
    <span className={cn('text-xs text-muted-foreground', def.type === 'url' && 'font-mono', className)}>
      {values.join(', ')}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Popover — toolbar menus (filter, sort, group, properties, view options)
// ---------------------------------------------------------------------------

export function Popover({
  trigger,
  children,
  align = 'left',
  width = 'w-72',
  className,
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: ReactNode | ((close: () => void) => ReactNode);
  align?: 'left' | 'right';
  width?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div ref={ref} className={cn('relative', className)}>
      {trigger({ open, toggle: () => setOpen((v) => !v) })}
      {open && (
        <div
          className={cn(
            'absolute z-50 mt-1 max-h-[70vh] overflow-y-auto border border-border bg-popover p-2 shadow-lg',
            width,
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {typeof children === 'function' ? children(close) : children}
        </div>
      )}
    </div>
  );
}

/** Toolbar button styling shared by every popover trigger. */
export function ToolbarButton({
  active,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        'flex h-8 items-center gap-1.5 px-2 text-xs font-medium transition-colors',
        active
          ? 'bg-workspace-accent/10 text-workspace-accent'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        props.className,
      )}
    >
      {children}
    </button>
  );
}

/** A `<select>` styled like the rest of the toolbar menus. */
export function MenuSelect({
  value,
  onChange,
  children,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('relative', className)}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 w-full appearance-none border bg-background pl-2 pr-6 text-xs focus:outline-none focus:ring-1 focus:ring-workspace-accent/40"
      >
        {children}
      </select>
      <ChevronDown
        size={11}
        className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  );
}
