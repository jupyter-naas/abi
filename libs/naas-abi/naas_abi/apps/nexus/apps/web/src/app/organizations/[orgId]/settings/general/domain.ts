export type OrgDomain = {
  domain: string;
  is_verified?: boolean;
};

/**
 * Organization login is keyed by custom domain, not the unused URL slug.
 * Prefer a verified domain, then any stored domain, then the current host.
 */
export function displayOrgDomain(
  domains: OrgDomain[] | null | undefined,
  fallbackHost = ''
): string {
  const rows = (domains ?? [])
    .map((row) => ({
      domain: row.domain.trim(),
      is_verified: Boolean(row.is_verified),
    }))
    .filter((row) => row.domain);
  const verified = rows.find((row) => row.is_verified);
  return verified?.domain || rows[0]?.domain || fallbackHost;
}
