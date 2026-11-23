'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { BadgeCheck, Building2, Check, Clock, Copy, Mail, MapPin, Save } from 'lucide-react';
import { selectSession, useAuthStore } from '@/stores/auth';
import { readOrganization, readOrganizationDomains } from '@/lib/organization-resource';
import { usePageDraft } from '@/hooks/use-page-state';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import { pendingDomainCount, verifiedDomains, type OrgDomain } from './domain';
import {
  ADDRESS_FIELDS,
  CONTACT_FIELDS,
  ORGANIZATION_FIELDS,
  identityChanges,
  identityFrom,
  identitySaveError,
  normalizeWebsite,
  type IdentityFieldSpec,
  type OrganizationIdentity,
} from './identity';
import { DEFAULT_TIMEZONE, timezoneChange, timezoneFrom, timezoneLabel, timezoneOptions } from './timezone';
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

/** What the form edits: the identity and the timezone. */
type GeneralFields = OrganizationIdentity & { timezone: string };

const BLANK: GeneralFields = { ...identityFrom({}), timezone: DEFAULT_TIMEZONE };

const generalFrom = (body: Record<string, unknown>): GeneralFields => ({
  ...identityFrom(body),
  timezone: timezoneFrom(body),
});

const FIELD_LABELS: Record<string, string> = Object.fromEntries([
  ...[...ORGANIZATION_FIELDS, ...CONTACT_FIELDS, ...ADDRESS_FIELDS].map(({ field, label }) => [field, label]),
  ['timezone', 'Timezone'],
]);

type DomainsState =
  | { status: 'loading' }
  | { status: 'ready'; domains: OrgDomain[] }
  | { status: 'hidden' }
  | { status: 'error' };

