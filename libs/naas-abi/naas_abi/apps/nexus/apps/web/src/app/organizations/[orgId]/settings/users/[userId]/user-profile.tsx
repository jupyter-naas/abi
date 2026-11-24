'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, Camera, RefreshCw, Save, Trash2, X } from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { useConfirm } from '@/components/ui/dialogs';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import { removableFromOrganization, removalConfirmation } from '../users-model';
import {
  changedProfileFields,
  saveMemberChanges,
  PROFILE_FIELDS,
  type MemberDetails,
  type MemberProfileField,
} from './member-details';
import { MemberAccess } from './member-access';
import { MemberRoleSection } from '@/components/people/member-role-section';
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
  const {
    updateMemberProfile,
    uploadMemberAvatar,
    removeMemberAvatar,
    removeFromOrganization,
    fetchMembers,
  } = useOrganizationStore();
  const { confirm, dialog: confirmDialog } = useConfirm();

  const [details, setDetails] = useState<MemberDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [refused, setRefused] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
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
        // Not an admin here: whoever opens the organization's Access still sees what they hold.
        setRefused(true);
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
    } catch {
      setLoadError('Failed to load this user. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [orgId, userId]);

  useEffect(() => {
    if (orgId && userId) void load();
  }, [orgId, userId, load]);


  if (loading) return <p className="text-sm text-muted-foreground">Loading user...</p>;
  if (!details) {
    return (
      <div className="account-profile-page">
        {!refused && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError || 'User not found.'}</span>
          </div>
        )}
        <MemberAccess orgId={orgId} personId={userId} />
      </div>
    );
  }

  const { member, account, organization_profile: orgProfile, workspaces } = details;
  const isSelf = member.user_id === authUser?.id;
  const canRemove = removableFromOrganization(member.user_id, authUser?.id);
  const changes = changedProfileFields(orgProfile, draft);
  // Their Role (level, org admin, workspaces, groups, policies) is saved in its own section.
  const dirty = Object.keys(changes).length > 0;
  // Always the account name (users.name): an organization cannot rename someone.
  const displayName = account.name || account.email || 'Unknown';
  const orgAvatarUrl = photoUrl(orgProfile.avatar);

  const handleSave = async () => {
    setError('');
    setSaving(true);
    try {
      const failed = await saveMemberChanges({
        profile: Object.keys(changes).length > 0 ? () => updateMemberProfile(orgId, member.user_id, changes) : null,
        access: null,
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
    // The workspaces they joined themselves (not those an org admin reaches anyway).
    const ownWorkspaces = workspaces.filter((w) => w.source === 'workspace').map((w) => w.name);
    if (!(await confirm(removalConfirmation(displayName, ownWorkspaces)))) {
      return;
    }
    setError('');
    setRemoving(true);
    try {
      // Every group of the organization; the last org admin is the API's 409, shown as is.
      await removeFromOrganization(orgId, member.user_id);
      await fetchMembers(orgId);
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
              title={isSelf ? 'You cannot remove yourself' : undefined}
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

      {!isSelf && (
        <MemberRoleSection
          scope={{ kind: 'organization', id: orgId }}
          userId={member.user_id}
          onChanged={() => void load()}
        />
      )}
      <MemberAccess orgId={orgId} personId={member.principal_id || member.user_id} />
      {confirmDialog}
    </div>
  );
}
