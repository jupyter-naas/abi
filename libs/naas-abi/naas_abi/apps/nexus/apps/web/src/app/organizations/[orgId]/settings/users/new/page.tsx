'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, UserPlus } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useOrganizationStore, type OrganizationMemberCreateProfile } from '@/stores/organization';
import { Checkbox } from '@/components/ui/checkbox';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import '@/app/account/profile/profile.css';
import '../users.css';

const BIO_MAX_LENGTH = 2000;

type Draft = Required<OrganizationMemberCreateProfile> & { email: string };

const EMPTY: Draft = {
  email: '',
  name: '',
  organization: '',
  job_title: '',
  service_line: '',
  country: '',
  interest: '',
  bio: '',
};

const TEXT_FIELDS: { field: keyof OrganizationMemberCreateProfile; label: string }[] = [
  { field: 'organization', label: 'Organization' },
  { field: 'job_title', label: 'Job title' },
  { field: 'service_line', label: 'Service line' },
  { field: 'country', label: 'Country' },
  { field: 'interest', label: 'Interest' },
];

interface OrgWorkspace {
  id: string;
  name: string;
}

/** Only the fields that were filled in, trimmed (empty ones are not sent). */
function filledProfile(draft: Draft): OrganizationMemberCreateProfile {
  const profile: OrganizationMemberCreateProfile = {};
  for (const key of ['name', ...TEXT_FIELDS.map((f) => f.field), 'bio'] as const) {
    const value = draft[key].trim();
    if (value) profile[key] = value;
  }
  return profile;
}

/**
 * Create user (Organization Settings > Users): a full page with the member's
 * organization profile. The account is created when no user has this email
 * yet, and the person gets a sign-in email either way.
 */
export default function OrgCreateUserPage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const { inviteMember } = useOrganizationStore();

  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [role, setRole] = useState<'admin' | 'member'>('member');
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [workspaceIds, setWorkspaceIds] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(`/api/organizations/${orgId}/workspaces`);
        if (res.status === 403) {
          router.replace(orgSettingsSectionPath(orgId, 'users'));
          return;
        }
        if (res.ok && !cancelled) setWorkspaces(await res.json());
      } catch {
        // The workspace list is optional here; assign them later from the Users table.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId, router]);

  const sortedWorkspaces = useMemo(
    () => [...workspaces].sort((a, b) => a.name.localeCompare(b.name)),
    [workspaces]
  );
  const email = draft.email.trim();
  const emailLooksValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const set = (field: keyof Draft) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setDraft((current) => ({ ...current, [field]: event.target.value }));

  const toggleWorkspace = (id: string) =>
    setWorkspaceIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
    );

  const handleCreate = async () => {
    if (!emailLooksValid) {
      setError('Enter a valid email address.');
      return;
    }
    setError('');
    setCreating(true);
    try {
      const member = await inviteMember(orgId, email, role, filledProfile(draft));
      if (!member) throw new Error('Failed to create the user');
      if (workspaceIds.length > 0) {
        const res = await authFetch(
          `/api/organizations/${orgId}/members/${member.userId}/workspaces`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workspace_ids: workspaceIds }),
          }
        );
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || 'User created, but the workspaces could not be assigned');
        }
      }
      router.push(`${orgSettingsSectionPath(orgId, 'users')}/${member.userId}`);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to create the user');
      setCreating(false);
    }
  };

  return (
    <div className="account-profile-page">
      <Link href={orgSettingsSectionPath(orgId, 'users')} className="org-member-detail-back">
        <ArrowLeft size={14} />
        Users
      </Link>

      <AccountPageHeader
        title="Create user"
        subtitle="Add someone to this organization. Their account is created if it does not exist yet, and they get a sign-in email."
        actions={
          <div className="org-member-detail-actions">
            <button
              type="button"
              onClick={() => router.push(orgSettingsSectionPath(orgId, 'users'))}
              className="org-member-detail-cancel-button"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={!emailLooksValid || creating}
              className="account-profile-save-button"
            >
              <UserPlus size={16} />
              {creating ? 'Creating...' : 'Create user'}
            </button>
          </div>
        }
      />

      {error && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <AccountSectionCard padded stack>
        <div className="account-profile-form-grid">
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-email">
              Email
            </label>
            <input
              id="create-user-email"
              type="email"
              value={draft.email}
              onChange={set('email')}
              placeholder="name@company.com"
              className="account-profile-field-input"
              autoFocus
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-name">
              Full name
            </label>
            <input
              id="create-user-name"
              type="text"
              value={draft.name}
              onChange={set('name')}
              placeholder="Used for a new account; an existing account keeps its name"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-role">
              Member role
            </label>
            <select
              id="create-user-role"
              value={role}
              onChange={(event) => setRole(event.target.value as 'admin' | 'member')}
              className="account-profile-field-input"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          {TEXT_FIELDS.map(({ field, label }) => (
            <div key={field} className="account-profile-field">
              <label className="account-profile-field-label" htmlFor={`create-user-${field}`}>
                {label}
              </label>
              <input
                id={`create-user-${field}`}
                type="text"
                value={draft[field]}
                onChange={set(field)}
                placeholder={label}
                className="account-profile-field-input"
              />
            </div>
          ))}
        </div>
        <div className="account-profile-field">
          <div className="account-profile-bio-header">
            <label className="account-profile-field-label" htmlFor="create-user-bio">
              Bio
            </label>
            <span className="account-profile-bio-count">
              {draft.bio.length} / {BIO_MAX_LENGTH}
            </span>
          </div>
          <textarea
            id="create-user-bio"
            value={draft.bio}
            onChange={(event) =>
              setDraft((current) => ({ ...current, bio: event.target.value.slice(0, BIO_MAX_LENGTH) }))
            }
            placeholder="Bio in this organization"
            rows={6}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>

      <section className="org-member-detail-section">
        <header className="org-member-detail-section-header">
          <h3>
            Workspaces{' '}
            <span className="org-member-detail-count">{workspaceIds.length}</span>
          </h3>
          <p>
            Workspaces they can access. Admins reach every workspace of the organization anyway.
          </p>
        </header>
        <div className="org-settings-users-table-wrap org-create-user-workspaces">
          {sortedWorkspaces.length === 0 ? (
            <p className="org-settings-users-no-match">No workspace in this organization.</p>
          ) : (
            <ul>
              {sortedWorkspaces.map((workspace) => (
                <li key={workspace.id}>
                  <label>
                    <Checkbox
                      checked={workspaceIds.includes(workspace.id)}
                      onCheckedChange={() => toggleWorkspace(workspace.id)}
                    />
                    <span>{workspace.name}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
