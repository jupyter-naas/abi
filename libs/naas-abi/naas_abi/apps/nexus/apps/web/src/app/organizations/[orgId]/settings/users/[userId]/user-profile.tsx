'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, Camera, RefreshCw, Save, Trash2, X } from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { useConfirm } from '@/components/ui/dialogs';
import { ROLE_LABELS as BUILT_IN_ROLE_LABELS, assignableRoles, changeMemberRole, roleChangeable } from '@/components/access/roles/role-change';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import {
  changedProfileFields,
  saveMemberChanges,
  PROFILE_FIELDS,
  type MemberDetails,
  type MemberProfileField,
} from './member-details';
import '@/app/account/profile/profile.css';
import '../users.css';

const BIO_MAX_LENGTH = 2000;
const INTEREST_MAX_LENGTH = 1000;

/** Single-line fields, in form order (bio is the textarea below them). */
const TEXT_FIELDS: { field: MemberProfileField; label: string; placeholder: string }[] = [
  { field: 'organization', label: 'Organization', placeholder: 'Organization' },
  { field: 'job_title', label: 'Job title', placeholder: 'Job title' },
  { field: 'service_line', label: 'Service line', placeholder: 'Service line' },
  { field: 'country', label: 'Country', placeholder: 'Country' },
  { field: 'interest', label: 'Interest', placeholder: 'Interests' },
];

const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
};

function photoUrl(avatar?: string | null) {
  if (!avatar) return '';
  return avatar.startsWith('/') ? `${getApiUrl()}${avatar}` : avatar;
}

function formatError(err: unknown, fallback: string) {
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
  } catch {
    // ignore parse errors
  }
  return fallback;
}

const emptyDraft = (): Record<MemberProfileField, string> =>
  Object.fromEntries(PROFILE_FIELDS.map((field) => [field, ''])) as Record<
    MemberProfileField,
    string
  >;

/**
 * One member of the organization, laid out like Account Settings > Profile.
 * Org admins set the member's profile here; it is the account that falls back
 * to these values (picture, organization, job title), never the other way round.
 * Members cannot edit it: the API only lets org owners and admins in.
 */
