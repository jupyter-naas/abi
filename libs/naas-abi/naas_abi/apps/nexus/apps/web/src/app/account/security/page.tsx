'use client';

import { useState } from 'react';
import { Shield, Key, Smartphone, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function SecurityPage() {
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);

  const sessions = [
    {
      id: '1',
      device: 'MacBook Pro',
      location: 'Paris, France',
      lastActive: 'Now',
      current: true,
    },
    {
      id: '2',
      device: 'iPhone 15',
      location: 'Paris, France',
      lastActive: '2 hours ago',
      current: false,
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">Security</h2>
        <p className="text-sm text-muted-foreground">
          Manage your account security settings
        </p>
      </div>

      {/* Password */}
      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
              <Key size={20} />
            </div>
            <div>
              <h3 className="font-medium">Password</h3>
              <p className="text-sm text-muted-foreground">
                Last changed 30 days ago
              </p>
            </div>
          </div>
          <button className="rounded-lg border bg-card px-4 py-2 text-sm font-medium hover:bg-secondary">
            Change Password
          </button>
        </div>
      </div>

      {/* Two-factor authentication */}
      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
              <Smartphone size={20} />
            </div>
            <div>
              <h3 className="font-medium">Two-Factor Authentication</h3>
              <p className="text-sm text-muted-foreground">
                {twoFactorEnabled
                  ? 'Your account is protected with 2FA'
                  : 'Add an extra layer of security'}
              </p>
            </div>
          </div>
          <button
            onClick={() => setTwoFactorEnabled(!twoFactorEnabled)}
            className={cn(
              'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              twoFactorEnabled
                ? 'bg-destructive/10 text-destructive hover:bg-destructive/20'
                : 'bg-blue-500 text-white hover:bg-blue-600'
            )}
          >
            {twoFactorEnabled ? 'Disable' : 'Enable'}
          </button>
        </div>
      </div>

      {/* Active sessions */}
      <div className="rounded-xl border bg-card p-6">
        <h3 className="mb-4 font-semibold">Active Sessions</h3>
        <div className="space-y-3">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="flex items-center justify-between rounded-lg border bg-secondary/30 p-4"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                  <Shield size={18} className="text-muted-foreground" />
                </div>
                <div>
                  <p className="font-medium">
                    {session.device}
                    {session.current && (
                      <span className="ml-2 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-500">
                        This device
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {session.location} · {session.lastActive}
                  </p>
                </div>
              </div>
              {!session.current && (
                <button className="text-sm text-destructive hover:underline">
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
        <button className="mt-4 text-sm text-destructive hover:underline">
          Sign out all other sessions
        </button>
      </div>

      {/* Danger zone */}
      <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-6">
        <div className="flex items-center gap-3">
          <AlertTriangle size={20} className="text-destructive" />
          <h3 className="font-semibold text-destructive">Danger Zone</h3>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Once you delete your account, there is no going back. Please be certain.
        </p>
        <button className="mt-4 rounded-lg border border-destructive bg-transparent px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive hover:text-white">
          Delete Account
        </button>
      </div>
    </div>
  );
}
