'use client';

import { useState, useRef, useEffect } from 'react';
import {
  Brush,
  Upload,
  Image as ImageIcon,
  Check,
  X,
  RefreshCw,
  Smile,
  Palette,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  SettingsEmpty,
  SettingsField,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { getApiUrl } from '@/lib/config';
import {
  useWorkspaceStore,
  PRESET_COLORS,
  DEFAULT_THEME,
  type WorkspaceTheme,
} from '@/stores/workspace';

// Common emoji choices for workspace icons
const EMOJI_OPTIONS = [
  '🔮', '🚀', '💎', '🎯', '⚡', '🔥', '🌟', '💡',
  '🏢', '📊', '🎨', '🔧', '📁', '🗂️', '💼', '🏠',
  '🌍', '🌐', '☁️', '🔒', '🛡️', '⚙️', '🎮', '🎵',
];

export default function ThemeSettingsPage() {
  // Use reactive selectors instead of getCurrentWorkspace()
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const updateWorkspaceTheme = useWorkspaceStore((state) => state.updateWorkspaceTheme);
  const updateWorkspace = useWorkspaceStore((state) => state.updateWorkspace);
  
  // Compute workspace from reactive state
  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const theme = workspace?.theme || DEFAULT_THEME;

  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [customColor, setCustomColor] = useState(theme.primaryColor);
  const [logoUrl, setLogoUrl] = useState(theme.logoUrl || '');
  const [backgroundImageUrl, setBackgroundImageUrl] = useState(theme.backgroundImageUrl || '');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Sync local state when workspace changes
  useEffect(() => {
    if (workspace) {
      setCustomColor(workspace.theme?.primaryColor || DEFAULT_THEME.primaryColor);
      setLogoUrl(workspace.theme?.logoUrl || '');
      setBackgroundImageUrl(workspace.theme?.backgroundImageUrl || '');
    }
  }, [workspace]);

  if (!workspace) {
    return <SettingsEmpty title="No workspace selected" />;
  }

  const handleColorChange = (color: string) => {
    updateWorkspaceTheme({ primaryColor: color });
    setCustomColor(color);
  };

  const handleEmojiSelect = (emoji: string) => {
    updateWorkspaceTheme({ logoEmoji: emoji });
    setShowEmojiPicker(false);
  };

  const handleLogoUrlChange = (url: string) => {
    setLogoUrl(url);
    updateWorkspaceTheme({ logoUrl: url });
  };

  const handleBackgroundImageUrlChange = (url: string) => {
    setBackgroundImageUrl(url);
    updateWorkspaceTheme({ backgroundImageUrl: url });
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadError(null);

    // Validate file type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml'];
    if (!validTypes.includes(file.type)) {
      setUploadError('Please upload a valid image file (PNG, JPG, GIF, WEBP, or SVG)');
      return;
    }

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      setUploadError('File size must be less than 5MB');
      return;
    }

    setUploading(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const formData = new FormData();
      formData.append('file', file);

      const response = await authFetch(
        `/api/workspaces/${currentWorkspaceId}/upload-logo`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (response.ok) {
        const data = await response.json();
        // Use the API base URL for the logo
        const fullUrl = `${getApiUrl()}${data.logo_url}`;
        setLogoUrl(fullUrl);
        updateWorkspaceTheme({ logoUrl: fullUrl });
      } else {
        const error = await response.json();
        setUploadError(`Upload failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadError('Failed to upload logo');
    } finally {
      setUploading(false);
      // Reset input
      if (event.target) {
        event.target.value = '';
      }
    }
  };

  const handleResetTheme = () => {
    updateWorkspaceTheme({ ...DEFAULT_THEME });
    setCustomColor(DEFAULT_THEME.primaryColor);
    setLogoUrl('');
  };

  const selectedRing = 'ring-2 ring-foreground ring-offset-2 ring-offset-background';
  const isCustomColor = !PRESET_COLORS.some((c) => c.value === theme.primaryColor);

  return (
    <div className="space-y-6">
      <SettingsPageHeader title="Workspace Theme" description="Customize the look and feel of your workspace" />

      <SettingsSection title="Preview">
        <div className="flex items-center gap-4 p-4" style={{ backgroundColor: theme.sidebarColor || '#111111' }}>
          <div
            className="flex h-12 w-12 items-center justify-center overflow-hidden text-2xl text-white"
            style={{ backgroundColor: theme.logoUrl ? 'transparent' : theme.primaryColor }}
          >
            {theme.logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={theme.logoUrl} alt="Logo" className="h-full w-full object-cover" />
            ) : (
              theme.logoEmoji || workspace.name.charAt(0)
            )}
          </div>
          <div>
            <h4 className="text-lg font-semibold text-white">{workspace.name}</h4>
            <p className="text-sm text-gray-400">{workspace.description}</p>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <ImageIcon size={16} className="text-muted-foreground" />
            Logo
          </span>
        }
      >
        <div className="space-y-5">
          <SettingsField label="Emoji Icon">
            <div className="relative">
              <Button variant="secondary" className="h-12 gap-3 px-4" onClick={() => setShowEmojiPicker(!showEmojiPicker)}>
                <span className="text-2xl">{theme.logoEmoji || '📁'}</span>
                <span className="font-normal text-muted-foreground">Click to change emoji</span>
                <Smile size={16} className="ml-2 text-muted-foreground" />
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
          </SettingsField>

          <SettingsField label="Logo Image" hint="The logo will be used instead of the emoji icon">
            <div className="space-y-3">
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <Button variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                  {uploading ? (
                    <>
                      <RefreshCw size={16} className="animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload size={16} />
                      Upload Logo
                    </>
                  )}
                </Button>
                <p className="mt-1 text-xs text-muted-foreground">PNG, JPG, GIF, WEBP, or SVG (max 5MB)</p>
              </div>
              {uploadError && <SettingsNotice tone="error">{uploadError}</SettingsNotice>}
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Or enter a URL</p>
                <div className="flex gap-2">
                  <Input
                    type="url"
                    value={logoUrl}
                    onChange={(e) => handleLogoUrlChange(e.target.value)}
                    placeholder="https://example.com/logo.png"
                    className="flex-1"
                  />
                  {logoUrl && (
                    <Button variant="secondary" size="icon" className="h-9 w-9" onClick={() => handleLogoUrlChange('')} title="Clear">
                      <X size={16} />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </SettingsField>

          <SettingsField label="Desktop wallpaper" hint="URL of the image used as the Home canvas background">
            <div className="flex gap-2">
              <Input
                type="url"
                value={backgroundImageUrl}
                onChange={(e) => handleBackgroundImageUrlChange(e.target.value)}
                placeholder="https://example.com/hero.jpg"
                className="flex-1"
              />
              {backgroundImageUrl && (
                <Button
                  variant="secondary"
                  size="icon"
                  className="h-9 w-9"
                  onClick={() => handleBackgroundImageUrlChange('')}
                  title="Clear"
                >
                  <X size={16} />
                </Button>
              )}
            </div>
          </SettingsField>
        </div>
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
        </div>
      </SettingsSection>

      <div className="flex items-center justify-between border-t border-border pt-6">
        <Button variant="secondary" onClick={handleResetTheme}>
          <RefreshCw size={16} />
          Reset to Default
        </Button>
        <p className="text-sm text-muted-foreground">Changes are saved automatically</p>
      </div>
    </div>
  );
}
