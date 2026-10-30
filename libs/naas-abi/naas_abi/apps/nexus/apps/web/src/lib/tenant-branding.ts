import type { MetadataRoute } from 'next';

const DEFAULT_TITLE = 'ABI Nexus | naas.ai';
const DEFAULT_DESCRIPTION =
  'The coordination platform where AI agents, knowledge, and humans connect into actionable intelligence.';
const DEFAULT_OG_IMAGE = '/abi-logo-rounded.png';
const DEFAULT_THEME_COLOR = '#050b10';
const DEFAULT_BACKGROUND_COLOR = '#050b10';
const PWA_ICON = '/abi-logo-rounded.png';

export type TenantBranding = {
  title: string;
  shortName: string;
  description: string;
  ogImageUrl: string | null;
  faviconUrl: string | null;
  themeColor: string;
  backgroundColor: string;
};

function apiBaseFromEnv(): string {
  return (
    process.env.NEXUS_INTERNAL_API_URL ||
    process.env.NEXUS_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:9879'
  );
}

/** First segment before " | " for home-screen labels; cap length for iOS. */
export function shortNameFromTabTitle(tabTitle: string): string {
  const segment = tabTitle.split('|')[0]?.trim() || tabTitle.trim();
  if (segment.length <= 12) return segment || 'ABI';
  return `${segment.slice(0, 11).trimEnd()}…`;
}

export function buildWebAppManifest(
  branding: TenantBranding,
  siteUrl: string,
): MetadataRoute.Manifest {
  return {
    id: siteUrl,
    name: branding.title,
    short_name: branding.shortName,
    description: branding.description,
    start_url: '/',
    scope: '/',
    display: 'standalone',
    orientation: 'any',
    theme_color: branding.themeColor,
    background_color: branding.backgroundColor,
    icons: [
      {
        src: PWA_ICON,
        sizes: '1024x1024',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: PWA_ICON,
        sizes: '1024x1024',
        type: 'image/png',
        purpose: 'maskable',
      },
    ],
  };
}

export async function fetchTenantBranding(): Promise<TenantBranding> {
  const apiBase = apiBaseFromEnv();

  try {
    const res = await fetch(`${apiBase}/api/tenant`, { next: { revalidate: 60 } });
    if (!res.ok) {
      return defaultTenantBranding();
    }
    const data = await res.json();
    const title = (data.og_title ?? data.tab_title ?? DEFAULT_TITLE) as string;
    const description = ((data.og_description ?? DEFAULT_DESCRIPTION) as string).trim();
    return {
      title,
      shortName: shortNameFromTabTitle((data.tab_title ?? title) as string),
      description: description || DEFAULT_DESCRIPTION,
      ogImageUrl: (data.og_image_url ?? null) as string | null,
      faviconUrl: (data.favicon_url ?? null) as string | null,
      themeColor: (data.primary_color ?? data.background_color ?? DEFAULT_THEME_COLOR) as string,
      backgroundColor: (data.background_color ?? DEFAULT_BACKGROUND_COLOR) as string,
    };
  } catch {
    return defaultTenantBranding();
  }
}

export function defaultTenantBranding(): TenantBranding {
  return {
    title: DEFAULT_TITLE,
    shortName: shortNameFromTabTitle(DEFAULT_TITLE),
    description: DEFAULT_DESCRIPTION,
    ogImageUrl: null,
    faviconUrl: null,
    themeColor: DEFAULT_THEME_COLOR,
    backgroundColor: DEFAULT_BACKGROUND_COLOR,
  };
}

export function siteUrlFromEnv(): string {
  return process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3042';
}

export { DEFAULT_DESCRIPTION, DEFAULT_OG_IMAGE, DEFAULT_TITLE };
