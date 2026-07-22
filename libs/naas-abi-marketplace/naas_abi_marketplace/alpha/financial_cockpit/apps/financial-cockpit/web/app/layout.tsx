import type { Metadata } from 'next';

import { BRAND } from '@/lib/brand';
import { canAccessThemePage } from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import { getThemeInlineStyle, themeInitScript } from '@/lib/theme/applyTheme';
import { loadThemeConfig } from '@/lib/theme/themeConfig';
import { themeConfigToColors } from '@/lib/theme/themeConfigShared';
import { ClientProviders } from '@/components/providers/ClientProviders';

import './globals.css';

export const metadata: Metadata = {
  title: 'naas — Financial Cockpit',
  description: 'Finance & pilotage dashboard',
  icons: {
    icon: [{ url: BRAND.faviconSrc, type: 'image/png' }],
    shortcut: [BRAND.faviconSrc],
    apple: [{ url: BRAND.faviconSrc, type: 'image/png' }],
  },
};

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
