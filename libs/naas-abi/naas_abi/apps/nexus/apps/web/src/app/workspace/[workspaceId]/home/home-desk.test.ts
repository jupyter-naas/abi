import { describe, expect, it } from 'vitest';

import {
  DESK_FALLBACK_COLOR,
  HERO_OVERLAY,
  deskFallbackColor,
  deskSurfaceIcons,
  isLightDeskColor,
  resolveDeskImageUrl,
  wallpaperStyle,
} from './home-desk';

describe('isLightDeskColor', () => {
  it('treats white and missing values as light', () => {
    expect(isLightDeskColor(undefined)).toBe(true);
    expect(isLightDeskColor('#FFFFFF')).toBe(true);
    expect(isLightDeskColor('#fff')).toBe(true);
    expect(isLightDeskColor('white')).toBe(true);
  });

  it('keeps a dark desk color', () => {
    expect(isLightDeskColor('#0a0a0a')).toBe(false);
    expect(isLightDeskColor('#111827')).toBe(false);
  });
});

describe('deskFallbackColor', () => {
  it('uses the dark platform desk when the theme is white', () => {
    expect(deskFallbackColor('#FFFFFF')).toBe(DESK_FALLBACK_COLOR);
    expect(deskFallbackColor(undefined)).toBe(DESK_FALLBACK_COLOR);
  });

  it('keeps an already dark theme color', () => {
    expect(deskFallbackColor('#111827')).toBe('#111827');
  });
});

describe('resolveDeskImageUrl', () => {
  it('uses the workspace wallpaper when set', () => {
    expect(resolveDeskImageUrl('https://api.example/modules/example/cover.jpg')).toBe(
      'https://api.example/modules/example/cover.jpg',
    );
  });

  it('returns nothing when the workspace has no wallpaper', () => {
    expect(resolveDeskImageUrl(undefined)).toBeUndefined();
    expect(resolveDeskImageUrl('   ')).toBeUndefined();
  });
});

describe('wallpaperStyle', () => {
  it('paints the hero overlay only when an image is set', () => {
    const styled = wallpaperStyle('/modules/example/assets/public/city.jpg', '#FFFFFF');
    expect(styled.backgroundImage).toContain(HERO_OVERLAY);
    expect(styled.backgroundImage).toContain('/modules/example/assets/public/city.jpg');
    expect(styled.backgroundColor).toBe(DESK_FALLBACK_COLOR);
  });

  it('falls back to a dark desk with no overlay when there is no image', () => {
    expect(wallpaperStyle(undefined, '#FFFFFF')).toEqual({
      backgroundColor: DESK_FALLBACK_COLOR,
    });
  });
});

describe('deskSurfaceIcons', () => {
  it('includes Chat and Files when both features are on', () => {
    expect(deskSurfaceIcons({ chat: true, files: true })).toEqual(['chat', 'files']);
  });

  it('omits a surface when its feature flag is off', () => {
    expect(deskSurfaceIcons({ chat: false, files: true })).toEqual(['files']);
    expect(deskSurfaceIcons({ chat: true, files: false })).toEqual(['chat']);
    expect(deskSurfaceIcons({ chat: false, files: false })).toEqual([]);
  });
});
