'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, Camera, RefreshCw, Save, Trash2, X } from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { useConfirm } from '@/components/ui/dialogs';
import { usePageDraft } from '@/hooks/use-page-state';
import { orgSettingsSectionPath } from '../../lib/nav';
import { removableFromOrganization, removalConfirmation } from '../users-model';
import {
  changedProfileFields,
  saveMemberChanges,
  PROFILE_FIELDS,
  type MemberDetails,
  type MemberProfileField,
} from './member-details';
import '@/components/access/access-base.css';
import '@/components/access/access.css';
import { ViewAsControl } from '@/components/access/people/view-as-control';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { PersonBack } from '@/components/access/people/person-info';
import { InstanceHeader } from '@/components/access/instance-header';
import { MemberRoleSection } from '@/components/people/member-role-section';
import '@/app/account/profile/profile.css';
// The unsaved-changes bar and the Save button of the settings pages.
import '@/app/organizations/[orgId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
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
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /** Read the member again (after a save, a new picture, a change of role): unsaved edits stay. */
  const load = useCallback(async () => {
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
      // The draft (usePageDraft) rebases on it: fields edited and not saved stay.
      setDetails(data);
    } catch {
      setLoadError('Failed to load this user. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [orgId, userId]);

  useEffect(() => {
    if (orgId && userId) void load();
  }, [orgId, userId, load]);

  // Their profile in this organization as saved, and the unsaved edits over it: kept for a
  // return to the page, as every settings form keeps its own (lib/page-state.ts).
  const savedProfile = details?.organization_profile ?? null;
  const server = useMemo(
    () =>
      savedProfile
        ? (Object.fromEntries(PROFILE_FIELDS.map((f) => [f, savedProfile[f] ?? ''])) as Record<
            MemberProfileField,
            string
          >)
        : null,
    [savedProfile]
  );
  const pageDraft = usePageDraft(
    orgId && userId ? { scope: `organization:${orgId}`, page: 'user', detail: userId } : null,
    server
  );


  if (loading) return <p className="text-sm text-muted-foreground">Loading user...</p>;
  if (!details) {
    return (
      <div className="access-instance-page">
        <PersonBack onClick={() => router.push(orgSettingsSectionPath(orgId, 'users'))} />
        {refused && <p className="text-sm text-muted-foreground">Only the organization’s admins see its people.</p>}
        {!refused && (
          <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
            {loadError || 'User not found.'}
          </SettingsNotice>
        )}
      </div>
    );
  }

  const { member, account, organization_profile: orgProfile, workspaces } = details;
  const isSelf = member.user_id === authUser?.id;
  const canRemove = removableFromOrganization(member.user_id, authUser?.id);
  const draft = pageDraft.values ?? (server as Record<MemberProfileField, string>);
  const setField = (field: MemberProfileField, value: string) => pageDraft.set({ [field]: value });
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
      pageDraft.discard();
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
      await load();
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
      await load();
    } catch (err) {
      setError(formatError(err, 'Failed to remove the picture'));
    }
  };

  const textField = ({ field, label, placeholder }: (typeof TEXT_FIELDS)[number]) => (
    <div key={field} className="account-profile-field">
      <label className="account-profile-field-label" htmlFor={`org-member-${field}`}>
        {label}
      </label>
      <input
        id={`org-member-${field}`}
        type="text"
        value={draft[field]}
        onChange={(event) =>
          setField(field, field === 'interest' ? event.target.value.slice(0, INTEREST_MAX_LENGTH) : event.target.value)
        }
        placeholder={placeholder}
        className="account-profile-field-input"
      />
    </div>
  );
  const readOnlyField = (key: string, label: string, value: string, title?: string) => (
    <div className="account-profile-field">
      <label className="account-profile-field-label" htmlFor={`org-member-${key}`}>
        {label}
      </label>
      <input
        id={`org-member-${key}`}
        type="text"
        value={value}
        className="account-profile-field-input account-profile-field-input-readonly"
        title={title}
        readOnly
        aria-readonly="true"
      />
    </div>
  );

  return (
    <div className="access-instance-page">
      {/* The page alone: back to Users, then who it is about, with their picture changed in
          place as on Account › Profile, then their profile and what they hold. */}
      <PersonBack onClick={() => router.push(orgSettingsSectionPath(orgId, 'users'))} />
      <InstanceHeader
        name={displayName}
        id={member.principal_id ?? member.user_id}
        avatar={
          <div className="account-profile-avatar-wrapper" data-member-avatar="">
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
              <div className="account-profile-avatar-placeholder">{displayName.charAt(0).toUpperCase()}</div>
            )}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="account-profile-avatar-upload-button"
              title="Upload a picture for this organization"
              aria-label="Upload a picture for this organization"
              data-action="upload-picture"
            >
              {uploading ? (
                <RefreshCw size={16} className="account-profile-avatar-upload-button-spin" />
              ) : (
                <Camera size={16} />
              )}
            </button>
          </div>
        }
        meta={
          <>
            {account.email ? <span>{account.email}</span> : null}
            <span className="block">Organization picture (max 2MB): their account shows it when it has none.</span>
            {orgAvatarUrl ? (
              <button
                type="button"
                onClick={() => void handleAvatarRemove()}
                className="account-profile-avatar-remove-button"
                data-action="remove-picture"
              >
                <X size={12} />
                Remove picture
              </button>
            ) : null}
          </>
        }
        actions={
          <>
            {member.principal_id && !isSelf && (
              <ViewAsControl personId={member.principal_id} name={displayName} workspaceId={null} />
            )}
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={!dirty || saving}
              className={saved ? 'org-settings-primary-button org-settings-primary-button-saved' : 'org-settings-primary-button'}
              data-action="save-profile"
            >
              <Save size={16} />
              {saved ? 'Saved!' : saving ? 'Saving...' : 'Save changes'}
            </button>
            <button
              type="button"
              onClick={() => void handleRemove()}
              disabled={!canRemove || removing}
              className="org-member-detail-remove-button"
              title={isSelf ? 'You cannot remove yourself' : undefined}
              data-action="remove-member"
            >
              <Trash2 size={16} />
              {removing ? 'Removing...' : 'Remove from organization'}
            </button>
          </>
        }
      />

      {(error || loadError) && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {error || loadError}
        </SettingsNotice>
      )}
      {pageDraft.dirty.length > 0 ? (
        <div className="org-settings-general-draft" role="status">
          <p className="org-settings-general-draft-text">
            {pageDraft.conflicts.length > 0
              ? `Changed elsewhere since you began editing: ${pageDraft.conflicts
                  .map((f) => TEXT_FIELDS.find((t) => t.field === f)?.label ?? 'Bio')
                  .join(', ')}. Saving keeps your version.`
              : 'Unsaved changes.'}
          </p>
          <button type="button" onClick={pageDraft.discard} className="org-settings-general-draft-discard">
            Discard changes
          </button>
        </div>
      ) : null}

      {/* Info and Profile in one section: their account's name and email once, read-only (their
          own profile changes them), then their profile in this organization. */}
      <SettingsSection bodyClassName="space-y-6 p-4">
        <div className="account-profile-form-grid" data-section="profile">
          {readOnlyField('name', 'Name', account.name ?? '', 'The account name (Account Settings > Profile)')}
          {readOnlyField('email', 'Email', account.email ?? '')}
          {TEXT_FIELDS.map(textField)}
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
            onChange={(event) => setField('bio', event.target.value.slice(0, BIO_MAX_LENGTH))}
            placeholder={account.bio ?? 'Bio in this organization'}
            rows={8}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
      </SettingsSection>

      {!isSelf && (
        <MemberRoleSection
          scope={{ kind: 'organization', id: orgId }}
          userId={member.user_id}
          onChanged={() => void load()}
        />
      )}
      {confirmDialog}
    </div>
  );
}
