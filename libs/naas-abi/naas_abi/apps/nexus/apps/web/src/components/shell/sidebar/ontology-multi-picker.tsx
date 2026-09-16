'use client';

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import './ontology-picker.css';

export type OntologyPickerOption = { value: string; label: string; detail?: string; title?: string };

/** Shared keyboard-accessible, cumulative picker for ontology files and systems. */
export function OntologyMultiPicker({ items, value, onToggle, onClear, loading, error, label, allLabel, noun, arrowOnly = false, popupAnchorRef }: {
  items: OntologyPickerOption[];
  value: string[];
  onToggle: (value: string) => void;
  onClear: () => void;
  loading: boolean;
  error: string | null;
  label: string;
  allLabel: string;
  noun: string;
  arrowOnly?: boolean;
  popupAnchorRef?: RefObject<HTMLElement>;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [box, setBox] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const options = useMemo(() => items.filter(item => `${item.label} ${item.detail || ''}`.toLowerCase().includes(query.trim().toLowerCase())), [items, query]);
  const available = !loading && !error;
  const optionCount = 1 + (available ? options.length : 0);
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
    if (index === 0) onClear();
    else if (available && options[index - 1]) onToggle(options[index - 1].value);
  }

  return <div ref={wrapRef} className={cn('ontology-picker', arrowOnly && 'ontology-picker--arrow')}>
    <button ref={triggerRef} type="button" onClick={() => { if (open) close(); else { setQuery(''); setActiveIndex(0); setOpen(true); } }}
      className={cn('ontology-picker-trigger', value.length > 0 && 'is-filtered')}
      aria-label={`Filter ${noun}: ${label}`} aria-expanded={open} aria-haspopup="listbox" aria-controls={open ? listId : undefined}
      title={label}>
      {!arrowOnly && <span className="ontology-picker-label">{label}</span>}<ChevronDown size={14} className="shrink-0 opacity-70" />
    </button>
    {open && box && createPortal(<div ref={popupRef} className="fixed z-[260] flex flex-col overflow-hidden border border-border bg-background shadow-xl" style={box}>
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background px-3 py-2">
        <Search size={14} className="shrink-0 text-muted-foreground opacity-70" />
        <input ref={searchRef} value={query} onChange={event => { setQuery(event.target.value); setActiveIndex(0); }}
          onKeyDown={event => {
            if (event.key === 'Escape') { event.preventDefault(); close(true); }
            else if (event.key === 'Tab') close(true);
            else if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex(Math.min(active + 1, optionCount - 1)); }
            else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex(Math.max(active - 1, 0)); }
            else if (event.key === 'Enter') { event.preventDefault(); pick(active); }
          }}
          placeholder={`Search ${noun}…`} className="min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none focus-visible:ring-0 placeholder:text-muted-foreground"
          role="combobox" aria-label={`Search ${noun}`} aria-autocomplete="list" aria-expanded={open} aria-controls={listId} aria-activedescendant={`${listId}-${active}`} />
      </div>
      <div className="min-h-0 overflow-y-auto">
        <div id={listId} role="listbox" aria-label={noun} aria-multiselectable="true">
          <button type="button" role="option" aria-selected={!value.length} id={`${listId}-0`} data-option-index={0} tabIndex={-1}
            onMouseEnter={() => setActiveIndex(0)} onMouseDown={event => event.preventDefault()} onClick={onClear}
            className={cn('flex w-full items-center gap-2 border-b border-border px-3 py-1.5 text-left text-xs', active === 0 ? 'bg-muted' : 'hover:bg-muted/70')}>
            <span className="flex-1">{allLabel}</span>{!value.length && <Check size={14} className="text-workspace-accent" />}
          </button>
          {available && options.map((item, index) => {
            const checked = value.includes(item.value);
            return <button key={item.value} type="button" role="option" aria-selected={checked} id={`${listId}-${index + 1}`} data-option-index={index + 1} tabIndex={-1}
              title={item.title || item.label} onMouseEnter={() => setActiveIndex(index + 1)} onMouseDown={event => event.preventDefault()} onClick={() => onToggle(item.value)}
              className={cn('flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs', active === index + 1 ? 'bg-muted' : 'hover:bg-muted/70')}>
              <span className="min-w-0 flex-1"><span className="block truncate">{item.label}</span>{item.detail && <span className="block truncate text-[11px] text-muted-foreground">{item.detail}</span>}</span>
              <span aria-hidden="true" className={cn('flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border', checked ? 'border-workspace-accent text-workspace-accent' : 'border-muted-foreground/50')}>
                {checked && <Check size={12} />}
              </span>
            </button>;
          })}
        </div>
        {loading ? <p role="status" className="px-3 py-4 text-xs text-muted-foreground">Loading {noun}…</p>
          : error ? <p role="alert" className="px-3 py-4 text-xs text-destructive">{error}</p>
          : !options.length && <p role="status" className="px-3 py-4 text-xs text-muted-foreground">No matching {noun}.</p>}
        {available && unavailableCount > 0 && <p role="status" className="border-t px-3 py-2 text-xs text-muted-foreground">{unavailableCount} selected {noun} unavailable. Choose {allLabel} to reset.</p>}
      </div>
    </div>, document.body)}
  </div>;
}
