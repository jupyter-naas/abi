'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { ExternalLink, Eye, Save } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import {
  OrgBrandingSettings,
  type OrgBrandingSettingsHandle,
} from './org-branding-settings';
import { isOrgAdminRole } from '../lib/nav';
import './branding.css';

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

export default function OrganizationBrandingPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const authReady = usePersistedAuthReady();
  const token = useAuthStore((state) => state.token);
  const { fetchOrganizations } = useOrganizationStore();
  const brandingRef = useRef<OrgBrandingSettingsHandle>(null);

  const [orgName, setOrgName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [brandingDirty, setBrandingDirty] = useState(false);
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
        setOrgName(typeof data.name === 'string' ? data.name : '');
        setOrgSlug(typeof data.slug === 'string' ? data.slug : '');

        if (isOrgAdminRole(data.current_user_role)) {
          await fetchOrganizations();
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to fetch organization:', error);
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
    if (!brandingRef.current?.isDirty()) return;

    setSaving(true);
    setSaveError(null);

    try {
      const brandingSaved = await brandingRef.current.save();
      if (brandingSaved) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        setSaveError('Failed to save branding.');
      }
    } catch (error) {
      console.error('Failed to save branding:', error);
      setSaveError('Failed to save branding.');
    } finally {
      setSaving(false);
    }
  };

  if (!authReady || loading) {
    return <div className="org-settings-loading">Loading...</div>;
  }

  return (
    <div className="org-settings-branding-page">
      <OrgSettingsPageHeader
        title="Branding"
        subtitle="Logos, colors, login page, and default theme for your organization"
        actions={
          <>
            {orgSlug ? (
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
              disabled={!brandingDirty || saving}
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

      <OrgBrandingSettings
        ref={brandingRef}
        orgId={orgId}
        orgDisplayName={orgName}
        onDirtyChange={setBrandingDirty}
      />

      {saveError ? <p className="org-settings-footnote">{saveError}</p> : null}
    </div>
  );
}
