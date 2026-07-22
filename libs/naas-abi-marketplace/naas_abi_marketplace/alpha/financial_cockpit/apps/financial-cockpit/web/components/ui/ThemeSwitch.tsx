'use client';

import { Switch } from 'react-aria-components';

type ThemeSwitchProps = {
  theme: 'light' | 'dark';
  onChange: () => void;
  className?: string;
  iconOnly?: boolean;
};

/** Sliding light/dark toggle for the sidebar footer. */
export function ThemeSwitch({
  theme,
  onChange,
  className = '',
  iconOnly = false,
}: ThemeSwitchProps) {
  const isDark = theme === 'dark';

  if (iconOnly) {
    return (
      <Switch
        isSelected={isDark}
        onChange={onChange}
        className={`flex h-10 w-10 items-center justify-center rounded-md text-[var(--text-muted)] outline-none transition hover:bg-[var(--accent)] hover:text-[var(--text)] data-[focus-visible]:ring-2 data-[focus-visible]:ring-inset data-[focus-visible]:ring-secondary ${className}`.trim()}
        aria-label={isDark ? 'Activer le mode clair' : 'Activer le mode sombre'}
      >
        {isDark ? <MoonIcon /> : <SunIcon />}
      </Switch>
    );
  }

  return (
    <Switch
      isSelected={isDark}
      onChange={onChange}
      className={`group flex cursor-pointer items-center justify-between gap-3 px-3 py-2 outline-none ${className}`.trim()}
      aria-label={isDark ? 'Activer le mode clair' : 'Activer le mode sombre'}
    >
      <span className="flex min-w-0 items-center gap-2 text-sm font-medium text-[var(--text-muted)]">
        {isDark ? <MoonIcon /> : <SunIcon />}
        <span className="truncate">{isDark ? 'Mode sombre' : 'Mode clair'}</span>
      </span>
      <span
        className="flex h-5 w-9 shrink-0 items-center bg-[var(--accent)] p-0.5 ring-1 ring-inset ring-[var(--border)] transition-colors group-data-[selected]:bg-[var(--secondary)] group-data-[focus-visible]:ring-2 group-data-[focus-visible]:ring-[var(--secondary)]"
        aria-hidden
      >
        <span className="h-4 w-4 bg-[var(--text)] transition-transform group-data-[selected]:translate-x-4" />
      </span>
    </Switch>
  );
}

function SunIcon() {
  return (
    <svg
      className="h-4 w-4 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      className="h-4 w-4 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3a6.5 6.5 0 1 0 11.5 11.5z" />
    </svg>
  );
}
