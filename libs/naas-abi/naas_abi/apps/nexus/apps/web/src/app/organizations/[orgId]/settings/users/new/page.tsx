'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, Camera, Mail, UserPlus, X } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useOrganizationStore, type OrganizationMemberCreateProfile } from '@/stores/organization';
import { Checkbox } from '@/components/ui/checkbox';
import { useInviteProviders } from '@/components/invitations/use-invite-providers';
import { inviteSuccessMessage, providerHint } from '@/lib/invitations';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import '@/app/account/profile/profile.css';
import '../users.css';

const BIO_MAX_LENGTH = 2000;
const AVATAR_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
const AVATAR_MAX_BYTES = 2 * 1024 * 1024;

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
 * organization profile. The person is invited through an identity provider:
 * the account is made there when it does not exist yet (the provider mails the
 * sign-in code). Someone who has not signed in yet has no member row to fill:
 * the invitation holds their roles, and the profile is set from their page
 * once they are in.
 */
export default function OrgCreateUserPage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const { inviteToOrganization, uploadMemberAvatar } = useOrganizationStore();
  const providers = useInviteProviders(true);

  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [role, setRole] = useState<'admin' | 'member'>('member');
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [workspaceIds, setWorkspaceIds] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [creating, setCreating] = useState(false);
  // Picked now, uploaded right after the user exists (organization picture, avatar_org).
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!avatarFile) {
      setAvatarPreview('');
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setAvatarPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  const pickAvatar = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!AVATAR_TYPES.includes(file.type)) {
      setError('Please choose a PNG, JPG, GIF or WEBP image.');
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      setError('The picture must be less than 2MB.');
      return;
    }
    setError('');
    setAvatarFile(file);
  };

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
    setNotice('');
    setCreating(true);
    try {
      const provider = providers.providerToSend();
      const { member, answer } = await inviteToOrganization(orgId, {
        email,
        role,
        provider,
        profile: filledProfile(draft),
        workspaceId: workspaceIds[0],
        workspaceRole: workspaceIds[0] ? 'member' : undefined,
      });
      if (answer.kind === 'invited') {
        // No account yet: the invitation holds the roles until they sign in,
        // one invitation per workspace picked.
        for (const workspaceId of workspaceIds.slice(1)) {
          await inviteToOrganization(orgId, {
            email,
            role,
            provider,
            workspaceId,
            workspaceRole: 'member',
          });
        }
        setNotice(inviteSuccessMessage(answer));
        setDraft(EMPTY);
        setWorkspaceIds([]);
        setAvatarFile(null);
        setCreating(false);
        return;
      }
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
      if (avatarFile) {
        try {
          await uploadMemberAvatar(orgId, member.userId, avatarFile);
        } catch (err) {
          throw new Error(
            `User created, but the picture could not be uploaded: ${
              err instanceof Error ? err.message : 'unknown error'
            }. Upload it from their page.`
          );
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
        subtitle="Add someone to this organization. Their account is created at the identity provider if it does not exist yet, and they sign in with the code it emails."
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

      {notice && (
        <div className="org-settings-users-alert" role="status">
          <Mail size={16} />
          <span>{notice}</span>
        </div>
      )}

      {providerHint(providers.chosen) && (
        <p className="org-settings-footnote">{providerHint(providers.chosen)}</p>
      )}

      <div className="account-profile-avatar-section">
        <div className="account-profile-avatar-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            accept={AVATAR_TYPES.join(',')}
            onChange={pickAvatar}
            className="account-profile-avatar-input"
          />
          {avatarPreview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={avatarPreview} alt="" className="account-profile-avatar-image" />
          ) : (
            <div className="account-profile-avatar-placeholder">
              {(draft.name || draft.email || '?').charAt(0).toUpperCase()}
            </div>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={creating}
            className="account-profile-avatar-upload-button"
            title="Choose a picture"
          >
            <Camera size={16} />
          </button>
        </div>
        <div>
          <h3 className="account-profile-avatar-info-name">{draft.name.trim() || 'New user'}</h3>
          <p className="account-profile-avatar-info-email">{draft.email.trim()}</p>
          <p className="account-profile-avatar-info-hint">
            Organization picture (max 2MB), uploaded when the user is created. Their account shows
            it when it has no picture.
          </p>
          {avatarFile ? (
            <button
              type="button"
              onClick={() => setAvatarFile(null)}
              className="account-profile-avatar-remove-button"
            >
              <X size={12} />
              Remove picture
            </button>
          ) : null}
        </div>
      </div>

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
          {providers.choosable && (
            <div className="account-profile-field">
              <label className="account-profile-field-label" htmlFor="create-user-provider">
                Identity provider
              </label>
              <select
                id="create-user-provider"
                value={providers.picked ?? ''}
                onChange={(event) => providers.setPicked(event.target.value)}
                className="account-profile-field-input"
              >
                {providers.known.providers.map((provider) => (
                  <option key={provider.name} value={provider.name}>
                    {provider.display_name}
                  </option>
                ))}
              </select>
            </div>
          )}
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
