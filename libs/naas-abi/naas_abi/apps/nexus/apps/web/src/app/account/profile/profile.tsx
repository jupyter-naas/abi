'use client';

import { useMemo, useState, useRef } from 'react';
import { Camera, Save, X, RefreshCw } from 'lucide-react';
import { toast } from '@/components/ui/toast';
import { getApiUrl } from '@/lib/config';
import { usePageDraft } from '@/hooks/use-page-state';
import { useAuthStore, type User } from '@/stores/auth';
import { AccountPageHeader } from '../components/account-page-header';
import { AccountSectionCard } from '../components/account-section-card';
import './profile.css';

const BIO_MAX_LENGTH = 2000;

/** What the form edits, as the server last said (`authUser`). */
type ProfileFields = {
  name: string;
  organization: string;
  job_title: string;
  bio: string;
  linkedin_url: string;
  github_handle: string;
};

const FIELD_LABELS: Record<keyof ProfileFields, string> = {
  name: 'Full Name',
  organization: 'Organization',
  job_title: 'Job title',
  bio: 'Bio',
  linkedin_url: 'LinkedIn profile',
  github_handle: 'GitHub username',
};

const EMPTY_PROFILE: ProfileFields = {
  name: '',
  organization: '',
  job_title: '',
  bio: '',
  linkedin_url: '',
  github_handle: '',
};

export function profileFields(user: User): ProfileFields {
  return {
    name: user.name || '',
    organization: user.organization || '',
    job_title: user.job_title || '',
    bio: user.bio || '',
    linkedin_url: user.linkedin_url || '',
    github_handle: user.github_handle || '',
  };
}

/** The unsaved profile edits: kept for a return to the page, never overwritten by a refresh of the user. */
const PROFILE_DRAFT = { scope: 'account', page: 'profile' };

type FastApiValidationError = {
  loc?: (string | number)[];
  msg?: string;
};

function formatApiError(err: unknown, fallback: string): string {
  if (!err || typeof err !== 'object') return fallback;
  const detail = (err as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = (detail as FastApiValidationError[])
      .map((d) => {
        const field = Array.isArray(d?.loc)
          ? d.loc.filter((p) => p !== 'body').join('.')
          : '';
        return field ? `${field}: ${d?.msg ?? ''}`.trim() : (d?.msg ?? '');
      })
      .filter(Boolean);
    if (messages.length) return messages.join('\n');
  }
  return fallback;
}