export default function OrgUserProfilePage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const userId = params.userId as string;
  const authUser = useAuthStore((state) => state.user);
  const { updateMemberProfile, uploadMemberAvatar, removeMemberAvatar, removeMember, fetchMembers } =
    useOrganizationStore();
  const { confirm, dialog: confirmDialog } = useConfirm();

  const [details, setDetails] = useState<MemberDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [draft, setDraft] = useState(emptyDraft);
  const [orgRole, setOrgRole] = useState<'admin' | 'member'>('member');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /** ``resetForm: false`` refreshes the data (e.g. a new picture) and keeps unsaved edits. */
  const load = useCallback(async ({ resetForm = true }: { resetForm?: boolean } = {}) => {
    try {
      const res = await authFetch(
        `/api/organizations/${orgId}/members/${encodeURIComponent(userId)}`
      );
      if (res.status === 403) {
        router.replace(orgSettingsSectionPath(orgId, 'users'));
        return;
      }
      if (!res.ok) {
        setLoadError(await readApiError(res, `Failed to load this user (HTTP ${res.status}).`));
        return;
      }
      const data: MemberDetails = await res.json();
      setDetails(data);
      if (!resetForm) return;
      setDraft(
        Object.fromEntries(
          PROFILE_FIELDS.map((field) => [field, data.organization_profile[field] ?? ''])
        ) as Record<MemberProfileField, string>
      );
      setOrgRole(data.member.role === 'admin' ? 'admin' : 'member');
    } catch {
      setLoadError('Failed to load this user. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [orgId, userId, router]);

  useEffect(() => {
    if (orgId && userId) void load();
  }, [orgId, userId, load]);

  if (loading) return <p className="text-sm text-muted-foreground">Loading user...</p>;
  if (!details) {
    return (
      <div className="org-settings-users-alert" role="alert">
        <AlertCircle size={16} />
        <span>{loadError || 'User not found.'}</span>
      </div>
    );
  }

  const { member, account, organization_profile: orgProfile, workspaces } = details;
  const isSelf = member.user_id === authUser?.id;
  const isOwner = member.role === 'owner';
  const canEditOrgRole = roleChangeable({ role: member.role, inherited: false, userId: member.user_id, selfId: authUser?.id });
  const canRemove = !isOwner && !isSelf;
  const changes = changedProfileFields(orgProfile, draft);
  const roleChanged = canEditOrgRole && orgRole !== member.role;
  const dirty = Object.keys(changes).length > 0 || roleChanged;
  // Always the account name (users.name): an organization cannot rename someone.
  const displayName = account.name || account.email || 'Unknown';
  const orgAvatarUrl = photoUrl(orgProfile.avatar);

  const handleSave = async () => {
    setError('');
    setSaving(true);
    try {
      const failed = await saveMemberChanges({
        profile: Object.keys(changes).length > 0 ? () => updateMemberProfile(orgId, member.user_id, changes) : null,
        // The same role change as Roles & permissions › People & roles.
        role: roleChanged
          ? () => changeMemberRole({ level: 'organization', organizationId: orgId }, member.user_id, orgRole)
          : null,
        // The Users list reads the members' roles from the store.
        refreshed: () => fetchMembers(orgId),
      });
      await load();
      if (failed) {
        setError(failed);
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    if (
      !(await confirm({
        title: `Remove ${displayName} from this organization?`,
        confirmLabel: 'Remove',
      }))
    ) {
      return;
    }
    setError('');
    setRemoving(true);
    try {
      await removeMember(orgId, member.user_id);
      router.push(orgSettingsSectionPath(orgId, 'users'));
    } catch (err) {
      setError(formatError(err, 'Failed to remove this user'));
      setRemoving(false);
    }
  };

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'].includes(file.type)) {
      setError('Please upload a valid image file (PNG, JPG, GIF, or WEBP)');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('File size must be less than 2MB');
      return;
    }
    setError('');
    setUploading(true);
    try {
      await uploadMemberAvatar(orgId, member.user_id, file);
      await load({ resetForm: false });
    } catch (err) {
      setError(formatError(err, 'Failed to upload the picture'));
    } finally {
      setUploading(false);
      if (event.target) event.target.value = '';
    }
  };

  const handleAvatarRemove = async () => {
    setError('');
    try {
      await removeMemberAvatar(orgId, member.user_id);
      await load({ resetForm: false });
    } catch (err) {
      setError(formatError(err, 'Failed to remove the picture'));
    }
  };

  return (
    <div className="account-profile-page">
      <Link href={orgSettingsSectionPath(orgId, 'users')} className="org-member-detail-back">
        <ArrowLeft size={14} />
        Users
      </Link>

      <AccountPageHeader
        title={displayName}
        subtitle="Their profile in this organization. Their account shows these values when it has none of its own."
        actions={
          <div className="org-member-detail-actions">
            <button
              type="button"
              onClick={() => void handleRemove()}
              disabled={!canRemove || removing}
              className="org-member-detail-remove-button"
              title={
                isOwner
                  ? 'The owner cannot be removed'
                  : isSelf
                    ? 'You cannot remove yourself'
                    : undefined
              }
            >
              <Trash2 size={16} />
              {removing ? 'Removing...' : 'Remove from organization'}
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={!dirty || saving}
              className={
                saved
                  ? 'account-profile-save-button account-profile-save-button-saved'
                  : 'account-profile-save-button'
              }
            >
              <Save size={16} />
              {saving ? 'Saving...' : saved ? 'Saved!' : 'Save changes'}
            </button>
          </div>
        }
      />

      {(error || loadError) && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{error || loadError}</span>
        </div>
      )}

      <div className="account-profile-avatar-section">
        <div className="account-profile-avatar-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
            onChange={(event) => void handleAvatarUpload(event)}
            className="account-profile-avatar-input"
          />
          {orgAvatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={orgAvatarUrl} alt={displayName} className="account-profile-avatar-image" />
          ) : (
            <div className="account-profile-avatar-placeholder">
              {displayName.charAt(0).toUpperCase()}
            </div>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="account-profile-avatar-upload-button"
            title="Upload a picture for this organization"
          >
            {uploading ? (
              <RefreshCw size={16} className="account-profile-avatar-upload-button-spin" />
            ) : (
              <Camera size={16} />
            )}
          </button>
        </div>
        <div>
          <h3 className="account-profile-avatar-info-name">{displayName}</h3>
          <p className="account-profile-avatar-info-email">{account.email}</p>
          <p className="account-profile-avatar-info-hint">
            Organization picture (max 2MB). Their account shows it when it has no picture.
          </p>
          {orgAvatarUrl ? (
            <button
              type="button"
              onClick={() => void handleAvatarRemove()}
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
            <label className="account-profile-field-label" htmlFor="org-member-name">
              Full name
            </label>
            <input
              id="org-member-name"
              type="text"
              value={account.name ?? ''}
              className="account-profile-field-input"
              title="The account name (Account Settings > Profile)"
              disabled
              readOnly
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="org-member-email">
              Email
            </label>
            <input
              id="org-member-email"
              type="email"
              value={account.email ?? ''}
              className="account-profile-field-input"
              disabled
              readOnly
            />
          </div>
          {TEXT_FIELDS.slice(0, 2).map(({ field, label, placeholder }) => (
            <div key={field} className="account-profile-field">
              <label className="account-profile-field-label" htmlFor={`org-member-${field}`}>
                {label}
              </label>
              <input
                id={`org-member-${field}`}
                type="text"
                value={draft[field]}
                onChange={(event) => setDraft((d) => ({ ...d, [field]: event.target.value }))}
                placeholder={placeholder}
                className="account-profile-field-input"
              />
            </div>
          ))}
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="org-member-role">
              Member role
            </label>
            <select
              id="org-member-role"
              value={isOwner ? 'owner' : orgRole}
              onChange={(event) => setOrgRole(event.target.value as 'admin' | 'member')}
              className="account-profile-field-input"
              disabled={!canEditOrgRole}
              title={
                isOwner
                  ? 'Owners come from the config'
                  : isSelf
                    ? 'You cannot change your own role'
                    : undefined
              }
            >
              {isOwner ? (
                <option value="owner">{BUILT_IN_ROLE_LABELS.owner}</option>
              ) : (
                assignableRoles('organization').map((role) => (
                  <option key={role} value={role}>
                    {BUILT_IN_ROLE_LABELS[role]}
                  </option>
                ))
              )}
            </select>
          </div>
          {TEXT_FIELDS.slice(2).map(({ field, label, placeholder }) => (
            <div key={field} className="account-profile-field">
              <label className="account-profile-field-label" htmlFor={`org-member-${field}`}>
                {label}
              </label>
              <input
                id={`org-member-${field}`}
                type="text"
                value={draft[field]}
                onChange={(event) =>
                  setDraft((d) => ({
                    ...d,
                    [field]:
                      field === 'interest'
                        ? event.target.value.slice(0, INTEREST_MAX_LENGTH)
                        : event.target.value,
                  }))
                }
                placeholder={placeholder}
                className="account-profile-field-input"
              />
            </div>
          ))}
        </div>
        <div className="account-profile-field">
          <div className="account-profile-bio-header">
            <label className="account-profile-field-label" htmlFor="org-member-bio">
              Bio
            </label>
            <span
              className={
                draft.bio.length > BIO_MAX_LENGTH
                  ? 'account-profile-bio-count account-profile-bio-count-over'
                  : 'account-profile-bio-count'
              }
            >
              {draft.bio.length} / {BIO_MAX_LENGTH}
            </span>
          </div>
          <textarea
            id="org-member-bio"
            value={draft.bio}
            onChange={(event) =>
              setDraft((d) => ({ ...d, bio: event.target.value.slice(0, BIO_MAX_LENGTH) }))
            }
            placeholder={account.bio ?? 'Bio in this organization'}
            rows={8}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>

      <section className="org-member-detail-section">
        <header className="org-member-detail-section-header">
          <h3>
            Workspaces{' '}
            <span className="org-member-detail-count">{workspaces.length}</span>
          </h3>
          <p>
            Workspaces they can access in this organization. Assign them from the Users table; org
            owners and admins reach every workspace.
          </p>
        </header>
        <div className="org-settings-users-table-wrap">
          {workspaces.length === 0 ? (
            <p className="org-settings-users-no-match">No workspace in this organization.</p>
          ) : (
            <table className="org-settings-users-table org-member-detail-workspaces">
              <thead>
                <tr>
                  <th>Workspace</th>
                  <th>Role</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {workspaces.map((workspace) => (
                  <tr key={workspace.id}>
                    <td>{workspace.name}</td>
                    <td>{ROLE_LABELS[workspace.role] ?? workspace.role}</td>
                    <td>
                      {workspace.source === 'organization' ? (
                        <span className="org-settings-users-badge org-settings-users-badge-member">
                          via organization
                        </span>
                      ) : (
                        <span className="org-member-detail-value">Workspace member</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
      {confirmDialog}
    </div>
  );
}
