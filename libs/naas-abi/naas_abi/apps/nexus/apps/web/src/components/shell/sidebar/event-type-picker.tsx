'use client';

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EventTypeOption } from '@/stores/events';
import { eventTypeOptions, eventTypeTriggerLabel } from './event-type-options';

/**
 * Event-type filter for the Events column. Same trigger, portaled list,
 * sticky search row and option rows as QuickOpen in the top nav
 * (../quick-open.tsx) — keep the two visually in step.
 */
export function EventTypePicker({
  types,
  value,
  onChange,
}: {
  types: readonly EventTypeOption[];
  value: string;
  onChange: (uri: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
  const [listBox, setListBox] = useState<{ top: number; left: number; width: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const options = useMemo(() => eventTypeOptions(types, query), [types, query]);

  useEffect(() => {
    setMounted(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
  }, []);

  const openList = useCallback(() => {
    setOpen(true);
    setQuery('');
    // Land on the current value so Enter is a no-op, not a silent change.
    setActiveIndex(Math.max(0, eventTypeOptions(types, '').findIndex((o) => o.value === value)));
  }, [types, value]);

  useLayoutEffect(() => {
    if (!open || !wrapRef.current) {
      setListBox(null);
      return;
    }
    const rect = wrapRef.current.getBoundingClientRect();
    setListBox({ top: rect.bottom + 4, left: rect.left, width: rect.width });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (wrapRef.current?.contains(target) || listRef.current?.contains(target)) return;
      close();
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>(`[data-event-type-index="${activeIndex}"]`);
    node?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  const pick = (uri: string) => {
    onChange(uri);
    close();
  };

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(options.length - 1, 0)));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const option = options[activeIndex];
      if (option) pick(option.value);
    }
  };

  const triggerLabel = eventTypeTriggerLabel(types, value);

  return (
    <div ref={wrapRef} className="relative w-full">
      <button
        type="button"
        onClick={() => (open ? close() : openList())}
        className={cn(
          'flex h-7 w-full items-center gap-2 rounded-md px-2.5 text-sm transition-colors hover:bg-muted/70 hover:text-foreground',
          value ? 'text-foreground' : 'text-muted-foreground',
        )}
        title="Filter by event type (server-side: returns the last N of this type)"
        aria-label={`Event type: ${triggerLabel}`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls="event-type-list"
      >
        <span className="min-w-0 flex-1 truncate text-left">{triggerLabel}</span>
        <ChevronDown size={14} className="shrink-0 opacity-70" />
      </button>

      {open && mounted
        ? createPortal(
            <div
              id="event-type-list"
              ref={listRef}
              role="listbox"
              className="fixed z-[260] max-h-[min(28rem,70vh)] overflow-y-auto border border-border bg-background shadow-xl"
              style={{
                top: listBox?.top ?? 56,
                left: listBox?.left ?? 0,
                width: listBox?.width ?? 280,
              }}
            >
              <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-background px-3 py-2">
                <Search size={14} className="shrink-0 opacity-70 text-muted-foreground" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActiveIndex(0);
                  }}
                  onKeyDown={onInputKeyDown}
                  placeholder="Search event types"
                  className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none focus-visible:ring-0 placeholder:text-muted-foreground"
                  aria-label="Search event types"
                  aria-autocomplete="list"
                  aria-controls="event-type-list"
                />
              </div>
              {options.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">No matches</p>
              ) : (
                <div>
                  <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Event types
                  </div>
                  {options.map((option, index) => {
                    const active = index === activeIndex;
                    return (
                      <button
                        key={option.value || 'all'}
                        type="button"
                        role="option"
                        aria-selected={option.value === value}
                        data-event-type-index={index}
                        onMouseEnter={() => setActiveIndex(index)}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => pick(option.value)}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm',
                          active ? 'bg-muted text-foreground' : 'text-foreground/90 hover:bg-muted/70',
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">{option.label}</span>
                        {option.value === value ? (
                          <Check size={14} className="shrink-0 text-workspace-accent" />
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
