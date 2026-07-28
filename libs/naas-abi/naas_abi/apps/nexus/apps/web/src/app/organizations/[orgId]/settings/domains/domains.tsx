'use client';

import { Globe, Plus } from 'lucide-react';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './domains.css';

export default function OrgDomainsPage() {
  return (
    <div className="org-settings-domains-page">
      <OrgSettingsPageHeader
        title="Domains"
        subtitle="Manage custom domains for your organization"
        actions={
          <button type="button" className="org-settings-primary-button">
            <Plus size={16} />
            Add Domain
          </button>
        }
      />

      <OrgSettingsSectionCard padded>
        <div className="org-settings-empty">
          <div className="org-settings-empty-icon">
            <Globe size={24} />
          </div>
          <h3 className="org-settings-empty-title">No custom domains configured</h3>
          <p className="org-settings-empty-body">
            Add a custom domain to use your own URL for the login page instead of
            nexus.app/org/your-slug/auth/login
          </p>
        </div>
      </OrgSettingsSectionCard>

      <p className="org-settings-footnote">Custom domain management coming soon</p>
    </div>
  );
}
