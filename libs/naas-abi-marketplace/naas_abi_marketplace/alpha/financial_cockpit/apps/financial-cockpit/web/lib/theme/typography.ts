export type TextTransform = 'none' | 'uppercase' | 'lowercase' | 'capitalize';

export type TypographyStyleId =
  | 'title'
  | 'subtitle'
  | 'title-1'
  | 'title-2'
  | 'title-3'
  | 'title-4'
  | 'title-5'
  | 'text';

export const TYPOGRAPHY_STYLE_IDS: TypographyStyleId[] = [
  'title',
  'subtitle',
  'title-1',
  'title-2',
  'title-3',
  'title-4',
  'title-5',
  'text',
];

export type TypographyStyle = {
  fontSize: string;
  fontWeight: string;
  lineHeight: string;
  letterSpacing: string;
  textTransform: TextTransform;
};

export type NumberDisplayStyle = 'decimal' | 'percent' | 'currency';

export const NUMBER_STYLE_IDS = ['decimal', 'percent', 'currency'] as const;
export type NumberStyleId = (typeof NUMBER_STYLE_IDS)[number];

/** How percent values are interpreted before Intl percent formatting. */
export type PercentInput = 'rate' | 'percent';

export type NumberStyleSettings = {
  fontFamily: string;
  fontSize: string;
  fontWeight: string;
  locale: string;
  maximumFractionDigits: number;
};

export type CurrencyNumberStyleSettings = NumberStyleSettings & {
  currency: string;
};

export type NumberFormatSettings = {
  decimal: NumberStyleSettings;
  percent: NumberStyleSettings;
  currency: CurrencyNumberStyleSettings;
};

export type FormatThemeNumberOptions = {
  style?: NumberDisplayStyle;
  currency?: string;
  /** Legacy suffix for decimal style (e.g. "k€"). Prefer `style: 'currency'`. */
  unit?: string;
  maximumFractionDigits?: number;
  minimumFractionDigits?: number;
  /** `rate`: 0.255 → 25,5 % · `percent`: 25.5 → 25,5 % */
  percentInput?: PercentInput;
};

export const NUMBER_STYLE_LABELS: Record<
  NumberStyleId,
  { label: string; description: string; previewValue: number; previewOptions?: FormatThemeNumberOptions }
> = {
  decimal: {
    label: 'Nombre',
    description: 'Valeurs numériques simples (KPI, quantités, compteurs).',
    previewValue: 1234567.89,
    previewOptions: { style: 'decimal' },
  },
  percent: {
    label: 'Pourcentage',
    description: 'Taux et évolutions en pourcentage.',
    previewValue: 0.256,
    previewOptions: { style: 'percent', percentInput: 'rate' },
  },
  currency: {
    label: 'Monétaire',
    description: 'Montants financiers avec devise.',
    previewValue: 1234567.89,
    previewOptions: { style: 'currency' },
  },
};

export const TYPOGRAPHY_STYLE_LABELS: Record<
  TypographyStyleId,
  { label: string; description: string; preview: string }
> = {
  title: {
    label: 'Title',
    description: 'Titre principal de page (sections du portail).',
    preview: 'Titre de page',
  },
  subtitle: {
    label: 'Subtitle',
    description: 'Sous-titre descriptif sous le titre de page.',
    preview: 'Sous-titre descriptif',
  },
  'title-1': {
    label: 'Titre 1',
    description: 'Niveau de titre le plus important (équivalent H1).',
    preview: 'Titre niveau 1',
  },
  'title-2': {
    label: 'Titre 2',
    description: 'Sous-titre de section (équivalent H2).',
    preview: 'Titre niveau 2',
  },
  'title-3': {
    label: 'Titre 3',
    description: 'Titre de bloc (équivalent H3).',
    preview: 'Titre niveau 3',
  },
  'title-4': {
    label: 'Titre 4',
    description: 'Titre intermédiaire (équivalent H4).',
    preview: 'Titre niveau 4',
  },
  'title-5': {
    label: 'Titre 5',
    description: 'Petit titre, libellés de cartes (équivalent H5).',
    preview: 'Titre niveau 5',
  },
  text: {
    label: 'Texte',
    description: 'Corps de texte standard du portail.',
    preview: 'Corps de texte pour les paragraphes et contenus.',
  },
};

