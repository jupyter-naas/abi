import type { CSSProperties } from 'react';

import {
  createDefaultThemeColors,
  THEME_MODE_STORAGE_KEY,
  type ThemeColorsState,
  type ThemeMode,
} from '@/lib/theme/tokens';
import {
  NUMBER_STYLE_IDS,
  TYPOGRAPHY_STYLE_IDS,
  numberStyleCssVar,
  numberStyleFontCssVar,
  typographyCssVar,
  typographyFontCssVar,
} from '@/lib/theme/typography';
import { themeConfigToColors, type ThemeConfigFile } from '@/lib/theme/themeConfigShared';

/**
 * Readable ink for text placed on top of `hex` — white on dark colors, near-black
 * on light ones (WCAG relative luminance). Lets the chrome (top bar / sidebar)
 * stay legible whatever brand colors the theme picks, light or dark.
 */
function readableOn(hex: string): string {
  const h = hex.replace('#', '');
  if (h.length !== 6) return '#ffffff';
  const channel = (i: number) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const luminance = 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
  return luminance > 0.5 ? '#19191C' : '#ffffff';
}

export function getThemeCssVariables(
  colors: ThemeColorsState,
  mode: ThemeMode,
): Record<string, string> {
  const modeColors = colors[mode];
  const vars: Record<string, string> = {
    '--primary': colors.brand.primary,
    '--secondary': colors.brand.secondary,
    '--bg': modeColors.bg,
    '--surface': modeColors.surface,
    '--accent': modeColors.accent,
    '--text': modeColors.text,
    '--text-muted': modeColors['text-muted'],
    '--border': modeColors.border,
    // Contrasting ink for the chrome bars and accent fills — kept legible
    // whether the brand color is dark (top bar) or light (sidebar).
    '--on-primary': readableOn(colors.brand.primary),
    '--on-secondary': readableOn(colors.brand.secondary),
    '--on-accent': readableOn(modeColors.accent),
    '--font-family': colors.fontFamily,
  };

  for (const id of TYPOGRAPHY_STYLE_IDS) {
    const style = colors.typography[id];
    vars[typographyCssVar(id, 'fontSize')] = style.fontSize;
    vars[typographyCssVar(id, 'fontWeight')] = style.fontWeight;
    vars[typographyCssVar(id, 'lineHeight')] = style.lineHeight;
    vars[typographyCssVar(id, 'letterSpacing')] = style.letterSpacing;
    vars[typographyCssVar(id, 'textTransform')] = style.textTransform;
    vars[typographyFontCssVar(id)] =
      `${style.fontWeight} ${style.fontSize}/${style.lineHeight} var(--font-family)`;
  }

  for (const id of NUMBER_STYLE_IDS) {
    const style = colors.numberFormat[id];
    vars[numberStyleCssVar(id, 'fontFamily')] = style.fontFamily;
    vars[numberStyleCssVar(id, 'fontSize')] = style.fontSize;
    vars[numberStyleCssVar(id, 'fontWeight')] = style.fontWeight;
    vars[numberStyleCssVar(id, 'locale')] = style.locale;
    vars[numberStyleCssVar(id, 'maximumFractionDigits')] = String(style.maximumFractionDigits);
    vars[numberStyleFontCssVar(id)] =
      `${style.fontWeight} ${style.fontSize}/1.2 ${style.fontFamily}`;
    if (id === 'currency') {
      vars['--type-number-currency-code'] = colors.numberFormat.currency.currency;
    }
  }

  const decimal = colors.numberFormat.decimal;
  vars['--type-number-font-family'] = decimal.fontFamily;
  vars['--type-number-font-size'] = decimal.fontSize;
  vars['--type-number-font-weight'] = decimal.fontWeight;
  vars['--type-number-font'] =
    `${decimal.fontWeight} ${decimal.fontSize}/1.2 ${decimal.fontFamily}`;
  vars['--type-number-locale'] = decimal.locale;
  vars['--type-number-max-fraction-digits'] = String(decimal.maximumFractionDigits);

  return vars;
}

export function getThemeInlineStyle(
  colors: ThemeColorsState,
  mode: ThemeMode,
): CSSProperties {
  return getThemeCssVariables(colors, mode) as CSSProperties;
}

function applyCssVariablesToRoot(root: HTMLElement, vars: Record<string, string>) {
  for (const [key, value] of Object.entries(vars)) {
    root.style.setProperty(key, value);
  }
}

export function applyTheme(
  mode: ThemeMode,
  colors: ThemeColorsState = createDefaultThemeColors(),
) {
  if (typeof document === 'undefined') {
    return;
  }

  document.documentElement.setAttribute('data-theme', mode);
  applyCssVariablesToRoot(document.documentElement, getThemeCssVariables(colors, mode));
}

export function loadThemeModeFromStorage(defaultMode: ThemeMode = 'light'): ThemeMode {
  if (typeof window === 'undefined') {
    return defaultMode;
  }

  const stored = localStorage.getItem(THEME_MODE_STORAGE_KEY);
  if (stored === 'dark') {
    return 'dark';
  }
  if (stored === 'light') {
    return 'light';
  }
  return defaultMode;
}

export function themeInitScript(config: ThemeConfigFile): string {
  const defaults = themeConfigToColors(config);
  const defaultMode = config.default_mode === 'dark' ? 'dark' : 'light';
  const lightVars = JSON.stringify(getThemeCssVariables(defaults, 'light'));
  const darkVars = JSON.stringify(getThemeCssVariables(defaults, 'dark'));

  return `
(function () {
  var mode = ${JSON.stringify(defaultMode)};
  try {
    var storedMode = localStorage.getItem('${THEME_MODE_STORAGE_KEY}');
    if (storedMode === 'dark' || storedMode === 'light') mode = storedMode;
  } catch (e) {}
  var root = document.documentElement;
  root.setAttribute('data-theme', mode);
  var themeVars = { light: ${lightVars}, dark: ${darkVars} };
  var vars = themeVars[mode];
  Object.keys(vars).forEach(function (key) {
    root.style.setProperty(key, vars[key]);
  });
})();
`.trim();
}

export function saveThemeModeToStorage(mode: ThemeMode) {
  if (typeof window === 'undefined') {
    return;
  }
  localStorage.setItem(THEME_MODE_STORAGE_KEY, mode);
}
