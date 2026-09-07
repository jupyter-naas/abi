'use client';

import { useEffect, useState } from 'react';
import { Building2, Save } from 'lucide-react';
import { useParams } from 'next/navigation';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './general.css';

export default function OrganizationGeneralPage() {
  const params = useParams();
  const orgId = params.orgId as string;

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const fetchOrg = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/organizations/${orgId}`);
        if (response.ok) {
          const data = await response.json();
          setName(data.name);
          setSlug(data.slug);
        }
      } catch (error) {
        console.error('Failed to fetch organization:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrg();
  }, [orgId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/organizations/${orgId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, slug }),
      });

      if (response.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      console.error('Failed to update organization:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="org-settings-loading">Loading...</div>;
  }

  return (
    <div className="org-settings-general-page">
      <OrgSettingsPageHeader
        title="General"
        subtitle="Manage basic organization information"
      />

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <Building2 size={20} />
          <h3 className="org-settings-card-heading-title">Organization Details</h3>
        </div>

        <div className="org-settings-section-card-stack">
          <div className="org-settings-field">
            <label className="org-settings-field-label" htmlFor="org-name">
              Organization Name
            </label>
            <input
              id="org-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Corporation"
              className="org-settings-input"
            />
            <p className="org-settings-field-hint">
              The display name for your organization
            </p>
          </div>

          <div className="org-settings-field">
            <label className="org-settings-field-label" htmlFor="org-slug">
              URL Slug
            </label>
            <div className="org-settings-slug-row">
              <span className="org-settings-slug-prefix">/org/</span>
              <input
                id="org-slug"
                type="text"
                value={slug}
                onChange={(e) =>
                  setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))
                }
                placeholder="acme-corp"
                className="org-settings-input"
              />
            </div>
            <p className="org-settings-field-hint">
              Used in your organization&apos;s login URL
            </p>
          </div>
        </div>
      </OrgSettingsSectionCard>

      <div className="org-settings-page-actions">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className={
            saved
              ? 'org-settings-primary-button org-settings-primary-button-saved'
              : 'org-settings-primary-button'
          }
        >
          <Save size={16} />
          {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