export const DEFAULT_TYPOGRAPHY: Record<TypographyStyleId, TypographyStyle> = {
  title: {
    fontSize: '1.875rem',
    fontWeight: '700',
    lineHeight: '1.25',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  subtitle: {
    fontSize: '1rem',
    fontWeight: '400',
    lineHeight: '1.5',
    letterSpacing: '0',
    textTransform: 'none',
  },
  'title-1': {
    fontSize: '2.25rem',
    fontWeight: '700',
    lineHeight: '1.2',
    letterSpacing: '0',
    textTransform: 'none',
  },
  'title-2': {
    fontSize: '1.875rem',
    fontWeight: '700',
    lineHeight: '1.25',
    letterSpacing: '0',
    textTransform: 'none',
  },
  'title-3': {
    fontSize: '1.5rem',
    fontWeight: '600',
    lineHeight: '1.3',
    letterSpacing: '0',
    textTransform: 'none',
  },
  'title-4': {
    fontSize: '1.25rem',
    fontWeight: '600',
    lineHeight: '1.35',
    letterSpacing: '0',
    textTransform: 'none',
  },
  'title-5': {
    fontSize: '0.875rem',
    fontWeight: '600',
    lineHeight: '1.4',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  text: {
    fontSize: '1rem',
    fontWeight: '400',
    lineHeight: '1.5',
    letterSpacing: '0',
    textTransform: 'none',
  },
};

const DEFAULT_DECIMAL_NUMBER: NumberStyleSettings = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  fontSize: '1.5rem',
  fontWeight: '700',
  locale: 'fr-FR',
  maximumFractionDigits: 0,
};

const DEFAULT_PERCENT_NUMBER: NumberStyleSettings = {
  ...DEFAULT_DECIMAL_NUMBER,
  maximumFractionDigits: 1,
};

const DEFAULT_CURRENCY_NUMBER: CurrencyNumberStyleSettings = {
  ...DEFAULT_DECIMAL_NUMBER,
  currency: 'EUR',
};

export const DEFAULT_NUMBER_FORMAT: NumberFormatSettings = {
  decimal: { ...DEFAULT_DECIMAL_NUMBER },
  percent: { ...DEFAULT_PERCENT_NUMBER },
  currency: { ...DEFAULT_CURRENCY_NUMBER },
};

export const NUMBER_CURRENCY_OPTIONS = [
  { id: 'EUR', label: 'Euro (EUR)' },
  { id: 'USD', label: 'Dollar (USD)' },
  { id: 'GBP', label: 'Livre (GBP)' },
  { id: 'CHF', label: 'Franc suisse (CHF)' },
] as const;

export const NUMBER_LOCALE_OPTIONS = [
  { id: 'fr-FR', label: 'Français (fr-FR)' },
  { id: 'en-US', label: 'Anglais (en-US)' },
  { id: 'de-DE', label: 'Allemand (de-DE)' },
] as const;

export const NUMBER_FRACTION_DIGITS_OPTIONS = [0, 1, 2, 3, 4, 5, 6] as const;

export function clampFractionDigits(value: number): number {
  return Math.min(6, Math.max(0, Math.trunc(value)));
}

export function typographyCssVar(styleId: TypographyStyleId, property: keyof TypographyStyle): string {
  return `--type-${styleId}-${property.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`)}`;
}

export function typographyFontCssVar(styleId: TypographyStyleId): string {
  return `--type-${styleId}-font`;
}

/** Use in styles like colors: `fontSize: typographyVar('title', 'fontSize')` → `var(--type-title-font-size)` */
export function typographyVar(styleId: TypographyStyleId, property: keyof TypographyStyle): string {
  return `var(${typographyCssVar(styleId, property)})`;
}

/** Shorthand for weight + size + line-height: `font: typographyFont('title')` */
export function typographyFont(styleId: TypographyStyleId): string {
  return `var(${typographyFontCssVar(styleId)})`;
}

export function numberStyleCssVar(styleId: NumberStyleId, property: keyof NumberStyleSettings): string {
  return `--type-number-${styleId}-${property.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`)}`;
}

export function numberStyleFontCssVar(styleId: NumberStyleId): string {
  return `--type-number-${styleId}-font`;
}

export function numberClassName(styleId: NumberStyleId = 'decimal'): string {
  return styleId === 'decimal' ? 'type-number' : `type-number-${styleId}`;
}

/** @deprecated Use numberStyleFontCssVar('decimal') */
export const NUMBER_TYPOGRAPHY_VARS = {
  fontFamily: '--type-number-decimal-font-family',
  fontSize: '--type-number-decimal-font-size',
  fontWeight: '--type-number-decimal-font-weight',
  locale: '--type-number-decimal-locale',
  maximumFractionDigits: '--type-number-decimal-max-fraction-digits',
} as const;

