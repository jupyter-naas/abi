'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Layers, Search, Users, X } from 'lucide-react';
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
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useDismiss(open, setOpen);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const sorted = [...users].sort((a, b) => a.user_email.localeCompare(b.user_email));
    return q ? sorted.filter((u) => u.user_email.toLowerCase().includes(q)) : sorted;
  }, [query, users]);

  const selected = users.find((u) => u.user_id === value);
  const picked = value !== ALL;
  const label = picked ? (selected?.user_email ?? value) : 'All users';

  const pick = (userId: string) => {
    onChange(userId);
    setOpen(false);
    setQuery('');
  };

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)} className={triggerClass(picked)} aria-expanded={open}>
        <Users size={14} className="flex-shrink-0 text-muted-foreground" />
        <span className="truncate font-medium">{label}</span>
        <ChevronDown size={14} className="flex-shrink-0 text-muted-foreground" />
      </button>
      {picked && (
        <button
          type="button"
          onClick={() => onChange(ALL)}
          className="absolute -right-2 -top-2 flex h-4 w-4 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground"
          aria-label="Clear the user filter"
          title="All users"
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
              placeholder="Search by email…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-9 w-full border border-input bg-background pl-8 pr-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="mt-1.5 max-h-64 overflow-y-auto">
            <button type="button" onClick={() => pick(ALL)} className={cn(optionClass(!picked), 'justify-between')}>
              <span className="font-medium">All users</span>
              <span className="text-xs text-muted-foreground">{users.length}</span>
            </button>
            <div className="my-1 border-t border-border/50" />
            {filtered.length === 0 && <p className="px-2.5 py-2 text-sm text-muted-foreground">No matches.</p>}
            {filtered.map((u) => (
              <button key={u.user_id} type="button" onClick={() => pick(u.user_id)} className={optionClass(value === u.user_id)}>
                <Avatar email={u.user_email} />
                <span className="truncate">{u.user_email}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
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
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, setOpen);
  const picked = value !== ALL;
  const current = workspaces.find((w) => w.workspace_id === value);
  const label = picked ? (current?.workspace_name ?? value) : 'All workspaces';
  const sorted = useMemo(
    () => [...workspaces].sort((a, b) => a.workspace_name.localeCompare(b.workspace_name)),
    [workspaces]
  );

  const pick = (workspaceId: string) => {
    onChange(workspaceId);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)} className={triggerClass(picked)} aria-expanded={open}>
        <Layers size={14} className="flex-shrink-0 text-muted-foreground" />
        <span className="truncate font-medium">{label}</span>
        <ChevronDown size={14} className="flex-shrink-0 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 max-h-80 w-60 overflow-y-auto border border-border bg-popover p-1.5 text-popover-foreground shadow-lg">
          <button type="button" onClick={() => pick(ALL)} className={optionClass(!picked)}>
            All workspaces
          </button>
          <div className="my-1 border-t border-border/50" />
          {sorted.map((w) => (
            <button
              key={w.workspace_id}
              type="button"
              onClick={() => pick(w.workspace_id)}
              className={optionClass(value === w.workspace_id)}
            >
              <span className="truncate">{w.workspace_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
