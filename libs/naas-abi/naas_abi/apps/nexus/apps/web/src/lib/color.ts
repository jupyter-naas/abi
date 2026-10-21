/** `#rrggbb` (or `rrggbb`) as the `H S% L%` triplet the Tailwind colour tokens use; null if invalid. */
export function hexToHslTriplet(hex: string | null | undefined): string | null {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec((hex ?? '').trim());
  if (!match) return null;
  const [r, g, b] = match.slice(1).map((part) => parseInt(part, 16) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

/**
 * CSS variables that put a brand colour (an organization's) on every colour token
 * family a subtree reads: the HSL tokens (--primary, --accent, --ring), the
 * workspace tokens (--workspace-*) and the hex design tokens (--color-primary*).
 * Empty when the primary colour is missing or invalid, so the defaults apply.
 */
export function brandColorVariables(
  primary: string | null | undefined,
  accent?: string | null
): Record<string, string> {
  const primaryHsl = hexToHslTriplet(primary);
  if (!primaryHsl || !primary) return {};
  const primaryHex = toHex(primary);
  const accentHsl = hexToHslTriplet(accent) ?? primaryHsl;
  const accentHex = hexToHslTriplet(accent) ? toHex(accent as string) : primaryHex;
  return {
    '--primary': primaryHsl,
    '--accent': accentHsl,
    '--ring': primaryHsl,
    '--workspace-primary': primaryHex,
    '--workspace-accent': accentHex,
    '--workspace-primary-hsl': primaryHsl,
    '--workspace-accent-hsl': accentHsl,
    '--color-primary': primaryHex,
    '--color-primary-hover': `color-mix(in srgb, ${primaryHex} 80%, black)`,
    '--color-primary-focus': `color-mix(in srgb, ${primaryHex} 30%, transparent)`,
    '--color-primary-subtle': `color-mix(in srgb, ${primaryHex} 10%, transparent)`,
  };
}

function toHex(value: string): string {
  const trimmed = value.trim();
  return trimmed.startsWith('#') ? trimmed : `#${trimmed}`;
}

/** Every variable brandColorVariables can set. */
export const BRAND_COLOR_VARIABLE_NAMES = [
  '--primary',
  '--accent',
  '--ring',
  '--workspace-primary',
  '--workspace-accent',
  '--workspace-primary-hsl',
  '--workspace-accent-hsl',
  '--color-primary',
  '--color-primary-hover',
  '--color-primary-focus',
  '--color-primary-subtle',
] as const;

type InlineStyle = Pick<CSSStyleDeclaration, 'getPropertyValue' | 'setProperty' | 'removeProperty'>;

/**
 * Puts brand colours on an element's inline style (the page root, so menus and
 * dialogs in portals get them too) and returns a function that restores what
 * was there. Variables the brand does not set are removed, so the stylesheet
 * defaults apply: with no brand at all, that is the platform default palette.
 */
export function applyBrandColorVariables(
  style: InlineStyle,
  variables: Record<string, string>
): () => void {
  const previous = BRAND_COLOR_VARIABLE_NAMES.map((name) => [name, style.getPropertyValue(name)] as const);
  for (const name of BRAND_COLOR_VARIABLE_NAMES) {
    const value = variables[name];
    if (value) style.setProperty(name, value);
    else style.removeProperty(name);
  }
  return () => {
    for (const [name, value] of previous) {
      if (value) style.setProperty(name, value);
      else style.removeProperty(name);
    }
  };
}
