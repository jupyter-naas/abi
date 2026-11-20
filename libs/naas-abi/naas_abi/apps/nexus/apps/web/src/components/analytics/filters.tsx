'use client';

import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ChevronDown, Layers, Search, Users, X, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from './avatar';
import { ALL } from './scope';
import type { UsersDirectoryEntry, WorkspacesDirectoryEntry } from './types';

/** Closes a menu on an outside click or Escape (`setOpen` is a state setter: stable). */
function useDismiss(open: boolean, setOpen: (open: boolean) => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, setOpen]);
  return ref;
}

const triggerClass = (active: boolean) =>
  cn(
    'flex h-9 max-w-[260px] items-center gap-2 border border-border bg-card pl-3 pr-2.5 text-sm text-foreground transition-colors',
    'hover:border-foreground/20 hover:bg-muted/40',
    active && 'border-primary bg-primary/5'
  );

const optionClass = (active: boolean) =>
  cn(
    'flex w-full items-center gap-2 px-2.5 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted',
    active && 'bg-primary/10 text-primary'
  );

interface FilterOption {
  id: string;
  label: string;
  /** Shown before the label (the user's avatar). */
  leading?: ReactNode;
}

/** A filter with a search box: "All …" or one of `options`, sorted by label. */
function SearchableFilter({
  value,
  onChange,
  options,
  icon: Icon,
  allLabel,
  searchPlaceholder,
  clearLabel,
}: {
  value: string;
  onChange: (id: string) => void;
  options: FilterOption[];
  icon: LucideIcon;
  allLabel: string;
  searchPlaceholder: string;
  clearLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useDismiss(open, setOpen);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const sorted = [...options].sort((a, b) => a.label.localeCompare(b.label));
    return q ? sorted.filter((o) => o.label.toLowerCase().includes(q)) : sorted;
  }, [query, options]);

  const selected = options.find((o) => o.id === value);
  const picked = value !== ALL;
  const label = picked ? (selected?.label ?? value) : allLabel;

  const pick = (id: string) => {
    onChange(id);
    setOpen(false);
    setQuery('');
  };

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)} className={triggerClass(picked)} aria-expanded={open}>
        <Icon size={14} className="flex-shrink-0 text-muted-foreground" />
        <span className="truncate font-medium">{label}</span>
        <ChevronDown size={14} className="flex-shrink-0 text-muted-foreground" />
      </button>
      {picked && (
        <button
          type="button"
          onClick={() => onChange(ALL)}
          className="absolute -right-2 -top-2 flex h-4 w-4 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground"
          aria-label={clearLabel}
          title={allLabel}
        >
          <X size={10} />
        </button>
      )}

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-72 border border-border bg-popover p-1.5 text-popover-foreground shadow-lg">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              placeholder={searchPlaceholder}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-9 w-full border border-input bg-background pl-8 pr-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="mt-1.5 max-h-64 overflow-y-auto">
            <button type="button" onClick={() => pick(ALL)} className={cn(optionClass(!picked), 'justify-between')}>
              <span className="font-medium">{allLabel}</span>
              <span className="text-xs text-muted-foreground">{options.length}</span>
            </button>
            <div className="my-1 border-t border-border/50" />
            {filtered.length === 0 && <p className="px-2.5 py-2 text-sm text-muted-foreground">No matches.</p>}
            {filtered.map((o) => (
              <button key={o.id} type="button" onClick={() => pick(o.id)} className={optionClass(value === o.id)}>
                {o.leading}
                <span className="truncate">{o.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** The user filter: the scope's members only (its `directory`), keyed by `user_id`. */
export function UserFilter({
  value,
  onChange,
  users,
}: {
  value: string;
  onChange: (userId: string) => void;
  users: UsersDirectoryEntry[];
}) {
  const options = useMemo(
    () => users.map((u) => ({ id: u.user_id, label: u.user_email, leading: <Avatar email={u.user_email} /> })),
    [users]
  );
  return (
    <SearchableFilter
      value={value}
      onChange={onChange}
      options={options}
      icon={Users}
      allLabel="All users"
      searchPlaceholder="Search by email…"
      clearLabel="Clear the user filter"
    />
  );
}

/** The workspace filter (organization scope only): the organization's workspaces. */
export function WorkspaceFilter({
  value,
  onChange,
  workspaces,
}: {
  value: string;
  onChange: (workspaceId: string) => void;
  workspaces: WorkspacesDirectoryEntry[];
}) {
  const options = useMemo(
    () => workspaces.map((w) => ({ id: w.workspace_id, label: w.workspace_name })),
    [workspaces]
  );
  return (
    <SearchableFilter
      value={value}
      onChange={onChange}
      options={options}
      icon={Layers}
      allLabel="All workspaces"
      searchPlaceholder="Search workspaces…"
      clearLabel="Clear the workspace filter"
    />
  );
}
