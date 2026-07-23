'use client';

export type ViewMode = 'gallery' | 'table';

type ViewToggleProps = {
  value: ViewMode;
  onChange: (view: ViewMode) => void;
};

export function ViewToggle({ value, onChange }: ViewToggleProps) {
  return (
    <div
      className="inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--surface)] p-0.5"
      role="group"
      aria-label="Mode d'affichage"
    >
      <button
        type="button"
        className={`inline-flex h-8 w-8 items-center justify-center rounded outline-none transition-colors focus-visible:ring-2 focus-visible:ring-secondary ${
          value === 'gallery'
            ? 'bg-[var(--accent)] text-[var(--text)]'
            : 'text-[var(--text-muted)] hover:bg-[var(--accent)]'
        }`}
        onClick={() => onChange('gallery')}
        aria-label="Vue galerie"
        aria-pressed={value === 'gallery'}
        title="Vue galerie"
      >
        <GridIcon />
      </button>
      <button
        type="button"
        className={`inline-flex h-8 w-8 items-center justify-center rounded outline-none transition-colors focus-visible:ring-2 focus-visible:ring-secondary ${
          value === 'table'
            ? 'bg-[var(--accent)] text-[var(--text)]'
            : 'text-[var(--text-muted)] hover:bg-[var(--accent)]'
        }`}
        onClick={() => onChange('table')}
        aria-label="Vue tableau"
        aria-pressed={value === 'table'}
        title="Vue tableau"
      >
        <ListIcon />
      </button>
    </div>
  );
}

function GridIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <path d="M3 9h18M3 15h18" />
    </svg>
  );
}
