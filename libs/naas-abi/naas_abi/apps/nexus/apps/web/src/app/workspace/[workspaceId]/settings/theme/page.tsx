'use client';

import { useState, useRef, useEffect } from 'react';
import {
  Brush,
  Upload,
  Image,
  Check,
  X,
  RefreshCw,
  Smile,
  Palette,
} from 'lucide-react';
import { cn } from '@/lib/utils';
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
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Sync local state when workspace changes
  useEffect(() => {
    if (workspace) {
      setCustomColor(workspace.theme?.primaryColor || DEFAULT_THEME.primaryColor);
      setLogoUrl(workspace.theme?.logoUrl || '');
    }
  }, [workspace?.id, workspace?.theme?.primaryColor, workspace?.theme?.logoUrl]);

  if (!workspace) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">No workspace selected</p>
      </div>
    );
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

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml'];
    if (!validTypes.includes(file.type)) {
      alert('Please upload a valid image file (PNG, JPG, GIF, WEBP, or SVG)');
      return;
    }

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      alert('File size must be less than 5MB');
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
        alert(`Upload failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload logo');
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

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold">Workspace Theme</h2>
        <p className="mt-1 text-muted-foreground">
          Customize the look and feel of your workspace
        </p>
      </div>

      {/* Preview */}
      <div className="rounded-xl border bg-card p-6">
        <h3 className="mb-4 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Preview
        </h3>
        <div
          className="flex items-center gap-4 rounded-lg p-4"
          style={{ backgroundColor: theme.sidebarColor || '#111111' }}
        >
          {/* Logo preview */}
          <div
            className="flex h-12 w-12 items-center justify-center rounded-xl text-white text-2xl overflow-hidden"
            style={{ backgroundColor: theme.logoUrl ? 'transparent' : theme.primaryColor }}
          >
            {theme.logoUrl ? (
              <img
                src={theme.logoUrl}
                alt="Logo"
                className="h-full w-full object-cover"
              />
            ) : (
              theme.logoEmoji || workspace.name.charAt(0)
            )}
          </div>
          <div>
            <h4 className="text-lg font-semibold text-white">{workspace.name}</h4>
            <p className="text-sm text-gray-400">{workspace.description}</p>
          </div>
        </div>
      </div>

      {/* Logo Settings */}
      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Image size={18} className="text-muted-foreground" />
          <h3 className="text-lg font-medium">Logo</h3>
        </div>

        <div className="space-y-4">
          {/* Emoji selector */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Emoji Icon
            </label>
            <div className="relative">
              <button
                onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3 hover:bg-muted transition-colors"
              >
                <span className="text-2xl">{theme.logoEmoji || '📁'}</span>
                <span className="text-sm text-muted-foreground">
                  Click to change emoji
                </span>
                <Smile size={16} className="ml-auto text-muted-foreground" />
              </button>

              {showEmojiPicker && (
                <div className="absolute left-0 top-full z-50 mt-2 w-80 rounded-lg border bg-card p-4 shadow-lg">
                  <div className="grid grid-cols-8 gap-2">
                    {EMOJI_OPTIONS.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => handleEmojiSelect(emoji)}
                        className={cn(
                          'flex h-10 w-10 items-center justify-center rounded-lg text-xl transition-colors',
                          'hover:bg-primary/10',
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
          </div>

          {/* Logo URL */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Logo Image
            </label>
            
            {/* Upload button */}
            <div className="mb-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml"
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="flex items-center gap-2 rounded-lg border bg-background px-4 py-2 text-sm hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
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
              </button>
              <p className="mt-1 text-xs text-muted-foreground">
                PNG, JPG, GIF, WEBP, or SVG (max 5MB)
              </p>
            </div>

            {/* Or URL input */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                Or enter a URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={logoUrl}
                  onChange={(e) => handleLogoUrlChange(e.target.value)}
                  placeholder="https://example.com/logo.png"
                  className="flex-1 rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                />
                {logoUrl && (
                  <button
                    onClick={() => handleLogoUrlChange('')}
                    className="rounded-lg border px-3 py-2 hover:bg-muted"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            </div>
            
            <p className="mt-2 text-xs text-muted-foreground">
              The logo will be used instead of the emoji icon
            </p>
          </div>
        </div>
      </div>

      {/* Color Settings */}
      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Palette size={18} className="text-muted-foreground" />
          <h3 className="text-lg font-medium">Colors</h3>
        </div>

        <div className="space-y-6">
          {/* Primary Color */}
          <div>
            <label className="block text-sm font-medium mb-3">
              Primary Color
            </label>
            <div className="flex flex-wrap gap-3">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color.value}
                  onClick={() => handleColorChange(color.value)}
                  className={cn(
                    'group relative flex h-12 w-12 items-center justify-center rounded-xl transition-transform hover:scale-110',
                    theme.primaryColor === color.value && 'ring-2 ring-white ring-offset-2 ring-offset-background'
                  )}
                  style={{ backgroundColor: color.value }}
                  title={color.name}
                >
                  {theme.primaryColor === color.value && (
                    <Check size={20} className="text-white" />
                  )}
                </button>
              ))}

              {/* Custom color picker */}
              <div className="relative">
                <input
                  type="color"
                  value={customColor}
                  onChange={(e) => handleColorChange(e.target.value)}
                  className="absolute inset-0 h-12 w-12 cursor-pointer opacity-0"
                />
                <div
                  className={cn(
                    'flex h-12 w-12 items-center justify-center rounded-xl border-2 border-dashed border-muted-foreground/50 transition-colors',
                    !PRESET_COLORS.some((c) => c.value === theme.primaryColor) &&
                      'ring-2 ring-white ring-offset-2 ring-offset-background'
                  )}
                  style={{
                    backgroundColor: !PRESET_COLORS.some((c) => c.value === theme.primaryColor)
                      ? theme.primaryColor
                      : 'transparent',
                  }}
                >
                  {PRESET_COLORS.some((c) => c.value === theme.primaryColor) ? (
                    <Brush size={16} className="text-muted-foreground" />
                  ) : (
                    <Check size={20} className="text-white" />
                  )}
                </div>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Current: {theme.primaryColor}
            </p>
          </div>

          {/* Accent Color */}
          <div>
            <label className="block text-sm font-medium mb-3">
              Accent Color
            </label>
            <div className="flex flex-wrap gap-3">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color.value}
                  onClick={() => updateWorkspaceTheme({ accentColor: color.value })}
                  className={cn(
                    'group relative flex h-10 w-10 items-center justify-center rounded-lg transition-transform hover:scale-110',
                    theme.accentColor === color.value && 'ring-2 ring-white ring-offset-2 ring-offset-background'
                  )}
                  style={{ backgroundColor: color.value }}
                  title={color.name}
                >
                  {theme.accentColor === color.value && (
                    <Check size={16} className="text-white" />
                  )}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Current: {theme.accentColor || 'Not set'}
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between border-t pt-6">
        <button
          onClick={handleResetTheme}
          className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm hover:bg-muted transition-colors"
        >
          <RefreshCw size={16} />
          Reset to Default
        </button>
        <p className="text-sm text-muted-foreground">
          Changes are saved automatically
        </p>
      </div>
    </div>
  );
}
