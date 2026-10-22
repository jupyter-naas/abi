'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Brush,
  Camera,
  Check,
  Image as ImageIcon,
  Palette,
  RefreshCw,
  Save,
  Trash2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  SettingsEmpty,
  SettingsField,
  SettingsNotice,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { getApiUrl } from '@/lib/config';
import { fetchCurrentBackgroundImage } from '@/lib/home-background';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { authFetch } from '@/stores/auth';
import {
  useWorkspaceStore,
  PRESET_COLORS,
  DEFAULT_THEME,
} from '@/stores/workspace';
import { BackgroundImageEditor } from '../../home/components/background-image-editor';
import { resolveDeskImageUrl } from '../../home/home-desk';
import { WorkspaceConfiguration } from './workspace-configuration';
import { WorkspaceGroupSelect } from '@/app/organizations/[orgId]/settings/workspaces/workspace-group-select';
import { WorkspaceOwnerSelect } from '@/app/organizations/[orgId]/settings/workspaces/workspace-owner-select';
import '@/app/account/profile/profile.css';
import './general.css';

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml'];
const LOGO_MAX_BYTES = 5 * 1024 * 1024;
/** Same limit as the API (WorkspaceUpdate.description). */
const DESCRIPTION_MAX_LENGTH = 200;

function assetUrl(url?: string | null): string {
  if (!url) return '';
  return url.startsWith('/') ? `${getApiUrl()}${url}` : url;
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
 * Settings → General: the workspace's identity (name, group, slug, description,
 * and logo stored in the workspace drive like account avatars), its desk
 * wallpaper (the same editor as Home → File → Edit background image) and its
 * colors.
 */
