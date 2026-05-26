import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import Script from 'next/script';
import { AnalyticsPageTracker } from '@/components/analytics-page-tracker';
import { ThemeProvider } from '@/components/theme-provider';
import { TenantProvider } from '@/contexts/tenant-context';
import { WebSocketProvider } from '@/contexts/websocket-context';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
});

const DEFAULT_TITLE = 'ABI Nexus | naas.ai';
const DEFAULT_DESCRIPTION =
  'The coordination platform where AI agents, knowledge, and humans connect into actionable intelligence.';
const DEFAULT_OG_IMAGE = '/abi-logo-rounded.png';

async function fetchTenantBranding(): Promise<{
  title: string;
  description: string | null;
  ogImageUrl: string | null;
}> {
  const apiBase =
    process.env.NEXUS_INTERNAL_API_URL ||
    process.env.NEXUS_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:9879';

  try {
    const res = await fetch(`${apiBase}/api/tenant`, { cache: 'no-store' });
    if (!res.ok) return { title: DEFAULT_TITLE, description: null, ogImageUrl: null };
    const data = await res.json();
    return {
      title: (data.og_title ?? data.tab_title ?? DEFAULT_TITLE) as string,
      description: (data.og_description ?? null) as string | null,
      ogImageUrl: (data.og_image_url ?? null) as string | null,
    };
  } catch {
    return { title: DEFAULT_TITLE, description: null, ogImageUrl: null };
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const metadataBase = new URL(
    process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3042'
  );

  const { title, description, ogImageUrl } = await fetchTenantBranding();
  const resolvedDescription = description ?? DEFAULT_DESCRIPTION;
  const ogImage = ogImageUrl || DEFAULT_OG_IMAGE;

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
      icon: [
        { url: '/favicon.ico', sizes: 'any' },
        { url: '/favicon.ico', sizes: '16x16', type: 'image/x-icon' },
        { url: '/favicon.ico', sizes: '32x32', type: 'image/x-icon' },
      ],
      shortcut: '/favicon.ico',
      apple: '/favicon.ico',
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
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
