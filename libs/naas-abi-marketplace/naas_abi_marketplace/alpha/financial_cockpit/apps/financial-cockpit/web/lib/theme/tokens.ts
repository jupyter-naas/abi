import {
  mergeNumberFormat,
  mergeTypography,
  type CurrencyNumberStyleSettings,
  type NumberFormatSettings,
  type NumberStyleId,
  type NumberStyleSettings,
  type TypographyStyle,
  type TypographyStyleId,
} from './typography';
import {
  mergeExportFormat,
  type CsvExportSettings,
  type ExportFormatSettings,
} from './exportFormat';

export type ThemeMode = 'light' | 'dark';

export type {
  CurrencyNumberStyleSettings,
  FormatThemeNumberOptions,
  NumberDisplayStyle,
  NumberFormatSettings,
  NumberStyleId,
  NumberStyleSettings,
  PercentInput,
  TextTransform,
  TypographyStyle,
  TypographyStyleId,
} from './typography';
export {
  CSV_DECIMAL_OPTIONS,
  CSV_ENCODING_OPTIONS,
  CSV_SEPARATOR_OPTIONS,
  DEFAULT_EXPORT_FORMAT,
  mergeExportFormat,
  type CsvEncoding,
  type CsvExportSettings,
  type ExportFormatSettings,
} from './exportFormat';
export {
  DEFAULT_NUMBER_FORMAT,
  DEFAULT_TYPOGRAPHY,
  NUMBER_CURRENCY_OPTIONS,
  NUMBER_LOCALE_OPTIONS,
  NUMBER_STYLE_IDS,
  NUMBER_STYLE_LABELS,
  TYPOGRAPHY_STYLE_IDS,
  TYPOGRAPHY_STYLE_LABELS,
  formatThemeNumber,
  numberClassName,
  numberStyleFontCssVar,
  numberTypographyVar,
  typographyClassName,
  typographyFont,
  typographyVar,
} from './typography';

export type ThemeTokenCategory =
  | 'brand'
  | 'surface'
  | 'text'
  | 'border'
  | 'hover'
  | 'typography';

export type ThemeTokenDefinition = {
  id: string;
  cssVar: string;
  label: string;
  description: string;
  category: ThemeTokenCategory;
  scope: 'brand' | ThemeMode;
  type: 'color' | 'font';
};

export const THEME_FONT_FAMILY = 'Inter, system-ui, sans-serif';

export type ThemeFontOption = {
  id: string;
  label: string;
  value: string;
};

export const THEME_FONT_OPTIONS: ThemeFontOption[] = [
  { id: 'inter', label: 'Inter', value: 'Inter, system-ui, sans-serif' },
  { id: 'dm-sans', label: 'DM Sans', value: '"DM Sans", system-ui, sans-serif' },
  {
    id: 'source-sans-3',
    label: 'Source Sans 3',
    value: '"Source Sans 3", system-ui, sans-serif',
  },
  {
    id: 'ibm-plex-sans',
    label: 'IBM Plex Sans',
    value: '"IBM Plex Sans", system-ui, sans-serif',
  },
  { id: 'open-sans', label: 'Open Sans', value: '"Open Sans", system-ui, sans-serif' },
  { id: 'system', label: 'Système', value: 'system-ui, sans-serif' },
];

export const THEME_NUMBER_FONT_OPTIONS: ThemeFontOption[] = [
  {
    id: 'mono',
    label: 'Monospace',
    value: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  },
  ...THEME_FONT_OPTIONS,
];

export function findFontOptionByValue(value: string): ThemeFontOption | undefined {
  return THEME_FONT_OPTIONS.find((option) => option.value === value);
}

export function findNumberFontOptionByValue(value: string): ThemeFontOption | undefined {
  return THEME_NUMBER_FONT_OPTIONS.find((option) => option.value === value);
}

export function fontOptionIdForValue(value: string): string {
  return findFontOptionByValue(value)?.id ?? THEME_FONT_OPTIONS[0].id;
}

export function numberFontOptionIdForValue(value: string): string {
  return findNumberFontOptionByValue(value)?.id ?? THEME_NUMBER_FONT_OPTIONS[0].id;
}

export function normalizeFontFamily(value: string | undefined): string {
  if (!value) {
    return THEME_FONT_FAMILY;
  }
  return findFontOptionByValue(value)?.value ?? THEME_FONT_FAMILY;
}

export const BRAND_COLOR_IDS = ['primary', 'secondary'] as const;
export type BrandColorId = (typeof BRAND_COLOR_IDS)[number];

