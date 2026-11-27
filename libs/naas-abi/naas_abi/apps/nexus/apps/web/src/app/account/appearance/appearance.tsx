'use client';

import { useTheme } from 'next-themes';
import { useState, useEffect } from 'react';
import { Sun, Moon, Check, SunMoon } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { AccountPageHeader } from '../components/account-page-header';
import './appearance.css';

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
];

export default function AppearancePage() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Light or Dark only: the theme in use (the organization's default, or the system's, until the
  // person picks one) is the one selected.
  const currentTheme = mounted ? (theme === 'light' || theme === 'dark' ? theme : resolvedTheme) : undefined;

  const handleThemeChange = (newTheme: string) => {
    setTheme(newTheme);
    localStorage.setItem('nexus-theme-user-override', 'true');
  };

  return (
    <div className="account-appearance-page">
      <AccountPageHeader
        title="Appearance"
        subtitle="Customize how NEXUS looks on your device"
      />

      {/* A section as on Organization › General and Branding: a 16px icon and a sentence-case title. */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <SunMoon size={16} className="text-muted-foreground" />
            Theme
          </span>
        }
        description="Select your preferred color scheme"
        bodyClassName="space-y-4 p-4"
      >
        <div className="account-appearance-theme-grid">
          {themes.map((t) => {
            const Icon = t.icon;
            const isSelected = currentTheme === t.id;

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => handleThemeChange(t.id)}
                className={
                  isSelected
                    ? 'account-appearance-theme-option account-appearance-theme-option-selected'
                    : 'account-appearance-theme-option'
                }
              >
                {isSelected && (
                  <div className="account-appearance-theme-option-check">
                    <Check size={16} />
                  </div>
                )}
                <div className="account-appearance-theme-option-icon">
                  <Icon size={20} />
                </div>
                <div className="account-appearance-theme-option-text">
                  <p className="account-appearance-theme-option-name">{t.label}</p>
                  <p className="account-appearance-theme-option-detail">{t.description}</p>
                </div>
              </button>
            );
          })}
        </div>
        <p className="account-appearance-hint-text">
          Theme changes are applied immediately and saved to your account.
        </p>
      </Card>
    </div>
  );
}
