import type { CSSProperties } from 'react';

export const DESK_FALLBACK_COLOR = '#0a0a0a';

export const HERO_OVERLAY =
  'linear-gradient(to bottom, rgba(70, 75, 75, 0.78) 0%, rgba(37, 40, 42, 0.68) 100%)';

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

export function deskFallbackColor(themeColor?: string): string {
  if (themeColor && !isLightDeskColor(themeColor)) return themeColor;
  return DESK_FALLBACK_COLOR;
}

export function resolveDeskImageUrl(workspaceImageUrl?: string): string | undefined {
  const url = workspaceImageUrl?.trim();
  return url || undefined;
}

export function wallpaperStyle(imageUrl?: string, fallbackColor?: string): CSSProperties {
  const deskColor = deskFallbackColor(fallbackColor);
  if (imageUrl) {
    return {
      backgroundColor: deskColor,
      backgroundImage: `${HERO_OVERLAY}, url(${JSON.stringify(imageUrl)})`,
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
