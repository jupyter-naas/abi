'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Building2, ExternalLink, Eye, Globe, Paintbrush, Save } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import {
  OrgBrandingSettings,
  type OrgBrandingSettingsHandle,
} from '../branding/org-branding-settings';
import { isOrgAdminRole } from '../lib/nav';
import { displayOrgDomain, type OrgDomain } from './domain';
import '../components/org-settings-components.css';
import '../branding/branding.css';
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
  const token = useAuthStore((state) => state.token);
  const { fetchOrganizations } = useOrganizationStore();
  const brandingRef = useRef<OrgBrandingSettingsHandle>(null);

  const [name, setName] = useState('');
  const [initialName, setInitialName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [domain, setDomain] = useState('');
  const [viewerRole, setViewerRole] = useState<string | null>(null);
  const [brandingDirty, setBrandingDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const canManageBranding = isOrgAdminRole(viewerRole);

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
        setOrgSlug(typeof data.slug === 'string' ? data.slug : '');

        const role = data.current_user_role ?? null;
        setViewerRole(role);

        const domainsRes = isOrgAdminRole(role)
          ? await authFetch(`/api/organizations/${orgId}/domains`)
          : null;

        if (cancelled) return;

        const domains: OrgDomain[] =
          domainsRes?.ok ? await domainsRes.json() : [];
        setDomain(displayOrgDomain(domains, window.location.host));

        if (isOrgAdminRole(role)) {
          await fetchOrganizations();
        }
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
  }, [authReady, orgId, token, fetchOrganizations]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    let ok = true;

    try {
      const { authFetch } = await import('@/stores/auth');

      if (name !== initialName) {
        const response = await authFetch(`/api/organizations/${orgId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name }),
        });

        if (response.ok) {
          setInitialName(name);
        } else {
          ok = false;
          setSaveError('Failed to save organization name.');
        }
      }

      if (ok && canManageBranding && brandingRef.current?.isDirty()) {
        const brandingSaved = await brandingRef.current.save();
        if (!brandingSaved) {
          ok = false;
          setSaveError('Failed to save branding.');
        }
      }

      if (ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
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
  const hasChanges = nameDirty || (canManageBranding && brandingDirty);

  return (
    <div className="org-settings-general-page">
      <OrgSettingsPageHeader
        title="General"
        subtitle="Organization details, login branding, and workspace defaults"
        actions={
          <>
            {canManageBranding && orgSlug ? (
              <a
                href={`/org/${orgSlug}/auth/login`}
                target="_blank"
                rel="noopener noreferrer"
                className="org-settings-preview-link"
              >
                <Eye size={14} />
                Preview Login Page
                <ExternalLink size={12} />
              </a>
            ) : null}
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={!hasChanges || saving}
              className={
                saved
                  ? 'org-settings-primary-button org-settings-primary-button-saved'
                  : 'org-settings-primary-button'
              }
            >
              <Save size={16} />
              {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}
            </button>
          </>
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

      {canManageBranding ? (
        <>
          <div className="org-settings-card-heading org-settings-general-branding-heading">
            <Paintbrush size={20} />
            <h3 className="org-settings-card-heading-title">Branding</h3>
          </div>
          <OrgBrandingSettings
            ref={brandingRef}
            orgId={orgId}
            orgDisplayName={name}
            onDirtyChange={setBrandingDirty}
          />
        </>
      ) : null}

      {saveError ? <p className="org-settings-footnote">{saveError}</p> : null}
    </div>
  );
}
