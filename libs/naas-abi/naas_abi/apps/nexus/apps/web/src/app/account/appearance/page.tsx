'use client';

import { useTheme } from 'next-themes';
import { useState, useEffect } from 'react';
import { Sun, Moon, Monitor, Check, Building2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const themes = [
  {
    id: 'light',
    label: 'Light',
    description: 'A bright theme for well-lit environments',
    icon: Sun,
  },
  {
    id: 'dark',
    label: 'Dark',
    description: 'A dark theme that reduces eye strain',
    icon: Moon,
  },
  {
    id: 'system',
    label: 'System',
    description: 'Automatically match your system preferences',
    icon: Monitor,
  },
  {
    id: 'organization',
    label: 'Organization',
    description: 'Use your organization\'s default theme',
    icon: Building2,
  },
];

export default function AppearancePage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Check if user has explicitly set a theme override
  const hasUserOverride = mounted && localStorage.getItem('nexus-theme-user-override') === 'true';
  
  // Get current theme: if no override, show "organization", otherwise show the actual theme
  const currentTheme = mounted 
    ? (hasUserOverride ? theme : 'organization')
    : 'organization';

  const handleThemeChange = (newTheme: string) => {
    if (newTheme === 'organization') {
      // Clear override - let org theme apply
      localStorage.removeItem('nexus-theme-user-override');
      // Reload to apply org theme
      window.location.reload();
    } else {
      // Set explicit theme and mark as override
      setTheme(newTheme);
      localStorage.setItem('nexus-theme-user-override', 'true');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Appearance</h2>
        <p className="text-sm text-muted-foreground">
          Customize how NEXUS looks on your device
        </p>
      </div>

      {/* Theme Selection */}
      <div className="space-y-4">
        <div>
          <h3 className="font-medium">Theme</h3>
          <p className="text-sm text-muted-foreground">
            Select your preferred color scheme
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
          {themes.map((t) => {
            const Icon = t.icon;
            const isSelected = currentTheme === t.id;

            return (
              <button
                key={t.id}
                onClick={() => handleThemeChange(t.id)}
                className={cn(
                  'relative flex flex-col items-start gap-3 rounded-xl border p-4 text-left transition-all',
                  'hover:border-blue-500/50 hover:bg-muted/50',
                  isSelected
                    ? 'border-blue-500 bg-blue-500/5'
                    : 'border-border bg-card'
                )}
              >
                {isSelected && (
                  <div className="absolute right-3 top-3">
                    <Check size={16} className="text-blue-500" />
                  </div>
                )}
                <div
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-lg',
                    isSelected ? 'bg-blue-500/10 text-blue-500' : 'bg-muted text-muted-foreground'
                  )}
                >
                  <Icon size={20} />
                </div>
                <div>
                  <p className="font-medium">{t.label}</p>
                  <p className="text-xs text-muted-foreground">{t.description}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Preview hint */}
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-sm text-muted-foreground">
          Theme changes are applied immediately and saved to your account.
        </p>
      </div>
    </div>
  );
}
