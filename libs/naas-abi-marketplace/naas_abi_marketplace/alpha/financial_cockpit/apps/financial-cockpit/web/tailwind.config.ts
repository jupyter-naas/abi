import type { Config } from 'tailwindcss';

import { DEFAULT_BRAND_COLORS } from './lib/theme/tokens';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-family)', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: DEFAULT_BRAND_COLORS.primary,
        secondary: DEFAULT_BRAND_COLORS.secondary,
        accent: 'var(--accent)',
      },
    },
  },
  plugins: [],
};

export default config;
