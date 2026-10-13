'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Camera, RefreshCw, Save, X } from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import '@/app/account/profile/profile.css';

const BIO_MAX_LENGTH = 2000;

function photoUrl(avatar?: string) {
  if (!avatar) return '';
  return avatar.startsWith('/') ? `${getApiUrl()}${avatar}` : avatar;
}

function formatError(err: unknown, fallback: string) {
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export default function OrgUserProfilePage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const userId = params.userId as string;
  const authUser = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const {
    fetchMembers,
    updateMemberProfile,
    uploadMemberAvatar,
    removeMemberAvatar,
    membersCache,
    membersLoading,
  } = useOrganizationStore();

  const members = membersCache[orgId] || [];
  const member = members.find((row) => row.userId === userId) || null;
  const myMembership = members.find((row) => row.userId === authUser?.id);
  const canManage =
    myMembership?.role === 'owner' || myMembership?.role === 'admin';

  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [bio, setBio] = useState('');
  const [orgRole, setOrgRole] = useState<'admin' | 'member'>('member');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (orgId) void fetchMembers(orgId);
  }, [orgId, fetchMembers]);

  useEffect(() => {
    if (!membersLoading && members.length > 0 && !canManage) {
      router.replace(orgSettingsSectionPath(orgId, 'users'));
    }
  }, [membersLoading, members.length, canManage, orgId, router]);

  useEffect(() => {
    if (!member) return;
    setName(member.name || '');
    setCompany(member.company || '');
    setRole(member.jobTitle || '');
    setBio(member.bio || '');
    setOrgRole(member.role === 'admin' ? 'admin' : 'member');
    setAvatarUrl(photoUrl(member.avatar));
  }, [member]);

  const syncSelf = (next: {
    name?: string;
    company?: string;
    role?: string;
    bio?: string;
    avatar?: string | undefined;
  }) => {
    if (!authUser || authUser.id !== userId) return;
    setUser({
      ...authUser,
      name: next.name ?? authUser.name,
      avatar: next.avatar ?? authUser.avatar,
      company: next.company ?? authUser.company,
      role: next.role ?? authUser.role,
      bio: next.bio ?? authUser.bio,
    });
  };

  const canEditOrgRole =
    canManage && member?.role !== 'owner' && member?.userId !== authUser?.id;

  const handleAvatarUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file || !orgId || !member) return;
    const validTypes = [
      'image/png',
      'image/jpeg',
      'image/jpg',
      'image/gif',
      'image/webp',
    ];
    if (!validTypes.includes(file.type)) {
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
      const updated = await uploadMemberAvatar(orgId, member.userId, file);
      const nextUrl = photoUrl(updated?.avatar);
      setAvatarUrl(nextUrl);
      syncSelf({ avatar: nextUrl || undefined });
    } catch (err) {
      setError(formatError(err, 'Failed to upload avatar'));
    } finally {
      setUploading(false);
      if (event.target) event.target.value = '';
    }
  };

  const handleAvatarRemove = async () => {
    if (!orgId || !member || !avatarUrl) return;
    setError('');
    try {
      await removeMemberAvatar(orgId, member.userId);
      setAvatarUrl('');
      syncSelf({ avatar: undefined });
    } catch (err) {
      setError(formatError(err, 'Failed to remove avatar'));
    }
  };

  const handleSave = async () => {
    if (!orgId || !member || !canManage) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Name is required');
      return;
    }
    setError('');
    setSaving(true);
    try {
      await updateMemberProfile(orgId, member.userId, {
        name: trimmedName,
        company: company.trim(),
        job_title: role.trim(),
        bio: bio.trim(),
        ...(canEditOrgRole ? { role: orgRole } : {}),
      });
      syncSelf({
        name: trimmedName,
        company: company.trim(),
        role: role.trim(),
        bio: bio.trim(),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(formatError(err, 'Failed to save profile'));
    } finally {
      setSaving(false);
    }
  };

  if (membersLoading && !member) {
    return <p className="text-sm text-muted-foreground">Loading profile...</p>;
  }

  if (!member) {
    return <p className="text-sm text-muted-foreground">User not found.</p>;
  }

  const email = member.email || '';

  return (
    <div className="account-profile-page">
      <AccountPageHeader
        title="Profile"
        subtitle="Manage their personal information"
      />

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="account-profile-avatar-section">
        <div className="account-profile-avatar-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
            onChange={(event) => void handleAvatarUpload(event)}
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
              {(name || email || '?').charAt(0).toUpperCase()}
            </div>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="account-profile-avatar-upload-button"
            title="Upload avatar"
          >
            {uploading ? (
              <RefreshCw
                size={16}
                className="account-profile-avatar-upload-button-spin"
              />
            ) : (
              <Camera size={16} />
            )}
          </button>
        </div>
        <div>
          <h3 className="account-profile-avatar-info-name">
            {name || 'Unknown'}
          </h3>
          <p className="account-profile-avatar-info-email">{email}</p>
          <p className="account-profile-avatar-info-hint">
            Click camera icon to upload avatar (max 2MB)
          </p>
          {avatarUrl ? (
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
            <label className="account-profile-field-label">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Email</label>
            <input
              type="email"
              value={email}
              className="account-profile-field-input"
              disabled
              readOnly
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Company</label>
            <input
              type="text"
              value={company}
              onChange={(event) => setCompany(event.target.value)}
              placeholder="Company"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Role</label>
            <input
              type="text"
              value={role}
              onChange={(event) => setRole(event.target.value)}
              placeholder="Job title"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">
              Organization role
            </label>
            <select
              value={member.role === 'owner' ? 'owner' : orgRole}
              onChange={(event) =>
                setOrgRole(event.target.value as 'admin' | 'member')
              }
              className="account-profile-field-input"
              disabled={!canEditOrgRole}
            >
              {member.role === 'owner' ? (
                <option value="owner">Owner</option>
              ) : (
                <>
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </>
              )}
            </select>
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
            onChange={(event) =>
              setBio(event.target.value.slice(0, BIO_MAX_LENGTH))
            }
            placeholder="Tell us about yourself..."
            rows={12}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>

      <div className="account-profile-actions">
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={!name.trim() || saving}
          className={
            saved
              ? 'account-profile-save-button account-profile-save-button-saved'
              : 'account-profile-save-button'
          }
        >
          <Save size={16} />
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
