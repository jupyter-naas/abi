'use client';

import { Plus, Shield, Crown, UserCircle } from 'lucide-react';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './users.css';

const DEMO_USERS = [
  { name: 'Alice Johnson', email: 'alice@example.com', role: 'owner' as const },
  { name: 'Bob Smith', email: 'bob@example.com', role: 'admin' as const },
  { name: 'Carol Lee', email: 'carol@example.com', role: 'member' as const },
];

export default function OrgUsersPage() {
  return (
    <div className="org-settings-users-page">
      <OrgSettingsPageHeader
        title="Users"
        subtitle="Manage who has access to this organization"
        actions={
          <button type="button" className="org-settings-primary-button">
            <Plus size={16} />
            Add User
          </button>
        }
      />

      <OrgSettingsSectionCard flush overflowHidden>
        <p className="org-settings-users-list-label">Organization Users</p>
        <ul className="org-settings-users-list">
          {DEMO_USERS.map((user) => (
            <li key={user.email} className="org-settings-users-row">
              <div className="org-settings-users-row-start">
                <div className="org-settings-users-avatar">
                  <UserCircle size={20} />
                </div>
                <div>
                  <p className="org-settings-users-name">{user.name}</p>
                  <p className="org-settings-users-email">{user.email}</p>
                </div>
              </div>
              {user.role === 'owner' ? (
                <span className="org-settings-users-badge org-settings-users-badge-owner">
                  <Crown size={12} />
                  Owner
                </span>
              ) : user.role === 'admin' ? (
                <span className="org-settings-users-badge org-settings-users-badge-admin">
                  <Shield size={12} />
                  Admin
                </span>
              ) : (
                <span className="org-settings-users-badge org-settings-users-badge-member">
                  <UserCircle size={12} />
                  Member
                </span>
              )}
            </li>
          ))}
        </ul>
      </OrgSettingsSectionCard>

      <p className="org-settings-footnote">User management coming soon</p>
    </div>
  );
}
