'use client';

import { useState } from 'react';
import { Bell, Mail, Save } from 'lucide-react';
import './notifications.css';

interface NotificationSetting {
  id: string;
  label: string;
  description: string;
  email: boolean;
  push: boolean;
}

export default function NotificationsPage() {
  const [settings, setSettings] = useState<NotificationSetting[]>([
    {
      id: 'agent-complete',
      label: 'Agent task completion',
      description: 'When an agent completes a long-running task',
      email: true,
      push: true,
    },
    {
      id: 'mentions',
      label: 'Mentions',
      description: 'When someone mentions you in a conversation',
      email: true,
      push: true,
    },
    {
      id: 'weekly-digest',
      label: 'Weekly digest',
      description: 'Summary of your workspace activity',
      email: true,
      push: false,
    },
    {
      id: 'product-updates',
      label: 'Product updates',
      description: 'New features and improvements',
      email: true,
      push: false,
    },
    {
      id: 'security-alerts',
      label: 'Security alerts',
      description: 'Important security notifications',
      email: true,
      push: true,
    },
  ]);
  const [saved, setSaved] = useState(false);

  const toggleSetting = (id: string, type: 'email' | 'push') => {
    setSettings(
      settings.map((s) =>
        s.id === id ? { ...s, [type]: !s[type] } : s
      )
    );
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="account-notifications-page">
      <div className="account-notifications-header">
        <h2 className="account-notifications-title">Notifications</h2>
        <p className="account-notifications-subtitle">
          Choose how you want to be notified
        </p>
      </div>

      <div className="account-notifications-table-card">
        <table className="account-notifications-table">
          <thead>
            <tr className="account-notifications-table-head-row">
              <th className="account-notifications-table-head-cell">Notification</th>
              <th className="account-notifications-table-head-cell account-notifications-table-head-cell-center">
                <div className="account-notifications-column-heading">
                  <Mail size={16} />
                  Email
                </div>
              </th>
              <th className="account-notifications-table-head-cell account-notifications-table-head-cell-center">
                <div className="account-notifications-column-heading">
                  <Bell size={16} />
                  Push
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {settings.map((setting) => (
              <tr key={setting.id} className="account-notifications-table-row">
                <td className="account-notifications-table-cell">
                  <div>
                    <p className="account-notifications-setting-label">{setting.label}</p>
                    <p className="account-notifications-setting-description">
                      {setting.description}
                    </p>
                  </div>
                </td>
                <td className="account-notifications-table-cell account-notifications-table-cell-center">
                  <button
                    type="button"
                    aria-pressed={setting.email}
                    onClick={() => toggleSetting(setting.id, 'email')}
                    className={
                      setting.email
                        ? 'account-notifications-toggle account-notifications-toggle-on'
                        : 'account-notifications-toggle account-notifications-toggle-off'
                    }
                  >
                    <span className="account-notifications-toggle-knob" />
                  </button>
                </td>
                <td className="account-notifications-table-cell account-notifications-table-cell-center">
                  <button
                    type="button"
                    aria-pressed={setting.push}
                    onClick={() => toggleSetting(setting.id, 'push')}
                    className={
                      setting.push
                        ? 'account-notifications-toggle account-notifications-toggle-on'
                        : 'account-notifications-toggle account-notifications-toggle-off'
                    }
                  >
                    <span className="account-notifications-toggle-knob" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="account-notifications-actions">
        <button
          type="button"
          onClick={handleSave}
          className={
            saved
              ? 'account-notifications-save-button account-notifications-save-button-saved'
              : 'account-notifications-save-button'
          }
        >
          <Save size={16} />
          {saved ? 'Saved!' : 'Save Preferences'}
        </button>
      </div>
    </div>
  );
}
