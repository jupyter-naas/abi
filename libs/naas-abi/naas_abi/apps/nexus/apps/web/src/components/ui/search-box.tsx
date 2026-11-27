'use client';

import { forwardRef } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * The one search field. Bordered, the border stays neutral on focus (no accent ring), a
 * clear button once there is text, and Escape clears it (an empty field lets Escape
 * through, so a dialog or a menu around it still closes).
 */
export const SearchBox = forwardRef<
  HTMLInputElement,
  {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    /** Accessible name; defaults to the placeholder. */
    label?: string;
    size?: 'sm' | 'md';
    autoFocus?: boolean;
    className?: string;
    onKeyDown?: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  }
>(function SearchBox(
  { value, onChange, placeholder = 'Search…', label, size = 'md', autoFocus, className, onKeyDown },
  ref
) {
  return (
    <label
      className={cn(
        'flex min-w-0 items-center gap-2 border border-input bg-background text-muted-foreground',
        size === 'sm' ? 'h-8 px-2 text-xs' : 'h-9 px-3 text-sm',
        className
      )}
    >
      <Search size={size === 'sm' ? 12 : 14} aria-hidden="true" className="shrink-0" />
      <input
        ref={ref}
        type="search"
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && value) {
            event.preventDefault();
            onChange('');
          }
          onKeyDown?.(event);
        }}
        placeholder={placeholder}
        aria-label={label ?? placeholder}
        className="min-w-0 flex-1 border-0 bg-transparent p-0 text-foreground shadow-none outline-none ring-0 placeholder:text-muted-foreground focus:outline-none focus:ring-0 focus-visible:ring-0 [&::-webkit-search-cancel-button]:hidden"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="inline-flex shrink-0 items-center text-muted-foreground hover:text-foreground"
        >
          <X size={size === 'sm' ? 12 : 14} />
        </button>
      ) : null}
    </label>
  );
});
