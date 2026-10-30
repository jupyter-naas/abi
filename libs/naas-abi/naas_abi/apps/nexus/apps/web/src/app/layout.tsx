import type { Metadata, Viewport } from 'next';
import localFont from 'next/font/local';
import Script from 'next/script';
import { AnalyticsPageTracker } from '@/components/analytics-page-tracker';
import { AuthSessionManager } from '@/components/auth-session-manager';
import { ServiceWorkerRegister } from '@/components/pwa/service-worker-register';
import { ThemeProvider } from '@/components/theme-provider';
import { TenantProvider } from '@/contexts/tenant-context';
import { WebSocketProvider } from '@/contexts/websocket-context';
import { DEFAULT_OG_IMAGE, fetchTenantBranding, siteUrlFromEnv } from '@/lib/tenant-branding';
import './globals.css';

const inter = localFont({
  src: '../../public/fonts/Inter-Variable.woff2',
  variable: '--font-inter',
  display: 'swap',
  weight: '100 900',
});

const jetbrainsMono = localFont({
  src: '../../public/fonts/JetBrainsMono-Variable.woff2',
  variable: '--font-mono',
  display: 'swap',
  weight: '100 800',
});

export async function generateMetadata(): Promise<Metadata> {
  const metadataBase = new URL(siteUrlFromEnv());

  const branding = await fetchTenantBranding();
  const { title, description, ogImageUrl, faviconUrl, shortName } = {
    title: branding.title,
    description: branding.description,
    ogImageUrl: branding.ogImageUrl,
    faviconUrl: branding.faviconUrl,
    shortName: branding.shortName,
  };
  const ogImage = ogImageUrl || DEFAULT_OG_IMAGE;
  const iconUrl = faviconUrl || '/favicon.ico';

  return {
    metadataBase,
    title,
    description,
    applicationName: shortName,
    appleWebApp: {
      capable: true,
      title: shortName,
      statusBarStyle: 'black-translucent',
    },
    openGraph: {
      title,
      description,
      images: [{ url: ogImage }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [ogImage],
    },
    icons: {
      icon: iconUrl,
      shortcut: iconUrl,
      apple: iconUrl,
    },
  };
}

export async function generateViewport(): Promise<Viewport> {
  const branding = await fetchTenantBranding();
  return {
    themeColor: [
      { media: '(prefers-color-scheme: light)', color: branding.themeColor },
      { media: '(prefers-color-scheme: dark)', color: branding.themeColor },
    ],
  };
}

function getServerRuntimeConfig() {
  return {
    apiUrl:
      process.env.NEXUS_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      '',
    env:
      process.env.NEXUS_ENV ||
      process.env.NEXT_PUBLIC_NEXUS_ENV ||
      'local',
    websocketPath:
      process.env.NEXUS_WS_PATH ||
      process.env.NEXT_PUBLIC_WS_PATH ||
      '/ws/socket.io',
    frontendUrl:
      process.env.NEXUS_FRONTEND_URL ||
      process.env.NEXT_PUBLIC_FRONTEND_URL ||
      '',
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Inline first so client modules never race an external /runtime-config.js
  // load (App Router can schedule async chunks before beforeInteractive src).
  const runtimeConfig = getServerRuntimeConfig();

  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <Script
          id="nexus-runtime-config-inline"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `window.__NEXUS_RUNTIME_CONFIG__=${JSON.stringify(runtimeConfig)};`,
          }}
        />
        <Script src="/runtime-config.js" strategy="beforeInteractive" />
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          <TenantProvider>
            <ServiceWorkerRegister />
            <AuthSessionManager />
            <WebSocketProvider>
              <AnalyticsPageTracker />
              {children}
            </WebSocketProvider>
          </TenantProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
