import {
  createDefaultThemeColors,
  normalizeThemeColors,
  type ThemeColorsState,
  type ThemeMode,
} from '@/lib/theme/tokens';

export const THEME_CONFIG_SCHEMA_VERSION = '1.0';

export type ThemeConfigFile = {
  schema_version: string;
  updated_at: string;
  default_mode: ThemeMode;
  brand: ThemeColorsState['brand'];
  light: ThemeColorsState['light'];
  dark: ThemeColorsState['dark'];
  fontFamily: string;
  typography: ThemeColorsState['typography'];
  numberFormat: ThemeColorsState['numberFormat'];
  exportFormat: ThemeColorsState['exportFormat'];
};

export function createDefaultThemeConfig(): ThemeConfigFile {
  const colors = createDefaultThemeColors();
  return {
    schema_version: THEME_CONFIG_SCHEMA_VERSION,
    updated_at: new Date().toISOString(),
    default_mode: 'light',
    brand: colors.brand,
    light: colors.light,
    dark: colors.dark,
    fontFamily: colors.fontFamily,
    typography: colors.typography,
    numberFormat: colors.numberFormat,
    exportFormat: colors.exportFormat,
  };
}

export function normalizeThemeConfig(parsed: Partial<ThemeConfigFile>): ThemeConfigFile {
  const colors = normalizeThemeColors(parsed);
  return {
    schema_version: parsed.schema_version ?? THEME_CONFIG_SCHEMA_VERSION,
    updated_at: parsed.updated_at ?? new Date().toISOString(),
    default_mode: parsed.default_mode === 'dark' ? 'dark' : 'light',
    brand: colors.brand,
    light: colors.light,
    dark: colors.dark,
    fontFamily: colors.fontFamily,
    typography: colors.typography,
    numberFormat: colors.numberFormat,
    exportFormat: colors.exportFormat,
  };
}

export function themeConfigToColors(config: ThemeConfigFile): ThemeColorsState {
  return normalizeThemeColors({
    brand: config.brand,
    light: config.light,
    dark: config.dark,
    fontFamily: config.fontFamily,
    typography: config.typography,
    numberFormat: config.numberFormat,
    exportFormat: config.exportFormat,
  });
}

export function colorsToThemeConfig(
  colors: ThemeColorsState,
  options?: { default_mode?: ThemeMode; updated_at?: string },
): ThemeConfigFile {
  const normalized = normalizeThemeColors(colors);
  return {
    schema_version: THEME_CONFIG_SCHEMA_VERSION,
    updated_at: options?.updated_at ?? new Date().toISOString(),
    default_mode: options?.default_mode ?? 'light',
    brand: normalized.brand,
    light: normalized.light,
    dark: normalized.dark,
    fontFamily: normalized.fontFamily,
    typography: normalized.typography,
    numberFormat: normalized.numberFormat,
    exportFormat: normalized.exportFormat,
  };
}