export default function GeneralSettingsPage() {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const updateWorkspaceTheme = useWorkspaceStore((state) => state.updateWorkspaceTheme);
  const applyWorkspaceTheme = useWorkspaceStore((state) => state.applyWorkspaceTheme);

  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const theme = workspace?.theme || DEFAULT_THEME;
  const canEdit = workspace?.currentUserRole === 'owner' || workspace?.currentUserRole === 'admin';

  const updateWorkspace = useWorkspaceStore((state) => state.updateWorkspace);
  const [name, setName] = useState(workspace?.name ?? '');
  const [description, setDescription] = useState(workspace?.description ?? '');
  const [group, setGroup] = useState(workspace?.group ?? '');
  const [existingGroups, setExistingGroups] = useState<string[]>([]);
  const [ownerId, setOwnerId] = useState(workspace?.ownerId ?? '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [customColor, setCustomColor] = useState(theme.primaryColor);
  const [uploading, setUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // The wallpaper editor renders its Save / Discard / Remove in the section header.
  const [wallpaperActions, setWallpaperActions] = useState<HTMLDivElement | null>(null);
  // Remounts the inline wallpaper editor after Save/Cancel so it reloads the current wallpaper.
  const [wallpaperEditorKey, setWallpaperEditorKey] = useState(0);
  const [driveBackgroundUrl, setDriveBackgroundUrl] = useState<string | undefined>();

  useEffect(() => {
    if (workspace) setCustomColor(workspace.theme?.primaryColor || DEFAULT_THEME.primaryColor);
  }, [workspace]);

  useEffect(() => {
    const orgId = workspace?.organizationId;
    if (!orgId) {
      setExistingGroups([]);
      return;
    }
    let cancelled = false;
    void authFetch(`/api/organizations/${orgId}/workspaces`)
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const rows: { workspace_group?: string | null }[] = await res.json();
        const groups = new Set(
          rows.map((row) => row.workspace_group?.trim()).filter(Boolean) as string[]
        );
        setExistingGroups([...groups].sort((a, b) => a.localeCompare(b)));
      })
      .catch(() => {
        if (!cancelled) setExistingGroups([]);
      });
    return () => {
      cancelled = true;
    };
  }, [workspace?.organizationId]);

  // Follow the store when switching workspace or after a save (not on every keystroke).
  const workspaceName = workspace?.name ?? '';
  const workspaceDescription = workspace?.description ?? '';
  const workspaceGroup = workspace?.group ?? '';
  useEffect(() => {
    setName(workspaceName);
    setDescription(workspaceDescription);
    setGroup(workspaceGroup);
    setDetailsError(null);
  }, [currentWorkspaceId, workspaceName, workspaceDescription, workspaceGroup]);

  // As on Home: the wallpaper lives in the workspace drive; when the theme lost
  // its pointer, ask the API for the committed file.
  const themeBackgroundUrl = resolveDeskImageUrl(theme.backgroundImageUrl);
  useEffect(() => {
    setDriveBackgroundUrl(undefined);
    if (!currentWorkspaceId || themeBackgroundUrl) return;
    let cancelled = false;
    void fetchCurrentBackgroundImage(currentWorkspaceId)
      .then((url) => {
        if (!cancelled && url) setDriveBackgroundUrl(url);
      })
      .catch(() => {
        // No wallpaper: the editor starts empty.
      });
    return () => {
      cancelled = true;
    };
  }, [currentWorkspaceId, themeBackgroundUrl]);
  const currentBackgroundUrl = themeBackgroundUrl || driveBackgroundUrl;

  if (!workspace || !currentWorkspaceId) {
    return <SettingsEmpty title="No workspace selected" />;
  }

  const logoSrc = assetUrl(theme.logoUrl);

  const handleColorChange = (color: string) => {
    updateWorkspaceTheme({ primaryColor: color });
    setCustomColor(color);
  };

  const trimmedName = name.trim();
  const trimmedDescription = description.trim();
  const trimmedGroup = group.trim();
  useEffect(() => {
    setOwnerId(workspace?.ownerId ?? '');
  }, [workspace?.ownerId]);

  const dirty =
    trimmedName !== workspace.name ||
    trimmedDescription !== (workspace.description ?? '') ||
    trimmedGroup !== (workspace.group ?? '') ||
    (workspace.organizationId ? ownerId !== (workspace.ownerId ?? '') : false);

  /** Save changes (top right): the workspace name, group and description. */
  const handleSaveDetails = async () => {
    if (!trimmedName) {
      setDetailsError('The workspace name cannot be empty.');
      return;
    }
    setDetailsError(null);
    setSaving(true);
    try {
      const res = await authFetch(`/api/workspaces/${currentWorkspaceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: trimmedName,
          description: trimmedDescription,
          workspace_group: trimmedGroup,
          ...(workspace.organizationId && ownerId ? { owner_id: ownerId } : {}),
        }),
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to save the workspace'));
      updateWorkspace(currentWorkspaceId, {
        name: trimmedName,
        description: trimmedDescription,
        group: trimmedGroup || undefined,
        ...(workspace.organizationId && ownerId ? { ownerId } : {}),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setDetailsError(err instanceof Error ? err.message : 'Failed to save the workspace');
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setLogoError(null);
    if (!LOGO_TYPES.includes(file.type)) {
      setLogoError('Please choose a PNG, JPG, GIF, WEBP or SVG image.');
      return;
    }
    if (file.size > LOGO_MAX_BYTES) {
      setLogoError('The logo must be less than 5MB.');
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await authFetch(`/api/workspaces/${currentWorkspaceId}/upload-logo`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to upload the logo'));
      const data: { logo_url: string } = await res.json();
      // The API already saved it (workspace drive): update the store only.
      applyWorkspaceTheme(currentWorkspaceId, { logoUrl: data.logo_url });
    } catch (err) {
      setLogoError(err instanceof Error ? err.message : 'Failed to upload the logo');
    } finally {
      setUploading(false);
    }
  };

  const handleLogoRemove = async () => {
    setLogoError(null);
    try {
      const res = await authFetch(`/api/workspaces/${currentWorkspaceId}/logo`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to remove the logo'));
      applyWorkspaceTheme(currentWorkspaceId, { logoUrl: '' });
    } catch (err) {
      setLogoError(err instanceof Error ? err.message : 'Failed to remove the logo');
    }
  };

  const handleResetColors = () => {
    updateWorkspaceTheme({
      primaryColor: DEFAULT_THEME.primaryColor,
      accentColor: DEFAULT_THEME.accentColor,
    });
    setCustomColor(DEFAULT_THEME.primaryColor);
  };

  const selectedRing = 'ring-2 ring-foreground ring-offset-2 ring-offset-background';
  const isCustomColor = !PRESET_COLORS.some((c) => c.value === theme.primaryColor);

  return (
    <div className="workspace-general space-y-6">
      <AccountPageHeader
        title="General"
        subtitle="The workspace name, group, description, logo, desk wallpaper and colors, plus its features and config preseeding."
        actions={
          canEdit ? (
            <button
              type="button"
              onClick={() => void handleSaveDetails()}
              disabled={!dirty || saving}
              className={
                saved
                  ? 'account-profile-save-button account-profile-save-button-saved workspace-general-save'
                  : 'account-profile-save-button workspace-general-save'
              }
            >
              <Save size={16} />
              {saving ? 'Saving...' : saved ? 'Saved!' : 'Save changes'}
            </button>
          ) : undefined
        }
      />

      {(detailsError || logoError) && (
        <SettingsNotice tone="error">{detailsError || logoError}</SettingsNotice>
      )}

      <div className="account-profile-avatar-section">
        <div className="account-profile-avatar-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            accept={LOGO_TYPES.join(',')}
            onChange={(event) => void handleLogoUpload(event)}
            className="account-profile-avatar-input"
          />
          {logoSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoSrc}
              alt="Workspace logo"
              className="account-profile-avatar-image workspace-logo-square"
            />
          ) : (
            <div
              className="account-profile-avatar-placeholder workspace-logo-square"
              style={{ backgroundColor: theme.primaryColor, color: '#fff' }}
            >
              {(trimmedName || workspace.name).charAt(0).toUpperCase()}
            </div>
          )}
          {canEdit && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="account-profile-avatar-upload-button"
              title="Upload a logo"
              aria-label="Upload a logo"
            >
              {uploading ? (
                <RefreshCw size={16} className="account-profile-avatar-upload-button-spin" />
              ) : (
                <Camera size={16} />
              )}
            </button>
          )}
        </div>
        <div className="min-w-0">
          <h3 className="account-profile-avatar-info-name">{workspace.name}</h3>
          <p className="account-profile-avatar-info-email">
            {workspace.slug ? `/${workspace.slug} · ` : ''}
            {workspace.id}
            {workspace.currentUserRole ? ` · Your role: ${workspace.currentUserRole}` : ''}
          </p>
          <p className="account-profile-avatar-info-hint">
            Logo: PNG, JPG, GIF, WEBP or SVG, max 5MB. Without a logo, the first letter of the
            name is shown.
          </p>
          {logoSrc && canEdit && (
            <button
              type="button"
              onClick={() => void handleLogoRemove()}
              className="mt-1 flex items-center gap-1.5 px-3 py-2 text-sm text-red-500 transition-colors hover:bg-red-500/10"
            >
              <Trash2 size={14} />
              Remove logo
            </button>
          )}
        </div>
      </div>

      <AccountSectionCard padded stack>
        <div className="account-profile-form-grid">
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="workspace-name">
              Workspace name
            </label>
            <input
              id="workspace-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={200}
              disabled={!canEdit || saving}
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="workspace-group">
              Group
            </label>
            <WorkspaceGroupSelect
              id="workspace-group"
              value={group}
              onChange={setGroup}
              existingGroups={existingGroups}
              disabled={!canEdit || saving}
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="workspace-slug">
              Slug
            </label>
            <input
              id="workspace-slug"
              type="text"
              value={workspace.slug ?? ''}
              readOnly
              disabled
              className="account-profile-field-input"
            />
          </div>
          {workspace.organizationId && canEdit && (
            <div className="account-profile-field">
              <label className="account-profile-field-label">Owner</label>
              <WorkspaceOwnerSelect
                orgId={workspace.organizationId}
                value={ownerId}
                onChange={setOwnerId}
                disabled={saving}
              />
            </div>
          )}
        </div>
        <div className="account-profile-field">
          <div className="account-profile-bio-header">
            <label className="account-profile-field-label" htmlFor="workspace-description">
              Description
            </label>
            <span className="account-profile-bio-count">{description.length} / {DESCRIPTION_MAX_LENGTH}</span>
          </div>
          <textarea
            id="workspace-description"
            value={description}
            onChange={(event) => setDescription(event.target.value.slice(0, DESCRIPTION_MAX_LENGTH))}
            placeholder="What is this workspace for?"
            rows={4}
            maxLength={DESCRIPTION_MAX_LENGTH}
            disabled={!canEdit || saving}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <ImageIcon size={16} className="text-muted-foreground" />
            Desktop wallpaper
          </span>
        }
        actions={canEdit ? <div ref={setWallpaperActions} /> : undefined}
      >
        {canEdit ? (
          <>
            <p className="mb-3 text-sm text-muted-foreground">
              The Home desk background. PNG, JPEG, GIF, WEBP or AVIF, up to 10 MB. Drag to move,
              scroll to zoom, then save.
            </p>
            <BackgroundImageEditor
              key={wallpaperEditorKey}
              open
              workspaceId={currentWorkspaceId}
              currentBackgroundUrl={currentBackgroundUrl}
              onClose={() => setWallpaperEditorKey((key) => key + 1)}
              onSaved={(backgroundImageUrl) =>
                applyWorkspaceTheme(currentWorkspaceId, { backgroundImageUrl })
              }
              onRemoved={() => {
                setDriveBackgroundUrl(undefined);
                applyWorkspaceTheme(currentWorkspaceId, { backgroundImageUrl: '' });
              }}
              saveLabel="Save wallpaper"
              cancelLabel="Discard changes"
              actionsContainer={wallpaperActions}
            />
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Only workspace owners and admins can change the wallpaper.
          </p>
        )}
      </SettingsSection>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <Palette size={16} className="text-muted-foreground" />
            Colors
          </span>
        }
        actions={
          <Button variant="secondary" size="sm" onClick={handleResetColors}>
            <RefreshCw size={14} />
            Reset colors
          </Button>
        }
      >
        <div className="space-y-6">
          <SettingsField label="Primary Color" hint={`Current: ${theme.primaryColor}`}>
            <div className="flex flex-wrap gap-3">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color.value}
                  type="button"
                  onClick={() => handleColorChange(color.value)}
                  className={cn(
                    'flex h-10 w-10 items-center justify-center transition-transform hover:scale-110',
                    theme.primaryColor === color.value && selectedRing
                  )}
                  style={{ backgroundColor: color.value }}
                  title={color.name}
                >
                  {theme.primaryColor === color.value && <Check size={18} className="text-white" />}
                </button>
              ))}

              <div className="relative">
                <input
                  type="color"
                  value={customColor}
                  onChange={(e) => handleColorChange(e.target.value)}
                  className="absolute inset-0 h-10 w-10 cursor-pointer opacity-0"
                  title="Custom color"
                />
                <div
                  className={cn(
                    'flex h-10 w-10 items-center justify-center border-2 border-dashed border-muted-foreground/50',
                    isCustomColor && selectedRing
                  )}
                  style={{ backgroundColor: isCustomColor ? theme.primaryColor : 'transparent' }}
                >
                  {isCustomColor ? (
                    <Check size={18} className="text-white" />
                  ) : (
                    <Brush size={16} className="text-muted-foreground" />
                  )}
                </div>
              </div>
            </div>
          </SettingsField>

          <SettingsField label="Accent Color" hint={`Current: ${theme.accentColor || 'Not set'}`}>
            <div className="flex flex-wrap gap-3">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color.value}
                  type="button"
                  onClick={() => updateWorkspaceTheme({ accentColor: color.value })}
                  className={cn(
                    'flex h-10 w-10 items-center justify-center transition-transform hover:scale-110',
                    theme.accentColor === color.value && selectedRing
                  )}
                  style={{ backgroundColor: color.value }}
                  title={color.name}
                >
                  {theme.accentColor === color.value && <Check size={16} className="text-white" />}
                </button>
              ))}
            </div>
          </SettingsField>

        </div>
      </SettingsSection>

      {canEdit && workspace && <WorkspaceConfiguration workspaceId={workspace.id} />}
    </div>
  );
}
