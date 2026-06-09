'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Loader2, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

export interface SearchableOption {
  uri: string;
  label: string;
  hint?: string;
}

export interface ApiRangeOption {
  uri: string;
  label: string;
  kind: 'class' | 'individual';
}

export interface ApiClassObjectProperty {
  uri: string;
  label: string;
  range_options: ApiRangeOption[];
}

export interface ApiRelationTarget {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
}

const RELATION_TARGET_SEARCH_DEBOUNCE_MS = 300;

function TargetOptionDisplay({ label, uri }: { label: string; uri: string }) {
  const showUri = Boolean(uri) && label !== uri;
  return (
    <span className="min-w-0 flex-1 text-left">
      <span className="block truncate">{label}</span>
      {showUri ? (
        <span className="mt-0.5 block truncate font-mono text-[10px] leading-tight text-muted-foreground">
          {uri}
        </span>
      ) : null}
    </span>
  );
}

export function SearchablePicker({
  value,
  options,
  disabled,
  loading,
  placeholder,
  searchPlaceholder,
  emptyMessage,
  onChange,
  className,
}: {
  value: string;
  options: SearchableOption[];
  disabled?: boolean;
  loading?: boolean;
  placeholder: string;
  searchPlaceholder: string;
  emptyMessage: string;
  onChange: (uri: string) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number; width: number } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const selected = useMemo(
    () => options.find((option) => option.uri === value) ?? null,
    [options, value],
  );

  useEffect(() => {
    if (open) {
      setQuery('');
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setPopoverPos(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const reposition = () => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(q) ||
        option.uri.toLowerCase().includes(q) ||
        (option.hint?.toLowerCase().includes(q) ?? false),
    );
  }, [options, query]);

  const handlePick = (uri: string) => {
    setOpen(false);
    if (uri !== value) onChange(uri);
  };

  return (
    <div className={cn('relative min-w-0 flex-1', className)}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled || loading}
        onClick={() => {
          if (disabled || loading) return;
          setOpen((v) => !v);
        }}
        className={cn(
          'flex w-full items-center justify-between rounded border bg-background px-2 py-1.5 text-sm outline-none',
          'focus:ring-1 focus:ring-primary',
          (disabled || loading) && 'cursor-not-allowed opacity-50',
        )}
      >
        <span className={cn('truncate text-left', !selected && 'text-muted-foreground')}>
          {loading ? 'Loading...' : selected ? selected.label : placeholder}
        </span>
        {loading ? (
          <Loader2 size={14} className="shrink-0 animate-spin text-muted-foreground" />
        ) : (
          <ChevronDown
            size={14}
            className={cn('shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
          />
        )}
      </button>

      {open && popoverPos && typeof document !== 'undefined' && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <div
            style={{ top: popoverPos.top, left: popoverPos.left, width: popoverPos.width }}
            className="fixed z-[9999] rounded-md border border-border bg-popover p-1 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative mb-1">
              <Search
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (filtered.length > 0) handlePick(filtered[0].uri);
                  } else if (e.key === 'Escape') {
                    setOpen(false);
                  }
                }}
                placeholder={searchPlaceholder}
                className="w-full rounded border-0 bg-muted py-2 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-primary/30"
              />
            </div>
            <div className="max-h-60 overflow-y-auto">
              {filtered.map((option) => {
                const isSelected = option.uri === value;
                return (
                  <button
                    key={option.uri}
                    type="button"
                    onClick={() => handlePick(option.uri)}
                    title={option.uri}
                    className="flex w-full items-center justify-between gap-2 rounded px-3 py-2 text-left text-sm hover:bg-accent"
                  >
                    <span className="min-w-0 truncate">
                      {option.label}
                      {option.hint ? (
                        <span className="ml-1 text-muted-foreground">({option.hint})</span>
                      ) : null}
                    </span>
                    {isSelected && <Check size={14} className="shrink-0 text-muted-foreground" />}
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="px-3 py-2 text-sm text-muted-foreground">{emptyMessage}</p>
              )}
            </div>
          </div>
        </>,
        document.body,
      )}
    </div>
  );
}

