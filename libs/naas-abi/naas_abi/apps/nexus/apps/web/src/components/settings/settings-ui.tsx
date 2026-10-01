import type { ReactNode } from 'react';
import { Loader2, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SettingsReloadButton } from '@/components/settings/settings-reload';

// Shared building blocks for every settings page, so headers, cards and states look the same.

export function SettingsPageHeader({
  title,
  badge,
  description,
  actions,
  leading,
  className,
}: {
  title: ReactNode;
  /** Shown next to the title, e.g. "9 enabled". */
  badge?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Rendered before the title, e.g. a back button or an avatar. */
  leading?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="flex min-w-0 flex-1 items-start gap-3">
        {leading}
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <h2 className="truncate text-lg font-semibold text-foreground">{title}</h2>
            {badge !== undefined && badge !== null ? (
              <span className="inline-flex shrink-0 items-center bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {badge}
              </span>
            ) : null}
          </div>
          {description ? <p className="mt-0.5 text-sm text-muted-foreground">{description}</p> : null}
        </div>
      </div>
      {/* Never wraps below the title: actions (e.g. the add button) stay in the top-right corner,
          with Reload just left of them. */}
      <div className="flex shrink-0 items-center justify-end gap-2">
        <SettingsReloadButton />
        {actions}
      </div>
    </div>
  );
}

export function SettingsSection({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn('border border-border bg-card', className)}>
      {title || actions ? (
        <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
          <div className="min-w-0">
            {title ? <h3 className="text-sm font-semibold text-foreground">{title}</h3> : null}
            {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className={cn('p-4', bodyClassName)}>{children}</div>
    </section>
  );
}

export function SettingsLoading({ label = 'Loading…', className }: { label?: string; className?: string }) {
  return (
    <div className={cn('flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground', className)}>
      <Loader2 size={16} className="animate-spin" />
      {label}
    </div>
  );
}

export function SettingsEmpty({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 border border-dashed border-border px-6 py-12 text-center',
        className
      )}
    >
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

/**
 * Table classes shared by every settings list. The wrapper is its own scroll box so the
 * header cells stay pinned (sticky) while the rows scroll.
 */
export const settingsTable = {
  wrapper: 'max-h-[65vh] overflow-auto border border-border bg-card',
  // Separate borders: with collapsed borders a sticky header loses its bottom border on scroll.
  table: 'w-full border-separate border-spacing-0 text-sm',
  headRow: 'text-left',
  th: 'sticky top-0 z-[1] border-b border-border bg-muted px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground',
  row: 'transition-colors hover:bg-muted/40 [&:last-child>td]:border-b-0',
  td: 'border-b border-border px-3 py-3 align-middle',
};

export function SettingsSearch({
  value,
  onChange,
  placeholder = 'Search…',
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn('relative', className)}>
      <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-none border border-input bg-background pl-9 pr-9 text-sm placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center text-muted-foreground hover:text-foreground"
        >
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}

/** Label + control + optional hint, stacked. */
export function SettingsField({
  label,
  hint,
  htmlFor,
  children,
  className,
}: {
  label: ReactNode;
  hint?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-foreground">
        {label}
      </label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

const noticeTones = {
  success: 'border-primary/30 bg-primary/10 text-primary',
  error: 'border-destructive/30 bg-destructive/10 text-destructive',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  info: 'border-border bg-muted/50 text-muted-foreground',
} as const;

/** Inline status banner (save confirmation, load error, warning). */
export function SettingsNotice({
  tone = 'info',
  icon,
  children,
  className,
}: {
  tone?: keyof typeof noticeTones;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-start gap-2 border px-3 py-2 text-sm', noticeTones[tone], className)}>
      {icon ? <span className="mt-0.5 shrink-0">{icon}</span> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export type SettingsFilterOption = { value: string; label: string };

/** Compact dropdown filter shown on the same row as a table's search bar. */
export function SettingsFilterSelect({
  label,
  value,
  onChange,
  options,
  className,
}: {
  /** Accessible name, e.g. "Status". */
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SettingsFilterOption[];
  className?: string;
}) {
  return (
    <select
      aria-label={label}
      title={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'h-9 rounded-none border border-input bg-background px-3 text-sm text-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        value !== options[0]?.value && 'border-primary text-primary',
        className
      )}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/**
 * Everything that sits above a settings table: the table metadata (counts) on the left,
 * then the search bar with the table's own filters on the same row.
 */
export function SettingsTableToolbar({
  search,
  onSearchChange,
  searchPlaceholder,
  filters,
  meta,
  className,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: ReactNode;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {meta ? <p className="text-xs text-muted-foreground">{meta}</p> : null}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <SettingsSearch value={search} onChange={onSearchChange} placeholder={searchPlaceholder} className="flex-1" />
        {filters ? <div className="flex flex-wrap items-center gap-2">{filters}</div> : null}
      </div>
    </div>
  );
}

/** "3 of 12 agents" when filtered, "12 agents" otherwise. */
export function countLabel(shown: number, total: number, noun: string, plural = `${noun}s`): string {
  const word = total === 1 ? noun : plural;
  return shown === total ? `${total} ${word}` : `${shown} of ${total} ${word}`;
}