export function numberTypographyVar(key: keyof typeof NUMBER_TYPOGRAPHY_VARS): string {
  return `var(${NUMBER_TYPOGRAPHY_VARS[key]})`;
}

export function typographyClassName(styleId: TypographyStyleId): string {
  return `type-${styleId}`;
}

function mergeTypographyStyle(
  defaults: TypographyStyle,
  parsed?: Partial<TypographyStyle>,
): TypographyStyle {
  if (!parsed) {
    return defaults;
  }
  return {
    fontSize: parsed.fontSize ?? defaults.fontSize,
    fontWeight: parsed.fontWeight ?? defaults.fontWeight,
    lineHeight: parsed.lineHeight ?? defaults.lineHeight,
    letterSpacing: parsed.letterSpacing ?? defaults.letterSpacing,
    textTransform: parsed.textTransform ?? defaults.textTransform,
  };
}

export function mergeTypography(
  parsed?: Partial<Record<TypographyStyleId, Partial<TypographyStyle>>>,
): Record<TypographyStyleId, TypographyStyle> {
  const next = { ...DEFAULT_TYPOGRAPHY };
  if (!parsed) {
    return next;
  }
  for (const id of TYPOGRAPHY_STYLE_IDS) {
    next[id] = mergeTypographyStyle(DEFAULT_TYPOGRAPHY[id], parsed[id]);
  }
  return next;
}

type LegacyFlatNumberFormat = {
  fontFamily?: string;
  fontSize?: string;
  fontWeight?: string;
  locale?: string;
  maximumFractionDigits?: number;
  percentMaximumFractionDigits?: number;
  currency?: string;
};

function mergeNumberStyle(
  defaults: NumberStyleSettings,
  parsed?: Partial<NumberStyleSettings>,
): NumberStyleSettings {
  if (!parsed) {
    return defaults;
  }
  return {
    fontFamily: parsed.fontFamily ?? defaults.fontFamily,
    fontSize: parsed.fontSize ?? defaults.fontSize,
    fontWeight: parsed.fontWeight ?? defaults.fontWeight,
    locale: parsed.locale ?? defaults.locale,
    maximumFractionDigits:
      parsed.maximumFractionDigits ?? defaults.maximumFractionDigits,
  };
}

function mergeCurrencyStyle(
  defaults: CurrencyNumberStyleSettings,
  parsed?: Partial<CurrencyNumberStyleSettings>,
): CurrencyNumberStyleSettings {
  return {
    ...mergeNumberStyle(defaults, parsed),
    currency: parsed?.currency ?? defaults.currency,
  };
}

function isNestedNumberFormat(parsed: unknown): parsed is Partial<NumberFormatSettings> {
  return Boolean(parsed && typeof parsed === 'object' && 'decimal' in parsed);
}

export function mergeNumberFormat(
  parsed?: Partial<NumberFormatSettings> | LegacyFlatNumberFormat,
): NumberFormatSettings {
  const defaults = DEFAULT_NUMBER_FORMAT;

  if (isNestedNumberFormat(parsed)) {
    return {
      decimal: mergeNumberStyle(defaults.decimal, parsed.decimal),
      percent: mergeNumberStyle(defaults.percent, parsed.percent),
      currency: mergeCurrencyStyle(defaults.currency, parsed.currency),
    };
  }

  const flat = parsed as LegacyFlatNumberFormat | undefined;
  if (!flat) {
    return {
      decimal: { ...defaults.decimal },
      percent: { ...defaults.percent },
      currency: { ...defaults.currency },
    };
  }

  const shared: Partial<NumberStyleSettings> = {
    fontFamily: flat.fontFamily,
    fontSize: flat.fontSize,
    fontWeight: flat.fontWeight,
    locale: flat.locale,
  };

  return {
    decimal: mergeNumberStyle(defaults.decimal, {
      ...shared,
      maximumFractionDigits: flat.maximumFractionDigits,
    }),
    percent: mergeNumberStyle(defaults.percent, {
      ...shared,
      maximumFractionDigits: flat.percentMaximumFractionDigits,
    }),
    currency: mergeCurrencyStyle(defaults.currency, {
      ...shared,
      maximumFractionDigits: flat.maximumFractionDigits,
      currency: flat.currency,
    }),
  };
}

