import type { Metadata } from 'next';

import { canAccessThemePage, getBrand } from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import { getThemeInlineStyle, themeInitScript } from '@/lib/theme/applyTheme';
import { loadThemeConfig } from '@/lib/theme/themeConfig';
import { themeConfigToColors } from '@/lib/theme/themeConfigShared';
import { ClientProviders } from '@/components/providers/ClientProviders';

import './globals.css';

// Document title/description come from the `brand:` block in config.yaml.
// The favicon is served automatically from app/icon.png (Next.js convention).
// Edit assets/favicon.ico — `npm run sync:brand` (run on predev and prebuild)
// copies it into app/.
export function generateMetadata(): Metadata {
  const brand = getBrand();
  return {
    title: brand.name,
    description: brand.description,
  };
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const themeConfig = loadThemeConfig();
  const session = await getSession();
  const canPersistTheme = session ? canAccessThemePage(session) : false;
  const themeColors = themeConfigToColors(themeConfig);
  const initialMode = themeConfig.default_mode === 'dark' ? 'dark' : 'light';

  return (
    <html
      lang="fr"
      data-theme={initialMode}
      style={getThemeInlineStyle(themeColors, initialMode)}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript(themeConfig) }} />
      </head>
      <body suppressHydrationWarning>
        <ClientProviders initialTheme={themeConfig} canPersistTheme={canPersistTheme}>
          {children}
        </ClientProviders>
      </body>
    </html>
  );
}
