'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface CheckboxFilterOption {
  uri: string;
  label: string;
  hint?: string;
}

function compactUri(uri: string): string {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

export function CheckboxFilter({
  label,
  loading,
  options,
  selected,
  onToggle,
  onSetSelected,
  requiredUris,
  minSelected,
  minSelectedWarning,
  emptyMessage,
}: {
  label: string;
  loading?: boolean;
  options: CheckboxFilterOption[];
  selected: string[];
  onToggle: (uri: string) => void;
  onSetSelected: (uris: string[]) => void;
  requiredUris?: string[];
  minSelected?: number;
  minSelectedWarning?: string;
  emptyMessage?: string;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const filtered = useMemo(() => {
    const t = filter.trim().toLowerCase();
    if (!t) return options;
    return options.filter(
      (o) => o.label.toLowerCase().includes(t) || o.uri.toLowerCase().includes(t)
    );
  }, [options, filter]);

  const required = useMemo(() => new Set(requiredUris ?? []), [requiredUris]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const visibleSelectedCount = filtered.reduce(
    (acc, o) => (selectedSet.has(o.uri) ? acc + 1 : acc),
    0
  );
  const allVisibleSelected =
    filtered.length > 0 && visibleSelectedCount === filtered.length;
  const noneVisibleSelected = visibleSelectedCount === 0;
  const indeterminate = !allVisibleSelected && !noneVisibleSelected;

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const handleSelectAllToggle = () => {
    if (allVisibleSelected) {
      const visibleUris = new Set(filtered.map((o) => o.uri));
      const next = selected.filter((uri) => !visibleUris.has(uri) || required.has(uri));
      onSetSelected(next);
    } else {
      const next = new Set(selected);
      for (const o of filtered) next.add(o.uri);
      onSetSelected(Array.from(next));
    }
  };

  const summary =
    selected.length === 0
      ? 'None'
      : options.length > 0 && selected.length === options.length
        ? 'All'
        : selected.length === 1
          ? options.find((o) => o.uri === selected[0])?.label ?? compactUri(selected[0])
          : `${selected.length} selected`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="flex w-full items-center justify-between rounded-md border bg-background px-3 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted/50"
      >
        <span className="flex min-w-0 items-center gap-2 truncate">
          <span className="shrink-0">{label}</span>
          <span className="truncate text-xs text-foreground/70">{summary}</span>
          {loading && <Loader2 size={12} className="shrink-0 animate-spin" />}
        </span>
        <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-full overflow-hidden rounded-md border bg-background shadow-lg">
          <div className="border-b p-2">
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter..."
              className="w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          {filtered.length > 0 && (
            <label className="flex cursor-pointer items-center gap-2 border-b bg-muted/40 px-3 py-1.5 text-xs font-medium hover:bg-muted">
              <input
                ref={selectAllRef}
                type="checkbox"
                checked={allVisibleSelected}
                onChange={handleSelectAllToggle}
                className="h-3 w-3"
              />
              <span className="flex-1">Select all</span>
              <span className="text-[10px] text-muted-foreground">
                {visibleSelectedCount} / {filtered.length}
              </span>
            </label>
          )}
          {minSelected !== undefined && selected.length < minSelected && minSelectedWarning && (
            <div className="flex items-center gap-1.5 border-b bg-amber-50 px-3 py-1.5 text-xs text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
              <AlertCircle size={12} />
              {minSelectedWarning}
            </div>
          )}
          <div className="max-h-56 overflow-y-auto py-1">
            {loading ? (
              <div className="flex items-center justify-center gap-2 px-3 py-4 text-xs text-muted-foreground">
                <Loader2 size={12} className="animate-spin" />
                Loading…
              </div>
            ) : filtered.length === 0 ? (
              <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                {emptyMessage ?? 'No options'}
              </p>
            ) : (
              filtered.map((opt) => {
                const isChecked = selectedSet.has(opt.uri);
                const isRequired = required.has(opt.uri);
                return (
                  <label
                    key={opt.uri}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 px-3 py-1 text-xs hover:bg-muted',
                      isRequired && 'opacity-90'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isRequired}
                      onChange={() => onToggle(opt.uri)}
                      className="h-3 w-3"
                    />
                    <span className="flex-1 truncate" title={opt.uri}>
                      {opt.label}
                    </span>
                    {opt.hint && (
                      <span className="text-[10px] text-muted-foreground">{opt.hint}</span>
                    )}
                  </label>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