export const MODE_COLOR_IDS = [
  'bg',
  'surface',
  'accent',
  'text',
  'text-muted',
  'border',
] as const;
export type ModeColorId = (typeof MODE_COLOR_IDS)[number];

export type ThemeColorValues = Record<BrandColorId | ModeColorId, string>;

export const DEFAULT_BRAND_COLORS: Record<BrandColorId, string> = {
  primary: '#19191C',
  secondary: '#f4f4f5',
};

export const DEFAULT_MODE_COLORS: Record<ThemeMode, Record<ModeColorId, string>> = {
  light: {
    bg: '#fafafa',
    surface: '#ffffff',
    accent: '#1FA574',
    text: '#09090b',
    'text-muted': '#71717a',
    border: '#e4e4e7',
  },
  dark: {
    bg: '#121214',
    surface: '#1c1c20',
    accent: '#1FA574',
    text: '#fafafa',
    'text-muted': '#a1a1aa',
    border: '#2e2e34',
  },
};

export const THEME_TOKEN_DEFINITIONS: ThemeTokenDefinition[] = [
  {
    id: 'primary',
    cssVar: '--primary',
    label: 'Primary',
    description: 'Couleur principale de la marque (boutons, onglet actif, filtre société).',
    category: 'brand',
    scope: 'brand',
    type: 'color',
  },
  {
    id: 'secondary',
    cssVar: '--secondary',
    label: 'Secondary',
    description: 'Couleur secondaire (badges, sélections, liens d’accent).',
    category: 'brand',
    scope: 'brand',
    type: 'color',
  },
  {
    id: 'bg-light',
    cssVar: '--bg',
    label: 'Fond',
    description: 'Arrière-plan principal de l’application.',
    category: 'surface',
    scope: 'light',
    type: 'color',
  },
  {
    id: 'surface-light',
    cssVar: '--surface',
    label: 'Surface',
    description: 'Cartes, barre latérale, en-têtes.',
    category: 'surface',
    scope: 'light',
    type: 'color',
  },
  {
    id: 'accent-light',
    cssVar: '--accent',
    label: 'Zone de survol',
    description:
      'Survol des liens et listes, champs discrets, pistes de progression.',
    category: 'hover',
    scope: 'light',
    type: 'color',
  },
  {
    id: 'text-light',
    cssVar: '--text',
    label: 'Texte',
    description: 'Texte principal.',
    category: 'text',
    scope: 'light',
    type: 'color',
  },
  {
    id: 'text-muted-light',
    cssVar: '--text-muted',
    label: 'Texte atténué',
    description: 'Libellés, métadonnées, texte secondaire.',
    category: 'text',
    scope: 'light',
    type: 'color',
  },
  {
    id: 'border-light',
    cssVar: '--border',
    label: 'Bordure',
    description: 'Séparateurs et contours.',
    category: 'border',
    scope: 'light',
    type: 'color',
  },
  {
    id: 'bg-dark',
    cssVar: '--bg',
    label: 'Fond',
    description: 'Arrière-plan principal de l’application.',
    category: 'surface',
    scope: 'dark',
    type: 'color',
  },
  {
    id: 'surface-dark',
    cssVar: '--surface',
    label: 'Surface',
    description: 'Cartes, barre latérale, en-têtes.',
    category: 'surface',
    scope: 'dark',
    type: 'color',
  },
  {
    id: 'accent-dark',
    cssVar: '--accent',
    label: 'Zone de survol',
    description:
      'Survol des liens et listes, champs discrets, pistes de progression.',
    category: 'hover',
    scope: 'dark',
    type: 'color',
  },
  {
    id: 'text-dark',
    cssVar: '--text',
    label: 'Texte',
    description: 'Texte principal.',
    category: 'text',
    scope: 'dark',
    type: 'color',
  },
  {
    id: 'text-muted-dark',
    cssVar: '--text-muted',
    label: 'Texte atténué',
    description: 'Libellés, métadonnées, texte secondaire.',
    category: 'text',
    scope: 'dark',
    type: 'color',
  },
  {
    id: 'border-dark',
    cssVar: '--border',
    label: 'Bordure',
    description: 'Séparateurs et contours.',
    category: 'border',
    scope: 'dark',
    type: 'color',
  },
  {
    id: 'font-family',
    cssVar: '--font-family',
    label: 'Police',
    description: 'Famille de police utilisée dans toute l’application.',
    category: 'typography',
    scope: 'brand',
    type: 'font',
  },
];

export const THEME_MODE_STORAGE_KEY = 'theme';
export const THEME_COLORS_STORAGE_KEY = 'theme-colors';

