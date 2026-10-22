'use client';

import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Brush, Camera, Check, Palette, Save, SlidersHorizontal, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { SettingsField, SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { OTHERS_GROUP } from '@/lib/workspace-picker';
import { authFetch } from '@/stores/auth';
import { DEFAULT_THEME, PRESET_COLORS } from '@/stores/workspace';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { orgSettingsSectionPath } from '../../lib/nav';
import {
  configurableFeatures,
  overridesFromChoices,
  WorkspaceFeaturesTable,
  type FeatureChoice,
  type WorkspaceFeatureCatalog,
} from '../workspace-features-table';
import { WorkspaceOwnerSelect } from '../workspace-owner-select';
import {
  catalogSeedPayload,
  WorkspaceInstancesSection,
  type CatalogSeedDraft,
} from '../workspace-instances-section';
import { useAuthStore } from '@/stores/auth';
import { slugify, WORKSPACE_SLUG } from './slug';
import '@/app/account/profile/profile.css';
import '@/app/workspace/[workspaceId]/settings/general/general.css';
import '../workspaces.css';

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml'];
const LOGO_MAX_BYTES = 5 * 1024 * 1024;
/** Same limit as the API (WorkspaceCreate.description). */
const DESCRIPTION_MAX_LENGTH = 200;
/** Group dropdown value that switches to typing a new group. */
const NEW_GROUP = '__new__';

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
 * Create workspace (Organization Settings > Workspaces), laid out like
 * Workspace Settings > General: logo, name, group, slug, description and
 * colors. Save (top right) creates it; the cross closes without saving. The
 * slug follows the name until edited. The group is picked from the
 * organization's groups, or typed as a new one. The logo is uploaded right
 * after the workspace exists, into the workspace drive
 * (``.settings/logos/logo.<ext>``); the desk wallpaper is set in General
 * once the workspace exists. Features left on Default follow the role
 * defaults and the config; any On/Off choice is saved as the workspace
 * overrides, like the Features column of the workspaces list, and then
 * replaces the config overrides (``workspace_overrides``) for this slug.
 */
export default function OrgCreateWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const listHref = orgSettingsSectionPath(orgId, 'workspaces');
  const currentUserId = useAuthStore((state) => state.user?.id);

  const [name, setName] = useState('');
  const [group, setGroup] = useState('');
  const [newGroup, setNewGroup] = useState(false);
  const [existingGroups, setExistingGroups] = useState<string[]>([]);
  const [slug, setSlug] = useState('');
  const [slugEdited, setSlugEdited] = useState(false);
  const [description, setDescription] = useState('');
  const [primaryColor, setPrimaryColor] = useState(DEFAULT_THEME.primaryColor);
  const [accentColor, setAccentColor] = useState(DEFAULT_THEME.accentColor ?? '');
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState('');
  const [featureCatalog, setFeatureCatalog] = useState<WorkspaceFeatureCatalog | null>(null);
  const [featureChoices, setFeatureChoices] = useState<Record<string, FeatureChoice>>({});
  const [featureCatalogFailed, setFeatureCatalogFailed] = useState(false);
  const [ownerId, setOwnerId] = useState('');
  const [catalogSeedDraft, setCatalogSeedDraft] = useState<CatalogSeedDraft>({});
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Groups already used in this organization, for the Group dropdown.
  useEffect(() => {
    if (!orgId) return;
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
        // No suggestions: "New group" still works.
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  useEffect(() => {
    if (currentUserId && !ownerId) setOwnerId(currentUserId);
  }, [currentUserId, ownerId]);

  // Feature catalog and role defaults, for the Features section.
  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    setFeatureCatalogFailed(false);
    // No catalog: the workspace follows the role defaults.
    void authFetch(`/api/organizations/${orgId}/workspace-features`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setFeatureCatalogFailed(true);
          return;
        }
        setFeatureCatalog(await res.json());
      })
      .catch(() => {
        if (!cancelled) setFeatureCatalogFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  useEffect(() => {
    if (!logoFile) {
      setLogoPreview('');
      return;
    }
    const url = URL.createObjectURL(logoFile);
    setLogoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [logoFile]);

  const trimmedName = name.trim();
  const effectiveSlug = slugEdited ? slug : slugify(name);
  const slugValid = WORKSPACE_SLUG.test(effectiveSlug);
  const canCreate = trimmedName.length > 0 && slugValid && !creating;

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
    const featureOverrides = overridesFromChoices(
      featureChoices,
      configurableFeatures(featureCatalog)
    );
    const catalog_seed = catalogSeedPayload(catalogSeedDraft);
    try {
      const res = await authFetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: trimmedName,
          slug: effectiveSlug,
          organization_id: orgId,
          owner_id: ownerId || currentUserId || undefined,
          workspace_group: group.trim() || null,
          description: description.trim() || null,
          primary_color: primaryColor,
          accent_color: accentColor || null,
          // Nothing changed: keep following the role defaults and the config.
          feature_overrides: Object.keys(featureOverrides).length ? featureOverrides : null,
          catalog_seed,
        }),
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

  const selectedRing = 'ring-2 ring-foreground ring-offset-2 ring-offset-background';
  const isCustomColor = !PRESET_COLORS.some((c) => c.value === primaryColor);

  return (
    <div
      className="workspace-general space-y-6"
      // Focus rings and Save follow the colour picked below.
      style={{ '--workspace-accent': primaryColor } as CSSProperties}
    >
      <AccountPageHeader
        title="Create workspace"
        subtitle="Add a workspace to this organization. Pick an owner, features, and optional instances; org owners and admins reach every workspace."
        actions={
          <div className="org-create-workspace-actions">
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={!canCreate}
              className="account-profile-save-button workspace-general-save"
            >
              <Save size={16} />
              {creating ? 'Creating...' : 'Create workspace'}
            </button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push(listHref)}
              disabled={creating}
              title="Close without creating"
              aria-label="Close without creating"
            >
              <X size={18} />
            </Button>
          </div>
        }
      />

      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}

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
            <img
              src={logoPreview}
              alt=""
              className="account-profile-avatar-image workspace-logo-square"
            />
          ) : (
            <div
              className="account-profile-avatar-placeholder workspace-logo-square"
              style={{ backgroundColor: primaryColor, color: '#fff' }}
            >
              {(trimmedName || '?').charAt(0).toUpperCase()}
            </div>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={creating}
            className="account-profile-avatar-upload-button"
            title="Choose a logo"
            aria-label="Choose a logo"
          >
            <Camera size={16} />
          </button>
        </div>
        <div className="min-w-0">
          <h3 className="account-profile-avatar-info-name">{trimmedName || 'New workspace'}</h3>
          <p className="account-profile-avatar-info-email">/{effectiveSlug || 'slug'}</p>
          <p className="account-profile-avatar-info-hint">
            Logo: PNG, JPG, GIF, WEBP or SVG, max 5MB, uploaded when the workspace is created.
            Without a logo, the first letter of the name is shown.
          </p>
          {logoFile && (
            <button
              type="button"
              onClick={() => setLogoFile(null)}
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
            <label className="account-profile-field-label" htmlFor="create-workspace-name">
              Workspace name
            </label>
            <input
              id="create-workspace-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Workspace name"
              maxLength={200}
              disabled={creating}
              className="account-profile-field-input"
              autoFocus
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-workspace-group">
              Group
            </label>
            <select
              id="create-workspace-group"
              value={newGroup ? NEW_GROUP : group}
              onChange={(event) => {
                if (event.target.value === NEW_GROUP) {
                  setNewGroup(true);
                  setGroup('');
                  return;
                }
                setNewGroup(false);
                setGroup(event.target.value);
              }}
              disabled={creating}
              className="account-profile-field-input"
            >
              <option value="">{OTHERS_GROUP} (no group)</option>
              {existingGroups.map((existing) => (
                <option key={existing} value={existing}>
                  {existing}
                </option>
              ))}
              <option value={NEW_GROUP}>+ New group…</option>
            </select>
            {newGroup && (
              <input
                type="text"
                value={group}
                onChange={(event) => setGroup(event.target.value)}
                placeholder="New group name"
                aria-label="New group name"
                maxLength={100}
                disabled={creating}
                className="account-profile-field-input org-create-workspace-new-group"
                autoFocus
              />
            )}
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label">Owner</label>
            <WorkspaceOwnerSelect
              orgId={orgId}
              value={ownerId}
              onChange={setOwnerId}
              disabled={creating}
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
              disabled={creating}
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
        <div className="account-profile-field">
          <div className="account-profile-bio-header">
            <label className="account-profile-field-label" htmlFor="create-workspace-description">
              Description
            </label>
            <span className="account-profile-bio-count">
              {description.length} / {DESCRIPTION_MAX_LENGTH}
            </span>
          </div>
          <textarea
            id="create-workspace-description"
            value={description}
            onChange={(event) => setDescription(event.target.value.slice(0, DESCRIPTION_MAX_LENGTH))}
            placeholder="What is this workspace for?"
            rows={4}
            maxLength={DESCRIPTION_MAX_LENGTH}
            disabled={creating}
            className="account-profile-field-textarea"
          />
        </div>
      </AccountSectionCard>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <SlidersHorizontal size={16} className="text-muted-foreground" />
            Features
          </span>
        }
        description="Default follows the role defaults. On shows a feature to every role, Off hides it. Any On or Off replaces the config overrides for this workspace. Change them later from the Features column of the workspaces list."
      >
        {featureCatalogFailed ? (
          <p className="text-sm text-muted-foreground">
            Features could not be loaded. The workspace will follow the role defaults; change
            them later from the Features column of the workspaces list.
          </p>
        ) : featureCatalog ? (
          <WorkspaceFeaturesTable
            catalog={featureCatalog}
            choices={featureChoices}
            disabled={creating}
            onChange={(feature, choice) =>
              setFeatureChoices((current) => ({ ...current, [feature]: choice }))
            }
          />
        ) : (
          <p className="text-sm text-muted-foreground">Loading features...</p>
        )}
      </SettingsSection>

      <WorkspaceInstancesSection
        orgId={orgId}
        featureCatalog={featureCatalog}
        featureChoices={featureChoices}
        draft={catalogSeedDraft}
        onDraftChange={setCatalogSeedDraft}
        disabled={creating}
      />

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <Palette size={16} className="text-muted-foreground" />
            Colors
          </span>
        }
      >
        <div className="space-y-6">
          <SettingsField label="Primary Color" hint={`Current: ${primaryColor}`}>
            <div className="flex flex-wrap gap-3">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color.value}
                  type="button"
                  onClick={() => setPrimaryColor(color.value)}
                  className={cn(
                    'flex h-10 w-10 items-center justify-center transition-transform hover:scale-110',
                    primaryColor === color.value && selectedRing
                  )}
                  style={{ backgroundColor: color.value }}
                  title={color.name}
                >
                  {primaryColor === color.value && <Check size={18} className="text-white" />}
                </button>
              ))}

              <div className="relative">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="absolute inset-0 h-10 w-10 cursor-pointer opacity-0"
                  title="Custom color"
                />
                <div
                  className={cn(
                    'flex h-10 w-10 items-center justify-center border-2 border-dashed border-muted-foreground/50',
                    isCustomColor && selectedRing
                  )}
                  style={{ backgroundColor: isCustomColor ? primaryColor : 'transparent' }}
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

          <SettingsField label="Accent Color" hint={`Current: ${accentColor || 'Not set'}`}>
            <div className="flex flex-wrap gap-3">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color.value}
                  type="button"
                  onClick={() => setAccentColor(color.value)}
                  className={cn(
                    'flex h-10 w-10 items-center justify-center transition-transform hover:scale-110',
                    accentColor === color.value && selectedRing
                  )}
                  style={{ backgroundColor: color.value }}
                  title={color.name}
                >
                  {accentColor === color.value && <Check size={16} className="text-white" />}
                </button>
              ))}
            </div>
          </SettingsField>
        </div>
      </SettingsSection>
    </div>
  );
}
