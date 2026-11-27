'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';
import { AlertCircle, Mail, MapPin, Plus } from 'lucide-react';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { OrgSettingsSectionCard } from '@/app/organizations/[orgId]/settings/components/org-settings-section-card';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import {
  ADDRESS_FIELDS,
  CONTACT_FIELDS,
  ORGANIZATION_FIELDS,
  identityCreateFields,
  identityFrom,
  normalizeWebsite,
  type IdentityFieldSpec,
  type OrganizationIdentity,
} from '@/app/organizations/[orgId]/settings/general/identity';
import { createOrganization, type Fetcher } from './organizations-api';
import { PLATFORM_ORGANIZATIONS_PATH, slugFromName } from './organizations-model';
import { organizationSettingsHref } from './organizations';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import '@/app/organizations/[orgId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/users/users.css';
import './organizations.css';

/** The slug the API takes: lowercase letters, digits and dashes, not at either end. */
const SLUG = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

/**
 * Platform Settings › Organizations › New: the organization's name and slug, and its
 * general information (the same fields as its General settings). Created, it opens
 * the organization's own settings, the caller its owner.
 */
export function NewOrganization({
  fetcher,
  navigate,
}: {
  fetcher?: Fetcher;
  navigate: (href: string) => void;
}) {
  const [values, setValues] = useState<OrganizationIdentity>(() => identityFrom({}));
  const [slug, setSlug] = useState('');
  const [slugEdited, setSlugEdited] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const name = values.name.trim();
  const slugValid = SLUG.test(slug);
  const ready = name !== '' && slugValid && !creating;

  const setField = (field: keyof OrganizationIdentity, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
    if (field === 'name' && !slugEdited) setSlug(slugFromName(value));
  };

  const create = async () => {
    if (!ready) return;
    setCreating(true);
    setError(null);
    const answer = await createOrganization(name, slug, fetcher, identityCreateFields(values));
    setCreating(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    navigate(organizationSettingsHref(answer.data.id));
  };

  const renderField = ({ field, label, placeholder, hint, type = 'text', autoComplete }: IdentityFieldSpec) => (
    <div key={field} className="org-settings-field">
      <label className="org-settings-field-label" htmlFor={`new-org-${field}`}>
        {label}
        {field === 'name' ? ' *' : null}
      </label>
      <input
        id={`new-org-${field}`}
        data-field={field}
        type={type}
        value={values[field]}
        onChange={(event) => setField(field, event.target.value)}
        onBlur={field === 'website' ? () => setField('website', normalizeWebsite(values.website)) : undefined}
        placeholder={placeholder}
        autoComplete={autoComplete ?? 'off'}
        required={field === 'name'}
        className="org-settings-input"
      />
      {hint ? <p className="org-settings-field-hint">{hint}</p> : null}
    </div>
  );

  return (
    <form
      className="platform-orgs-new-page"
      // The website is made a URL on create and the API checks every field: the
      // browser's own checks would refuse "acme.com" before that.
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void create();
      }}
    >
      <OrgSettingsPageHeader
        title="New organization"
        subtitle="Its name and general information; branding, members and workspaces follow in its settings"
        actions={
          <span className="platform-orgs-new-actions">
            <Link href={PLATFORM_ORGANIZATIONS_PATH} className="org-settings-users-secondary-button" data-action="cancel">
              Cancel
            </Link>
            <button type="submit" className="org-settings-primary-button" data-action="create" disabled={!ready}>
              <Plus size={16} />
              {creating ? 'Creating…' : 'Create organization'}
            </button>
          </span>
        }
      />

      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          <span role="alert">{error}</span>
        </SettingsNotice>
      )}

      {/* As Organization › General: its first block has no heading; Name and Slug side by side
          (as Workspace › General's), then the rest of its identity. */}
      <OrgSettingsSectionCard padded>
        <div className="org-settings-section-card-stack">
          <div className="org-settings-general-grid">
            {renderField(ORGANIZATION_FIELDS[0])}
            <div className="org-settings-field">
              <label className="org-settings-field-label" htmlFor="new-org-slug">
                Slug *
              </label>
              <input
                id="new-org-slug"
                data-field="slug"
                type="text"
                value={slug}
                onChange={(event) => {
                  setSlug(event.target.value);
                  setSlugEdited(true);
                }}
                placeholder="acme"
                autoComplete="off"
                required
                className="org-settings-input org-settings-general-mono"
              />
              <p className="org-settings-field-hint platform-orgs-slug-hint">
                {slug && !slugValid
                  ? 'Lowercase letters, digits and dashes, starting and ending with a letter or digit.'
                  : 'Names the organization in its sign-in address. It cannot be reused.'}
              </p>
            </div>
          </div>
          <div className="org-settings-general-grid">{ORGANIZATION_FIELDS.slice(1).map(renderField)}</div>
        </div>
      </OrgSettingsSectionCard>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <Mail size={16} className="text-muted-foreground" />
            Contact
          </span>
        }
      >
        <div className="org-settings-general-grid">{CONTACT_FIELDS.map(renderField)}</div>
      </SettingsSection>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <MapPin size={16} className="text-muted-foreground" />
            Address
          </span>
        }
      >
        <div className="org-settings-section-card-stack">
          {ADDRESS_FIELDS.slice(0, 2).map(renderField)}
          <div className="org-settings-general-grid org-settings-general-grid-3">
            {ADDRESS_FIELDS.slice(2).map(renderField)}
          </div>
        </div>
      </SettingsSection>
    </form>
  );
}

export default function NewOrganizationPage() {
  const router = useRouter();
  const navigate = useCallback((href: string) => router.push(href), [router]);
  return <NewOrganization navigate={navigate} />;
}
