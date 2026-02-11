'use client';

import { useState } from 'react';
import { Bell, Mail, Save } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">Notifications</h2>
        <p className="text-sm text-muted-foreground">
          Choose how you want to be notified
        </p>
      </div>

      {/* Settings table */}
      <div className="rounded-xl border bg-card">
        <table className="w-full">
          <thead>
            <tr className="border-b text-left text-sm text-muted-foreground">
              <th className="p-4 font-medium">Notification</th>
              <th className="p-4 font-medium text-center">
                <div className="flex items-center justify-center gap-2">
                  <Mail size={16} />
                  Email
                </div>
              </th>
              <th className="p-4 font-medium text-center">
                <div className="flex items-center justify-center gap-2">
                  <Bell size={16} />
                  Push
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {settings.map((setting) => (
              <tr key={setting.id} className="border-b last:border-0">
                <td className="p-4">
                  <div>
                    <p className="font-medium">{setting.label}</p>
                    <p className="text-sm text-muted-foreground">
                      {setting.description}
                    </p>
                  </div>
                </td>
                <td className="p-4 text-center">
                  <button
                    onClick={() => toggleSetting(setting.id, 'email')}
                    className={cn(
                      'h-6 w-11 rounded-full transition-colors',
                      setting.email ? 'bg-blue-500' : 'bg-secondary'
                    )}
                  >
                    <div
                      className={cn(
                        'h-5 w-5 rounded-full bg-white transition-transform',
                        setting.email ? 'translate-x-5' : 'translate-x-0.5'
                      )}
                    />
                  </button>
                </td>
                <td className="p-4 text-center">
                  <button
                    onClick={() => toggleSetting(setting.id, 'push')}
                    className={cn(
                      'h-6 w-11 rounded-full transition-colors',
                      setting.push ? 'bg-blue-500' : 'bg-secondary'
                    )}
                  >
                    <div
                      className={cn(
                        'h-5 w-5 rounded-full bg-white transition-transform',
                        setting.push ? 'translate-x-5' : 'translate-x-0.5'
                      )}
                    />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Save button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          className={cn(
            'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
            saved
              ? 'bg-blue-500/20 text-blue-500'
              : 'bg-blue-500 text-white hover:bg-blue-600'
          )}
        >
          <Save size={16} />
          {saved ? 'Saved!' : 'Save Preferences'}
        </button>
      </div>
    </div>
  );
}