export default function ProfilePage() {
  const authUser = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  // The server's snapshot is the user as the store holds it; the edits are a draft over it, so
  // a background refresh of the user updates the fields not edited and never the edited ones.
  const server = useMemo(() => (authUser ? profileFields(authUser) : null), [authUser]);
  const draft = usePageDraft(PROFILE_DRAFT, server);
  const { name, organization, job_title: jobTitle, bio, linkedin_url: linkedinUrl, github_handle: githubHandle } =
    draft.values ?? EMPTY_PROFILE;
  const email = authUser?.email || '';
  const avatarUrl = authUser?.avatar || '';
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      toast.error('Not an image', 'Upload a PNG, JPG, GIF or WEBP file.');
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      toast.error('Image too large', 'The file must be under 2 MB.');
      return;
    }

    setUploading(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const formData = new FormData();
      formData.append('file', file);

      const response = await authFetch(
        `/api/auth/upload-avatar`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (response.ok) {
        const data = await response.json();
        const fullUrl = `${getApiUrl()}${data.avatar_url}`;
        if (authUser) {
          setUser({ ...authUser, avatar: fullUrl });
        }
      } else {
        const error = await response.json().catch(() => ({}));
        toast.error('Upload failed', formatApiError(error, 'Unknown error'));
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload avatar');
    } finally {
      setUploading(false);
      if (event.target) {
        event.target.value = '';
      }
    }
  };

  const handleAvatarRemove = async () => {
    if (!avatarUrl) return;
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch('/api/auth/avatar', { method: 'DELETE' });
      if (response.ok) {
        if (authUser) {
          setUser({ ...authUser, avatar: undefined });
        }
      } else {
        const error = await response.json().catch(() => ({}));
        toast.error('Remove failed', formatApiError(error, 'Unknown error'));
      }
    } catch (error) {
      console.error('Remove avatar error:', error);
      toast.error('Failed to remove avatar');
    }
  };

  const handleSave = async () => {
    try {
      const { authFetch } = await import('@/stores/auth');
      const payload: Record<string, string> = {};
      const trimmedName = name.trim();
      if (trimmedName) payload.name = trimmedName;
      payload.organization = organization.trim();
      payload.job_title = jobTitle.trim();
      payload.bio = bio.trim();
      payload.linkedin_url = linkedinUrl.trim();
      payload.github_handle = githubHandle.trim();

      const response = await authFetch('/api/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        toast.error('Failed to save profile', formatApiError(err, 'Unknown error'));
        return;
      }

      const updated = await response.json();
      const normalizeAvatar = (a?: string) =>
        a && a.startsWith('/') ? `${getApiUrl()}${a}` : a;
      if (authUser) {
        setUser({
          ...authUser,
          name: updated.name,
          email: updated.email,
          avatar: normalizeAvatar(updated.avatar),
          organization: updated.organization,
          job_title: updated.job_title,
          bio: updated.bio,
          linkedin_url: updated.linkedin_url ?? undefined,
          github_handle: updated.github_handle ?? undefined,
        });
      }
      draft.discard();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
      toast.error('Failed to save profile');
    }
  };

  return (
    <div className="account-profile-page">
      <AccountPageHeader
        title="Profile"
        subtitle="Manage your personal information"
        actions={
          <button
            onClick={handleSave}
            className={
              saved
                ? 'account-profile-save-button account-profile-save-button-saved'
                : 'account-profile-save-button'
            }
          >
            <Save size={16} />
            {saved ? 'Saved!' : 'Save Changes'}
          </button>
        }
      />

      {draft.dirty.length > 0 ? (
        <div className="account-profile-draft" role="status">
          <p className="account-profile-draft-text">
            {draft.conflicts.length > 0
              ? `Changed elsewhere since you began editing: ${draft.conflicts.map((f) => FIELD_LABELS[f]).join(', ')}. Saving keeps your version.`
              : 'Unsaved changes.'}
          </p>
          <button type="button" onClick={draft.discard} className="account-profile-draft-discard">
            Discard changes
          </button>
        </div>
      ) : null}

      <div className="account-profile-avatar-section">
        <div className="account-profile-avatar-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
            onChange={handleAvatarUpload}
            className="account-profile-avatar-input"
          />
          {avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatarUrl}
              alt={name}
              className="account-profile-avatar-image"
            />
          ) : (
            <div className="account-profile-avatar-placeholder">
              {name.charAt(0).toUpperCase()}
            </div>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="account-profile-avatar-upload-button"
            title="Upload avatar"
          >
            {uploading ? (
              <RefreshCw size={16} className="account-profile-avatar-upload-button-spin" />
            ) : (
              <Camera size={16} />
            )}
          </button>
        </div>
        <div>
          <h3 className="account-profile-avatar-info-name">{name}</h3>
          <p className="account-profile-avatar-info-email">{email}</p>
          <p className="account-profile-avatar-info-hint">
            Click camera icon to upload avatar (max 2MB)
          </p>
          {avatarUrl && (
            <button
              onClick={handleAvatarRemove}
              className="account-profile-avatar-remove-button"
            >
              <X size={12} />
              Remove picture
            </button>
          )}
        </div>
      </div>

      <AccountSectionCard padded stack>
        <div className="account-profile-form-grid">
          <div className="account-profile-field">
            <label className="account-profile-field-label">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => draft.set({ name: e.target.value })}
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Email</label>
            <input
              type="email"
              value={email}
              readOnly
              aria-readonly="true"
              className="account-profile-field-input account-profile-field-input-readonly"
            />
            <p className="account-profile-field-hint">
              Your identity provider manages your email address, so it can&apos;t be changed here.
            </p>
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Organization</label>
            <input
              type="text"
              value={organization}
              onChange={(e) => draft.set({ organization: e.target.value })}
              placeholder="Your organization"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Job title</label>
            <input
              type="text"
              value={jobTitle}
              onChange={(e) => draft.set({ job_title: e.target.value })}
              placeholder="Your job title"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">LinkedIn profile</label>
            <input
              type="url"
              value={linkedinUrl}
              onChange={(e) => draft.set({ linkedin_url: e.target.value })}
              placeholder="https://www.linkedin.com/in/your-name"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">GitHub username</label>
            <input
              type="text"
              value={githubHandle}
              onChange={(e) => draft.set({ github_handle: e.target.value })}
              placeholder="your-github-username"
              className="account-profile-field-input"
            />
          </div>
        </div>
        <div className="account-profile-field">
          <div className="account-profile-bio-header">
            <label className="account-profile-field-label">Bio</label>
            <span
              className={
                bio.length > BIO_MAX_LENGTH
                  ? 'account-profile-bio-count account-profile-bio-count-over'
                  : 'account-profile-bio-count'
              }
            >
              {bio.length} / {BIO_MAX_LENGTH}
            </span>
          </div>
          <textarea
            value={bio}
            onChange={(e) => draft.set({ bio: e.target.value.slice(0, BIO_MAX_LENGTH) })}
            placeholder="Tell us about yourself..."
            rows={12}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>
    </div>
  );
}
