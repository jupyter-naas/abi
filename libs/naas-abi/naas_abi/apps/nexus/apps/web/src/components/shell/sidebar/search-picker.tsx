'use client';

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import './search-picker.css';

export type SearchPickerOption = { value: string; label: string; detail?: string; title?: string };

/**
 * A keyboard-accessible picker with a search box, shared across the app: cumulative (ontology
 * files, systems and types; tasks; maps) or, ``single``, one choice (the Files Drive and View
 * pickers, the Settings column's Organization and Workspace): picking closes it and the choice
 * is checked, not ticked. Without ``allLabel`` there is no All row.
 */
export function SearchPicker({ items, value, onToggle, onClear, loading, error, label, allLabel, noun, arrowOnly = false, popupAnchorRef, action, single = false, ariaLabel, size = 'xs' }: {
  items: SearchPickerOption[];
  value: string[];
  onToggle: (value: string) => void;
  onClear: () => void;
  loading: boolean;
  error: string | null;
  label: string;
  /** The first row, choosing none (All …); without it, a choice among ``items`` only. */
  allLabel?: string;
  noun: string;
  arrowOnly?: boolean;
  popupAnchorRef?: RefObject<HTMLElement>;
  action?: { label: string; onClick: () => void };
  /** The text size: `xs` in the sidebar's sections, `sm` as the pages' text (Settings' level pickers). */
  size?: 'xs' | 'sm';
  single?: boolean;
  /** The trigger's name before its label (default ``Filter <noun>``). */
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [box, setBox] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const actionRef = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const options = useMemo(() => items.filter(item => `${item.label} ${item.detail || ''}`.toLowerCase().includes(query.trim().toLowerCase())), [items, query]);
  const available = !error && items.length > 0;
  // The row index of the first item: after the All row, when there is one.
  const base = allLabel === undefined ? 0 : 1;
  const optionCount = base + (available ? options.length : 0);
  const active = Math.min(activeIndex, optionCount - 1);
  const unavailableCount = value.filter(value => !items.some(item => item.value === value)).length;

  const close = useCallback((restoreFocus = false) => {
    setOpen(false); setQuery(''); setActiveIndex(0);
    if (restoreFocus) triggerRef.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    const anchor = popupAnchorRef?.current || wrapRef.current;
    if (!anchor) return;
    function position() {
      const rect = anchor?.getBoundingClientRect();
      if (!rect) return;
      const roomBelow = window.innerHeight - rect.bottom - 12;
      const roomAbove = rect.top - 12;
      const below = roomBelow >= 220 || roomBelow >= roomAbove;
      const maxHeight = Math.max(80, Math.min(448, below ? roomBelow : roomAbove));
      const width = Math.min(rect.width, window.innerWidth - 16);
      setBox({ top: below ? rect.bottom + 4 : rect.top - maxHeight - 4, left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)), width, maxHeight });
    }
    position();
    const observer = new ResizeObserver(position);
    observer.observe(anchor);
    window.addEventListener('resize', position);
    const onScroll = (event: Event) => { if (!(event.target instanceof Node) || !popupRef.current?.contains(event.target)) position(); };
    window.addEventListener('scroll', onScroll, true);
    return () => { observer.disconnect(); window.removeEventListener('resize', position); window.removeEventListener('scroll', onScroll, true); };
  }, [open, popupAnchorRef]);

  const positioned = box !== null;
  useEffect(() => {
    if (!open || !positioned) return;
    searchRef.current?.focus();
  }, [open, positioned]);

  useEffect(() => {
    if (!open) return;
    const outside = (event: Event) => {
      const target = event.target as Node;
      if (!wrapRef.current?.contains(target) && !popupRef.current?.contains(target)) close();
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('focusin', outside); };
  }, [open, close]);

  useEffect(() => {
    if (open) popupRef.current?.querySelector<HTMLElement>(`[data-option-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active, open]);

  function pick(index: number) {
    if (base === 1 && index === 0) onClear();
    else if (available && options[index - base]) onToggle(options[index - base].value);
    else return;
    if (single) close(true);
  }

  return <div ref={wrapRef} className={cn('search-picker', arrowOnly && 'search-picker--arrow')}>
    <button ref={triggerRef} type="button" onClick={() => { if (open) close(); else { setQuery(''); setActiveIndex(0); setOpen(true); } }}
      className={cn('search-picker-trigger', size === 'sm' && 'search-picker-trigger--sm', value.length > 0 && 'is-filtered')}
      aria-label={`${ariaLabel ?? `Filter ${noun}`}: ${label}`} aria-expanded={open} aria-haspopup="listbox" aria-controls={open ? listId : undefined}
      title={label}>
      {!arrowOnly && <span className="search-picker-label">{label}</span>}<ChevronDown size={14} className="shrink-0 opacity-70" />
    </button>
    {open && box && createPortal(<div ref={popupRef} className="fixed z-[260] flex flex-col overflow-hidden border border-border bg-background shadow-xl" style={box}>
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background px-3 py-2">
        <Search size={14} className="shrink-0 text-muted-foreground opacity-70" />
        <input ref={searchRef} value={query} onChange={event => { setQuery(event.target.value); setActiveIndex(0); }}
          onKeyDown={event => {
            if (event.key === 'Escape') { event.preventDefault(); close(true); }
            else if (event.key === 'Tab') {
              if (action && !event.shiftKey) { event.preventDefault(); actionRef.current?.focus(); }
              else close(true);
            }
            else if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex(Math.min(active + 1, Math.max(optionCount - 1, 0))); }
            else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex(Math.max(active - 1, 0)); }
            else if (event.key === 'Enter') { event.preventDefault(); pick(active); }
          }}
          placeholder={`Search ${noun}…`} className={cn('min-w-0 flex-1 bg-transparent text-foreground outline-none focus-visible:ring-0 placeholder:text-muted-foreground', size === 'sm' ? 'text-sm' : 'text-xs')}
          role="combobox" aria-label={`Search ${noun}`} aria-autocomplete="list" aria-expanded={open} aria-controls={listId} aria-activedescendant={`${listId}-${active}`} />
      </div>
      <div className="min-h-0 overflow-y-auto">
        <div id={listId} role="listbox" aria-label={noun} aria-multiselectable={!single}>
          {allLabel !== undefined && <button type="button" role="option" aria-selected={!value.length} id={`${listId}-0`} data-option-index={0} tabIndex={-1}
            onMouseEnter={() => setActiveIndex(0)} onMouseDown={event => event.preventDefault()} onClick={() => pick(0)}
            className={cn('flex w-full items-center gap-2 border-b border-border px-3 py-1.5 text-left', size === 'sm' ? 'text-sm' : 'text-xs', active === 0 ? 'bg-muted' : 'hover:bg-muted/70')}>
            <span className="flex-1">{allLabel}</span>{!value.length && <Check size={14} className="text-workspace-accent" />}
          </button>}
          {available && options.map((item, index) => {
            const checked = value.includes(item.value);
            return <button key={item.value} type="button" role="option" aria-selected={checked} id={`${listId}-${index + base}`} data-option-index={index + base} tabIndex={-1}
              title={item.title || item.label} onMouseEnter={() => setActiveIndex(index + base)} onMouseDown={event => event.preventDefault()} onClick={() => pick(index + base)}
              className={cn('flex w-full items-center gap-2 px-3 py-1.5 text-left', size === 'sm' ? 'text-sm' : 'text-xs', active === index + base ? 'bg-muted' : 'hover:bg-muted/70')}>
              <span className="min-w-0 flex-1"><span className="block truncate">{item.label}</span>{item.detail && <span className="block truncate text-[11px] text-muted-foreground">{item.detail}</span>}</span>
              {single ? checked && <Check size={14} className="text-workspace-accent" />
                : <span aria-hidden="true" className={cn('flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border', checked ? 'border-workspace-accent text-workspace-accent' : 'border-muted-foreground/50')}>
                  {checked && <Check size={12} />}
                </span>}
            </button>;
          })}
        </div>
        {error ? <p role="alert" className="px-3 py-4 text-xs text-destructive">{error}</p>
          : loading && !items.length ? <p role="status" className="px-3 py-4 text-xs text-muted-foreground">Loading {noun}…</p>
          : !options.length && <p role="status" className="px-3 py-4 text-xs text-muted-foreground">No matching {noun}.</p>}
        {available && unavailableCount > 0 && <p role="status" className="border-t px-3 py-2 text-xs text-muted-foreground">{unavailableCount} selected {noun} unavailable. {allLabel !== undefined && `Choose ${allLabel} to reset.`}</p>}
      </div>
      {action && <button ref={actionRef} type="button" className="search-picker-action"
        onKeyDown={event => {
          if (event.key === 'Escape') { event.preventDefault(); close(true); }
          else if (event.key === 'Tab' && event.shiftKey) { event.preventDefault(); searchRef.current?.focus(); }
        }}
        onClick={() => { close(true); action.onClick(); }}>{action.label}</button>}
    </div>, document.body)}
  </div>;
}
