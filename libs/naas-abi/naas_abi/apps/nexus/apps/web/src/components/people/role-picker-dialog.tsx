'use client';

import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import type { RoleOption } from '@/lib/member-roles';

/** What a group or policy is, under its name in a person's Role. */
export function roleHint(option: RoleOption): string | null {
  if (option.workspace) return option.administers ? 'Administers this workspace' : 'Works in this workspace';
  if (option.kind === 'level') return 'Level, in all their workspaces';
  if (option.kind === 'own') return 'Their membership here';
  if (option.kind === 'admins') return 'Administers it';
  return null;
}

/**
 * Add groups or policies to a person (Users › a person › Groups or Policies, the add button):
 * the ones they may be given, searched by name, one or several picked. A level replaces the
 * other one, so picking Members unpicks Viewers. `problemOf` says why the pick cannot be added
 * (what the API would refuse); a refusal of `onAdd` is said in the dialog.
 */
export function RolePickerDialog({
  open,
  title,
  options,
  onClose,
  onAdd,
  problemOf,
}: {
  open: boolean;
  title: string;
  options: RoleOption[];
  onClose: () => void;
  onAdd: (picked: RoleOption[]) => Promise<void>;
  problemOf?: (picked: RoleOption[]) => string | null;
}) {
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setPicked([]);
    setError('');
    setBusy(false);
  }, [open]);

  const shown = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return options.filter((o) => words.every((w) => o.name.toLowerCase().includes(w)));
  }, [options, query]);
  const chosen = options.filter((o) => picked.includes(o.id));
  const problem = chosen.length > 0 ? (problemOf?.(chosen) ?? null) : null;

  const toggle = (option: RoleOption, on: boolean) => {
    setError('');
    setPicked((current) => {
      if (!on) return current.filter((id) => id !== option.id);
      const levels = new Set(options.filter((o) => o.kind === 'level').map((o) => o.id));
      const kept = option.kind === 'level' ? current.filter((id) => !levels.has(id)) : current;
      return [...kept, option.id];
    });
  };

  const add = async () => {
    setBusy(true);
    setError('');
    try {
      await onAdd(chosen);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not add them');
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      title={title}
      onClose={onClose}
      data-role-picker=""
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => void add()} disabled={chosen.length === 0 || !!problem || busy} data-action="add-picked">
            {busy ? 'Adding…' : chosen.length > 1 ? `Add ${chosen.length}` : 'Add'}
          </Button>
        </>
      }
    >
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by name"
          aria-label="Search"
          className="h-9 pl-8"
          data-field="role-search"
        />
      </div>
      <ul className="max-h-72 overflow-y-auto border border-border" data-role-options="">
        {shown.length === 0 && (
          <li className="px-3 py-4 text-sm text-muted-foreground">
            {options.length === 0 ? 'Nothing more to add.' : 'Nothing matches.'}
          </li>
        )}
        {shown.map((option) => {
          const hint = roleHint(option);
          return (
            <li key={option.id} className="border-b border-border last:border-b-0" data-role-option={option.id}>
              <label className="flex cursor-pointer items-start gap-3 px-3 py-2 hover:bg-muted/50">
                <Checkbox
                  checked={picked.includes(option.id)}
                  onCheckedChange={(on) => toggle(option, on)}
                  aria-label={option.name}
                  disabled={busy}
                  className="mt-0.5"
                />
                <span className="min-w-0">
                  <span className="block truncate text-sm text-foreground">{option.name}</span>
                  {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      {(problem || error) && (
        <p className="text-xs text-destructive" role="alert" data-role-problem="">
          {error || problem}
        </p>
      )}
    </Dialog>
  );
}
