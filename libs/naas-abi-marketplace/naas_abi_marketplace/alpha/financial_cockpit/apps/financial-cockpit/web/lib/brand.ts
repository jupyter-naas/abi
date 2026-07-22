import { DEFAULT_BRAND_COLORS } from '@/lib/theme/tokens';

export const BRAND = {
  name: 'naas',
  logoSrc: '/logo.png',
  logoAlt: 'naas',
  faviconSrc: '/favicon.png',
  colors: {
    primary: DEFAULT_BRAND_COLORS.primary,
    secondary: DEFAULT_BRAND_COLORS.secondary,
  },
} as const;
