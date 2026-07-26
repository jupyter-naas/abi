'use client';

import { useTheme } from 'next-themes';
import { useState, useEffect } from 'react';
import { Sun, Moon, Monitor, Check, Building2 } from 'lucide-react';
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
  {
    id: 'system',
    label: 'System',
    description: 'Automatically match your system preferences',
    icon: Monitor,
  },
  {
    id: 'organization',
    label: 'Organization',
    description: "Use your organization's default theme",
    icon: Building2,
  },
];

export default function AppearancePage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const hasUserOverride = mounted && localStorage.getItem('nexus-theme-user-override') === 'true';

  const currentTheme = mounted
    ? hasUserOverride
      ? theme
      : 'organization'
    : 'organization';

  const handleThemeChange = (newTheme: string) => {
    if (newTheme === 'organization') {
      localStorage.removeItem('nexus-theme-user-override');
      window.location.reload();
    } else {
      setTheme(newTheme);
      localStorage.setItem('nexus-theme-user-override', 'true');
    }
  };

  return (
    <div className="account-appearance-page">
      <AccountPageHeader
        title="Appearance"
        subtitle="Customize how NEXUS looks on your device"
      />

      <div className="account-appearance-theme-section">
        <div className="account-appearance-theme-heading">
          <h3 className="account-appearance-theme-label">Theme</h3>
          <p className="account-appearance-theme-description">
            Select your preferred color scheme
          </p>
        </div>

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
      </div>

      <div className="account-appearance-hint">
        <p className="account-appearance-hint-text">
          Theme changes are applied immediately and saved to your account.
        </p>
      </div>
    </div>
  );
}
