'use client';

import { useState, useEffect, useRef } from 'react';
import { Camera, Save, X, RefreshCw } from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { useAuthStore } from '@/stores/auth';
import { AccountPageHeader } from '../components/account-page-header';
import { AccountSectionCard } from '../components/account-section-card';
import './profile.css';

const BIO_MAX_LENGTH = 2000;

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
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [bio, setBio] = useState('');
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (authUser) {
      setName(authUser.name || '');
      setEmail(authUser.email || '');
      setCompany(authUser.company || '');
      setRole(authUser.role || '');
      setBio(authUser.bio || '');
      setAvatarUrl(authUser.avatar || '');
    }
  }, [authUser]);

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      alert('Please upload a valid image file (PNG, JPG, GIF, or WEBP)');
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      alert('File size must be less than 2MB');
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
        setAvatarUrl(fullUrl);

        if (authUser) {
          setUser({ ...authUser, avatar: fullUrl });
        }
      } else {
        const error = await response.json().catch(() => ({}));
        alert(`Upload failed: ${formatApiError(error, 'Unknown error')}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload avatar');
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
        setAvatarUrl('');
        if (authUser) {
          setUser({ ...authUser, avatar: undefined });
        }
      } else {
        const error = await response.json().catch(() => ({}));
        alert(`Remove failed: ${formatApiError(error, 'Unknown error')}`);
      }
    } catch (error) {
      console.error('Remove avatar error:', error);
      alert('Failed to remove avatar');
    }
  };

  const handleSave = async () => {
    try {
      const { authFetch } = await import('@/stores/auth');
      const payload: Record<string, string> = {};
      const trimmedName = name.trim();
      const trimmedEmail = email.trim();
      if (trimmedName) payload.name = trimmedName;
      if (trimmedEmail) payload.email = trimmedEmail;
      payload.company = company.trim();
      payload.role = role.trim();
      payload.bio = bio.trim();

      const response = await authFetch('/api/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        alert(formatApiError(err, 'Failed to save profile'));
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
          // @ts-ignore - store model extended
          company: updated.company,
          // @ts-ignore
          role: updated.role,
          // @ts-ignore
          bio: updated.bio,
        } as any);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
      alert('Failed to save profile');
    }
  };

  return (
    <div className="account-profile-page">
      <AccountPageHeader
        title="Profile"
        subtitle="Manage your personal information"
      />

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
              onChange={(e) => setName(e.target.value)}
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Company</label>
            <input
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Your company"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Role</label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Your role"
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
            onChange={(e) => setBio(e.target.value.slice(0, BIO_MAX_LENGTH))}
            placeholder="Tell us about yourself..."
            rows={12}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>

      <div className="account-profile-actions">
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
      </div>
    </div>
  );
}
