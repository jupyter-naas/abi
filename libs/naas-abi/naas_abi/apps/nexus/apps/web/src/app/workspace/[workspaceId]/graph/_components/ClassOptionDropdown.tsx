'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { OntologyClassOption } from './types';

export interface ClassOptionDropdownProps {
  options: OntologyClassOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}

export function ClassOptionDropdown({
  options,
  value,
  onChange,
  placeholder,
  disabled = false,
}: ClassOptionDropdownProps) {
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
    if (!t) return options;
    return options.filter(
      (option) =>
        option.name.toLowerCase().includes(t) ||
        option.description.toLowerCase().includes(t),
    );
  }, [options, searchQuery]);

  const selected = options.find((option) => option.id === value);
  const selectedDisplay = selected
    ? selected.description
      ? `${selected.name}: ${selected.description}`
      : selected.name
    : '';

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((prev) => !prev)}
        disabled={disabled}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-background px-3 py-2 text-left text-sm outline-none focus:ring-2 focus:ring-primary',
          'hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-60',
        )}
      >
        <span className={cn('line-clamp-2 break-words', !value && 'text-muted-foreground')}>
          {selectedDisplay || placeholder}
        </span>
        <ChevronDown size={14} className={cn('shrink-0 text-muted-foreground', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full max-h-64 overflow-hidden rounded-lg border bg-background shadow-lg">
          <div className="sticky top-0 border-b bg-background p-2">
            <input
              type="text"
              placeholder="Search class..."
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
              className={cn('w-full px-3 py-2 text-left text-sm hover:bg-muted', !value && 'bg-muted')}
            >
              <span className="text-muted-foreground">{placeholder}</span>
            </button>
            {filtered.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => {
                  onChange(option.id);
                  setOpen(false);
                  setSearchQuery('');
                }}
                className={cn(
                  'w-full px-3 py-2 text-left text-sm hover:bg-muted',
                  value === option.id && 'bg-muted',
                )}
              >
                <span className="block break-words">
                  {option.name}
                  {option.description ? `: ${option.description}` : ''}
                </span>
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
