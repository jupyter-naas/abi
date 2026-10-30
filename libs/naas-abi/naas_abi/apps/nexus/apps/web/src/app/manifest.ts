import type { MetadataRoute } from 'next';
import { buildWebAppManifest, fetchTenantBranding, siteUrlFromEnv } from '@/lib/tenant-branding';

export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const branding = await fetchTenantBranding();
  return buildWebAppManifest(branding, siteUrlFromEnv());
}
