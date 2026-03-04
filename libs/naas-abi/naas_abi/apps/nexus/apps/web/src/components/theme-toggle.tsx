'use client';

import * as React from 'react';
import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground">
        <Sun size={18} />
      </div>
    );
  }

  return (
    <button
      onClick={() => {
        if (theme === 'dark') {
          setTheme('light');
        } else if (theme === 'light') {
          setTheme('system');
        } else {
          setTheme('dark');
        }
      }}
      className={cn(
        'flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors',
        'hover:bg-accent hover:text-accent-foreground'
      )}
      title={`Current theme: ${theme}. Click to cycle.`}
    >
      {theme === 'dark' && <Moon size={18} />}
      {theme === 'light' && <Sun size={18} />}
      {theme === 'system' && <Monitor size={18} />}
    </button>
  );
}

export function ThemeToggleDropdown() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!mounted) {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground">
        <Sun size={18} />
      </div>
    );
  }

  const themes = [
    { value: 'light', label: 'Light', icon: <Sun size={16} /> },
    { value: 'dark', label: 'Dark', icon: <Moon size={16} /> },
    { value: 'system', label: 'System', icon: <Monitor size={16} /> },
  ];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors',
          'hover:bg-accent hover:text-accent-foreground',
          open && 'bg-accent text-accent-foreground'
        )}
      >
        {theme === 'dark' && <Moon size={18} />}
        {theme === 'light' && <Sun size={18} />}
        {theme === 'system' && <Monitor size={18} />}
      </button>

      {open && (
        <div className="glass-card absolute right-0 top-full z-50 mt-1 w-36 p-1">
          {themes.map((t) => (
            <button
              key={t.value}
              onClick={() => {
                setTheme(t.value);
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                'hover:bg-primary/10',
                theme === t.value && 'bg-primary/15 text-primary'
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
