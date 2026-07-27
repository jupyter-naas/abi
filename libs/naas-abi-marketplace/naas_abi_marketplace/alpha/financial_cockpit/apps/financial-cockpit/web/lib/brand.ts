import yaml from 'js-yaml';

import rawConfig from '@/config/config.yaml';
import { DEFAULT_BRAND_COLORS } from '@/lib/theme/tokens';
import type { BrandConfig } from '@/lib/types';

// Client-safe: this module is imported from client components (e.g. the
// sidebar logo), so it parses config.yaml directly instead of going through the
// server-only loadConfig. Server code should prefer `getBrand()` from loadConfig.
const brand = ((yaml.load(rawConfig) as { brand?: BrandConfig })?.brand ??
  {}) as BrandConfig;

export const BRAND = {
  name: brand.name ?? 'naas',
  description: brand.description ?? '',
  logoSrc: brand.logo_src ?? '/logo.png',
  logoAlt: brand.name ?? 'naas',
  faviconSrc: brand.favicon_src ?? '/icon.png',
  colors: {
    primary: DEFAULT_BRAND_COLORS.primary,
    secondary: DEFAULT_BRAND_COLORS.secondary,
  },
} as const;
