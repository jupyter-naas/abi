import type { CSSProperties } from 'react';

/** Workspace accent (falls back to primary) at 30% opacity — desk base and wallpaper tint. */
export const DESK_ACCENT_TINT =
  'color-mix(in srgb, var(--workspace-accent, var(--workspace-primary, #22c55e)) 30%, transparent)';

/** Flat overlay on wallpaper images (same tint as the empty desk). */
export const DESK_IMAGE_OVERLAY = `linear-gradient(${DESK_ACCENT_TINT}, ${DESK_ACCENT_TINT})`;

/** @deprecated Use DESK_ACCENT_TINT; kept for tests that reference the old dark desk. */
export const DESK_FALLBACK_COLOR = '#0a0a0a';

/** @deprecated Use DESK_IMAGE_OVERLAY. */
export const HERO_OVERLAY = DESK_IMAGE_OVERLAY;

export type DeskSurfaceId = 'chat' | 'files';

/** White or near-white theme leftovers must not paint the desk. */
export function isLightDeskColor(hex?: string): boolean {
  if (!hex) return true;
  let value = hex.trim().replace('#', '');
  if (value.length === 3) {
    value = value
      .split('')
      .map((ch) => ch + ch)
      .join('');
  }
  if (value.length !== 6 || /[^0-9a-fA-F]/.test(value)) return true;
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

export function deskFallbackColor(_themeColor?: string): string {
  return DESK_ACCENT_TINT;
}

export function resolveDeskImageUrl(workspaceImageUrl?: string): string | undefined {
  const url = workspaceImageUrl?.trim();
  return url || undefined;
}

export function wallpaperStyle(imageUrl?: string, _fallbackColor?: string): CSSProperties {
  const deskColor = deskFallbackColor();
  if (imageUrl) {
    return {
      backgroundColor: deskColor,
      backgroundImage: `${DESK_IMAGE_OVERLAY}, url(${JSON.stringify(imageUrl)})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    };
  }
  return { backgroundColor: deskColor };
}

export function deskSurfaceIcons(flags: { chat?: boolean; files?: boolean }): DeskSurfaceId[] {
  const icons: DeskSurfaceId[] = [];
  if (flags.chat) icons.push('chat');
  if (flags.files) icons.push('files');
  return icons;
}
