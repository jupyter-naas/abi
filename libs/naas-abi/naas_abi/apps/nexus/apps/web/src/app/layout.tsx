import type { Metadata } from 'next';
import localFont from 'next/font/local';
import Script from 'next/script';
import { AnalyticsPageTracker } from '@/components/analytics-page-tracker';
import { ThemeProvider } from '@/components/theme-provider';
import { TenantProvider } from '@/contexts/tenant-context';
import { WebSocketProvider } from '@/contexts/websocket-context';
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

const DEFAULT_TITLE = 'ABI Nexus | naas.ai';
const DEFAULT_DESCRIPTION =
  'The coordination platform where AI agents, knowledge, and humans connect into actionable intelligence.';
const DEFAULT_OG_IMAGE = '/abi-logo-rounded.png';

async function fetchTenantBranding(): Promise<{
  title: string;
  description: string | null;
  ogImageUrl: string | null;
  faviconUrl: string | null;
}> {
  const apiBase =
    process.env.NEXUS_INTERNAL_API_URL ||
    process.env.NEXUS_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:9879';

  try {
    const res = await fetch(`${apiBase}/api/tenant`, { cache: 'no-store' });
    if (!res.ok) {
      return { title: DEFAULT_TITLE, description: null, ogImageUrl: null, faviconUrl: null };
    }
    const data = await res.json();
    return {
      title: (data.og_title ?? data.tab_title ?? DEFAULT_TITLE) as string,
      description: (data.og_description ?? null) as string | null,
      ogImageUrl: (data.og_image_url ?? null) as string | null,
      faviconUrl: (data.favicon_url ?? null) as string | null,
    };
  } catch {
    return { title: DEFAULT_TITLE, description: null, ogImageUrl: null, faviconUrl: null };
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const metadataBase = new URL(
    process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3042'
  );

  const { title, description, ogImageUrl, faviconUrl } = await fetchTenantBranding();
  const resolvedDescription = description ?? DEFAULT_DESCRIPTION;
  const ogImage = ogImageUrl || DEFAULT_OG_IMAGE;
  const iconUrl = faviconUrl || '/favicon.ico';

  return {
    metadataBase,
    title,
    description: resolvedDescription,
    openGraph: {
      title,
      description: resolvedDescription,
      images: [{ url: ogImage }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description: resolvedDescription,
      images: [ogImage],
    },
    icons: {
      icon: iconUrl,
      shortcut: iconUrl,
      apple: iconUrl,
    },
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
