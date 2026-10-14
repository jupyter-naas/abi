'use client';

import { Search, X } from 'lucide-react';

/** Search box of the Platform Settings dashboard and table pages. Esc clears it. */
export function SearchBox({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
  label: string;
}) {
  return (
    <label className="platform-dashboard-search">
      <Search size={14} />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') onChange('');
        }}
        placeholder={placeholder}
        aria-label={label}
      />
      {value && (
        <button
          type="button"
          className="platform-dashboard-search-clear"
          onClick={() => onChange('')}
          aria-label="Clear search"
        >
          <X size={14} />
        </button>
      )}
    </label>
  );
}
