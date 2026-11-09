'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Building2, Globe, Save } from 'lucide-react';
import { selectSession, useAuthStore } from '@/stores/auth';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import { isOrgAdminRole } from '../lib/nav';
import { displayOrgDomain, type OrgDomain } from './domain';
import '../components/org-settings-components.css';
import './general.css';

function usePersistedAuthReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setReady(true);
      return;
    }
    return useAuthStore.persist.onFinishHydration(() => setReady(true));
  }, []);
  return ready;
}

export default function OrganizationGeneralPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const authReady = usePersistedAuthReady();
  const token = useAuthStore(selectSession);

  const [name, setName] = useState('');
  const [initialName, setInitialName] = useState('');
  const [domain, setDomain] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!authReady) return;
    if (!orgId || !token) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    const load = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');

        const orgRes = await authFetch(`/api/organizations/${orgId}`);
        if (cancelled) return;

        if (!orgRes.ok) {
          console.error('Failed to fetch organization:', orgRes.status);
          return;
        }

        const data = await orgRes.json();
        const orgName = typeof data.name === 'string' ? data.name : '';
        setName(orgName);
        setInitialName(orgName);

        const role = data.current_user_role ?? null;

        const domainsRes = isOrgAdminRole(role)
          ? await authFetch(`/api/organizations/${orgId}/domains`)
          : null;

        if (cancelled) return;

        const domains: OrgDomain[] =
          domainsRes?.ok ? await domainsRes.json() : [];
        setDomain(displayOrgDomain(domains, window.location.host));
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to fetch organization:', error);
          setDomain(window.location.host);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [authReady, orgId, token]);

  const handleSave = async () => {
    if (name === initialName) return;

    setSaving(true);
    setSaveError(null);

    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/organizations/${orgId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });

      if (response.ok) {
        setInitialName(name);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        setSaveError('Failed to save organization name.');
      }
    } catch (error) {
      console.error('Failed to update organization:', error);
      setSaveError('Failed to save changes.');
    } finally {
      setSaving(false);
    }
  };

  if (!authReady || loading) {
    return <div className="org-settings-loading">Loading...</div>;
  }

  const nameDirty = name !== initialName;

  return (
    <div className="org-settings-general-page">
      <OrgSettingsPageHeader
        title="General"
        subtitle="Organization name and domain"
        actions={
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={!nameDirty || saving}
            className={
              saved
                ? 'org-settings-primary-button org-settings-primary-button-saved'
                : 'org-settings-primary-button'
            }
          >
            <Save size={16} />
            {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}
          </button>
        }
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
            <label className="org-settings-field-label" htmlFor="org-domain">
              Domain
            </label>
            <div className="org-settings-slug-row">
              <Globe size={16} className="org-settings-slug-prefix" />
              <input
                id="org-domain"
                type="text"
                value={domain}
                readOnly
                className="org-settings-input org-settings-input-readonly"
              />
            </div>
            <p className="org-settings-field-hint">
              Domain used to access this organization
            </p>
          </div>
        </div>
      </OrgSettingsSectionCard>

      {saveError ? <p className="org-settings-footnote">{saveError}</p> : null}
    </div>
  );
}
