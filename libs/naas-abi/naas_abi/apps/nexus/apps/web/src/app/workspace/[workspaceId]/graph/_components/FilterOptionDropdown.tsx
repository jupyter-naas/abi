'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FilterOption } from './types';

export interface FilterOptionDropdownProps {
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}

export function FilterOptionDropdown({
  options,
  value,
  onChange,
  placeholder,
}: FilterOptionDropdownProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
        setSearchQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    const t = searchQuery.trim().toLowerCase();
    const list = !t
      ? options
      : options.filter(
          (o) => o.label.toLowerCase().includes(t) || o.uri.toLowerCase().includes(t),
        );
    if (value && !list.some((o) => o.uri === value)) {
      const sel = options.find((o) => o.uri === value);
      if (sel) return [sel, ...list];
    }
    return list;
  }, [options, searchQuery, value]);

  const selected = options.find((o) => o.uri === value);
  const displayLabel = selected ? selected.label : '';

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary',
          'hover:bg-muted/50',
        )}
      >
        <span className={cn('truncate', !value && 'text-muted-foreground')}>
          {displayLabel || placeholder}
        </span>
        <ChevronDown size={14} className={cn('shrink-0 text-muted-foreground', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full min-w-[16rem] max-h-64 overflow-hidden rounded-lg border bg-background shadow-lg">
          <div className="sticky top-0 border-b bg-background p-2">
            <input
              type="text"
              placeholder={`Search ${placeholder.toLowerCase()}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              autoFocus
            />
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setOpen(false);
                setSearchQuery('');
              }}
              className={cn(
                'flex w-full items-center px-3 py-2 text-left text-sm',
                'hover:bg-muted',
                !value && 'bg-muted',
              )}
            >
              <span className="text-muted-foreground">{placeholder}</span>
            </button>
            {filtered.map((option) => (
              <button
                key={option.uri}
                type="button"
                onClick={() => {
                  onChange(option.uri);
                  setOpen(false);
                  setSearchQuery('');
                }}
                className={cn(
                  'flex w-full items-center px-3 py-2 text-left text-sm',
                  'hover:bg-muted',
                  value === option.uri && 'bg-muted',
                )}
              >
                <span className="truncate">{option.label}</span>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                No matches for &quot;{searchQuery}&quot;
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
