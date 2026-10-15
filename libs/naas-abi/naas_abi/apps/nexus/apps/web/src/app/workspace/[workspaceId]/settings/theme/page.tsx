'use client';

import { useEffect, useRef, useState } from 'react';
import { Brush, Camera, Check, Image as ImageIcon, Palette, RefreshCw, Smile, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  SettingsEmpty,
  SettingsField,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { getApiUrl } from '@/lib/config';
import { fetchCurrentBackgroundImage } from '@/lib/home-background';
import { authFetch } from '@/stores/auth';
import {
  useWorkspaceStore,
  PRESET_COLORS,
  DEFAULT_THEME,
} from '@/stores/workspace';
import { BackgroundImageEditor } from '../../home/components/background-image-editor';
import { resolveDeskImageUrl } from '../../home/home-desk';

// Common emoji choices for workspace icons
const EMOJI_OPTIONS = [
  '🔮', '🚀', '💎', '🎯', '⚡', '🔥', '🌟', '💡',
  '🏢', '📊', '🎨', '🔧', '📁', '🗂️', '💼', '🏠',
  '🌍', '🌐', '☁️', '🔒', '🛡️', '⚙️', '🎮', '🎵',
];

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml'];
const LOGO_MAX_BYTES = 5 * 1024 * 1024;

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
 * Settings → Theme: the workspace's identity (logo, stored in the workspace
 * drive like account avatars, or an emoji), its desk wallpaper (the same editor
 * as Home → File → Edit background image) and its colors.
 */
export default function ThemeSettingsPage() {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const updateWorkspaceTheme = useWorkspaceStore((state) => state.updateWorkspaceTheme);
  const applyWorkspaceTheme = useWorkspaceStore((state) => state.applyWorkspaceTheme);

  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const theme = workspace?.theme || DEFAULT_THEME;
  const canEdit = workspace?.currentUserRole === 'owner' || workspace?.currentUserRole === 'admin';

  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [customColor, setCustomColor] = useState(theme.primaryColor);
  const [uploading, setUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Remounts the inline wallpaper editor after Save/Cancel so it reloads the current wallpaper.
  const [wallpaperEditorKey, setWallpaperEditorKey] = useState(0);
  const [driveBackgroundUrl, setDriveBackgroundUrl] = useState<string | undefined>();

  useEffect(() => {
    if (workspace) setCustomColor(workspace.theme?.primaryColor || DEFAULT_THEME.primaryColor);
  }, [workspace]);

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

  const handleEmojiSelect = (emoji: string) => {
    updateWorkspaceTheme({ logoEmoji: emoji });
    setShowEmojiPicker(false);
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
    <div className="space-y-6">
      <SettingsPageHeader
        title="Workspace Theme"
        description="The workspace logo, desk wallpaper and colors. Changes are saved automatically."
      />

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <ImageIcon size={16} className="text-muted-foreground" />
            Identity
          </span>
        }
      >
        <div className="flex flex-wrap items-center gap-5">
          <div className="relative">
            <input
              ref={fileInputRef}
              type="file"
              accept={LOGO_TYPES.join(',')}
              onChange={(event) => void handleLogoUpload(event)}
              className="hidden"
            />
            <div
              className="flex h-20 w-20 items-center justify-center overflow-hidden text-3xl text-white"
              style={{ backgroundColor: logoSrc ? 'transparent' : theme.primaryColor }}
            >
              {logoSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoSrc} alt="Workspace logo" className="h-full w-full object-cover" />
              ) : (
                theme.logoEmoji || workspace.name.charAt(0)
              )}
            </div>
            {canEdit && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="absolute -bottom-2 -right-2 flex h-8 w-8 items-center justify-center bg-workspace-accent text-white shadow-md transition-colors hover:bg-workspace-accent/90 disabled:opacity-60"
                title="Upload a logo"
                aria-label="Upload a logo"
              >
                {uploading ? <RefreshCw size={14} className="animate-spin" /> : <Camera size={14} />}
              </button>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h4 className="truncate text-lg font-semibold text-foreground">{workspace.name}</h4>
            {workspace.description && (
              <p className="truncate text-sm text-muted-foreground">{workspace.description}</p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              Logo: PNG, JPG, GIF, WEBP or SVG, max 5MB. Without a logo, the emoji is shown.
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <div className="relative">
                <Button
                  variant="secondary"
                  size="sm"
                  className="gap-2"
                  onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                  disabled={!canEdit}
                >
                  <span className="text-base">{theme.logoEmoji || '📁'}</span>
                  Change emoji
                  <Smile size={14} className="text-muted-foreground" />
                </Button>
                {showEmojiPicker && (
                  <div className="absolute left-0 top-full z-50 mt-2 w-80 border border-border bg-popover p-3 shadow-lg">
                    <div className="grid grid-cols-8 gap-1">
                      {EMOJI_OPTIONS.map((emoji) => (
                        <button
                          key={emoji}
                          type="button"
                          onClick={() => handleEmojiSelect(emoji)}
                          className={cn(
                            'flex h-9 w-9 items-center justify-center text-xl transition-colors hover:bg-primary/10',
                            theme.logoEmoji === emoji && 'bg-primary/20 ring-2 ring-primary'
                          )}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {logoSrc && canEdit && (
                <Button variant="secondary" size="sm" className="gap-1" onClick={() => void handleLogoRemove()}>
                  <X size={14} />
                  Remove logo
                </Button>
              )}
            </div>
          </div>
        </div>
        {logoError && (
          <div className="mt-3">
            <SettingsNotice tone="error">{logoError}</SettingsNotice>
          </div>
        )}
      </SettingsSection>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <ImageIcon size={16} className="text-muted-foreground" />
            Desktop wallpaper
          </span>
        }
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
              fallbackColor={theme.backgroundColor}
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

          <div className="flex justify-end">
            <Button variant="secondary" onClick={handleResetColors}>
              <RefreshCw size={16} />
              Reset colors
            </Button>
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}
