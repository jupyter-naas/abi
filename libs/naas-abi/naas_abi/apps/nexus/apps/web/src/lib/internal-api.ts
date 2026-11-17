/** Server-side ABI base URL (Docker compose uses NEXUS_INTERNAL_API_URL). */
export function nexusInternalApiBase(): string {
  const configured =
    process.env.NEXUS_INTERNAL_API_URL ??
    process.env.NEXUS_API_URL ??
    process.env.NEXT_PUBLIC_API_URL;
  if (configured?.startsWith('http')) return configured.replace(/\/$/, '');
  if (configured) return `http://${configured.replace(/\/$/, '')}`;
  return 'http://localhost:9879';
}