export type ThemeColorsState = {
  brand: Record<BrandColorId, string>;
  light: Record<ModeColorId, string>;
  dark: Record<ModeColorId, string>;
  fontFamily: string;
  typography: Record<TypographyStyleId, TypographyStyle>;
  numberFormat: NumberFormatSettings;
  exportFormat: ExportFormatSettings;
};

type LegacyBrand = Partial<Record<BrandColorId | 'accent-1' | 'accent-2', string>>;

function mergeModeColors(
  defaults: Record<ModeColorId, string>,
  parsed?: Partial<Record<string, string>>,
): Record<ModeColorId, string> {
  const next = { ...defaults };
  if (!parsed) {
    return next;
  }
  for (const key of MODE_COLOR_IDS) {
    const value = parsed[key];
    if (value) {
      next[key] = value;
    }
  }
  return next;
}

export function createDefaultThemeColors(): ThemeColorsState {
  return {
    brand: { ...DEFAULT_BRAND_COLORS },
    light: { ...DEFAULT_MODE_COLORS.light },
    dark: { ...DEFAULT_MODE_COLORS.dark },
    fontFamily: THEME_FONT_FAMILY,
    typography: mergeTypography(),
    numberFormat: mergeNumberFormat(),
    exportFormat: mergeExportFormat(),
  };
}

export function normalizeThemeColors(
  parsed: Partial<ThemeColorsState> & { brand?: LegacyBrand },
): ThemeColorsState {
  const defaults = createDefaultThemeColors();
  const brand: LegacyBrand = parsed.brand ?? {};

  return {
    brand: {
      primary: brand.primary ?? brand['accent-1'] ?? defaults.brand.primary,
      secondary: brand.secondary ?? brand['accent-2'] ?? defaults.brand.secondary,
    },
    light: mergeModeColors(defaults.light, parsed.light),
    dark: mergeModeColors(defaults.dark, parsed.dark),
    fontFamily: normalizeFontFamily(parsed.fontFamily),
    typography: mergeTypography(parsed.typography),
    numberFormat: mergeNumberFormat(parsed.numberFormat),
    exportFormat: mergeExportFormat(parsed.exportFormat),
  };
}

export function getTokenValue(
  colors: ThemeColorsState,
  token: ThemeTokenDefinition,
): string {
  if (token.id === 'font-family') {
    return colors.fontFamily;
  }

  if (token.scope === 'brand') {
    return colors.brand[token.id as BrandColorId];
  }

  const modeId = token.id.replace(/-(?:light|dark)$/, '') as ModeColorId;
  return colors[token.scope][modeId];
}

export function setTokenValue(
  colors: ThemeColorsState,
  token: ThemeTokenDefinition,
  value: string,
): ThemeColorsState {
  if (token.id === 'font-family') {
    return { ...colors, fontFamily: value };
  }

  if (token.scope === 'brand') {
    return {
      ...colors,
      brand: { ...colors.brand, [token.id]: value },
    };
  }

  const modeId = token.id.replace(/-(?:light|dark)$/, '') as ModeColorId;
  return {
    ...colors,
    [token.scope]: { ...colors[token.scope], [modeId]: value },
  };
}

export function updateTypographyStyle(
  colors: ThemeColorsState,
  styleId: TypographyStyleId,
  patch: Partial<TypographyStyle>,
): ThemeColorsState {
  return {
    ...colors,
    typography: {
      ...colors.typography,
      [styleId]: { ...colors.typography[styleId], ...patch },
    },
  };
}

export function updateNumberStyle(
  colors: ThemeColorsState,
  styleId: NumberStyleId,
  patch: Partial<NumberStyleSettings> | Partial<CurrencyNumberStyleSettings>,
): ThemeColorsState {
  return {
    ...colors,
    numberFormat: {
      ...colors.numberFormat,
      [styleId]: { ...colors.numberFormat[styleId], ...patch },
    },
  };
}

/** @deprecated Use updateNumberStyle */
export function updateNumberFormat(
  colors: ThemeColorsState,
  patch: Partial<NumberFormatSettings>,
): ThemeColorsState {
  return {
    ...colors,
    numberFormat: mergeNumberFormat({ ...colors.numberFormat, ...patch }),
  };
}

export function updateExportFormat(
  colors: ThemeColorsState,
  patch: Partial<ExportFormatSettings>,
): ThemeColorsState {
  return {
    ...colors,
    exportFormat: mergeExportFormat({
      csv: { ...colors.exportFormat.csv, ...patch.csv },
    }),
  };
}
