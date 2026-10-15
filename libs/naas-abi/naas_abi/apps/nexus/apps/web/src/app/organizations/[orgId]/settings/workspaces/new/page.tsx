'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, Camera, FolderPlus, X } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import { slugify, WORKSPACE_SLUG } from './slug';
import '@/app/account/profile/profile.css';
import '../../users/users.css';

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml'];
const LOGO_MAX_BYTES = 5 * 1024 * 1024;

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
 * Create workspace (Organization Settings > Workspaces). The logo is picked
 * here and uploaded right after the workspace exists, into the workspace drive
 * (``.settings/logos/logo.<ext>``, previous logos archived), like account avatars.
 */
export default function OrgCreateWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const listHref = orgSettingsSectionPath(orgId, 'workspaces');

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugEdited, setSlugEdited] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!logoFile) {
      setLogoPreview('');
      return;
    }
    const url = URL.createObjectURL(logoFile);
    setLogoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [logoFile]);

  const effectiveSlug = slugEdited ? slug : slugify(name);
  const slugValid = WORKSPACE_SLUG.test(effectiveSlug);
  const canCreate = name.trim().length > 0 && slugValid && !creating;

  const pickLogo = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!LOGO_TYPES.includes(file.type)) {
      setError('Please choose a PNG, JPG, GIF, WEBP or SVG image.');
      return;
    }
    if (file.size > LOGO_MAX_BYTES) {
      setError('The logo must be less than 5MB.');
      return;
    }
    setError('');
    setLogoFile(file);
  };

  const handleCreate = async () => {
    if (!canCreate) return;
    setError('');
    setCreating(true);
    try {
      const res = await authFetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), slug: effectiveSlug, organization_id: orgId }),
      });
      if (!res.ok) {
        throw new Error(await readApiError(res, `Failed to create the workspace (HTTP ${res.status}).`));
      }
      const workspace: { id: string } = await res.json();
      if (logoFile) {
        const form = new FormData();
        form.append('file', logoFile);
        const upload = await authFetch(`/api/workspaces/${workspace.id}/upload-logo`, {
          method: 'POST',
          body: form,
        });
        if (!upload.ok) {
          throw new Error(
            `Workspace created, but the logo could not be uploaded: ${await readApiError(
              upload,
              `HTTP ${upload.status}`
            )}. Upload it from the workspace settings.`
          );
        }
      }
      router.push(listHref);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to create the workspace');
      setCreating(false);
    }
  };

  return (
    <div className="account-profile-page">
      <Link href={listHref} className="org-member-detail-back">
        <ArrowLeft size={14} />
        Workspaces
      </Link>

      <AccountPageHeader
        title="Create workspace"
        subtitle="Add a workspace to this organization. You become its owner; org owners and admins reach it too."
        actions={
          <div className="org-member-detail-actions">
            <button
              type="button"
              onClick={() => router.push(listHref)}
              className="org-member-detail-cancel-button"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={!canCreate}
              className="account-profile-save-button"
            >
              <FolderPlus size={16} />
              {creating ? 'Creating...' : 'Create workspace'}
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

      <div className="account-profile-avatar-section">
        <div className="account-profile-avatar-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            accept={LOGO_TYPES.join(',')}
            onChange={pickLogo}
            className="account-profile-avatar-input"
          />
          {logoPreview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoPreview} alt="" className="account-profile-avatar-image" />
          ) : (
            <div className="account-profile-avatar-placeholder">
              {(name.trim() || '?').charAt(0).toUpperCase()}
            </div>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={creating}
            className="account-profile-avatar-upload-button"
            title="Choose a logo"
          >
            <Camera size={16} />
          </button>
        </div>
        <div>
          <h3 className="account-profile-avatar-info-name">{name.trim() || 'New workspace'}</h3>
          <p className="account-profile-avatar-info-email">/{effectiveSlug || 'slug'}</p>
          <p className="account-profile-avatar-info-hint">
            Workspace logo (PNG, JPG, GIF, WEBP or SVG, max 5MB), uploaded when the workspace is
            created. Without one, the organization logo is shown.
          </p>
          {logoFile ? (
            <button
              type="button"
              onClick={() => setLogoFile(null)}
              className="account-profile-avatar-remove-button"
            >
              <X size={12} />
              Remove logo
            </button>
          ) : null}
        </div>
      </div>

      <AccountSectionCard padded stack>
        <div className="account-profile-form-grid">
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-workspace-name">
              Name
            </label>
            <input
              id="create-workspace-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Workspace name"
              maxLength={200}
              className="account-profile-field-input"
              autoFocus
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-workspace-slug">
              Slug
            </label>
            <input
              id="create-workspace-slug"
              type="text"
              value={effectiveSlug}
              onChange={(event) => {
                setSlugEdited(true);
                setSlug(event.target.value.toLowerCase());
              }}
              placeholder="workspace-slug"
              maxLength={100}
              className="account-profile-field-input"
            />
            {effectiveSlug && !slugValid && (
              <span className="account-profile-field-label org-create-workspace-hint">
                Lowercase letters, digits and dashes; at least two characters, no dash at either
                end.
              </span>
            )}
          </div>
        </div>
      </AccountSectionCard>
    </div>
  );
}
