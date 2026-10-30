import { describe, expect, it } from 'vitest';
import { buildWebAppManifest, defaultTenantBranding, shortNameFromTabTitle } from './tenant-branding';

describe('shortNameFromTabTitle', () => {
  it('uses the segment before the pipe', () => {
    expect(shortNameFromTabTitle('ABI | naas.ai')).toBe('ABI');
  });

  it('truncates long single-segment titles', () => {
    expect(shortNameFromTabTitle('Very Long Product Name Here')).toBe('Very Long P…');
  });
});

describe('buildWebAppManifest', () => {
  it('emits installable standalone manifest with tenant colors', () => {
    const branding = {
      ...defaultTenantBranding(),
      title: 'ABI | naas.ai',
      shortName: 'ABI',
      themeColor: '#52E088',
      backgroundColor: '#050b10',
    };
    const manifest = buildWebAppManifest(branding, 'https://zen.naas.ai');

    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url).toBe('/');
    expect(manifest.id).toBe('https://zen.naas.ai');
    expect(manifest.theme_color).toBe('#52E088');
    expect(manifest.short_name).toBe('ABI');
    expect(manifest.icons?.length).toBeGreaterThanOrEqual(2);
  });
});
