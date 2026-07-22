import type { ThemeColorsState, ThemeMode } from '@/lib/theme/tokens';
import { colorsToThemeConfig, type ThemeConfigFile } from '@/lib/theme/themeConfigShared';

export async function fetchThemeConfig(): Promise<ThemeConfigFile | null> {
  const response = await fetch('/api/theme', { cache: 'no-store' });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as ThemeConfigFile;
}

export async function saveThemeConfigToApi(
  colors: ThemeColorsState,
  defaultMode: ThemeMode,
): Promise<boolean> {
  const payload = colorsToThemeConfig(colors, { default_mode: defaultMode });
  const response = await fetch('/api/theme', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.ok;
}
