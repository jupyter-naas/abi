'use client';

import { Plus, Shield, Crown, UserCircle } from 'lucide-react';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './admins.css';

const DEMO_ADMINS = [
  { name: 'Alice Johnson', email: 'alice@example.com', role: 'owner' as const },
  { name: 'Bob Smith', email: 'bob@example.com', role: 'admin' as const },
];

export default function OrgAdminsPage() {
  return (
    <div className="org-settings-admins-page">
      <OrgSettingsPageHeader
        title="Admins"
        subtitle="Manage who can administer this organization"
        actions={
          <button type="button" className="org-settings-primary-button">
            <Plus size={16} />
            Add Admin
          </button>
        }
      />

      <OrgSettingsSectionCard flush overflowHidden>
        <p className="org-settings-admins-list-label">Organization Admins</p>
        <ul className="org-settings-admins-list">
          {DEMO_ADMINS.map((admin) => (
            <li key={admin.email} className="org-settings-admins-row">
              <div className="org-settings-admins-row-start">
                <div className="org-settings-admins-avatar">
                  <UserCircle size={20} />
                </div>
                <div>
                  <p className="org-settings-admins-name">{admin.name}</p>
                  <p className="org-settings-admins-email">{admin.email}</p>
                </div>
              </div>
              {admin.role === 'owner' ? (
                <span className="org-settings-admins-badge org-settings-admins-badge-owner">
                  <Crown size={12} />
                  Owner
                </span>
              ) : (
                <span className="org-settings-admins-badge org-settings-admins-badge-admin">
                  <Shield size={12} />
                  Admin
                </span>
              )}
            </li>
          ))}
        </ul>
      </OrgSettingsSectionCard>

      <p className="org-settings-footnote">Admin management coming soon</p>
    </div>
  );
}