export default function OrganizationGeneralPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const authReady = usePersistedAuthReady();
  const token = useAuthStore(selectSession);

  // The organization as last read (a fresh read replaces it), and the unsaved edits over it:
  // kept for a return to the page, never overwritten by a read (lib/page-state.ts).
  const [server, setServer] = useState<GeneralFields | null>(null);
  const draft = usePageDraft<GeneralFields>(orgId ? { scope: `organization:${orgId}`, page: 'general' } : null, server);
  const values = draft.values ?? BLANK;
  const initial = server ?? BLANK;
  const timezone = values.timezone;
  const [domains, setDomains] = useState<DomainsState>({ status: 'loading' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

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
        const [orgRes, domainsRes] = await Promise.all([
          readOrganization(orgId),
          readOrganizationDomains(orgId),
        ]);
        if (cancelled) return;

        if (orgRes.ok) {
          setServer(generalFrom(await orgRes.json()));
        } else {
          console.error('Failed to fetch organization:', orgRes.status);
        }

        if (domainsRes.ok) {
          setDomains({ status: 'ready', domains: (await domainsRes.json()) as OrgDomain[] });
        } else {
          // The domains are for the organization's administrators only.
          setDomains({ status: domainsRes.status === 403 ? 'hidden' : 'error' });
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to fetch organization:', error);
          setDomains({ status: 'error' });
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

  const changes = { ...identityChanges(initial, values), ...timezoneChange(initial.timezone, timezone) };
  const dirty = Object.keys(changes).length > 0;
  // The browser's list with offsets, built once; the saved timezone is added if it lacks it.
  const timezoneLabels = useMemo(() => {
    const now = new Date();
    return new Map(timezoneOptions().map((name) => [name, timezoneLabel(name, now)]));
  }, []);
  const timezones = useMemo(
    () =>
      timezoneOptions(timezone).map((name) => ({ name, label: timezoneLabels.get(name) ?? timezoneLabel(name) })),
    [timezone, timezoneLabels]
  );

  const handleSave = async () => {
    if (!dirty) return;
    setSaving(true);
    setSaveError(null);
    try {
      const { authFetch } = await import('@/stores/auth');
      const body = { ...changes };
      if (typeof body.website === 'string') body.website = normalizeWebsite(body.website);
      const response = await authFetch(`/api/organizations/${orgId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (response.ok) {
        setServer(generalFrom(await response.json()));
        draft.discard();
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        const payload = await response.json().catch(() => null);
        setSaveError(identitySaveError(response.status, payload?.detail));
      }
    } catch (error) {
      console.error('Failed to update organization:', error);
      setSaveError('The changes could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  const copyId = async () => {
    try {
      await navigator.clipboard.writeText(orgId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard refused: the id stays selectable in its field.
    }
  };

  if (!authReady || loading) {
    return <div className="org-settings-loading">Loading...</div>;
  }

  const renderField = ({ field, label, placeholder, hint, type = 'text', autoComplete }: IdentityFieldSpec) => (
    <div key={field} className="org-settings-field">
      <label className="org-settings-field-label" htmlFor={`org-${field}`}>
        {label}
      </label>
      <input
        id={`org-${field}`}
        type={type}
        value={values[field]}
        onChange={(e) => draft.set({ [field]: e.target.value } as Partial<GeneralFields>)}
        onBlur={field === 'website' ? () => draft.set({ website: normalizeWebsite(values.website) }) : undefined}
        placeholder={placeholder}
        autoComplete={autoComplete ?? 'off'}
        className="org-settings-input"
      />
      {hint ? <p className="org-settings-field-hint">{hint}</p> : null}
    </div>
  );

  const verified = domains.status === 'ready' ? verifiedDomains(domains.domains) : [];
  const pending = domains.status === 'ready' ? pendingDomainCount(domains.domains) : 0;

  return (
    <div className="org-settings-general-page">
      <OrgSettingsPageHeader
        title="General"
        subtitle="The organization's identity, contact details, timezone and verified domains"
        actions={
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={!dirty || saving}
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

      {saveError ? <p className="org-settings-footnote org-settings-general-error">{saveError}</p> : null}
      {!server ? (
        <p className="org-settings-footnote org-settings-general-error">The organization could not be read.</p>
      ) : null}
      {draft.dirty.length > 0 ? (
        <div className="org-settings-general-draft" role="status">
          <p className="org-settings-general-draft-text">
            {draft.conflicts.length > 0
              ? `Changed elsewhere since you began editing: ${draft.conflicts.map((f) => FIELD_LABELS[f] ?? f).join(', ')}. Saving keeps your version.`
              : 'Unsaved changes.'}
          </p>
          <button type="button" onClick={draft.discard} className="org-settings-general-draft-discard">
            Discard changes
          </button>
        </div>
      ) : null}

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <Building2 size={20} />
          <h3 className="org-settings-card-heading-title">Organization</h3>
        </div>
        <div className="org-settings-section-card-stack">
          {renderField(ORGANIZATION_FIELDS[0])}
          <div className="org-settings-field">
            <label className="org-settings-field-label" htmlFor="org-id">
              Organization ID
            </label>
            <div className="org-settings-slug-row">
              <input
                id="org-id"
                type="text"
                value={orgId}
                readOnly
                className="org-settings-input org-settings-input-readonly org-settings-general-mono"
              />
              <button
                type="button"
                onClick={() => void copyId()}
                className="org-settings-general-copy"
                aria-label="Copy the organization ID"
                title="Copy"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <p className="org-settings-field-hint">Names the organization in the API and in access policies</p>
          </div>
          <div className="org-settings-general-grid">
            {ORGANIZATION_FIELDS.slice(1).map(renderField)}
          </div>
        </div>
      </OrgSettingsSectionCard>

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <Mail size={20} />
          <h3 className="org-settings-card-heading-title">Contact</h3>
        </div>
        <div className="org-settings-general-grid">{CONTACT_FIELDS.map(renderField)}</div>
      </OrgSettingsSectionCard>

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <MapPin size={20} />
          <h3 className="org-settings-card-heading-title">Address</h3>
        </div>
        <div className="org-settings-section-card-stack">
          {ADDRESS_FIELDS.slice(0, 2).map(renderField)}
          <div className="org-settings-general-grid org-settings-general-grid-3">
            {ADDRESS_FIELDS.slice(2).map(renderField)}
          </div>
        </div>
      </OrgSettingsSectionCard>

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <Clock size={20} />
          <h3 className="org-settings-card-heading-title">Timezone</h3>
        </div>
        <div className="org-settings-field">
          <label className="org-settings-field-label" htmlFor="org-timezone">
            Timezone
          </label>
          <select
            id="org-timezone"
            value={timezone}
            onChange={(e) => draft.set({ timezone: e.target.value })}
            className="org-settings-input"
          >
            {timezones.map(({ name, label }) => (
              <option key={name} value={name}>
                {label}
              </option>
            ))}
          </select>
          <p className="org-settings-field-hint">
            Analytics periods (Today, Yesterday, This week, This month) start at midnight in this timezone,
            for the organization and each of its workspaces.
          </p>
        </div>
      </OrgSettingsSectionCard>

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <BadgeCheck size={20} />
          <h3 className="org-settings-card-heading-title">Verified domains</h3>
        </div>
        <div className="org-settings-section-card-stack">
          <p className="org-settings-field-hint">
            Email domains the organization proved it owns: people with these addresses are
            recognized as its own and sign in through its identity provider.
          </p>
          {domains.status === 'hidden' ? (
            <p className="org-settings-field-hint">Only the organization&apos;s administrators see its domains.</p>
          ) : domains.status === 'error' ? (
            <p className="org-settings-field-hint">The domains could not be read.</p>
          ) : verified.length === 0 ? (
            <p className="org-settings-general-empty">No verified domain yet.</p>
          ) : (
            <ul className="org-settings-general-domains">
              {verified.map((domain) => (
                <li key={domain} className="org-settings-general-domain">
                  <BadgeCheck size={14} aria-hidden />
                  {domain}
                </li>
              ))}
            </ul>
          )}
          {domains.status === 'ready' ? (
            <p className="org-settings-field-hint">
              {pending > 0 ? `${pending} waiting for verification. ` : null}
              <Link href={`/organizations/${orgId}/settings/domains`} className="org-settings-general-link">
                Manage domains
              </Link>
            </p>
          ) : null}
        </div>
      </OrgSettingsSectionCard>
    </div>
  );
}