function applyNumberStyleToRoot(
  root: HTMLElement,
  styleId: NumberStyleId,
  style: NumberStyleSettings,
  currencyCode?: string,
) {
  root.style.setProperty(numberStyleCssVar(styleId, 'fontFamily'), style.fontFamily);
  root.style.setProperty(numberStyleCssVar(styleId, 'fontSize'), style.fontSize);
  root.style.setProperty(numberStyleCssVar(styleId, 'fontWeight'), style.fontWeight);
  root.style.setProperty(numberStyleCssVar(styleId, 'locale'), style.locale);
  root.style.setProperty(
    numberStyleCssVar(styleId, 'maximumFractionDigits'),
    String(style.maximumFractionDigits),
  );
  root.style.setProperty(
    numberStyleFontCssVar(styleId),
    `${style.fontWeight} ${style.fontSize}/1.2 ${style.fontFamily}`,
  );
  if (currencyCode) {
    root.style.setProperty('--type-number-currency-code', currencyCode);
  }
}

function inferStyleFromUnit(unit?: string): NumberDisplayStyle {
  if (unit === '%') {
    return 'percent';
  }
  if (unit === '€' || unit === '$' || unit === '£') {
    return 'currency';
  }
  return 'decimal';
}

function resolveFormatOptions(
  options?: FormatThemeNumberOptions,
): Required<Pick<FormatThemeNumberOptions, 'style'>> & FormatThemeNumberOptions {
  const style = options?.style ?? inferStyleFromUnit(options?.unit);
  return { ...options, style };
}

export function applyTypographyToRoot(
  root: HTMLElement,
  typography: Record<TypographyStyleId, TypographyStyle>,
  numberFormat: NumberFormatSettings,
) {
  for (const id of TYPOGRAPHY_STYLE_IDS) {
    const style = typography[id];
    root.style.setProperty(typographyCssVar(id, 'fontSize'), style.fontSize);
    root.style.setProperty(typographyCssVar(id, 'fontWeight'), style.fontWeight);
    root.style.setProperty(typographyCssVar(id, 'lineHeight'), style.lineHeight);
    root.style.setProperty(typographyCssVar(id, 'letterSpacing'), style.letterSpacing);
    root.style.setProperty(typographyCssVar(id, 'textTransform'), style.textTransform);
    root.style.setProperty(
      typographyFontCssVar(id),
      `${style.fontWeight} ${style.fontSize}/${style.lineHeight} var(--font-family)`,
    );
  }

  for (const id of NUMBER_STYLE_IDS) {
    const style = numberFormat[id];
    applyNumberStyleToRoot(
      root,
      id,
      style,
      id === 'currency' ? numberFormat.currency.currency : undefined,
    );
  }

  // Legacy aliases for decimal
  root.style.setProperty('--type-number-font-family', numberFormat.decimal.fontFamily);
  root.style.setProperty('--type-number-font-size', numberFormat.decimal.fontSize);
  root.style.setProperty('--type-number-font-weight', numberFormat.decimal.fontWeight);
  root.style.setProperty(
    '--type-number-font',
    `${numberFormat.decimal.fontWeight} ${numberFormat.decimal.fontSize}/1.2 ${numberFormat.decimal.fontFamily}`,
  );
  root.style.setProperty('--type-number-locale', numberFormat.decimal.locale);
  root.style.setProperty(
    '--type-number-max-fraction-digits',
    String(numberFormat.decimal.maximumFractionDigits),
  );
}

export function formatThemeNumber(
  value: number,
  numberFormat: NumberFormatSettings,
  options?: FormatThemeNumberOptions,
): string {
  const resolved = resolveFormatOptions(options);
  const { style } = resolved;
  const styleConfig = numberFormat[style];

  if (style === 'currency') {
    const currencyConfig = numberFormat.currency;
    return new Intl.NumberFormat(styleConfig.locale, {
      style: 'currency',
      currency: resolved.currency ?? currencyConfig.currency,
      maximumFractionDigits:
        resolved.maximumFractionDigits ?? styleConfig.maximumFractionDigits,
      minimumFractionDigits: resolved.minimumFractionDigits,
    }).format(value);
  }

  if (style === 'percent') {
    const percentInput =
      resolved.percentInput ?? (resolved.unit === '%' ? 'percent' : 'rate');
    const numeric = percentInput === 'percent' ? value / 100 : value;

    return new Intl.NumberFormat(styleConfig.locale, {
      style: 'percent',
      maximumFractionDigits:
        resolved.maximumFractionDigits ?? styleConfig.maximumFractionDigits,
      minimumFractionDigits: resolved.minimumFractionDigits,
    }).format(numeric);
  }

  const formatted = new Intl.NumberFormat(styleConfig.locale, {
    maximumFractionDigits:
      resolved.maximumFractionDigits ?? styleConfig.maximumFractionDigits,
    minimumFractionDigits: resolved.minimumFractionDigits,
  }).format(value);

  return resolved.unit ? `${formatted} ${resolved.unit}` : formatted;
}
