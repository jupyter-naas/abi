'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, ChevronDown, Search, Users, Layers, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type DateRangeKey = '7d' | '30d' | '90d' | 'custom';

export interface FilterValue {
  range: DateRangeKey;
  start_date?: string;
  end_date?: string;
  user_email: string; // 'all' or a specific email
  workspace_id: string; // 'all' or a specific workspace id
}

interface UserOption {
  user_email: string;
  user_id: string;
}

interface WorkspaceOption {
  workspace_id: string;
  workspace_name: string;
}

interface FilterBarProps {
  value: FilterValue;
  onChange: (next: FilterValue) => void;
  users: UserOption[];
  workspaces: WorkspaceOption[];
}

export function FilterBar({ value, onChange, users, workspaces }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <DateRangePicker value={value} onChange={onChange} />
      <UserSelect value={value} onChange={onChange} users={users} />
      <WorkspaceSelect value={value} onChange={onChange} workspaces={workspaces} />
    </div>
  );
}

function DateRangePicker({ value, onChange }: { value: FilterValue; onChange: (v: FilterValue) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const options: { key: DateRangeKey; label: string }[] = [
    { key: '7d', label: 'Last 7 days' },
    { key: '30d', label: 'Last 30 days' },
    { key: '90d', label: 'Last 90 days' },
    { key: 'custom', label: 'Custom range' },
  ];

  const pick = (k: DateRangeKey) => {
    if (k === 'custom') {
      onChange({ ...value, range: 'custom' });
      return;
    }
    const days = k === '7d' ? 7 : k === '30d' ? 30 : 90;
    const end = new Date();
    const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
    onChange({
      ...value,
      range: k,
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    });
    setOpen(false);
  };

  const labelFor = (v: FilterValue) => options.find((o) => o.key === v.range)?.label ?? 'Date range';

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-9 items-center gap-2 rounded-lg border border-border bg-background pl-3 pr-2.5 text-sm transition-colors',
          'hover:border-foreground/20 hover:bg-muted/40',
          open && 'border-primary/50',
        )}
      >
        <Calendar size={14} className="text-muted-foreground" />
        <span className="font-medium">{labelFor(value)}</span>
        <ChevronDown size={14} className="text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-64 rounded-xl border border-border bg-popover p-1.5 shadow-lg">
          {options.map((o) => (
            <button
              key={o.key}
              onClick={() => pick(o.key)}
              className={cn(
                'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors',
                'hover:bg-muted',
                value.range === o.key && 'bg-primary/10 text-primary',
              )}
            >
              {o.label}
              {value.range === o.key && <span className="text-xs">●</span>}
            </button>
          ))}
          {value.range === 'custom' && (
            <div className="border-t border-border/60 mt-1.5 p-2 space-y-2">
              <label className="block text-xs text-muted-foreground">Start</label>
              <input
                type="date"
                value={value.start_date?.slice(0, 10) ?? ''}
                onChange={(e) =>
                  onChange({ ...value, start_date: new Date(e.target.value).toISOString() })
                }
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              />
              <label className="block text-xs text-muted-foreground">End</label>
              <input
                type="date"
                value={value.end_date?.slice(0, 10) ?? ''}
                onChange={(e) =>
                  onChange({ ...value, end_date: new Date(e.target.value).toISOString() })
                }
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function UserSelect({
  value,
  onChange,
  users,
}: {
  value: FilterValue;
  onChange: (v: FilterValue) => void;
  users: UserOption[];
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = useMemo(() => {
    if (!query) return users;
    const q = query.toLowerCase();
    return users.filter((u) => u.user_email.toLowerCase().includes(q));
  }, [query, users]);

  const label = value.user_email === 'all' ? 'All users' : value.user_email;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-9 items-center gap-2 rounded-lg border border-border bg-background pl-3 pr-2.5 text-sm transition-colors max-w-[260px]',
          'hover:border-foreground/20 hover:bg-muted/40',
          value.user_email !== 'all' && 'border-primary/40 bg-primary/5',
        )}
      >
        <Users size={14} className="text-muted-foreground flex-shrink-0" />
        <span className="font-medium truncate">{label}</span>
        {value.user_email !== 'all' ? (
          <X
            size={13}
            className="text-muted-foreground hover:text-foreground flex-shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              onChange({ ...value, user_email: 'all' });
            }}
          />
        ) : (
          <ChevronDown size={14} className="text-muted-foreground flex-shrink-0" />
        )}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-72 rounded-xl border border-border bg-popover p-1.5 shadow-lg">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              placeholder="Search by email..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div className="mt-1.5 max-h-64 overflow-y-auto">
            <button
              onClick={() => {
                onChange({ ...value, user_email: 'all' });
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-muted',
                value.user_email === 'all' && 'bg-primary/10 text-primary',
              )}
            >
              <span className="font-medium">All users</span>
              <span className="text-xs text-muted-foreground">{users.length}</span>
            </button>
            <div className="my-1 border-t border-border/50" />
            {filtered.length === 0 && (
              <p className="px-2.5 py-2 text-sm text-muted-foreground">No matches.</p>
            )}
            {filtered.map((u) => (
              <button
                key={u.user_email}
                onClick={() => {
                  onChange({ ...value, user_email: u.user_email });
                  setOpen(false);
                  setQuery('');
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted',
                  value.user_email === u.user_email && 'bg-primary/10 text-primary',
                )}
              >
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

function WorkspaceSelect({
  value,
  onChange,
  workspaces,
}: {
  value: FilterValue;
  onChange: (v: FilterValue) => void;
  workspaces: WorkspaceOption[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const current = workspaces.find((w) => w.workspace_id === value.workspace_id);
  const label = value.workspace_id === 'all' ? 'All workspaces' : current?.workspace_name ?? value.workspace_id;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-9 items-center gap-2 rounded-lg border border-border bg-background pl-3 pr-2.5 text-sm transition-colors',
          'hover:border-foreground/20 hover:bg-muted/40',
          value.workspace_id !== 'all' && 'border-primary/40 bg-primary/5',
        )}
      >
        <Layers size={14} className="text-muted-foreground" />
        <span className="font-medium">{label}</span>
        <ChevronDown size={14} className="text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-56 rounded-xl border border-border bg-popover p-1.5 shadow-lg">
          <button
            onClick={() => {
              onChange({ ...value, workspace_id: 'all' });
              setOpen(false);
            }}
            className={cn(
              'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-muted',
              value.workspace_id === 'all' && 'bg-primary/10 text-primary',
            )}
          >
            All workspaces
          </button>
          <div className="my-1 border-t border-border/50" />
          {workspaces.map((w) => (
            <button
              key={w.workspace_id}
              onClick={() => {
                onChange({ ...value, workspace_id: w.workspace_id });
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-muted',
                value.workspace_id === w.workspace_id && 'bg-primary/10 text-primary',
              )}
            >
              <span className="truncate">{w.workspace_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Avatar({ email, size = 22 }: { email: string; size?: number }) {
  const initial = (email[0] ?? '?').toUpperCase();
  const colors = [
    'bg-rose-500',
    'bg-orange-500',
    'bg-amber-500',
    'bg-emerald-500',
    'bg-teal-500',
    'bg-sky-500',
    'bg-blue-500',
    'bg-indigo-500',
    'bg-violet-500',
    'bg-fuchsia-500',
  ];
  let hash = 0;
  for (let i = 0; i < email.length; i++) hash = (hash * 31 + email.charCodeAt(i)) | 0;
  const cls = colors[Math.abs(hash) % colors.length];
  return (
    <span
      className={cn(
        'flex flex-shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white',
        cls,
      )}
      style={{ width: size, height: size }}
    >
      {initial}
    </span>
  );
}
