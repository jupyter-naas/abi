import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/components/ui/page-header';
import { SearchBox } from '@/components/ui/search-box';
import { SettingsReloadButton } from '@/components/settings/settings-reload';

// What only settings pages add to the kit (components/ui): Reload in the header, the table
// toolbar and its filters, the back button. Cards, notices, empty and loading states,
// fields and the search box are the kit's own.

/** A settings page's header: the kit's PageHeader, with Reload just left of the actions. */
export function SettingsPageHeader(props: Parameters<typeof PageHeader>[0]) {
  return (
    <PageHeader
      {...props}
      actions={
        <>
          <SettingsReloadButton />
          {props.actions}
        </>
      }
    />
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
        <SearchBox value={search} onChange={onSearchChange} placeholder={searchPlaceholder} className="flex-1" />
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

/**
 * Back to the list a page was opened from, beside its title (a person's page under Users):
 * a link to `href`, or a button calling `onClick`.
 */
export function SettingsBackButton({ label, href, onClick }: { label: string; href?: string; onClick?: () => void }) {
  const className =
    'mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground';
  const icon = <ArrowLeft size={14} />;
  if (href) {
    return (
      <Link href={href} className={className} aria-label={`Back to ${label}`} title={`Back to ${label}`} data-action="back">
        {icon}
      </Link>
    );
  }
  return (
    <button type="button" className={className} onClick={onClick} aria-label={`Back to ${label}`} title={`Back to ${label}`} data-action="back">
      {icon}
    </button>
  );
}
