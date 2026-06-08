'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, ChevronDown, Search, Users, Layers, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Scenario, ScenarioId } from '../lib/types';

export interface FilterValue {
  scenario_id: ScenarioId;
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
  scenarios: Scenario[];
  users: UserOption[];
  workspaces: WorkspaceOption[];
}

export function FilterBar({ value, onChange, scenarios, users, workspaces }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <ScenarioPicker value={value} onChange={onChange} scenarios={scenarios} />
      <UserSelect value={value} onChange={onChange} users={users} />
      <WorkspaceSelect value={value} onChange={onChange} workspaces={workspaces} />
    </div>
  );
}

function ScenarioPicker({
  value,
  onChange,
  scenarios,
}: {
  value: FilterValue;
  onChange: (v: FilterValue) => void;
  scenarios: Scenario[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const current = scenarios.find((s) => s.scenario_id === value.scenario_id);
  const label = current?.scenario ?? 'Last 7 days';

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-9 items-center gap-2 border border-border bg-background pl-3 pr-2.5 text-sm transition-colors',
          'hover:border-foreground/20 hover:bg-muted/40',
          open && 'border-workspace-accent',
        )}
      >
        <Calendar size={14} className="text-muted-foreground" />
        <span className="font-medium">{label}</span>
        <ChevronDown size={14} className="text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-64 border border-border bg-popover p-1.5 shadow-lg">
          {scenarios.map((s) => (
            <button
              key={s.scenario_id}
              onClick={() => {
                onChange({ ...value, scenario_id: s.scenario_id });
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between px-2.5 py-2 text-sm transition-colors',
                'hover:bg-muted',
                value.scenario_id === s.scenario_id && 'bg-workspace-accent-10 text-workspace-accent',
              )}
            >
              {s.scenario}
              {value.scenario_id === s.scenario_id && <span className="text-xs">●</span>}
            </button>
          ))}
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
          'flex h-9 items-center gap-2 border border-border bg-background pl-3 pr-2.5 text-sm transition-colors max-w-[260px]',
          'hover:border-foreground/20 hover:bg-muted/40',
          value.user_email !== 'all' && 'border-workspace-accent bg-workspace-accent-5',
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
        <div className="absolute left-0 top-full z-50 mt-1.5 w-72 border border-border bg-popover p-1.5 shadow-lg">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              placeholder="Search by email..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-9 w-full border border-border bg-background pl-8 pr-2 text-sm focus:outline-none focus:ring-2 focus:ring-workspace-accent/30"
            />
          </div>
          <div className="mt-1.5 max-h-64 overflow-y-auto">
            <button
              onClick={() => {
                onChange({ ...value, user_email: 'all' });
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between px-2.5 py-2 text-sm transition-colors hover:bg-muted',
                value.user_email === 'all' && 'bg-workspace-accent-10 text-workspace-accent',
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
                  'flex w-full items-center gap-2 px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted',
                  value.user_email === u.user_email && 'bg-workspace-accent-10 text-workspace-accent',
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
          'flex h-9 items-center gap-2 border border-border bg-background pl-3 pr-2.5 text-sm transition-colors max-w-[260px]',
          'hover:border-foreground/20 hover:bg-muted/40',
          value.workspace_id !== 'all' && 'border-workspace-accent bg-workspace-accent-5',
        )}
      >
        <Layers size={14} className="text-muted-foreground flex-shrink-0" />
        <span className="font-medium truncate">{label}</span>
        {value.workspace_id !== 'all' ? (
          <X
            size={13}
            className="text-muted-foreground hover:text-foreground flex-shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              onChange({ ...value, workspace_id: 'all' });
            }}
          />
        ) : (
          <ChevronDown size={14} className="text-muted-foreground flex-shrink-0" />
        )}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-56 border border-border bg-popover p-1.5 shadow-lg">
          <button
            onClick={() => {
              onChange({ ...value, workspace_id: 'all' });
              setOpen(false);
            }}
            className={cn(
              'flex w-full items-center justify-between px-2.5 py-2 text-sm transition-colors hover:bg-muted',
              value.workspace_id === 'all' && 'bg-workspace-accent-10 text-workspace-accent',
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
                'flex w-full items-center justify-between px-2.5 py-2 text-sm transition-colors hover:bg-muted',
                value.workspace_id === w.workspace_id && 'bg-workspace-accent-10 text-workspace-accent',
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
