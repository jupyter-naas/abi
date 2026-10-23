'use client';

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Plus, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { OTHERS_GROUP } from '@/lib/workspace-picker';
import '@/components/shell/sidebar/ontology-picker.css';

const NO_GROUP_LABEL = `${OTHERS_GROUP} (no group)`;

type GroupRow =
  | { kind: 'none' }
  | { kind: 'existing'; name: string }
  | { kind: 'create'; name: string };

function buildRows(query: string, existingGroups: string[]): GroupRow[] {
  const q = query.trim().toLowerCase();
  const rows: GroupRow[] = [];
  if (
    !q ||
    NO_GROUP_LABEL.toLowerCase().includes(q) ||
    OTHERS_GROUP.toLowerCase().includes(q)
  ) {
    rows.push({ kind: 'none' });
  }
  for (const name of existingGroups) {
    if (!q || name.toLowerCase().includes(q)) {
      rows.push({ kind: 'existing', name });
    }
  }
  const trimmed = query.trim();
  if (
    trimmed &&
    !existingGroups.some((name) => name.toLowerCase() === trimmed.toLowerCase()) &&
    (!q || trimmed.toLowerCase().includes(q))
  ) {
    rows.push({ kind: 'create', name: trimmed });
  }
  return rows;
}

function rowKey(row: GroupRow, index: number): string {
  if (row.kind === 'none') return 'none';
  if (row.kind === 'existing') return `existing:${row.name}`;
  return `create:${row.name}:${index}`;
}

function isRowSelected(row: GroupRow, value: string): boolean {
  const trimmed = value.trim();
  if (row.kind === 'none') return !trimmed;
  if (row.kind === 'existing') return row.name === trimmed;
  return row.kind === 'create' && row.name === trimmed;
}

export function WorkspaceGroupSelect({
  id,
  value,
  onChange,
  existingGroups,
  disabled,
}: {
  id?: string;
  value: string;
  onChange: (group: string) => void;
  existingGroups: string[];
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [box, setBox] = useState<{
    top: number;
    left: number;
    width: number;
    maxHeight: number;
  } | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  const rows = useMemo(() => buildRows(query, existingGroups), [query, existingGroups]);
  const optionCount = rows.length;
  const active = optionCount ? Math.min(activeIndex, optionCount - 1) : 0;

  const trimmedValue = value.trim();
  const triggerLabel = trimmedValue ? trimmedValue : NO_GROUP_LABEL;

  const close = useCallback((restoreFocus = false) => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
    if (restoreFocus) triggerRef.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    const anchor = wrapRef.current;
    if (!anchor) return;
    function position() {
      const rect = anchor?.getBoundingClientRect();
      if (!rect) return;
      const roomBelow = window.innerHeight - rect.bottom - 12;
      const roomAbove = rect.top - 12;
      const below = roomBelow >= 220 || roomBelow >= roomAbove;
      const maxHeight = Math.max(80, Math.min(448, below ? roomBelow : roomAbove));
      const width = Math.min(Math.max(rect.width, 280), window.innerWidth - 16);
      setBox({
        top: below ? rect.bottom + 4 : rect.top - maxHeight - 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
        width,
        maxHeight,
      });
    }
    position();
    const observer = new ResizeObserver(position);
    observer.observe(anchor);
    window.addEventListener('resize', position);
    const onScroll = (event: Event) => {
      if (!(event.target instanceof Node) || !popupRef.current?.contains(event.target)) position();
    };
    window.addEventListener('scroll', onScroll, true);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

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
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
    };
  }, [open, close]);

  useEffect(() => {
    if (open) {
      popupRef.current
        ?.querySelector<HTMLElement>(`[data-option-index="${active}"]`)
        ?.scrollIntoView({ block: 'nearest' });
    }
  }, [active, open]);

  function pick(index: number) {
    const row = rows[index];
    if (!row) return;
    if (row.kind === 'none') onChange('');
    else onChange(row.name);
    close(true);
  }

  return (
    <div ref={wrapRef} className="ontology-picker">
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          if (open) close();
          else {
            setQuery('');
            setActiveIndex(0);
            setOpen(true);
          }
        }}
        className={cn(
          'ontology-picker-trigger account-profile-field-input min-h-9 justify-between text-sm text-foreground',
          trimmedValue && 'is-filtered'
        )}
        aria-label={`Workspace group: ${triggerLabel}`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={open ? listId : undefined}
        title={triggerLabel}
      >
        <span className="ontology-picker-label">{triggerLabel}</span>
        <ChevronDown size={14} className="shrink-0 opacity-70" />
      </button>
      {open &&
        box &&
        createPortal(
          <div
            ref={popupRef}
            className="fixed z-[260] flex flex-col overflow-hidden border border-border bg-background shadow-xl"
            style={box}
          >
            <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background px-3 py-2">
              <Search size={14} className="shrink-0 text-muted-foreground opacity-70" />
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setActiveIndex(0);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    close(true);
                  } else if (event.key === 'Tab') {
                    close(true);
                  } else if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    setActiveIndex(Math.min(active + 1, Math.max(optionCount - 1, 0)));
                  } else if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    setActiveIndex(Math.max(active - 1, 0));
                  } else if (event.key === 'Enter' && optionCount) {
                    event.preventDefault();
                    pick(active);
                  }
                }}
                placeholder="Search or create group…"
                className="min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none focus-visible:ring-0 placeholder:text-muted-foreground"
                role="combobox"
                aria-label="Search workspace groups"
                aria-autocomplete="list"
                aria-expanded={open}
                aria-controls={listId}
                aria-activedescendant={optionCount ? `${listId}-${active}` : undefined}
              />
            </div>
            <div className="min-h-0 overflow-y-auto">
              <div id={listId} role="listbox" aria-label="Workspace group">
                {rows.map((row, index) => {
                  const checked = isRowSelected(row, value);
                  const label =
                    row.kind === 'none'
                      ? NO_GROUP_LABEL
                      : row.kind === 'existing'
                        ? row.name
                        : `Create “${row.name}”`;
                  return (
                    <button
                      key={rowKey(row, index)}
                      type="button"
                      role="option"
                      aria-selected={checked}
                      id={`${listId}-${index}`}
                      data-option-index={index}
                      tabIndex={-1}
                      title={label}
                      onMouseEnter={() => setActiveIndex(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => pick(index)}
                      className={cn(
                        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs',
                        active === index ? 'bg-muted' : 'hover:bg-muted/70',
                        row.kind === 'create' && 'text-workspace-accent'
                      )}
                    >
                      {row.kind === 'create' && (
                        <Plus size={14} className="shrink-0 opacity-80" aria-hidden />
                      )}
                      <span className="min-w-0 flex-1 truncate">{label}</span>
                      {checked && <Check size={14} className="shrink-0 text-workspace-accent" />}
                    </button>
                  );
                })}
              </div>
              {!rows.length && (
                <p role="status" className="px-3 py-4 text-xs text-muted-foreground">
                  Type a name to create a new group.
                </p>
              )}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