export function RelationTargetPicker({
  predicateUri,
  property,
  value,
  graphUri,
  workspaceId,
  disabled,
  onChange,
  className,
}: {
  predicateUri: string;
  property: ApiClassObjectProperty | undefined;
  value: string;
  graphUri: string;
  workspaceId: string;
  disabled?: boolean;
  onChange: (targetUri: string) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [targets, setTargets] = useState<ApiRelationTarget[]>([]);
  const [loading, setLoading] = useState(false);
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number; width: number } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(query), RELATION_TARGET_SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!open || !graphUri || !predicateUri || !property) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    void authFetch(`${getApiUrl()}/api/graph/discovery/relation-targets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        graph_uri: graphUri,
        range_class_uris: property.range_options
          .filter((option) => option.kind === 'class')
          .map((option) => option.uri),
        individual_uris: property.range_options
          .filter((option) => option.kind === 'individual')
          .map((option) => option.uri),
        search: debouncedQuery,
        limit: 300,
      }),
    })
      .then(async (res) => {
        if (cancelled) return;
        if (res.ok) {
          const data = (await res.json()) as ApiRelationTarget[];
          setTargets(Array.isArray(data) ? data : []);
        } else {
          setTargets([]);
        }
      })
      .catch(() => {
        if (!cancelled) setTargets([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, graphUri, predicateUri, property, workspaceId, debouncedQuery]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setDebouncedQuery('');
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setPopoverPos(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const reposition = () => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open]);

  const options = useMemo(() => {
    const mapped = targets.map((target) => ({
      uri: target.uri,
      label: target.label,
      hint: target.class_label || undefined,
    }));
    if (value && !mapped.some((option) => option.uri === value)) {
      mapped.unshift({ uri: value, label: value, hint: undefined });
    }
    return mapped;
  }, [targets, value]);

  const selected = options.find((option) => option.uri === value) ?? null;

  const handlePick = (uri: string) => {
    setOpen(false);
    if (uri !== value) onChange(uri);
  };

  return (
    <div className={cn('relative min-w-0 flex-[2]', className)}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled || !predicateUri}
        onClick={() => {
          if (disabled || !predicateUri) return;
          setOpen((v) => !v);
        }}
        className={cn(
          'flex w-full items-start justify-between rounded border bg-background px-2 py-1.5 text-sm outline-none',
          'focus:ring-1 focus:ring-primary',
          (disabled || !predicateUri) && 'cursor-not-allowed opacity-50',
        )}
      >
        <span className={cn('min-w-0 flex-1 text-left', !selected && 'text-muted-foreground')}>
          {selected ? (
            <TargetOptionDisplay label={selected.label} uri={selected.uri} />
          ) : (
            <span className="block truncate">Search and select target</span>
          )}
        </span>
        <ChevronDown
          size={14}
          className={cn('mt-0.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
        />
      </button>

      {open && popoverPos && typeof document !== 'undefined' && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <div
            style={{ top: popoverPos.top, left: popoverPos.left, width: popoverPos.width }}
            className="fixed z-[9999] rounded-md border border-border bg-popover p-1 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative mb-1">
              <Search
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (options.length > 0) handlePick(options[0].uri);
                  } else if (e.key === 'Escape') {
                    setOpen(false);
                  }
                }}
                placeholder="Search target individuals..."
                className="w-full rounded border-0 bg-muted py-2 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-primary/30"
              />
            </div>
            <div className="max-h-60 overflow-y-auto">
              {loading ? (
                <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                  <Loader2 size={14} className="animate-spin" />
                  Searching...
                </div>
              ) : (
                <>
                  {options.map((option) => {
                    const isSelected = option.uri === value;
                    return (
                      <button
                        key={option.uri}
                        type="button"
                        onClick={() => handlePick(option.uri)}
                        title={option.uri}
                        className="flex w-full items-start justify-between gap-2 rounded px-3 py-2 text-left text-sm hover:bg-accent"
                      >
                        <TargetOptionDisplay label={option.label} uri={option.uri} />
                        {isSelected && <Check size={14} className="mt-0.5 shrink-0 text-muted-foreground" />}
                      </button>
                    );
                  })}
                  {options.length === 0 && (
                    <p className="px-3 py-2 text-sm text-muted-foreground">No matching individuals</p>
                  )}
                </>
              )}
            </div>
          </div>
        </>,
        document.body,
      )}
    </div>
  );
}
