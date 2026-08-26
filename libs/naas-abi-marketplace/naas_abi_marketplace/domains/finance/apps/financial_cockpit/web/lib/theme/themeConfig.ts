import 'server-only';

import { existsSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

import {
  createDefaultThemeConfig,
  normalizeThemeConfig,
  type ThemeConfigFile,
} from '@/lib/theme/themeConfigShared';
import bundledThemeConfig from '@/config/theme.json';

export type { ThemeConfigFile } from '@/lib/theme/themeConfigShared';
export {
  colorsToThemeConfig,
  createDefaultThemeConfig,
  normalizeThemeConfig,
  themeConfigToColors,
  THEME_CONFIG_SCHEMA_VERSION,
} from '@/lib/theme/themeConfigShared';

const THEME_CONFIG_PATH = join(process.cwd(), 'config', 'theme.json');

export function loadThemeConfig(): ThemeConfigFile {
  // `fs` has no real backing store on Cloudflare Workers — fall back to the
  // theme file bundled at build time there instead of crashing (or silently
  // dropping the configured theme in favour of defaults).
  try {
    if (existsSync(THEME_CONFIG_PATH)) {
      const raw = readFileSync(THEME_CONFIG_PATH, 'utf8');
      const parsed = JSON.parse(raw) as Partial<ThemeConfigFile>;
      return normalizeThemeConfig(parsed);
    }
  } catch {
    // fall through to the bundled theme below
  }

  return normalizeThemeConfig(bundledThemeConfig as Partial<ThemeConfigFile>);
}

export function writeThemeConfig(config: ThemeConfigFile): ThemeConfigFile {
  const normalized = normalizeThemeConfig(config);
  const next: ThemeConfigFile = {
    ...normalized,
    updated_at: new Date().toISOString(),
  };
  try {
    writeFileSync(THEME_CONFIG_PATH, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
  } catch {
    // No writable filesystem in this environment (e.g. Cloudflare Workers) —
    // theme edits won't persist across requests.
  }
  return next;
}
