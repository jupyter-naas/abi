'use client';

import { useState } from 'react';
import { Shield, Key, Smartphone, AlertTriangle } from 'lucide-react';
import { AccountPageHeader } from '../components/account-page-header';
import { AccountSectionCard } from '../components/account-section-card';
import { AccountActionRow } from '../components/account-action-row';
import './security.css';

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
    <div className="account-security-page">
      <AccountPageHeader
        title="Security"
        subtitle="Manage your account security settings"
      />

      <AccountSectionCard padded>
        <AccountActionRow
          icon={Key}
          title="Password"
          description="Last changed 30 days ago"
          action={
            <button type="button" className="account-security-outline-button">
              Change Password
            </button>
          }
        />
      </AccountSectionCard>

      <AccountSectionCard padded>
        <AccountActionRow
          icon={Smartphone}
          title="Two-Factor Authentication"
          description={
            twoFactorEnabled
              ? 'Your account is protected with 2FA'
              : 'Add an extra layer of security'
          }
          action={
            <button
              type="button"
              onClick={() => setTwoFactorEnabled(!twoFactorEnabled)}
              className={
                twoFactorEnabled
                  ? 'account-security-2fa-button account-security-2fa-button-disable'
                  : 'account-security-2fa-button account-security-2fa-button-enable'
              }
            >
              {twoFactorEnabled ? 'Disable' : 'Enable'}
            </button>
          }
        />
      </AccountSectionCard>

      <AccountSectionCard padded>
        <h3 className="account-security-sessions-title">Active Sessions</h3>
        <div className="account-security-session-list">
          {sessions.map((session) => (
            <div key={session.id} className="account-security-session-item">
              <div className="account-action-row-start">
                <div className="account-security-session-icon-wrap">
                  <Shield size={18} />
                </div>
                <div>
                  <p className="account-security-session-device">
                    {session.device}
                    {session.current && (
                      <span className="account-security-session-badge">This device</span>
                    )}
                  </p>
                  <p className="account-security-session-meta">
                    {session.location} · {session.lastActive}
                  </p>
                </div>
              </div>
              {!session.current && (
                <button type="button" className="account-security-revoke-button">
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
        <button type="button" className="account-security-sign-out-others">
          Sign out all other sessions
        </button>
      </AccountSectionCard>

      <div className="account-security-danger-card">
        <div className="account-security-danger-header">
          <AlertTriangle size={20} />
          <h3 className="account-security-danger-title">Danger Zone</h3>
        </div>
        <p className="account-security-danger-description">
          Once you delete your account, there is no going back. Please be certain.
        </p>
        <button type="button" className="account-security-danger-button">
          Delete Account
        </button>
      </div>
    </div>
  );
}
